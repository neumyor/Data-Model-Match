import json
import math
import unittest
from copy import deepcopy
from pathlib import Path

try:
    from .benchmark_validator import validate_benchmark_manifest, validate_threshold_manifest
except ImportError:  # unittest discover -s tests/semantic_benchmark loads top-level modules.
    from benchmark_validator import validate_benchmark_manifest, validate_threshold_manifest


ROOT = Path(__file__).resolve().parents[2]
BENCHMARK_DIR = ROOT / "docs" / "semantic-benchmark"


def structural_scores(ground_truth, predictions):
    true_positive = sum(len(set(predictions[i]) & set(ground_truth[i])) for i in range(len(ground_truth)))
    false_positive = sum(len(set(predictions[i]) - set(ground_truth[i])) for i in range(len(ground_truth)))
    false_negative = sum(len(set(ground_truth[i]) - set(predictions[i])) for i in range(len(ground_truth)))
    precision = true_positive / (true_positive + false_positive)
    recall = true_positive / (true_positive + false_negative)
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def binary_f1(expected, predicted, label):
    tp = sum(value == label and guess == label for value, guess in zip(expected, predicted))
    fp = sum(value != label and guess == label for value, guess in zip(expected, predicted))
    fn = sum(value == label and guess != label for value, guess in zip(expected, predicted))
    return 2 * tp / (2 * tp + fp + fn) if 2 * tp + fp + fn else 0.0


def content_macro_f1(expected_fields, predicted_fields):
    scores = []
    for field in expected_fields:
        labels = sorted(set(expected_fields[field]) | set(predicted_fields[field]))
        scores.extend(binary_f1(expected_fields[field], predicted_fields[field], label) for label in labels)
    return sum(scores) / len(scores)


def unknown_rate(predicted_fields):
    values = [value for field in predicted_fields.values() for value in field]
    return sum(value == "UNKNOWN" for value in values) / len(values)


def profile_consistency(runs):
    comparisons = 0
    matches = 0
    for previous, current in zip(runs, runs[1:]):
        for field in previous:
            comparisons += 1
            matches += previous[field] == current[field]
    return matches / comparisons


def hit_at_k(relevant, ranking, k):
    return float(bool(set(relevant) & set(ranking[:k])))


def reciprocal_rank(relevant, ranking):
    for index, item in enumerate(ranking, start=1):
        if item in relevant:
            return 1.0 / index
    return 0.0


def ndcg_at_k(relevance, ranking, k):
    def dcg(values):
        return sum((2**value - 1) / math.log2(index + 2) for index, value in enumerate(values))

    actual = dcg([relevance.get(item, 0) for item in ranking[:k]])
    ideal = dcg(sorted(relevance.values(), reverse=True)[:k])
    return actual / ideal if ideal else 0.0


def nearest_rank_percentile(values, percentile):
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


class MetricFormulaTests(unittest.TestCase):
    def test_structural_precision_recall_f1_use_micro_counts(self):
        precision, recall, f1 = structural_scores(
            [["a", "b"], ["c"]],
            [["a", "x"], ["c", "y"]],
        )
        self.assertAlmostEqual(precision, 2 / 4)
        self.assertAlmostEqual(recall, 2 / 3)
        self.assertAlmostEqual(f1, 4 / 7)

    def test_content_macro_f1_and_unknown_rate_keep_unknown_in_denominator(self):
        expected = {"environment": ["urban", "rural"], "scale": ["small", "large"]}
        predicted = {"environment": ["urban", "UNKNOWN"], "scale": ["small", "UNKNOWN"]}
        self.assertAlmostEqual(content_macro_f1(expected, predicted), 1 / 3)
        self.assertAlmostEqual(unknown_rate(predicted), 0.5)

    def test_profile_consistency_compares_adjacent_runs_and_explicit_unknown(self):
        self.assertAlmostEqual(
            profile_consistency(
                [
                    {"task": "detection", "scale": "UNKNOWN"},
                    {"task": "detection", "scale": "UNKNOWN"},
                    {"task": "tracking", "scale": "UNKNOWN"},
                ]
            ),
            3 / 4,
        )

    def test_retrieval_metrics(self):
        relevant = {"ds_a", "ds_c"}
        ranking = ["ds_x", "ds_c", "ds_a"]
        self.assertEqual(hit_at_k(relevant, ranking, 2), 1.0)
        self.assertAlmostEqual(reciprocal_rank(relevant, ranking), 0.5)
        self.assertAlmostEqual(
            ndcg_at_k({"ds_a": 2, "ds_c": 1, "ds_x": 0}, ranking, 3),
            (1 / math.log2(3) + 3 / math.log2(4)) / (3 + 1 / math.log2(3)),
        )

    def test_resource_metric_percentile_is_nearest_rank(self):
        self.assertEqual(nearest_rank_percentile([10, 20, 30, 40], 0.95), 40)
        self.assertEqual(sum([2, 3, 4]) / 3, 3)


class GovernanceAssetTests(unittest.TestCase):
    def read_json(self, name):
        with (BENCHMARK_DIR / name).open(encoding="utf-8") as handle:
            return json.load(handle)

    def test_schemas_and_templates_are_json_and_template_has_required_scale(self):
        manifest_schema = self.read_json("benchmark-manifest.schema.json")
        manifest = self.read_json("benchmark-manifest.template.json")
        ground_truth_schema = self.read_json("ground-truth.schema.json")
        ground_truth = self.read_json("ground-truth.template.json")
        self.assertEqual(manifest_schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(ground_truth_schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertEqual(len(manifest["datasets"]), manifest["datasetCount"])
        self.assertEqual(len(manifest["taskQueries"]), manifest["taskQueryCount"])
        self.assertGreaterEqual(len(manifest["datasets"]), 15)
        self.assertGreaterEqual(len(manifest["taskQueries"]), 50)
        self.assertEqual(ground_truth["schemaVersion"], 1)

    def test_manifest_is_deidentified_and_has_no_dataset_name_logic(self):
        manifest = self.read_json("benchmark-manifest.template.json")
        text = json.dumps(manifest)
        self.assertNotIn("/", text)
        self.assertNotIn("\\", text)
        self.assertNotIn("http", text)
        self.assertNotIn("COCO", text)
        self.assertEqual(manifest["deidentification"]["status"], "deidentified")
        self.assertEqual(
            set(manifest["deidentification"]["forbiddenReferences"]),
            {"dataset_name", "absolute_path", "credential", "authorization_header", "raw_media", "private_url"},
        )

    def test_thresholds_are_explicitly_preliminary(self):
        thresholds = self.read_json("threshold-manifest.json")
        self.assertEqual(thresholds["status"], "preliminary_pending_independent_calibration")
        self.assertTrue(thresholds["calibrationRequired"])
        self.assertTrue(thresholds["calibrationProtocol"]["approvalRequired"])
        self.assertEqual(validate_threshold_manifest(thresholds), [])

    def _valid_manifest(self):
        manifest = deepcopy(self.read_json("benchmark-manifest.template.json"))
        dataset_ids = [item["datasetId"] for item in manifest["datasets"]]
        query_ids = [item["queryId"] for item in manifest["taskQueries"]]
        manifest["split"]["datasetIds"] = {
            "development": dataset_ids[:5],
            "calibration": dataset_ids[5:10],
            "test": dataset_ids[10:],
        }
        manifest["split"]["queryIds"] = {
            "development": query_ids[:17],
            "calibration": query_ids[17:34],
            "test": query_ids[34:],
        }
        return manifest

    def _catalogs(self):
        ground_truth = self.read_json("ground-truth.template.json")
        perturbations = self.read_json("perturbation-rules.json")
        return {ground_truth["version"]}, {rule["ruleId"] for rule in perturbations["rules"]}

    def test_mechanical_manifest_validator_accepts_complete_synthetic_shape(self):
        manifest = self._valid_manifest()
        ground_truth_versions, perturbation_ids = self._catalogs()
        self.assertEqual(
            validate_benchmark_manifest(
                manifest,
                ground_truth_versions=ground_truth_versions,
                perturbation_rule_ids=perturbation_ids,
            ),
            [],
        )

    def test_mechanical_manifest_validator_rejects_count_mismatch(self):
        manifest = self._valid_manifest()
        manifest["datasetCount"] -= 1
        errors = validate_benchmark_manifest(
            manifest,
            ground_truth_versions=self._catalogs()[0],
            perturbation_rule_ids=self._catalogs()[1],
        )
        self.assertTrue(any("datasetCount" in error and "does not equal" in error for error in errors))

    def test_mechanical_manifest_validator_rejects_split_overlap_and_missing_ids(self):
        manifest = self._valid_manifest()
        manifest["split"]["datasetIds"]["test"] = manifest["split"]["datasetIds"]["development"][:1]
        errors = validate_benchmark_manifest(
            manifest,
            ground_truth_versions=self._catalogs()[0],
            perturbation_rule_ids=self._catalogs()[1],
        )
        self.assertTrue(any("overlaps" in error for error in errors))
        self.assertTrue(any("union must cover exactly" in error for error in errors))

    def test_mechanical_manifest_validator_rejects_unresolved_references(self):
        manifest = self._valid_manifest()
        manifest["datasets"][0]["groundTruthVersion"] = "gt_missing_v1"
        manifest["taskQueries"][0]["perturbationVersions"] = ["perturbation_missing_v1"]
        errors = validate_benchmark_manifest(
            manifest,
            ground_truth_versions=self._catalogs()[0],
            perturbation_rule_ids=self._catalogs()[1],
        )
        self.assertTrue(any("unresolved reference gt_missing_v1" in error for error in errors))
        self.assertTrue(any("unresolved reference perturbation_missing_v1" in error for error in errors))

    def test_placeholder_template_is_not_claimed_as_a_complete_manifest(self):
        template = self.read_json("benchmark-manifest.template.json")
        errors = validate_benchmark_manifest(
            template,
            ground_truth_versions=self._catalogs()[0],
            perturbation_rule_ids=self._catalogs()[1],
        )
        self.assertTrue(errors)
        self.assertTrue(any("$.split.datasetIds" in error for error in errors))
        self.assertTrue(any("$.split.queryIds" in error for error in errors))

    def test_final_threshold_state_requires_calibration_and_approval_evidence(self):
        thresholds = self.read_json("threshold-manifest.json")
        thresholds["status"] = "final_approved"
        errors = validate_threshold_manifest(thresholds)
        self.assertTrue(any("final state requires completed" in error for error in errors))
        self.assertTrue(any("final state requires approved" in error for error in errors))

    def test_final_threshold_state_accepts_complete_non_secret_evidence(self):
        thresholds = self.read_json("threshold-manifest.json")
        thresholds["status"] = "final_approved"
        thresholds["calibrationProtocol"]["independentCalibrator"] = "calibrator_01"
        thresholds["calibrationProtocol"]["independentCalibratorStatus"] = "completed"
        thresholds["calibrationEvidence"] = {
            "status": "completed",
            "reportId": "calibration_phase7_v1",
            "reportSha256": "a" * 64,
            "completedAt": "2026-09-09T01:00:00Z",
        }
        thresholds["approval"] = {
            "status": "approved",
            "approverId": "approver_01",
            "approvedAt": "2026-09-09T02:00:00Z",
            "changeRecordId": "CR-0001",
        }
        self.assertEqual(validate_threshold_manifest(thresholds), [])


if __name__ == "__main__":
    unittest.main()
