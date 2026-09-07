import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from datamodelmatch.config import ConfigError, load_llm_config
from datamodelmatch.llm import LLMClient, LLMError
from datamodelmatch.matcher import MatchError, match_models
from datamodelmatch.models import load_model


class CoreTests(unittest.TestCase):
    def test_loads_json_sample_model_and_infers_types(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.json"
            path.write_text(json.dumps({"id": 1, "active": True, "name": "Ada"}), encoding="utf-8")

            model = load_model(path)

        self.assertEqual(model.name, "model")
        self.assertEqual([(field.name, field.type) for field in model.fields], [
            ("id", "integer"),
            ("active", "boolean"),
            ("name", "string"),
        ])

    def test_loads_json_schema_model(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "model.json"
            path.write_text(json.dumps({
                "type": "object",
                "properties": {
                    "user_id": {"type": "string", "description": "External user identifier"}
                }
            }), encoding="utf-8")

            model = load_model(path)

        self.assertEqual(model.fields[0].description, "External user identifier")

    def test_validates_match_result(self) -> None:
        source = _model("source", "user_id", "email")
        target = _model("target", "id", "email_address")
        client = Mock(spec=LLMClient)
        client.complete_json.return_value = {
            "matches": [
                {
                    "source_field": "user_id",
                    "target_field": "id",
                    "confidence": 0.9,
                    "reason": "Both identify the user",
                },
                {
                    "source_field": "email",
                    "target_field": "email_address",
                    "confidence": 1,
                    "reason": "Both contain the email address",
                },
            ],
            "unmatched_source_fields": [],
            "unmatched_target_fields": [],
        }

        result = match_models(source, target, client)

        self.assertEqual(result.matches[0].target_field, "id")
        self.assertEqual(client.complete_json.call_count, 1)

    def test_rejects_unknown_field_in_llm_result(self) -> None:
        source = _model("source", "user_id")
        target = _model("target", "id")
        client = Mock(spec=LLMClient)
        client.complete_json.return_value = {
            "matches": [{
                "source_field": "missing",
                "target_field": "id",
                "confidence": 0.9,
                "reason": "invalid",
            }],
            "unmatched_source_fields": [],
            "unmatched_target_fields": [],
        }

        with self.assertRaises(MatchError):
            match_models(source, target, client)

    def test_rejects_invalid_config(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.llm.json"
            path.write_text(json.dumps({
                "endpoint": "http://localhost",
                "apiKey": "secret",
                "model": "test",
                "stream": False,
            }), encoding="utf-8")

            with self.assertRaises(ConfigError):
                load_llm_config(path)

    def test_parses_fenced_json_response(self) -> None:
        self.assertEqual(_parse_content_for_test("```json\n{\"ok\": true}\n```"), {"ok": True})


def _model(name: str, *fields: str):
    from datamodelmatch.models import DataModel, Field

    return DataModel(name, tuple(Field(field, "string") for field in fields))


def _parse_content_for_test(content: str):
    from datamodelmatch.llm import _parse_json_content

    return _parse_json_content(content)


if __name__ == "__main__":
    unittest.main()
