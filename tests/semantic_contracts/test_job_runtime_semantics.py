"""Tests for the frozen, non-public semantic job runtime policy."""

from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "docs" / "semantic-contracts"


class JobRuntimeSemanticsTests(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = json.loads(
            (ROOT / "job-runtime-semantics-v1.json").read_text(encoding="utf-8")
        )
        self.common = json.loads((ROOT / "common.schema.json").read_text(encoding="utf-8"))
        self.vlm = json.loads(
            (ROOT / "vlm-configuration.schema.json").read_text(encoding="utf-8")
        )

    def test_policy_is_closed_and_covers_the_frozen_error_code_enum(self) -> None:
        self.assertEqual(
            set(self.policy),
            {
                "version",
                "runtimeSemanticsVersion",
                "scope",
                "errorDisposition",
                "attempts",
                "retry",
                "cancellation",
                "workerRecovery",
                "sseReplay",
                "publication",
            },
        )
        self.assertEqual(self.policy["version"], 1)
        self.assertEqual(self.policy["runtimeSemanticsVersion"], "1.0.0")
        error_codes = set(self.common["$defs"]["errorCode"]["enum"])
        self.assertEqual(set(self.policy["errorDisposition"]), error_codes)
        for code, disposition in self.policy["errorDisposition"].items():
            with self.subTest(code=code):
                self.assertEqual(set(disposition), {"retryable", "reason"})
                self.assertIsInstance(disposition["retryable"], bool)
                self.assertIsInstance(disposition["reason"], str)
                self.assertTrue(disposition["reason"])

    def test_retryable_mapping_is_conservative_and_exact(self) -> None:
        retryable = {
            code
            for code, disposition in self.policy["errorDisposition"].items()
            if disposition["retryable"]
        }
        self.assertEqual(
            retryable,
            {
                "VLM_UNAVAILABLE",
                "VLM_TIMEOUT",
                "VLM_EMPTY_RESPONSE",
                "VLM_INVALID_RESPONSE",
                "RATE_LIMITED",
            },
        )

    def test_attempt_and_retry_budget_semantics_are_unambiguous(self) -> None:
        attempts = self.policy["attempts"]
        self.assertEqual(attempts["initialAttempt"], 0)
        self.assertEqual(attempts["attemptFieldMeaning"], "count_of_started_execution_attempts")
        self.assertEqual(
            attempts["maxAttemptsFieldMeaning"],
            "maximum_number_of_retries_after_the_initial_attempt",
        )
        self.assertEqual(attempts["totalAttemptFormula"], "1 + maxAttempts")
        self.assertFalse(_eligible(attempt=1, max_attempts=0, retryable=True, cancelled=False))
        self.assertTrue(_eligible(attempt=1, max_attempts=2, retryable=True, cancelled=False))
        self.assertTrue(_eligible(attempt=2, max_attempts=2, retryable=True, cancelled=False))
        self.assertFalse(_eligible(attempt=3, max_attempts=2, retryable=True, cancelled=False))
        self.assertFalse(_eligible(attempt=1, max_attempts=2, retryable=False, cancelled=False))
        self.assertFalse(_eligible(attempt=1, max_attempts=2, retryable=True, cancelled=True))
        self.assertEqual(self.vlm["properties"]["retry"]["properties"]["maxAttempts"]["minimum"], 0)

    def test_backoff_and_jitter_are_deterministic_and_bounded(self) -> None:
        retry = self.policy["retry"]
        self.assertEqual(retry["algorithm"], "deterministic_bounded_exponential_jitter")
        self.assertEqual(retry["maximumDelayMs"], 60000)
        first = _delay_ms("job_001", retry_ordinal=1, base_delay_ms=500, maximum=60000)
        repeated = _delay_ms("job_001", retry_ordinal=1, base_delay_ms=500, maximum=60000)
        second = _delay_ms("job_001", retry_ordinal=2, base_delay_ms=500, maximum=60000)
        self.assertEqual(first, repeated)
        self.assertGreaterEqual(first, 400)
        self.assertLessEqual(first, 600)
        self.assertGreaterEqual(second, 800)
        self.assertLessEqual(second, 1200)
        self.assertLessEqual(
            _delay_ms("job_001", retry_ordinal=20, base_delay_ms=60000, maximum=60000),
            60000,
        )

    def test_terminal_races_worker_recovery_sse_and_publication_are_frozen(self) -> None:
        cancellation = self.policy["cancellation"]
        self.assertEqual(cancellation["acceptedStates"], ["queued", "running", "partially_completed"])
        self.assertEqual(cancellation["idempotentTerminalState"], "cancelled")
        self.assertEqual(
            cancellation["winnerRule"],
            "the first durable terminal transition under the job lock wins",
        )
        self.assertIn("durable cancellation before this check prevents publication", cancellation["publishRule"])

        recovery = self.policy["workerRecovery"]
        self.assertEqual(recovery["leaseDurationSeconds"], 60)
        self.assertEqual(recovery["renewalIntervalSeconds"], 15)
        self.assertIn("consumed attempt", recovery["uncertainExternalCallRule"])
        self.assertIn("without consuming", recovery["preLeaseCrashRule"])
        self.assertIn("non-current lease token", recovery["staleWorkerRule"])

        replay = self.policy["sseReplay"]
        self.assertEqual(replay["minimumRetentionSeconds"], 604800)
        self.assertIn("greater than Last-Event-ID", replay["lastEventIdRule"])
        self.assertIn("GET job", replay["expiredRetentionRule"])
        self.assertIn("exactly one end event", replay["terminalRule"])

        publication = self.policy["publication"]
        self.assertEqual(
            publication["protocol"],
            [
                "write_and_fsync_validated_profile_artifact",
                "write_and_fsync_published_pointer_if_resolvedRevision_matches",
                "write_and_fsync_completed_job_record",
                "append_and_fsync_result_event",
                "append_and_fsync_end_event",
            ],
        )
        self.assertIn("never republishes a different profile", publication["recoveryRule"])


def _eligible(attempt: int, max_attempts: int, retryable: bool, cancelled: bool) -> bool:
    return retryable and attempt <= max_attempts and not cancelled


def _delay_ms(job_id: str, retry_ordinal: int, base_delay_ms: int, maximum: int) -> int:
    digest = hashlib.sha256(f"{job_id}:{retry_ordinal}".encode("utf-8")).hexdigest()
    fraction = int(digest[:8], 16) / 4294967295
    multiplier = 0.8 + 0.4 * fraction
    return min(maximum, int(base_delay_ms * (2 ** (retry_ordinal - 1)) * multiplier))


if __name__ == "__main__":
    unittest.main()
