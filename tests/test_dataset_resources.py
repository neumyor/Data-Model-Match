import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from datamodelmatch.dataset_resources import (
    DatasetResourceError,
    _validate_huggingface_url,
    import_dataset,
    search_huggingface_datasets,
)


class DatasetResourceTests(unittest.TestCase):
    def test_search_normalizes_huggingface_candidates(self) -> None:
        payload = [
            {
                "id": "demo/team-dataset",
                "author": "demo",
                "downloads": 42,
                "likes": 3,
                "tags": ["text-classification", "en"],
                "cardData": {"pretty_name": "Demo Dataset", "license": "mit"},
            }
        ]
        with patch("datamodelmatch.dataset_resources._get_json", return_value=payload) as get_json:
            results = search_huggingface_datasets("demo", 5)

        self.assertEqual(get_json.call_count, 1)
        self.assertEqual(results[0]["id"], "demo/team-dataset")
        self.assertEqual(results[0]["license"], "mit")
        self.assertEqual(results[0]["downloads"], 42)

    def test_search_validates_input(self) -> None:
        with self.assertRaisesRegex(DatasetResourceError, "non-empty"):
            search_huggingface_datasets(" ")
        with self.assertRaisesRegex(DatasetResourceError, "between 1 and 100"):
            search_huggingface_datasets("x", 0)

    def test_imports_local_csv_jsonl_and_generates_profile(self) -> None:
        events = []
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "train.csv").write_text(
                "id,text,label\n1,hello,0\n2,world,1\n",
                encoding="utf-8",
            )
            (source / "validation.jsonl").write_text(
                '{"id": 3, "text": "test", "label": 0}\n',
                encoding="utf-8",
            )
            (source / "config.llm.json").write_text(
                '{"apiKey": "must-not-be-copied"}',
                encoding="utf-8",
            )
            record, profile = import_dataset(
                "local",
                str(source),
                "local-v1",
                root / "imported",
                "dataset_example",
                "sample",
                1024 * 1024,
                lambda name, data: events.append((name, data)),
            )

            self.assertTrue((root / "imported" / "train.csv").is_file())
            self.assertFalse((root / "imported" / "config.llm.json").exists())
            self.assertEqual(record.status, "ready")
            self.assertEqual(record.file_count, 2)
            self.assertTrue(record.resolved_revision.startswith("local-"))
            self.assertEqual(profile["source"]["revision"], record.resolved_revision)
            self.assertEqual(profile["source"]["type"], "local")
            self.assertEqual(profile["formats"], ["csv", "jsonl"])
            fields = {item["name"]: item for item in profile["features"]}
            self.assertEqual(fields["id"]["dataType"], "integer")
            self.assertEqual(fields["text"]["dataType"], "string")
            self.assertEqual(fields["label"]["semanticRole"], "label")
            self.assertEqual({item["name"] for item in profile["splits"]}, {"train", "validation"})
            self.assertIn("text", profile["modalities"])
            self.assertIn("classification", profile["taskHints"])
            self.assertEqual(events[0][0], "stage")
            self.assertEqual(events[-1][0], "result")

    def test_recognizes_cvat_tracking_images_and_boxes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            images = source / "images"
            overlays = source / "boxes"
            images.mkdir(parents=True)
            overlays.mkdir()
            for name in ("frame_000000.PNG", "frame_000001.PNG"):
                (images / name).write_bytes(b"png")
            (overlays / "frame_000000.PNG").write_bytes(b"overlay")
            (source / "annotations.xml").write_text(
                """<annotations><meta><task><original_size><width>1280</width><height>720</height></original_size></task></meta>
                <track id=\"7\" label=\"person\"><box frame=\"0\" outside=\"0\" xtl=\"1\" ytl=\"2\" xbr=\"30\" ybr=\"60\" />
                <box frame=\"1\" outside=\"1\" xtl=\"1\" ytl=\"2\" xbr=\"30\" ybr=\"60\" /></track></annotations>""",
                encoding="utf-8",
            )
            record, profile = import_dataset(
                "local", str(source), "local", root / "target",
                "dataset_cvat", "full", 1024 * 1024,
            )

        features = {item["name"]: item for item in profile["features"]}
        self.assertEqual(record.status, "ready")
        self.assertEqual(profile["formats"], ["cvat-xml"])
        self.assertEqual(profile["modalities"], ["image"])
        self.assertEqual(profile["taskHints"], ["object-detection", "object-tracking"])
        self.assertEqual(profile["sampleCount"], 2)
        self.assertEqual(profile["splits"], [{"name": "unknown", "rowCount": 2}])
        self.assertEqual(features["image"]["shape"], [720, 1280, 3])
        self.assertEqual(features["boxes"]["shape"], ["variable", 4])
        self.assertIn("person", features["labels"]["description"])
        self.assertFalse(any("没有可用于静态分析" in warning for warning in profile["warnings"]))

    def test_json_and_invalid_parquet_are_safely_inspected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "test.json").write_text(
                json.dumps({"records": [{"answer": "yes", "scores": [1, 2]}]}),
                encoding="utf-8",
            )
            (source / "archive.parquet").write_bytes(b"PAR1payloadPAR1")
            _, profile = import_dataset(
                "local",
                str(source),
                "r1",
                root / "target",
                "dataset_static",
                "full",
                1024 * 1024,
            )

        fields = {item["name"]: item for item in profile["features"]}
        self.assertEqual(fields["answer"]["dataType"], "string")
        self.assertEqual(fields["scores"]["dataType"], "array")
        self.assertEqual(fields["scores"]["shape"], [2])
        self.assertIn("parquet", profile["formats"])
        self.assertTrue(any("Parquet" in warning for warning in profile["warnings"]))

    def test_reads_huggingface_dataset_infos_for_vision_schema(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "dataset_infos.json").write_text(
                json.dumps(
                    {
                        "dummy": {
                            "features": {
                                "img": {"_type": "Image"},
                                "label": {
                                    "_type": "ClassLabel",
                                    "num_classes": 2,
                                    "names": ["cat", "dog"],
                                },
                            },
                            "task_templates": [
                                {"task": "image-classification", "image_column": "img"}
                            ],
                            "splits": {
                                "train": {"num_examples": 5},
                                "test": {"num_examples": 2},
                            },
                        }
                    }
                ),
                encoding="utf-8",
            )

            _, profile = import_dataset(
                "local",
                str(source),
                "local",
                root / "target",
                "dataset_infos_vision",
                "full",
                1024 * 1024,
            )

        features = {item["name"]: item for item in profile["features"]}
        self.assertEqual(profile["modalities"], ["image"])
        self.assertEqual(profile["taskHints"], ["image-classification"])
        self.assertEqual(features["img"]["dataType"], "image")
        self.assertEqual(features["label"]["dataType"], "classlabel")
        self.assertEqual(features["label"]["semanticRole"], "label")
        self.assertEqual(
            {item["name"]: item["rowCount"] for item in profile["splits"]},
            {"train": 5, "test": 2},
        )
        self.assertEqual(profile["sampleCount"], 0)

    def test_reads_real_parquet_schema_with_pyarrow(self) -> None:
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            self.skipTest("pyarrow is unavailable")

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            pq.write_table(
                pa.table(
                    {
                        "img": pa.array([b"image-a", b"image-b"], type=pa.binary()),
                        "label": pa.array([0, 1], type=pa.int64()),
                    }
                ),
                source / "train.parquet",
            )

            _, profile = import_dataset(
                "local",
                str(source),
                "local",
                root / "target",
                "dataset_parquet_vision",
                "full",
                1024 * 1024,
            )

        features = {item["name"]: item for item in profile["features"]}
        self.assertEqual(profile["modalities"], ["image"])
        self.assertEqual(profile["taskHints"], ["image-classification"])
        self.assertEqual(features["img"]["dataType"], "image")
        self.assertEqual(features["label"]["dataType"], "classlabel")
        self.assertEqual(profile["sampleCount"], 2)

    def test_infers_segmentation_and_ignores_label_metadata_json(self) -> None:
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            self.skipTest("pyarrow is unavailable")

        image_type = pa.struct([("bytes", pa.binary()), ("path", pa.string())])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            pq.write_table(
                pa.table(
                    {
                        "pixel_values": pa.array(
                            [{"bytes": b"image", "path": None}],
                            type=image_type,
                        ),
                        "label": pa.array(
                            [{"bytes": b"mask", "path": None}],
                            type=image_type,
                        ),
                    }
                ),
                source / "train.parquet",
            )
            (source / "id2label.json").write_text(
                '{"0": "background", "1": "road"}',
                encoding="utf-8",
            )

            _, profile = import_dataset(
                "local",
                str(source),
                "local",
                root / "target",
                "dataset_segmentation",
                "full",
                1024 * 1024,
            )

        self.assertEqual(profile["taskHints"], ["image-segmentation"])
        self.assertEqual({item["name"] for item in profile["features"]}, {"pixel_values", "label"})
        label = next(item for item in profile["features"] if item["name"] == "label")
        self.assertEqual(label["semanticRole"], "label")
        self.assertIn("掩码", label["description"])
        self.assertEqual(profile["sampleCount"], 1)

    def test_infers_object_detection_from_nested_boxes(self) -> None:
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            self.skipTest("pyarrow is unavailable")

        image_type = pa.struct([("bytes", pa.binary()), ("path", pa.string())])
        objects_type = pa.struct([
            ("bbox", pa.list_(pa.list_(pa.float32(), 4))),
            ("category", pa.list_(pa.int64())),
        ])
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            pq.write_table(
                pa.table(
                    {
                        "image": pa.array(
                            [{"bytes": b"image", "path": None}],
                            type=image_type,
                        ),
                        "objects": pa.array(
                            [{"bbox": [[0.0, 0.0, 1.0, 1.0]], "category": [0]}],
                            type=objects_type,
                        ),
                    }
                ),
                source / "train.parquet",
            )

            _, profile = import_dataset(
                "local",
                str(source),
                "local",
                root / "target",
                "dataset_detection",
                "full",
                1024 * 1024,
            )

        self.assertEqual(profile["modalities"], ["image"])
        self.assertEqual(profile["taskHints"], ["object-detection"])
        objects = next(item for item in profile["features"] if item["name"] == "objects")
        self.assertEqual(objects["semanticRole"], "label")
        self.assertEqual(objects["dataType"], "object")

    def test_recognizes_common_categorical_label_names(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "train.csv").write_text(
                "sepal_length,species\n5.1,setosa\n6.2,versicolor\n",
                encoding="utf-8",
            )

            _, profile = import_dataset(
                "local", str(source), "local", root / "target",
                "dataset_species", "sample", 1024 * 1024,
            )

            features = {item["name"]: item for item in profile["features"]}
            self.assertEqual(features["species"]["semanticRole"], "label")
            self.assertEqual(profile["taskHints"], ["classification"])

    def test_rejects_symlink_that_escapes_source_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            outside = root / "outside.csv"
            outside.write_text("id\n1\n", encoding="utf-8")
            (source / "inside.csv").write_text("id\n2\n", encoding="utf-8")
            link = source / "outside.csv"
            try:
                link.symlink_to(outside)
            except OSError:
                self.skipTest("Symbolic links are unavailable on this platform")

            _, profile = import_dataset(
                "local",
                str(source),
                "r1",
                root / "target",
                "dataset_links",
                "sample",
                1024 * 1024,
            )

        self.assertTrue(any("symbolic-link file" in warning for warning in profile["warnings"]))

    def test_rejects_unsafe_sources_and_byte_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "large.csv").write_text("text\n" + "x" * 100, encoding="utf-8")
            with self.assertRaisesRegex(DatasetResourceError, "byte limit"):
                import_dataset(
                    "local",
                    str(source),
                    "r1",
                    root / "target",
                    "dataset_limited",
                    "sample",
                    10,
                )
        with self.assertRaisesRegex(DatasetResourceError, "official domains"):
            import_dataset(
                "huggingface",
                "http://huggingface.co/datasets/demo/data",
                "main",
                Path(tempfile.gettempdir()) / "target",
                "dataset_bad_url",
                "metadata",
                1024,
            )

    def test_allows_current_huggingface_cdn_content_host(self) -> None:
        _validate_huggingface_url(
            "https://us.aws.cdn.hf.co/xet-bridge-us/object",
            allow_content_hosts=True,
        )
        with self.assertRaisesRegex(DatasetResourceError, "official domains"):
            _validate_huggingface_url(
                "https://cdn.hf.co.evil.example/object",
                allow_content_hosts=True,
            )

    def test_huggingface_import_uses_resolved_revision_and_limited_sample(self) -> None:
        metadata = {
            "id": "demo/data",
            "sha": "abc123",
            "description": "Demo",
            "tags": ["text-classification"],
            "cardData": {"license": "apache-2.0", "language": ["en"]},
            "siblings": [
                {"rfilename": "train.csv"},
                {"rfilename": "README.md"},
                {"rfilename": "test.jsonl"},
            ],
        }
        downloaded = []

        def fake_download(dataset_id, revision, file_names, staging, max_bytes, emit):
            self.assertEqual(dataset_id, "demo/data")
            self.assertEqual(revision, "abc123")
            self.assertEqual(max_bytes, 1024 * 1024)
            for file_name in file_names:
                path = staging / file_name
                path.parent.mkdir(parents=True, exist_ok=True)
                if file_name.endswith(".csv"):
                    path.write_text("text,label\nhello,0\n", encoding="utf-8")
                else:
                    path.write_text('{"text": "world", "label": 1}\n', encoding="utf-8")
            downloaded.extend(file_names)
            return list(file_names)

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("datamodelmatch.dataset_resources._get_json", return_value=metadata), patch(
                "datamodelmatch.dataset_resources._download_huggingface_files",
                side_effect=fake_download,
            ):
                record, profile = import_dataset(
                    "huggingface",
                    "https://huggingface.co/datasets/demo/data/tree/main",
                    "main",
                    root / "target",
                    "dataset_remote",
                    "sample",
                    1024 * 1024,
                )

        self.assertEqual(downloaded, ["test.jsonl", "train.csv"])
        self.assertEqual(record.source, "demo/data")
        self.assertEqual(record.resolved_revision, "abc123")
        self.assertEqual(profile["source"]["revision"], "abc123")
        self.assertEqual(profile["license"], "apache-2.0")
        self.assertEqual(profile["languages"], ["en"])

    def test_huggingface_metadata_mode_downloads_no_data(self) -> None:
        metadata = {"id": "demo/data", "sha": "abc123", "siblings": [{"rfilename": "train.csv"}]}
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with patch("datamodelmatch.dataset_resources._get_json", return_value=metadata), patch(
                "datamodelmatch.dataset_resources._download_huggingface_files"
            ) as download:
                record, profile = import_dataset(
                    "huggingface",
                    "demo/data",
                    "main",
                    root / "target",
                    "dataset_metadata",
                    "metadata",
                    1024 * 1024,
                )

        self.assertFalse(download.called)
        self.assertEqual(record.status, "needs_review")
        self.assertEqual(profile["sampleCount"], 0)


if __name__ == "__main__":
    unittest.main()
