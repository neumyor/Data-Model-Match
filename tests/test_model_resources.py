import io
import base64
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from datamodelmatch.model_resources import (
    ModelResourceError,
    _parse_github_source,
    _resolve_github_revision,
    import_model,
    search_github_models,
)


class ModelResourceTests(unittest.TestCase):
    def test_parses_github_urls_and_owner_repository_pairs(self) -> None:
        self.assertEqual(_parse_github_source("karpathy/minGPT"), ("karpathy", "minGPT"))
        self.assertEqual(
            _parse_github_source("https://github.com/karpathy/minGPT.git"),
            ("karpathy", "minGPT"),
        )
        with self.assertRaisesRegex(ModelResourceError, "GitHub source"):
            _parse_github_source("http://github.com/karpathy/minGPT")

    @patch("datamodelmatch.model_resources._github_json")
    def test_accepts_full_commit_sha_without_github_api_lookup(self, github_json) -> None:
        revision = "A" * 40

        self.assertEqual(_resolve_github_revision("org", "repo", revision), "a" * 40)
        github_json.assert_not_called()

    @patch("datamodelmatch.model_resources._github_json")
    def test_search_github_models_returns_lightweight_candidates(self, github_json) -> None:
        github_json.return_value = {
            "items": [{
                "full_name": "org/project",
                "name": "project",
                "html_url": "https://github.com/org/project",
                "description": "A model",
                "default_branch": "main",
                "stargazers_count": 17,
                "updated_at": "2026-01-01T00:00:00Z",
            }],
        }

        result = search_github_models("vision transformer", 1)

        self.assertEqual(result[0]["fullName"], "org/project")
        self.assertEqual(result[0]["stars"], 17)
        self.assertIn("machine-learning", github_json.call_args.args[0])

    def test_imports_and_profiles_safe_local_model_directory(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "README.md").write_text(
                "# Mini text generation model\n"
                "A Transformer for text generation. Use a tokenizer before inference.\n",
                encoding="utf-8",
            )
            (source / "requirements.txt").write_text("torch\ntransformers\n", encoding="utf-8")
            (source / "main.py").write_text(
                "from transformers import AutoTokenizer, AutoModelForCausalLM\n",
                encoding="utf-8",
            )
            (source / "LICENSE").write_text("MIT License\n", encoding="utf-8")
            (source / "weights.bin").write_bytes(b"not imported")
            (source / ".env").write_text("API_KEY=must-not-be-copied\n", encoding="utf-8")
            events = []

            record, profile = import_model(
                "local",
                str(source),
                None,
                root / "destination",
                "model_mini",
                "full",
                1024 * 1024,
                events.append,
            )

            self.assertEqual(record.status, "ready")
            self.assertEqual(record.kind, "model")
            self.assertTrue(record.resolved_revision.startswith("local-"))
            self.assertEqual(profile["source"]["type"], "local")
            self.assertIn("pytorch", profile["frameworks"])
            self.assertIn("transformers", profile["frameworks"])
            self.assertIn("transformer", profile["architectures"])
            self.assertIn("text-generation", profile["tasks"])
            self.assertEqual(profile["inputContract"]["modalities"], ["text"])
            self.assertIn("tokenize", profile["inputContract"]["preprocessing"])
            self.assertEqual(profile["license"], "MIT")
            self.assertTrue((root / "destination" / "README.md").is_file())
            self.assertFalse((root / "destination" / "weights.bin").exists())
            self.assertFalse((root / "destination" / ".env").exists())
            self.assertEqual(events[-1], {"type": "end", "status": "completed"})

    def test_recognizes_chinese_text_classification_description(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "README.md").write_text(
                "# 中文文本分类模型\n使用 tokenizer 处理文本并输出分类标签。\n",
                encoding="utf-8",
            )
            (source / "inference.py").write_text(
                "from transformers import AutoModelForSequenceClassification\n",
                encoding="utf-8",
            )

            _, profile = import_model(
                "local", str(source), None, root / "destination",
                "model_chinese", "sample", 1024 * 1024,
            )

            self.assertIn("text-classification", profile["tasks"])

    def test_does_not_turn_incidental_vision_repository_terms_into_required_modalities(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "README.md").write_text(
                "# Vision model\nImage classification and object detection.\n"
                "The export guide mentions text generation and audio tracks.\n",
                encoding="utf-8",
            )
            (source / "predict.py").write_text(
                "# vision-language support and audio loading utilities\n"
                "def predict(image):\n    return image\n",
                encoding="utf-8",
            )

            _, profile = import_model(
                "local",
                str(source),
                None,
                root / "destination",
                "model_vision_terms",
                "sample",
                1024 * 1024,
            )

        self.assertIn("image-classification", profile["tasks"])
        self.assertIn("object-detection", profile["tasks"])
        self.assertNotIn("text-generation", profile["tasks"])
        self.assertNotIn("image-to-text", profile["tasks"])
        self.assertEqual(profile["inputContract"]["modalities"], ["image"])
        self.assertNotIn("tokenize", profile["inputContract"]["preprocessing"])
        self.assertNotIn("resample", profile["inputContract"]["preprocessing"])

    def test_infers_cifar_cross_entropy_model_as_image_classification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "README.md").write_text(
                "# Train CIFAR10 with PyTorch\n",
                encoding="utf-8",
            )
            (source / "main.py").write_text(
                "import torchvision\n"
                "criterion = nn.CrossEntropyLoss()\n"
                "num_classes = 10\n",
                encoding="utf-8",
            )

            _, profile = import_model(
                "local",
                str(source),
                None,
                root / "destination",
                "model_cifar",
                "sample",
                1024 * 1024,
            )

        self.assertEqual(profile["tasks"], ["image-classification"])
        self.assertEqual(profile["inputContract"]["modalities"], ["image"])
        self.assertEqual(profile["outputContract"]["fields"][0]["name"], "logits")

    def test_multi_task_vision_model_exposes_alternative_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "README.md").write_text(
                "# Vision suite\n"
                "Image classification, object detection, and image segmentation.\n",
                encoding="utf-8",
            )
            (source / "predict.py").write_text("import torch\n", encoding="utf-8")

            _, profile = import_model(
                "local",
                str(source),
                None,
                root / "destination",
                "model_multi_vision",
                "sample",
                1024 * 1024,
            )

        outputs = {item["name"]: item for item in profile["outputContract"]["fields"]}
        self.assertEqual(set(outputs), {"logits", "detections", "mask"})
        self.assertTrue(all(not item["required"] for item in outputs.values()))

    def test_rejects_local_symlink_escape_and_size_limit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            external = root / "external.py"
            external.write_text("print('do not read')", encoding="utf-8")
            (source / "linked.py").symlink_to(external)
            with self.assertRaisesRegex(ModelResourceError, "symbolic link outside"):
                import_model("local", str(source), None, root / "destination", "model_link", "full", 1024)

            linked_root = root / "linked-source"
            linked_root.symlink_to(source, target_is_directory=True)
            with self.assertRaisesRegex(ModelResourceError, "directory must not be a symbolic link"):
                import_model("local", str(linked_root), None, root / "destination", "model_root_link", "full", 1024)

            (source / "README.md").write_text("x" * 64, encoding="utf-8")
            with self.assertRaisesRegex(ModelResourceError, "exceeds max_bytes"):
                import_model("local", str(source), None, root / "destination", "model_size", "full", 8)

    @patch("datamodelmatch.model_resources._read_limited")
    @patch("datamodelmatch.model_resources._resolve_github_revision")
    def test_imports_fixed_github_archive_without_weights(self, resolve_revision, read_limited) -> None:
        resolve_revision.return_value = "a" * 40
        read_limited.return_value = _archive_bytes({
            "org-repo-aaaaaaaa/README.md": "# Vision classifier\nImage classification with PyTorch.\n",
            "org-repo-aaaaaaaa/requirements.txt": "torch\n",
            "org-repo-aaaaaaaa/inference.py": "import torch\n",
            "org-repo-aaaaaaaa/model.safetensors": "do not extract",
            "org-repo-aaaaaaaa/.git/config": "ignored",
        })
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            record, profile = import_model(
                "github",
                "https://github.com/org/repo",
                "v1.2.3",
                root / "destination",
                "model_repo",
                "full",
                1024 * 1024,
            )

            self.assertEqual(record.source, "org/repo")
            self.assertEqual(record.revision, "v1.2.3")
            self.assertEqual(record.resolved_revision, "a" * 40)
            self.assertIn("image-classification", profile["tasks"])
            self.assertFalse((root / "destination" / "model.safetensors").exists())
            self.assertFalse((root / "destination" / ".git").exists())
            self.assertEqual(
                read_limited.call_args.args[0],
                "https://codeload.github.com/org/repo/zip/" + "a" * 40,
            )

    def test_metadata_mode_does_not_copy_local_source_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "README.md").write_text("# Local model", encoding="utf-8")

            _, profile = import_model(
                "local", str(source), None, root / "destination", "model_meta",
                "metadata", 1024 * 1024,
            )

            self.assertFalse((root / "destination" / "README.md").exists())
            self.assertTrue((root / "destination" / "LOCAL.metadata.json").exists())
            self.assertEqual(profile["tasks"], [])

    @patch("datamodelmatch.model_resources._resolve_github_revision", return_value="a" * 40)
    @patch("datamodelmatch.model_resources._github_json")
    def test_sample_mode_uses_github_tree_and_blob_apis(self, github_json, _resolve) -> None:
        readme = b"# Text classification\nPyTorch model with tokenizer.\n"
        source = b"import torch\n"
        github_json.side_effect = [
            {
                "tree": [
                    {"type": "blob", "path": "README.md", "sha": "readme", "size": len(readme)},
                    {"type": "blob", "path": "inference.py", "sha": "source", "size": len(source)},
                    {"type": "blob", "path": "weights.bin", "sha": "weights", "size": 100},
                ]
            },
            {"encoding": "base64", "content": base64.b64encode(readme).decode("ascii")},
            {"encoding": "base64", "content": base64.b64encode(source).decode("ascii")},
        ]
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _, profile = import_model(
                "github", "org/repo", "main", root / "destination",
                "model_api_sample", "sample", 1024 * 1024,
            )

            self.assertTrue((root / "destination" / "README.md").is_file())
            self.assertTrue((root / "destination" / "inference.py").is_file())
            self.assertFalse((root / "destination" / "weights.bin").exists())
            self.assertIn("text-classification", profile["tasks"])


def _archive_bytes(files: dict[str, str]) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w") as archive:
        for name, content in files.items():
            archive.writestr(name, content)
    return output.getvalue()


if __name__ == "__main__":
    unittest.main()
