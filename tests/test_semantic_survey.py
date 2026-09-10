import json
import tempfile
import unittest
from pathlib import Path

from datamodelmatch.semantic_survey import SurveyLimits, SurveyError, survey_snapshot


class SemanticSurveyTests(unittest.TestCase):
    def test_sketch_is_deterministic_and_reports_candidates_without_open_semantics(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "snapshot"
            (root / "renamed" / "nested").mkdir(parents=True)
            (root / "renamed" / "nested" / "frame.png").write_bytes(
                b"\x89PNG\r\n\x1a\n"
                + b"\x00\x00\x00\rIHDR"
                + (2).to_bytes(4, "big")
                + (3).to_bytes(4, "big")
                + bytes([8, 2])
                + b"\x00\x00\x00\x00"
            )
            (root / "labels.csv").write_text("id,label\n1,x\n", encoding="utf-8")
            (root / "notes.txt").write_text("plain documentation", encoding="utf-8")
            (root / "irrelevant.bin").write_bytes(b"ignored by classification")
            first = survey_snapshot(root)
            second = survey_snapshot(root)

        self.assertEqual(first, second)
        self.assertEqual(first.file_count, 4)
        self.assertIn("renamed/nested", first.directory_patterns)
        self.assertEqual(first.image_candidates, ("renamed/nested/frame.png",))
        self.assertEqual(first.annotation_candidates, ("labels.csv",))
        self.assertEqual(first.documentation_candidates, ())
        encoded = json.dumps(first.to_dict(), ensure_ascii=False)
        self.assertNotIn("city", encoded)
        self.assertNotIn("aerial", encoded)
        self.assertNotIn("task", encoded)

    def test_missing_readme_is_not_an_error_and_sensitive_symlink_and_escape_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "snapshot"
            root.mkdir()
            outside = Path(directory) / "outside.txt"
            outside.write_text("outside", encoding="utf-8")
            (root / "config.llm.json").write_text("secret", encoding="utf-8")
            (root / "visible.txt").write_text("visible", encoding="utf-8")
            try:
                (root / "escape.txt").symlink_to(outside)
                (root / "linked-dir").symlink_to(outside.parent, target_is_directory=True)
            except OSError:
                self.skipTest("symlinks are unavailable")
            sketch = survey_snapshot(root)

        self.assertEqual(sketch.file_count, 1)
        codes = {item.reason_code for item in sketch.skipped_paths}
        self.assertIn("SENSITIVE_FILE_SKIPPED", codes)
        self.assertIn("SYMLINK_SKIPPED", codes)

    def test_limits_are_explicit_and_diagnosable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "a.bin").write_bytes(b"12345")
            (root / "b.bin").write_bytes(b"12345")
            sketch = survey_snapshot(
                root,
                SurveyLimits(max_files=1, max_depth=2, max_file_bytes=5, max_total_bytes=5),
            )
        self.assertEqual(sketch.file_count, 1)
        self.assertEqual(sketch.total_bytes, 5)
        self.assertTrue(any(item.reason_code == "FILE_COUNT_LIMIT" for item in sketch.skipped_paths))

    def test_rejects_invalid_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaises(SurveyError):
                survey_snapshot(Path(directory) / "missing")
