import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from datamodelmatch.dataset_transform import DatasetTransformError, transform_dataset
from datamodelmatch.resource_store import ResourceStore
from datamodelmatch.resource_types import ResourceRecord


class DatasetTransformTests(unittest.TestCase):
    def test_agent_plan_is_rechecked_before_the_resource_is_registered(self) -> None:
        class Planner:
            config = SimpleNamespace(model="test-planner")
            last_model = "test-planner"
            attempt_count = 1

            def __init__(self) -> None:
                self.calls = 0

            def complete_json(self, _system: str, _user: str) -> dict:
                self.calls += 1
                if self.calls == 1:
                    return {
                        "summary": "将 image_path 映射为 image。",
                        "fieldMappings": [{
                            "datasetField": "image_path", "modelField": "image",
                            "kind": "semantic", "confidence": 1, "reason": "同一输入。",
                        }],
                        "operations": [],
                        "warnings": [],
                    }
                return {"summary": "复检补充。", "fieldMappings": [], "transforms": [], "warnings": []}

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ResourceStore(root / ".datamodelmatch")
            store.ensure()
            source = store.root / "resources" / "datasets" / "dataset_source"
            source.mkdir(parents=True)
            (source / "data.csv").write_text("image_path,label\na.png,cat\n", encoding="utf-8")
            self._save_dataset(store, "dataset_source", source, ["image_path", "label"])
            self._save_model(store, "model_target", "Vision model")
            planner = Planner()

            record, profile = transform_dataset(
                store, "dataset_source", "model_target",
                {"status": "adaptable", "fieldMappings": [{"datasetField": "image_path", "modelField": "image"}]},
                store.root / "resources" / "datasets" / "dataset_adapted", "dataset_adapted", client=planner,
            )

            self.assertEqual(planner.calls, 2)
            self.assertEqual(record.status, "ready")
            self.assertEqual(profile["verification"]["status"], "compatible")
            self.assertTrue(profile["transform"]["verified"])

    def test_invalid_agent_plan_never_creates_a_derived_resource(self) -> None:
        class InvalidPlanner:
            config = SimpleNamespace(model="test-planner")
            last_model = "test-planner"
            attempt_count = 1

            def complete_json(self, _system: str, _user: str) -> dict:
                return {"summary": "bad", "fieldMappings": [], "operations": [], "warnings": []}

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ResourceStore(root / ".datamodelmatch")
            store.ensure()
            source = store.root / "resources" / "datasets" / "dataset_source"
            source.mkdir(parents=True)
            (source / "data.csv").write_text("image_path\na.png\n", encoding="utf-8")
            self._save_dataset(store, "dataset_source", source, ["image_path"])
            self._save_model(store, "model_target", "Vision model")
            target = store.root / "resources" / "datasets" / "dataset_adapted"

            with self.assertRaisesRegex(DatasetTransformError, "未覆盖模型必需字段"):
                transform_dataset(
                    store, "dataset_source", "model_target", {"status": "adaptable", "fieldMappings": []},
                    target, "dataset_adapted", client=InvalidPlanner(),
                )
            self.assertFalse(target.exists())
            with self.assertRaises(KeyError):
                store.get("dataset_adapted")

    def test_transforms_csv_and_jsonl_without_mutating_source(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ResourceStore(root.resolve() / ".datamodelmatch")
            store.ensure()
            source = store.root / "resources" / "datasets" / "dataset_source"
            source.mkdir(parents=True)
            (source / "train.csv").write_text(
                "image_path,label,split\ncat.png,cat,train\n",
                encoding="utf-8",
            )
            (source / "validation.jsonl").write_text(
                '{"image_path":"dog.png","label":"dog"}\n\n',
                encoding="utf-8",
            )
            (source / "README.txt").write_text("source snapshot\n", encoding="utf-8")
            before = {
                path.relative_to(source): path.read_bytes()
                for path in source.rglob("*")
                if path.is_file()
            }
            self._save_dataset(store, "dataset_source", source, ["image_path", "label", "split"])
            self._save_model(store, "model_target", "Vision model")

            events = []
            record, profile = transform_dataset(
                store=store,
                dataset_resource_id="dataset_source",
                model_resource_id="model_target",
                report={
                    "status": "adaptable",
                    "fieldMappings": [
                        {
                            "datasetField": "image_path",
                            "modelField": "image",
                            "kind": "transform",
                        },
                        {"datasetField": "label", "modelField": "target"},
                    ],
                },
                destination=store.root / "resources" / "datasets" / "dataset_adapted",
                resource_id="dataset_adapted",
                emit=lambda name, data: events.append((name, data)),
            )

            target = store.root / record.local_path
            self.assertEqual(
                (target / "train.csv").read_text(encoding="utf-8"),
                "image,target,split\ncat.png,cat,train\n",
            )
            self.assertEqual(
                json.loads((target / "validation.jsonl").read_text(encoding="utf-8")),
                {"image": "dog.png", "target": "dog"},
            )
            self.assertEqual((target / "README.txt").read_text(encoding="utf-8"), "source snapshot\n")
            self.assertEqual(
                {
                    path.relative_to(source): path.read_bytes()
                    for path in source.rglob("*")
                    if path.is_file()
                },
                before,
            )
            self.assertEqual(record.provenance, profile["provenance"])
            self.assertEqual(
                record.provenance,
                {
                    "sourceDatasetId": "dataset_source",
                    "sourceDatasetName": "Source dataset",
                    "targetModelId": "model_target",
                    "targetModelName": "Vision model",
                    "transformStatus": "verified",
                },
            )
            manifest = json.loads((target / "datamodelmatch-transform.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["provenance"], record.provenance)
            self.assertEqual(manifest["kind"], "contract-adapter")
            self.assertEqual(profile["verification"]["status"], "compatible")
            self.assertEqual([name for name, _ in events[:2]], ["stage", "stage"])
            self.assertEqual(events[-1][0], "stage")
            self.assertEqual(events[-1][1]["name"], "complete")

    def test_transforms_parquet_when_pyarrow_is_available(self) -> None:
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            self.skipTest("pyarrow is unavailable")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ResourceStore(root.resolve() / ".datamodelmatch")
            store.ensure()
            source = store.root / "resources" / "datasets" / "dataset_source"
            source.mkdir(parents=True)
            pq.write_table(
                pa.table({"image_path": ["cat.png"], "label": [1]}),
                source / "train.parquet",
            )
            source_bytes = (source / "train.parquet").read_bytes()
            self._save_dataset(store, "dataset_source", source, ["image_path", "label"])
            self._save_model(store, "model_target", "Vision model")

            transform_dataset(
                store,
                "dataset_source",
                "model_target",
                {
                    "status": "adaptable",
                    "fieldMappings": [{"datasetField": "image_path", "modelField": "image"}],
                },
                store.root / "resources" / "datasets" / "dataset_adapted",
                "dataset_adapted",
            )

            table = pq.read_table(
                store.root / "resources" / "datasets" / "dataset_adapted" / "train.parquet"
            )
            self.assertEqual(table.column_names, ["image", "label"])
            self.assertEqual(table["image"].to_pylist(), ["cat.png"])
            self.assertEqual((source / "train.parquet").read_bytes(), source_bytes)

    def test_rejects_wrong_resource_kind_and_missing_mappings(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ResourceStore(root.resolve() / ".datamodelmatch")
            store.ensure()
            dataset_path = store.root / "resources" / "datasets" / "dataset_source"
            dataset_path.mkdir(parents=True)
            (dataset_path / "data.csv").write_text("value\n1\n", encoding="utf-8")
            self._save_dataset(store, "dataset_source", dataset_path, ["value"])
            self._save_model(store, "model_target", "Target model")

            with self.assertRaisesRegex(DatasetTransformError, "数据集和一个模型"):
                transform_dataset(
                    store,
                    "model_target",
                    "model_target",
                    {
                        "status": "adaptable",
                        "fieldMappings": [{"datasetField": "value", "modelField": "image"}],
                    },
                    root / "adapted",
                    "dataset_adapted",
                )
            with self.assertRaisesRegex(DatasetTransformError, "未覆盖模型必需字段"):
                transform_dataset(
                    store,
                    "dataset_source",
                    "model_target",
                    {"status": "adaptable", "fieldMappings": []},
                    root / "adapted",
                    "dataset_adapted",
                )
            with self.assertRaisesRegex(DatasetTransformError, "字段映射必须是数组"):
                transform_dataset(
                    store,
                    "dataset_source",
                    "model_target",
                    {"status": "adaptable", "fieldMappings": {}},
                    root / "adapted",
                    "dataset_adapted",
                )
            with self.assertRaisesRegex(DatasetTransformError, "转换后可用"):
                transform_dataset(
                    store,
                    "dataset_source",
                    "model_target",
                    {
                        "status": "compatible",
                        "fieldMappings": [{"datasetField": "value", "modelField": "image"}],
                    },
                    root / "adapted",
                    "dataset_adapted",
                )

    def test_rejects_malformed_json_format(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            store = ResourceStore(root.resolve() / ".datamodelmatch")
            store.ensure()
            source = store.root / "resources" / "datasets" / "dataset_source"
            source.mkdir(parents=True)
            (source / "broken.json").write_text('{"records": [', encoding="utf-8")
            self._save_dataset(store, "dataset_source", source, ["value"])
            self._save_model(store, "model_target", "Target model")

            with self.assertRaises(json.JSONDecodeError):
                transform_dataset(
                    store,
                    "dataset_source",
                    "model_target",
                    {
                        "status": "adaptable",
                        "fieldMappings": [{"datasetField": "value", "modelField": "image"}],
                    },
                    root / "adapted",
                    "dataset_adapted",
                )

    @staticmethod
    def _save_dataset(
        store: ResourceStore,
        resource_id: str,
        source: Path,
        feature_names: list[str],
    ) -> None:
        store.save(
            ResourceRecord(
                id=resource_id,
                kind="dataset",
                source_type="local",
                source=str(source),
                revision="local",
                resolved_revision="local-v1",
                name="Source dataset",
                status="ready",
                local_path=str(source.relative_to(store.root)),
                profile_path=f"profiles/datasets/{resource_id}.json",
                file_count=sum(1 for path in source.rglob("*") if path.is_file()),
                size_bytes=sum(path.stat().st_size for path in source.rglob("*") if path.is_file()),
                created_at="2026-09-08T00:00:00Z",
                updated_at="2026-09-08T00:00:00Z",
            ),
            {
                "resourceId": resource_id,
                "name": "Source dataset",
                "modalities": ["text"],
                "taskHints": ["text-classification"],
                "license": "MIT",
                "features": [
                    {
                        "name": name,
                        "dataType": "string",
                        "semanticRole": "label" if name == "label" else "input",
                        "nullable": False,
                        "shape": [],
                    }
                    for name in feature_names
                ],
            },
        )

    @staticmethod
    def _save_model(store: ResourceStore, resource_id: str, name: str) -> None:
        store.save(
            ResourceRecord(
                id=resource_id,
                kind="model",
                source_type="local",
                source="local:model",
                revision="local",
                resolved_revision="local-v1",
                name=name,
                status="ready",
                local_path=f"resources/models/{resource_id}",
                profile_path=f"profiles/models/{resource_id}.json",
                file_count=0,
                size_bytes=0,
                created_at="2026-09-08T00:00:00Z",
                updated_at="2026-09-08T00:00:00Z",
            ),
            {
                "resourceId": resource_id,
                "name": name,
                "tasks": ["text-classification"],
                "frameworks": ["test"],
                "license": "MIT",
                "inputContract": {
                    "modalities": ["text"],
                    "fields": [
                        {
                            "name": "image",
                            "dataType": "string",
                            "shape": [],
                            "required": True,
                        },
                        {
                            "name": "target",
                            "dataType": "string",
                            "shape": [],
                            "required": False,
                        },
                    ],
                    "preprocessing": [],
                    "constraints": [],
                },
            },
        )


if __name__ == "__main__":
    unittest.main()
