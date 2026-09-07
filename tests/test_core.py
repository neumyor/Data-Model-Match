import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from datamodelmatch.config import ConfigError, load_llm_config
from datamodelmatch.llm import LLMClient
from datamodelmatch.matcher import MatchError, match_models
from datamodelmatch.models import Entity, Field, ModelDocument, load_model
from datamodelmatch.config import LLMConfig


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
        source = _document("source", "user_id", "email")
        target = _document("target", "id", "email_address")
        client = Mock(spec=LLMClient)
        client.config = LLMConfig("https://example.com/v1/chat/completions", "secret", "test-model")
        client.complete_json.return_value = {
            "matches": [
                {
                    "source": {"entityId": "entity", "fieldId": "user_id"},
                    "target": {"entityId": "entity", "fieldId": "id"},
                    "kind": "semantic",
                    "confidence": 0.9,
                    "reason": "Both identify the user",
                },
                {
                    "source": {"entityId": "entity", "fieldId": "email"},
                    "target": {"entityId": "entity", "fieldId": "email_address"},
                    "kind": "exact",
                    "confidence": 1,
                    "reason": "Both contain the email address",
                },
            ],
        }

        result = match_models(source, target, client)

        self.assertEqual(result.matches[0].target.field_id, "id")
        self.assertEqual(result.unmatched_source_fields, ())
        self.assertEqual(result.unmatched_target_fields, ())
        self.assertEqual(client.complete_json.call_count, 1)

    def test_rejects_unknown_field_in_llm_result(self) -> None:
        source = _document("source", "user_id")
        target = _document("target", "id")
        client = Mock(spec=LLMClient)
        client.config = LLMConfig("https://example.com/v1/chat/completions", "secret", "test-model")
        client.complete_json.return_value = {
            "matches": [{
                "source": {"entityId": "entity", "fieldId": "missing"},
                "target": {"entityId": "entity", "fieldId": "id"},
                "kind": "semantic",
                "confidence": 0.9,
                "reason": "invalid",
            }]
        }

        with self.assertRaises(MatchError):
            match_models(source, target, client)

    def test_derives_unmatched_fields_locally(self) -> None:
        source = _document("source", "id", "legacy_code")
        target = _document("target", "id", "status")
        client = Mock(spec=LLMClient)
        client.config = LLMConfig("https://example.com/v1/chat/completions", "secret", "test-model")
        client.complete_json.return_value = {
            "matches": [{
                "source": {"entityId": "entity", "fieldId": "id"},
                "target": {"entityId": "entity", "fieldId": "id"},
                "kind": "exact",
                "confidence": 1,
                "reason": "Same identifier",
            }]
        }

        result = match_models(source, target, client)

        self.assertEqual(result.unmatched_source_fields[0].field_id, "legacy_code")
        self.assertEqual(result.unmatched_target_fields[0].field_id, "status")

    def test_wraps_duplicate_match_validation_as_match_error(self) -> None:
        source = _document("source", "id")
        target = _document("target", "id", "other_id")
        client = Mock(spec=LLMClient)
        client.config = LLMConfig("https://example.com/v1/chat/completions", "secret", "test-model")
        client.complete_json.return_value = {
            "matches": [
                {
                    "source": {"entityId": "entity", "fieldId": "id"},
                    "target": {"entityId": "entity", "fieldId": "id"},
                    "kind": "exact",
                    "confidence": 1,
                    "reason": "Same identifier",
                },
                {
                    "source": {"entityId": "entity", "fieldId": "id"},
                    "target": {"entityId": "entity", "fieldId": "other_id"},
                    "kind": "semantic",
                    "confidence": 0.5,
                    "reason": "Duplicate source",
                },
            ]
        }

        with self.assertRaisesRegex(MatchError, "source match endpoints"):
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


def _document(name: str, *fields: str) -> ModelDocument:
    return ModelDocument(
        version="1",
        id=name,
        name=name,
        entities=(
            Entity(
                id="entity",
                name="Entity",
                description="Test entity",
                fields=tuple(
                    Field(field, data_type="string", description=f"{field} field")
                    for field in fields
                ),
            ),
        ),
    )


def _parse_content_for_test(content: str):
    from datamodelmatch.llm import _parse_json_content

    return _parse_json_content(content)


if __name__ == "__main__":
    unittest.main()
