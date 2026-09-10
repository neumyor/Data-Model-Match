import copy
import json
import tempfile
import unittest
from pathlib import Path

from datamodelmatch.resource_store import ResourceStore
from datamodelmatch.resource_types import ResourceRecord
from datamodelmatch.semantic_store import SemanticArtifactStore
from datamodelmatch.semantic_types import (
    DatasetSemanticProfile,
    ProfileJobRequest,
    SemanticContractError,
    SemanticIdempotencyConflictError,
    SemanticJobError,
    SemanticJobNotCancellableError,
    SemanticJobTransitionError,
    SemanticStorageSafetyError,
)


class SemanticArtifactStoreTests(unittest.TestCase):
    def test_normal_lifecycle_persists_profile_and_ordered_events(self) -> None:
        with _workspace() as (root, legacy, semantic):
            request = _request()
            job = semantic.create_profile_job(request)
            semantic.start_job(job.job_id)
            semantic.emit_stage(job.job_id, "structural", "started")
            semantic.emit_progress(job.job_id, "structural", 0, 0)
            completed = semantic.publish_profile(job.job_id, _profile())

            self.assertEqual(completed.status, "completed")
            self.assertIsNotNone(completed.result_ref)
            self.assertEqual(
                semantic.get_published_profile("dataset_001").snapshot_revision,
                "rev-20260909",
            )
            events = semantic.list_events(job.job_id)
            self.assertEqual([event.event_id for event in events], [1, 2, 3, 4])
            self.assertEqual([event.event_type for event in events], ["stage", "progress", "result", "end"])
            self.assertEqual(semantic.list_events(job.job_id, after_event_id=2), events[2:])

            reloaded = SemanticArtifactStore(ResourceStore(root))
            self.assertEqual(reloaded.get_job(job.job_id).status, "completed")
            self.assertEqual(reloaded.get_profile_for_job(job.job_id).to_dict(), _profile().to_dict())
            self.assertEqual(legacy.get("dataset_001").resolved_revision, "rev-20260909")

    def test_invalid_transitions_do_not_publish_profile(self) -> None:
        with _workspace() as (_, _, semantic):
            job = semantic.create_profile_job(_request())
            with self.assertRaises(SemanticJobTransitionError):
                semantic.publish_profile(job.job_id, _profile())
            with self.assertRaises(SemanticJobTransitionError):
                semantic.mark_partially_completed(job.job_id)
            semantic.start_job(job.job_id)
            semantic.mark_partially_completed(job.job_id)
            with self.assertRaises(SemanticJobTransitionError):
                semantic.publish_profile(job.job_id, _profile())
            self.assertIsNone(semantic.get_profile_for_job(job.job_id))

    def test_idempotency_reuses_canonical_request_and_rejects_explicit_conflict(self) -> None:
        with _workspace() as (_, _, semantic):
            first = semantic.create_profile_job(_request(idempotency_key="explicit-key"))
            same = semantic.create_profile_job(_request(idempotency_key="explicit-key"))
            alternate_explicit = semantic.create_profile_job(_request(idempotency_key="other-key"))
            self.assertEqual(first.job_id, same.job_id)
            self.assertEqual(first.job_id, alternate_explicit.job_id)

            with self.assertRaises(SemanticIdempotencyConflictError):
                semantic.create_profile_job(
                    _request(
                        idempotency_key="explicit-key",
                        configuration_fingerprint="sha256:" + "b" * 64,
                    )
                )

    def test_cancellation_is_idempotent_and_protects_profile_publication(self) -> None:
        with _workspace() as (_, _, semantic):
            job = semantic.create_profile_job(_request())
            cancelled = semantic.cancel_job(job.job_id)
            self.assertEqual(cancelled.status, "cancelled")
            self.assertEqual(semantic.cancel_job(job.job_id), cancelled)
            self.assertEqual([event.event_type for event in semantic.list_events(job.job_id)], ["end"])
            with self.assertRaises(SemanticJobTransitionError):
                semantic.start_job(job.job_id)
            with self.assertRaises(SemanticJobTransitionError):
                semantic.publish_profile(job.job_id, _profile())
            self.assertIsNone(semantic.get_profile_for_job(job.job_id))

    def test_old_revision_winner_rule_preserves_last_complete_profile(self) -> None:
        with _workspace() as (_, legacy, semantic):
            first = semantic.create_profile_job(_request())
            semantic.start_job(first.job_id)
            semantic.publish_profile(first.job_id, _profile())
            stale = semantic.create_profile_job(
                _request(configuration_fingerprint="sha256:" + "b" * 64)
            )

            old_record = legacy.get("dataset_001")
            legacy.save(
                ResourceRecord(
                    **{
                        **old_record.__dict__,
                        "resolved_revision": "rev-20260910",
                        "updated_at": "2026-09-09T13:00:00Z",
                    }
                ),
                legacy.load_profile("dataset_001"),
            )
            semantic.start_job(stale.job_id)
            superseded = semantic.publish_profile(
                stale.job_id,
                _profile(configuration_fingerprint="sha256:" + "b" * 64),
            )

            self.assertEqual(superseded.status, "superseded")
            self.assertEqual(
                semantic.get_published_profile("dataset_001").configuration_fingerprint,
                "sha256:" + "a" * 64,
            )
            self.assertEqual(
                [event.event_type for event in semantic.list_events(stale.job_id)],
                ["warning", "end"],
            )

    def test_partial_and_failed_jobs_never_replace_a_complete_profile(self) -> None:
        with _workspace() as (_, _, semantic):
            complete = semantic.create_profile_job(_request())
            semantic.start_job(complete.job_id)
            semantic.publish_profile(complete.job_id, _profile())

            partial = semantic.create_profile_job(
                _request(configuration_fingerprint="sha256:" + "b" * 64)
            )
            semantic.start_job(partial.job_id)
            semantic.mark_partially_completed(partial.job_id)
            failed = semantic.fail_job(
                partial.job_id,
                SemanticJobError(
                    code="INSUFFICIENT_EVIDENCE",
                    message="Sampling coverage was insufficient.",
                    retryable=False,
                ),
            )

            self.assertEqual(failed.status, "failed")
            self.assertIsNone(semantic.get_profile_for_job(partial.job_id))
            self.assertEqual(
                semantic.get_published_profile("dataset_001").configuration_fingerprint,
                "sha256:" + "a" * 64,
            )
            self.assertEqual(
                [event.event_type for event in semantic.list_events(partial.job_id)],
                ["error", "end"],
            )

    def test_malformed_persisted_artifact_is_rejected_on_reload(self) -> None:
        with _workspace() as (root, _, semantic):
            job = semantic.create_profile_job(_request())
            job_path = root / "semantic-artifacts" / "v1" / "jobs" / f"{job.job_id}.json"
            job_path.write_text("{not-json", encoding="utf-8")
            with self.assertRaisesRegex(SemanticContractError, "invalid JSON"):
                semantic.get_job(job.job_id)

    def test_path_safety_rejects_symlinked_artifact_directory(self) -> None:
        with _workspace() as (root, _, semantic):
            semantic.create_profile_job(_request())
            jobs = root / "semantic-artifacts" / "v1" / "jobs"
            for item in jobs.iterdir():
                item.unlink()
            jobs.rmdir()
            outside = root.parent / "outside-semantic-artifacts"
            outside.mkdir()
            jobs.symlink_to(outside, target_is_directory=True)

            with self.assertRaises(SemanticStorageSafetyError):
                semantic.create_profile_job(
                    _request(configuration_fingerprint="sha256:" + "b" * 64)
                )

    def test_profile_validation_rejects_malformed_references_and_empty_evidence(self) -> None:
        raw = _profile().to_dict()
        empty_evidence = copy.deepcopy(raw)
        empty_evidence["evidence"] = []
        with self.assertRaisesRegex(SemanticContractError, "claims and evidence"):
            DatasetSemanticProfile.from_dict(empty_evidence)

        dangling = copy.deepcopy(raw)
        dangling["contentSemantics"]["objectCategories"] = ["missing_claim"]
        with self.assertRaisesRegex(SemanticContractError, "unresolved claim"):
            DatasetSemanticProfile.from_dict(dangling)

    def test_legacy_catalog_and_profile_are_unchanged_by_semantic_artifacts(self) -> None:
        with _workspace() as (root, legacy, semantic):
            catalog_before = (root / "catalog.json").read_bytes()
            profile_before = (root / legacy.get("dataset_001").profile_path).read_bytes()
            job = semantic.create_profile_job(_request())
            semantic.start_job(job.job_id)
            semantic.publish_profile(job.job_id, _profile())

            self.assertEqual((root / "catalog.json").read_bytes(), catalog_before)
            self.assertEqual(
                (root / legacy.get("dataset_001").profile_path).read_bytes(),
                profile_before,
            )


class _workspace:
    def __enter__(self):
        self._directory = tempfile.TemporaryDirectory()
        root = Path(self._directory.name) / ".datamodelmatch"
        legacy = ResourceStore(root)
        record = ResourceRecord(
            id="dataset_001",
            kind="dataset",
            source_type="local",
            source="/tmp/source",
            revision="local",
            resolved_revision="rev-20260909",
            name="semantic-fixture",
            status="ready",
            local_path="resources/datasets/dataset_001",
            profile_path="profiles/datasets/dataset_001.json",
            file_count=1,
            size_bytes=12,
            created_at="2026-09-09T12:00:00Z",
            updated_at="2026-09-09T12:00:00Z",
        )
        (root / record.local_path).mkdir(parents=True)
        legacy.save(record, {"resourceId": record.id, "name": record.name})
        return root, legacy, SemanticArtifactStore(legacy)

    def __exit__(self, exc_type, exc_value, traceback):
        self._directory.cleanup()


def _request(
    configuration_fingerprint: str = "sha256:" + "a" * 64,
    idempotency_key: str | None = None,
) -> ProfileJobRequest:
    return ProfileJobRequest(
        resource_id="dataset_001",
        snapshot_revision="rev-20260909",
        configuration_fingerprint=configuration_fingerprint,
        idempotency_key=idempotency_key,
    )


def _profile(
    configuration_fingerprint: str = "sha256:" + "a" * 64,
) -> DatasetSemanticProfile:
    contracts = json.loads(
        (
            Path(__file__).parents[1]
            / "docs"
            / "semantic-contracts"
            / "fixtures"
            / "contracts.json"
        ).read_text(encoding="utf-8")
    )
    raw = next(
        item["instance"]
        for item in contracts
        if item["name"] == "valid-dataset-semantic-profile"
    )
    raw = copy.deepcopy(raw)
    raw["generator"]["configurationFingerprint"] = configuration_fingerprint
    return DatasetSemanticProfile.from_dict(raw)


if __name__ == "__main__":
    unittest.main()
