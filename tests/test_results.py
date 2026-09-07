import unittest

from datamodelmatch.results import (
    FieldRef,
    Match,
    MatchMeta,
    MatchResult,
    ResultValidationError,
)


class MatchResultTests(unittest.TestCase):
    def test_serializes_nested_matches_and_structured_unmatched_fields(self) -> None:
        result = MatchResult(
            source_model_id="source-v1",
            target_model_id="target-v2",
            matches=[
                Match(
                    source=FieldRef("user", "email"),
                    target=FieldRef("customer", "emailAddress"),
                    kind="semantic",
                    confidence=0.92,
                    reason="Both identify the user's email address.",
                )
            ],
            unmatched_source_fields=[FieldRef("user", "legacyCode")],
            unmatched_target_fields=[{"entityId": "customer", "fieldId": "createdAt"}],
            meta=MatchMeta(model="glm-5.3-flash", attempt_count=2),
        )

        self.assertEqual(
            result.to_dict(),
            {
                "sourceModelId": "source-v1",
                "targetModelId": "target-v2",
                "matches": [
                    {
                        "source": {"entityId": "user", "fieldId": "email"},
                        "target": {"entityId": "customer", "fieldId": "emailAddress"},
                        "kind": "semantic",
                        "confidence": 0.92,
                        "reason": "Both identify the user's email address.",
                    }
                ],
                "unmatchedSourceFields": [{"entityId": "user", "fieldId": "legacyCode"}],
                "unmatchedTargetFields": [{"entityId": "customer", "fieldId": "createdAt"}],
                "meta": {"model": "glm-5.3-flash", "attemptCount": 2},
            },
        )

    def test_accepts_mapping_payloads_for_main_flow_boundaries(self) -> None:
        result = MatchResult(
            "source",
            "target",
            [
                {
                    "source": {"entityId": "a", "fieldId": "id"},
                    "target": {"entityId": "b", "fieldId": "id"},
                    "kind": "exact",
                    "confidence": 1,
                    "reason": "Same identifier",
                }
            ],
            [],
            [{"entityId": "b", "fieldId": "name"}],
            {"model": "local-model", "attemptCount": 0},
        )

        self.assertEqual(result.matches[0].confidence, 1.0)
        self.assertEqual(result.unmatched_target_fields[0], FieldRef("b", "name"))

    def test_rejects_invalid_match_values(self) -> None:
        for kwargs in (
            {"kind": "approximate"},
            {"confidence": -0.1},
            {"confidence": 1.1},
            {"confidence": float("nan")},
            {"reason": " "},
        ):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ResultValidationError):
                    Match(
                        source=FieldRef("a", "x"),
                        target=FieldRef("b", "y"),
                        **kwargs,
                    )

    def test_rejects_duplicate_or_overlapping_fields(self) -> None:
        match = Match(
            source_entity_id="a",
            source_field_id="x",
            target_entity_id="b",
            target_field_id="y",
            reason="match",
        )
        with self.assertRaises(ResultValidationError):
            MatchResult("s", "t", [match, match], [], [], {"model": "m", "attemptCount": 1})
        with self.assertRaises(ResultValidationError):
            MatchResult(
                "s",
                "t",
                [match],
                [FieldRef("a", "x")],
                [],
                {"model": "m", "attemptCount": 1},
            )

    def test_rejects_invalid_ids_and_metadata(self) -> None:
        with self.assertRaises(ResultValidationError):
            MatchResult("", "target", [], [], [], {"model": "m", "attemptCount": 1})
        with self.assertRaises(ResultValidationError):
            MatchResult("source", "target", [], [], [], {"model": "m", "attemptCount": -1})
        with self.assertRaises(ResultValidationError):
            MatchResult("source", "target", [], [], [], {"model": "", "attemptCount": 1})


if __name__ == "__main__":
    unittest.main()
