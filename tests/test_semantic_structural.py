import os
import tempfile
import unittest
from pathlib import Path

from datamodelmatch.llm import LLMError
from datamodelmatch.semantic_inspection import inspect_file
from datamodelmatch.semantic_structural import (
    DocumentationExcerpt,
    StructuralAnalysisInput,
    StructuralAnalysisLimits,
    analyze_structural_semantics,
    create_default_structural_client,
)
from datamodelmatch.semantic_survey import survey_snapshot


def _png(width: int, height: int) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + bytes([8, 2])
        + b"\x00\x00\x00\x00"
    )


class _Client:
    def __init__(self, *responses):
        self.responses = list(responses)
        self.config = type("Config", (), {"model": "test-structural"})()
        self.last_model = "test-deployment"
        self.attempt_count = 0
        self.prompts = []

    def complete_json(self, system_prompt, user_prompt):
        self.attempt_count += 1
        self.prompts.append((system_prompt, user_prompt))
        item = self.responses.pop(0)
        if isinstance(item, BaseException):
            raise item
        return item


def _final(structural, refs):
    return {
        "action": "final",
        "structural": structural,
        "fieldEvidence": [
            {"field": field, "evidenceRefs": refs.get(field, [])}
            for field in (
                "tasks",
                "modalities",
                "sampleOrganization",
                "temporalStructure",
                "supervision",
                "annotationSemantics",
                "resourceRoles",
                "resourceRelations",
            )
        ],
    }


def _structural(**override):
    value = {
        "tasks": [],
        "modalities": ["RGB"],
        "sampleOrganization": "independent_image",
        "temporalStructure": "none",
        "supervision": [],
        "annotationSemantics": [],
        "resourceRoles": ["media", "annotation", "metadata"],
        "resourceRelations": ["image_to_annotation"],
    }
    value.update(override)
    return value


class StructuralAgentTests(unittest.TestCase):
    def _input(self, root, facts, docs=(), executor=None):
        sketch = survey_snapshot(root)
        return StructuralAnalysisInput(
            snapshot_revision="revision-1",
            sketch=sketch,
            inspection_facts=tuple(facts),
            documentation_excerpts=tuple(docs),
            executor=executor or (lambda path: inspect_file(root / path, snapshot_root=root)),
        )

    def test_detection_tracking_and_segmentation_from_wp2_facts_without_dataset_names(self):
        cases = [
            ("anonymous-a", "boxes.csv", "frame_id,track_id,xmin,ymin,xmax,ymax\n1,9,1,2,3,4\n",
             _structural(
                 tasks=["object_detection", "multi_object_tracking"],
                 sampleOrganization="image_sequence",
                 temporalStructure="sequence",
                 supervision=["bbox", "track"],
                 annotationSemantics=["claim_annotation_bbox", "claim_annotation_track_id", "claim_annotation_frame_id"],
                 resourceRelations=["image_to_annotation", "frame_to_track"],
             )),
            ("anonymous-b", "labels.json", '[{"image_id":"a","segmentation":"rle","category_id":1}]',
             _structural(
                 tasks=["semantic_segmentation"],
                 supervision=["semantic_mask"],
                 annotationSemantics=["claim_annotation_mask"],
             )),
            ("anonymous-c", "boxes.csv", "image_id,xmin,ymin,xmax,ymax\nx,1,2,3,4\n",
             _structural(
                 tasks=["object_detection"],
                 supervision=["bbox"],
                 annotationSemantics=["claim_annotation_bbox"],
             )),
        ]
        for directory_name, annotation_name, contents, structural in cases:
            with self.subTest(directory_name=directory_name), tempfile.TemporaryDirectory() as directory:
                root = Path(directory) / directory_name
                root.mkdir()
                (root / "renamed_frame.png").write_bytes(_png(4, 3))
                (root / annotation_name).write_text(contents, encoding="utf-8")
                fact = inspect_file(root / annotation_name, snapshot_root=root)
                response = _final(
                    structural,
                    {field: ["evidence_inspection_001"] for field in (
                        "tasks", "modalities", "sampleOrganization", "temporalStructure",
                        "supervision", "annotationSemantics", "resourceRoles", "resourceRelations",
                    )},
                )
                result = analyze_structural_semantics(self._input(root, [fact]), _Client(response))
                self.assertEqual(result.status, "COMPLETED")
                self.assertEqual(result.candidate.tasks, tuple(structural["tasks"]))
                self.assertEqual(result.candidate.supervision, tuple(structural["supervision"]))
                self.assertFalse(any("anonymous" in warning for warning in result.warnings))

    def test_no_readme_and_renamed_root_can_return_explicit_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "root-without-identity"
            root.mkdir()
            (root / "renamed.png").write_bytes(_png(4, 3))
            image = inspect_file(root / "renamed.png", snapshot_root=root)
            response = _final(
                _structural(resourceRoles=["media"], resourceRelations=["UNKNOWN"]),
                {
                    "modalities": ["evidence_inspection_001"],
                    "sampleOrganization": ["evidence_inspection_001"],
                    "temporalStructure": ["evidence_inspection_001"],
                    "resourceRoles": ["evidence_inspection_001"],
                },
            )
            result = analyze_structural_semantics(self._input(root, [image]), _Client(response))
        self.assertEqual(result.status, "COMPLETED")
        self.assertEqual(result.candidate.tasks, ())
        unknowns = {claim.field: claim.unknown_reason for claim in result.claims if claim.status == "UNKNOWN"}
        self.assertEqual(unknowns["tasks"], "NO_EVIDENCE")
        self.assertEqual(unknowns["supervision"], "NO_EVIDENCE")

    def test_conflicting_deterministic_evidence_becomes_unknown(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "frame.png").write_bytes(_png(4, 3))
            (root / "labels.csv").write_text("frame_id,track_id,xmin,ymin,xmax,ymax\n1,2,1,2,3,4\n", encoding="utf-8")
            fact = inspect_file(root / "labels.csv", snapshot_root=root)
            response = _final(
                _structural(
                    tasks=["object_detection"],
                    sampleOrganization="independent_image",
                    temporalStructure="none",
                    supervision=["bbox"],
                    annotationSemantics=["claim_annotation_bbox"],
                    resourceRelations=["image_to_annotation"],
                ),
                {field: ["evidence_inspection_001"] for field in (
                    "tasks", "modalities", "sampleOrganization", "temporalStructure",
                    "supervision", "annotationSemantics", "resourceRoles", "resourceRelations",
                )},
            )
            result = analyze_structural_semantics(self._input(root, [fact]), _Client(response))
        self.assertEqual(result.status, "COMPLETED")
        self.assertEqual(result.candidate.tasks, ())
        self.assertEqual(result.candidate.temporal_structure, "UNKNOWN")
        claims = {claim.field: claim for claim in result.claims}
        self.assertEqual(claims["tasks"].unknown_reason, "CONFLICTING_EVIDENCE")
        self.assertEqual(claims["tasks"].status, "UNKNOWN")

    def test_allowlisted_finite_inspection_loop_integrates_wp2_facts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "renamed"
            root.mkdir()
            (root / "frame.png").write_bytes(_png(4, 3))
            (root / "labels.csv").write_text("image_id,xmin,ymin,xmax,ymax\nx,1,2,3,4\n", encoding="utf-8")
            first = {"action": "inspect", "requests": [{"action": "inspect_file", "path": "labels.csv"}]}
            final = _final(
                _structural(
                    tasks=["object_detection"],
                    supervision=["bbox"],
                    annotationSemantics=["claim_annotation_bbox"],
                ),
                {field: ["evidence_inspection_001"] for field in (
                    "tasks", "modalities", "sampleOrganization", "temporalStructure",
                    "supervision", "annotationSemantics", "resourceRoles", "resourceRelations",
                )},
            )
            result = analyze_structural_semantics(self._input(root, [], executor=lambda path: inspect_file(root / path, snapshot_root=root)), _Client(first, final))
        self.assertEqual(result.status, "COMPLETED")
        self.assertEqual(result.inspection_requests[0].path, "labels.csv")
        self.assertEqual(result.candidate.tasks, ("object_detection",))

    def test_malformed_response_invalid_tool_request_and_timeout_are_redacted_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "frame.png").write_bytes(_png(4, 3))
            (root / "labels.csv").write_text("image_id,label\nx,a\n", encoding="utf-8")
            item = self._input(root, [])
            malformed = analyze_structural_semantics(item, _Client({"action": "final"}))
            invalid = analyze_structural_semantics(
                item,
                _Client({"action": "inspect", "requests": [{"action": "read_file", "path": "../../secret"}]}),
            )
            timed_out = analyze_structural_semantics(item, _Client(LLMError("Authorization: Bearer secret-token")))
            empty = analyze_structural_semantics(item, _Client(LLMError("LLM response content must be a non-empty string")))
        for result in (malformed, invalid, timed_out, empty):
            self.assertEqual(result.status, "FAILED")
            self.assertIsNone(result.candidate)
            self.assertEqual(result.claims, ())
            self.assertNotIn("secret-token", " ".join(result.warnings))

    def test_rejects_exhausted_tool_budget(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "labels.csv").write_text("image_id,label\nx,a\n", encoding="utf-8")
            item = StructuralAnalysisInput(
                snapshot_revision="revision-1",
                sketch=survey_snapshot(root),
                inspection_facts=(),
                documentation_excerpts=(),
                executor=lambda path: inspect_file(root / path, snapshot_root=root),
                limits=StructuralAnalysisLimits(max_tool_requests=1, max_model_calls=2),
            )
            request = {"action": "inspect", "requests": [{"action": "inspect_file", "path": "labels.csv"}]}
            result = analyze_structural_semantics(item, _Client(request, request))
        self.assertEqual(result.status, "FAILED")
        self.assertIn("budget", result.warnings[0])

    @unittest.skipUnless(os.environ.get("RUN_REAL_LLM_TESTS") == "1", "set RUN_REAL_LLM_TESTS=1 for real API acceptance")
    def test_real_llm_success_and_controlled_timeout_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "frame.png").write_bytes(_png(4, 3))
            (root / "labels.csv").write_text("image_id,xmin,ymin,xmax,ymax\nx,1,2,3,4\n", encoding="utf-8")
            fact = inspect_file(root / "labels.csv", snapshot_root=root)
            client = create_default_structural_client(timeout_seconds=75)
            result = analyze_structural_semantics(self._input(root, [fact]), client)
            self.assertEqual(result.status, "COMPLETED")
            self.assertGreaterEqual(result.model_call_count, 1)
            self.assertTrue(result.model)
            timeout_client = create_default_structural_client(timeout_seconds=0.001)
            timeout = analyze_structural_semantics(self._input(root, [fact]), timeout_client)
        self.assertEqual(timeout.status, "FAILED")
        self.assertIsNone(timeout.candidate)
        self.assertNotIn("Bearer", " ".join(timeout.warnings))
