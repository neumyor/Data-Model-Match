import json
import sys
import tempfile
import unittest
from pathlib import Path

from datamodelmatch.semantic_code import DatasetCodeExecutor


class DatasetCodeExecutorTests(unittest.TestCase):
    def test_runs_agent_authored_code_and_validates_selected_images(self):
        code = """import json
import os
from pathlib import Path
Path(os.environ['RESULT_PATH']).write_text(json.dumps({
    'summary': 'Found one sample.',
    'images': ['sample.png'],
    'imageStatus': 'sampled',
}), encoding='utf-8')
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "snapshot"
            root.mkdir()
            (root / "sample.png").write_bytes(b"\x89PNG\r\n\x1a\nminimal")
            result = DatasetCodeExecutor(root, python=sys.executable).run(code)

        self.assertEqual(result.summary, "Found one sample.")
        self.assertEqual(len(result.images), 1)
        self.assertEqual(result.images[0].path, "sample.png")
        self.assertTrue(result.images[0].data_url.startswith("data:image/png;base64,"))

    def test_rejects_non_image_selected_by_agent_code(self):
        code = """import json
import os
from pathlib import Path
Path(os.environ['RESULT_PATH']).write_text(json.dumps({
    'summary': 'Not an image.',
    'images': ['sample.txt'],
    'imageStatus': 'sampled',
}), encoding='utf-8')
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "snapshot"
            root.mkdir()
            (root / "sample.txt").write_text("not an image", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "not a supported image"):
                DatasetCodeExecutor(root, python=sys.executable).run(code)

    def test_accepts_an_agent_workdir_image_without_a_work_prefix(self):
        code = """import json
import os
from pathlib import Path
image = Path(os.environ['AGENT_WORKDIR']) / 'sample.png'
image.write_bytes(b'\\x89PNG\\r\\n\\x1a\\nminimal')
Path(os.environ['RESULT_PATH']).write_text(json.dumps({
    'summary': 'Wrote one sample.',
    'images': ['sample.png'],
    'imageStatus': 'sampled',
}), encoding='utf-8')
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "snapshot"
            root.mkdir()
            result = DatasetCodeExecutor(root, python=sys.executable).run(code)

        self.assertEqual(result.images[0].path, "work/sample.png")

    def test_accepts_none_found_after_agent_inspection(self):
        code = """import json
import os
from pathlib import Path
Path(os.environ['RESULT_PATH']).write_text(json.dumps({
    'summary': 'Inspected every local file and found no readable image.',
    'images': [],
    'imageStatus': 'none_found',
}), encoding='utf-8')
"""
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "snapshot"
            root.mkdir()
            (root / "metadata.json").write_text("{}", encoding="utf-8")
            result = DatasetCodeExecutor(root, python=sys.executable).run(code)

        self.assertEqual(result.image_availability, "none_found")


if __name__ == "__main__":
    unittest.main()
