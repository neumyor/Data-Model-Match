import json
import struct
import tempfile
import unittest
from pathlib import Path

from datamodelmatch.semantic_inspection import (
    InspectionError,
    InspectionLimits,
    DelimitedTableInspectionFact,
    ImageInspectionFact,
    JsonInspectionFact,
    ParquetInspectionFact,
    VideoInspectionFact,
    XmlInspectionFact,
    inspect_file,
)


def _png(width: int, height: int) -> bytes:
    return (
        b"\x89PNG\r\n\x1a\n"
        + b"\x00\x00\x00\rIHDR"
        + width.to_bytes(4, "big")
        + height.to_bytes(4, "big")
        + bytes([8, 2])
        + b"\x00\x00\x00\x00"
    )


class SemanticInspectionTests(unittest.TestCase):
    def test_image_header_facts_are_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            image = root / "frame.png"
            image.write_bytes(_png(640, 480))
            fact = inspect_file(image, snapshot_root=root)
        self.assertIsInstance(fact, ImageInspectionFact)
        self.assertEqual((fact.status, fact.width, fact.height, fact.channels), ("COMPLETED", 640, 480, 3))
        self.assertEqual(fact.container, "png")

    def test_video_invalid_and_unsupported_are_never_guessed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            invalid = root / "broken.mp4"
            invalid.write_bytes(b"not a video")
            valid_header = root / "container.mp4"
            valid_header.write_bytes(b"\x00\x00\x00\x18ftypisom" + b"\x00" * 8)
            invalid_fact = inspect_file(invalid, snapshot_root=root)
            unsupported_fact = inspect_file(valid_header, snapshot_root=root)
        self.assertIsInstance(invalid_fact, VideoInspectionFact)
        self.assertEqual((invalid_fact.status, invalid_fact.error_code), ("FAILED", "INVALID_MEDIA"))
        self.assertEqual((unsupported_fact.status, unsupported_fact.error_code), ("UNSUPPORTED", "VIDEO_METADATA_UNSUPPORTED"))
        self.assertIsNone(unsupported_fact.duration_ms)
        self.assertIsNone(unsupported_fact.frame_count)

    def test_table_json_jsonl_and_xml_facts_respect_bounds_and_reject_doctype(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "table.csv").write_text("id,label\n1,a\n2,b\n3,c\n", encoding="utf-8")
            (root / "records.json").write_text(json.dumps({"records": [{"id": 1, "ok": True}]}), encoding="utf-8")
            (root / "records.jsonl").write_text('{"id":1}\nnot-json\n{"id":2}\n', encoding="utf-8")
            (root / "annotations.xml").write_text("<annotations><box id=\"1\" /></annotations>", encoding="utf-8")
            (root / "unsafe.xml").write_text(
                "<!DOCTYPE foo [<!ENTITY xxe SYSTEM \"file:///etc/passwd\">]><foo>&xxe;</foo>",
                encoding="utf-8",
            )
            table = inspect_file(root / "table.csv", InspectionLimits(max_rows=2), root)
            record = inspect_file(root / "records.json", snapshot_root=root)
            jsonl = inspect_file(root / "records.jsonl", snapshot_root=root)
            xml = inspect_file(root / "annotations.xml", snapshot_root=root)
            unsafe = inspect_file(root / "unsafe.xml", snapshot_root=root)
        self.assertIsInstance(table, DelimitedTableInspectionFact)
        self.assertTrue(table.truncated)
        self.assertEqual(table.row_count, 2)
        self.assertIsInstance(record, JsonInspectionFact)
        self.assertEqual(record.row_count, 1)
        self.assertEqual(jsonl.invalid_rows, 1)
        self.assertIsInstance(xml, XmlInspectionFact)
        self.assertEqual((xml.root_tag, xml.element_count), ("annotations", 2))
        self.assertEqual(unsafe.error_code, "XML_DOCTYPE_REJECTED")

    def test_large_sensitive_symlink_and_path_escape_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "snapshot"
            root.mkdir()
            large = root / "large.json"
            large.write_text('{"x": "123456"}', encoding="utf-8")
            sensitive = root / "secrets.json"
            sensitive.write_text("{}", encoding="utf-8")
            outside = Path(directory) / "outside.json"
            outside.write_text("{}", encoding="utf-8")
            try:
                link = root / "link.json"
                link.symlink_to(outside)
            except OSError:
                link = None
            large_fact = inspect_file(large, InspectionLimits(max_bytes=4), snapshot_root=root)
            with self.assertRaises(InspectionError):
                inspect_file(sensitive, snapshot_root=root)
            if link is not None:
                with self.assertRaises(InspectionError):
                    inspect_file(link, snapshot_root=root)
            with self.assertRaises(InspectionError):
                inspect_file(outside, snapshot_root=root)
        self.assertEqual(large_fact.error_code, "BYTE_LIMIT")

    def test_parquet_schema_and_row_facts(self) -> None:
        try:
            import pyarrow as pa
            import pyarrow.parquet as pq
        except ImportError:
            self.skipTest("pyarrow is unavailable")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "table.parquet"
            pq.write_table(pa.table({"id": [1, 2, 3], "name": ["a", "b", "c"]}), path)
            fact = inspect_file(path, InspectionLimits(max_rows=2), snapshot_root=root)
        self.assertIsInstance(fact, ParquetInspectionFact)
        self.assertEqual(fact.status, "COMPLETED")
        self.assertEqual(fact.physical_row_count, 3)
        self.assertEqual(fact.row_count, 2)
        self.assertTrue(fact.truncated)
        self.assertEqual([column.name for column in fact.columns], ["id", "name"])
