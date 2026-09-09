import json
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import Mock, patch

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

    @patch("datamodelmatch.llm.urlopen")
    def test_resolves_logical_model_and_fails_over_between_deployments(self, urlopen) -> None:
        urlopen.side_effect = [
            _response({
                "data": [
                    {
                        "id": "GLM_slow",
                        "modelName": "glm-5.3-flash",
                        "status": "START",
                        "supported_protocols": [{"code": "OPENAI_HTTP"}],
                    },
                    {
                        "id": "GLM_healthy",
                        "root": "glm-5.3-flash",
                        "status": "START",
                        "supported_protocols": [{"endpoint": "/v1/chat/completions"}],
                    },
                ]
            }),
            OSError("response read timed out"),
            _response({
                "model": "glm-5.3-flash",
                "choices": [{"message": {"content": "{\"ok\": true}"}}],
            }),
        ]
        client = LLMClient(
            LLMConfig(
                "https://example.com/v1/chat/completions",
                "secret",
                "glm-5.3-flash",
            ),
            timeout_seconds=60,
        )

        result = client.complete_json("system", "user")

        self.assertEqual(result, {"ok": True})
        self.assertEqual(client.last_model, "GLM_healthy")
        self.assertEqual(client.attempt_count, 2)
        requested_models = [
            json.loads(call.args[0].data)["model"]
            for call in urlopen.call_args_list[1:]
        ]
        self.assertEqual(requested_models, ["GLM_slow", "GLM_healthy"])

    @patch("datamodelmatch.llm.urlopen")
    def test_can_reject_application_invalid_deployment_and_use_next(self, urlopen) -> None:
        urlopen.side_effect = [
            _response({
                "data": [
                    {"id": "GLM_first", "modelName": "glm-5.3-flash", "status": "START"},
                    {"id": "GLM_second", "modelName": "glm-5.3-flash", "status": "START"},
                ]
            }),
            _response({"choices": [{"message": {"content": "{\"value\": 1}"}}]}),
            _response({"choices": [{"message": {"content": "{\"value\": 2}"}}]}),
        ]
        client = LLMClient(
            LLMConfig(
                "https://example.com/v1/chat/completions",
                "secret",
                "glm-5.3-flash",
            )
        )

        self.assertEqual(client.complete_json("system", "user"), {"value": 1})
        client.reject_last_model()
        self.assertEqual(client.complete_json("system", "user"), {"value": 2})
        self.assertEqual(client.last_model, "GLM_second")


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


class _Response:
    def __init__(self, value: dict) -> None:
        self._stream = BytesIO(json.dumps(value).encode("utf-8"))

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self) -> bytes:
        return self._stream.read()


def _response(value: dict) -> _Response:
    return _Response(value)


if __name__ == "__main__":
    unittest.main()
