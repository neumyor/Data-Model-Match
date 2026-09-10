import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from datamodelmatch.resource_cli import _import, _validate_local_source
from datamodelmatch.resource_store import ResourceStore
from datamodelmatch.resource_types import ResourceRecord


class ResourceCliTests(unittest.TestCase):
    def test_allows_workspace_child_and_rejects_protected_subtree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            source = workspace / "fixtures" / "dataset"
            source.mkdir(parents=True)
            store = ResourceStore(workspace / ".datamodelmatch")
            store.ensure()

            with patch("datamodelmatch.resource_cli.Path.cwd", return_value=workspace):
                self.assertEqual(_validate_local_source(str(source), store), str(source.resolve()))
                with self.assertRaisesRegex(ValueError, "受保护路径"):
                    _validate_local_source(str(store.root), store)

    def test_dataset_import_requires_semantic_profile_before_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "data.csv").write_text("image,label\nx.png,car\n", encoding="utf-8")
            store = ResourceStore(root / "store")
            arguments = argparse.Namespace(
                kind="dataset",
                source_type="local",
                source=str(source),
                revision="",
                download_mode="sample",
                max_bytes=1024 * 1024,
            )
            now = "2026-09-10T00:00:00Z"
            record = ResourceRecord(
                id="dataset_semantic",
                kind="dataset",
                source_type="local",
                source=str(source),
                revision="local",
                resolved_revision="local-test",
                name="semantic",
                status="ready",
                local_path="placeholder",
                profile_path="placeholder",
                file_count=1,
                size_bytes=1,
                created_at=now,
                updated_at=now,
            )
            base_profile = {
                "version": 1,
                "resourceId": record.id,
                "name": record.name,
                "completeness": 1,
                "warnings": [],
            }
            semantic = {"resourceId": record.id, "summary": "语义结论"}

            with patch("datamodelmatch.resource_cli._validate_local_source", return_value=str(source)), \
                 patch("datamodelmatch.dataset_resources.import_dataset", return_value=(record, base_profile)), \
                 patch("datamodelmatch.semantic_runtime.build_semantic_profile", side_effect=lambda store, resource_id: (
                     self.assertEqual(store.get(resource_id).status, "analyzing") or semantic
                 )), \
                 patch("datamodelmatch.resource_cli._emit") as emit:
                self.assertEqual(_import(arguments, store), 0)

            events = [call.args[0] for call in emit.call_args_list]
            self.assertEqual(events[-2:], ["result", "end"])
            self.assertEqual(store.get(record.id).status, "ready")

    def test_dataset_import_rolls_back_when_semantic_analysis_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            store = ResourceStore(root / "store")
            arguments = argparse.Namespace(
                kind="dataset",
                source_type="local",
                source=str(source),
                revision="",
                download_mode="sample",
                max_bytes=1024 * 1024,
            )
            now = "2026-09-10T00:00:00Z"
            record = ResourceRecord(
                id="dataset_failed_semantic",
                kind="dataset",
                source_type="local",
                source=str(source),
                revision="local",
                resolved_revision="local-test",
                name="semantic",
                status="ready",
                local_path="placeholder",
                profile_path="placeholder",
                file_count=1,
                size_bytes=1,
                created_at=now,
                updated_at=now,
            )
            base_profile = {
                "version": 1,
                "resourceId": record.id,
                "name": record.name,
                "completeness": 1,
                "warnings": [],
            }

            with patch("datamodelmatch.resource_cli._validate_local_source", return_value=str(source)), \
                 patch("datamodelmatch.dataset_resources.import_dataset", return_value=(record, base_profile)), \
                 patch("datamodelmatch.semantic_runtime.build_semantic_profile", side_effect=ValueError("agent unavailable")):
                with self.assertRaisesRegex(ValueError, "agent unavailable"):
                    _import(arguments, store)

            with self.assertRaises(KeyError):
                store.get(record.id)


if __name__ == "__main__":
    unittest.main()
