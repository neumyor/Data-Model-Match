import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from datamodelmatch.resource_cli import _validate_local_source
from datamodelmatch.resource_store import ResourceStore


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


if __name__ == "__main__":
    unittest.main()
