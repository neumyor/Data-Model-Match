import tempfile
import unittest
from pathlib import Path

from datamodelmatch.resource_store import ResourceStore
from datamodelmatch.resource_types import ResourceRecord


class ResourceStoreTests(unittest.TestCase):
    def test_saves_lists_loads_and_deletes_resource(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ResourceStore(Path(directory))
            record = ResourceRecord(
                id="dataset_123",
                kind="dataset",
                source_type="local",
                source="/tmp/example",
                revision="local",
                resolved_revision="local",
                name="example",
                status="ready",
                local_path="resources/datasets/dataset_123",
                profile_path="profiles/datasets/dataset_123.json",
                file_count=1,
                size_bytes=12,
                created_at="2026-09-08T00:00:00Z",
                updated_at="2026-09-08T00:00:00Z",
            )
            resource_path = Path(directory) / record.local_path
            resource_path.mkdir(parents=True)
            (resource_path / "data.csv").write_text("id\n1\n", encoding="utf-8")

            store.save(record, {"resourceId": record.id, "name": "example"})

            self.assertEqual(store.list("dataset"), [record])
            self.assertEqual(store.get(record.id), record)
            self.assertEqual(store.load_profile(record.id)["name"], "example")

            store.delete(record.id)

            self.assertEqual(store.list(), [])
            self.assertFalse(resource_path.exists())

    def test_replaces_record_with_same_id(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ResourceStore(Path(directory))
            first = _record("profiling")
            second = _record("ready")

            store.save(first, {"resourceId": first.id})
            store.save(second, {"resourceId": second.id})

            self.assertEqual(len(store.list()), 1)
            self.assertEqual(store.get(second.id).status, "ready")

    def test_rejects_catalog_paths_outside_managed_directories(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ResourceStore(Path(directory))
            record = _record("ready")
            unsafe = ResourceRecord(
                **{
                    **record.__dict__,
                    "profile_path": "../../config.llm.json",
                }
            )

            with self.assertRaisesRegex(ValueError, "escapes"):
                store.save(unsafe, {"resourceId": unsafe.id})


def _record(status: str) -> ResourceRecord:
    return ResourceRecord(
        id="model_123",
        kind="model",
        source_type="github",
        source="owner/repo",
        revision="main",
        resolved_revision="abc123",
        name="repo",
        status=status,
        local_path="resources/models/model_123",
        profile_path="profiles/models/model_123.json",
        file_count=2,
        size_bytes=24,
        created_at="2026-09-08T00:00:00Z",
        updated_at="2026-09-08T00:00:01Z",
    )


if __name__ == "__main__":
    unittest.main()
