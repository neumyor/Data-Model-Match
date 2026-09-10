import unittest

from datamodelmatch.semantic_aggregation import aggregate_field
from datamodelmatch.semantic_vision import VisualObservation


def obs(identifier, categories=("urban",), status="COMPLETED", failure=None):
    return VisualObservation(
        identifier, "sample_" + identifier, tuple(categories), ("road",), ("aerial",),
        "small", "low", "rare", ("daylight",), "moving", "fast",
        "MiniCPM-V-4.5", "sha256:" + "a" * 64, status, ("evidence_" + identifier,),
        failure,
    )


class SemanticAggregationTests(unittest.TestCase):
    def test_single_observation_is_observed_not_supported(self):
        result = aggregate_field([obs("one")], "objectCategories", 10, 1)
        self.assertEqual(result.status, "OBSERVED")
        self.assertIsNone(result.unknown_reason)
        self.assertEqual(result.distributions[0].proportion, 1.0)

    def test_threshold_and_failed_samples_are_retained(self):
        observations = [obs(str(index)) for index in range(3)] + [obs("bad", status="FAILED", failure="VLM_TIMEOUT")]
        result = aggregate_field(observations, "objectCategories", 4, 4)
        self.assertEqual(result.status, "SUPPORTED")
        self.assertEqual(result.completed_count, 3)
        self.assertEqual(result.failed_count, 1)

    def test_no_completed_and_conflict_are_unknown(self):
        failed = aggregate_field([obs("bad", status="UNSUPPORTED", failure="UNSUPPORTED_MEDIA")], "objectCategories", 1, 1)
        self.assertEqual(failed.unknown_reason, "NO_EVIDENCE")
        conflict = aggregate_field([obs("a", ("urban",)), obs("b", ("rural",)), obs("c", ("urban",)), obs("d", ("rural",))], "objectCategories", 4, 4)
        self.assertEqual(conflict.status, "UNKNOWN")
        self.assertEqual(conflict.unknown_reason, "CONFLICTING_EVIDENCE")

    def test_coverage_blocks_supported(self):
        result = aggregate_field([obs("a"), obs("b"), obs("c")], "objectCategories", 10, 3)
        self.assertEqual(result.status, "OBSERVED")
