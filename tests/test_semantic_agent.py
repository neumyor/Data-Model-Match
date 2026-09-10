import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError

from datamodelmatch.semantic_agent import SemanticAgentClient, SemanticAgentError


class _Response:
    def __init__(self, payload: object) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return json.dumps(self.payload).encode("utf-8")


def _write_config(path: Path, **overrides: object) -> None:
    payload = {
        "endpoint": "https://llm.example.invalid/v1/chat/completions",
        "apiKey": "test-secret-key",
        "model": "test-model",
        "stream": False,
    }
    payload.update(overrides)
    path.write_text(json.dumps(payload), encoding="utf-8")


class SemanticAgentClientTests(unittest.TestCase):
    def test_from_config_rejects_missing_or_invalid_required_fields(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.llm.json"
            with self.assertRaisesRegex(SemanticAgentError, "configuration is invalid"):
                SemanticAgentClient.from_config(path)

            _write_config(path, stream=True)
            with self.assertRaisesRegex(SemanticAgentError, "configuration is invalid"):
                SemanticAgentClient.from_config(path)

            _write_config(path, endpoint="http://llm.example.invalid/v1/chat/completions")
            with self.assertRaisesRegex(SemanticAgentError, "configuration is invalid"):
                SemanticAgentClient.from_config(path)

            _write_config(path, apiKey="")
            with self.assertRaisesRegex(SemanticAgentError, "configuration is invalid"):
                SemanticAgentClient.from_config(path)

            _write_config(path, model="")
            with self.assertRaisesRegex(SemanticAgentError, "configuration is invalid"):
                SemanticAgentClient.from_config(path)

    def test_analyze_dataset_accepts_plain_and_fenced_json_objects(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.llm.json"
            _write_config(path)
            responses = iter(
                [
                    _Response({"choices": [{"message": {"content": "{\"summary\":\"road scenes\"}"}}]}),
                    _Response({"choices": [{"message": {"content": "```json\n{\"ranked\":true}\n```"}}]}),
                ]
            )
            client = SemanticAgentClient.from_config(
                path,
                transport=lambda request, timeout: next(responses),
            )

            self.assertEqual(
                client.analyze_dataset({"evidence": ["README"]}),
                {"summary": "road scenes"},
            )
            self.assertEqual(client.match_task({"task": "road detection"}), {"ranked": True})

    def test_request_body_uses_stream_false_and_never_contains_api_key(self) -> None:
        captured = {}

        def transport(request, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["authorization"] = request.get_header("Authorization")
            captured["timeout"] = timeout
            return _Response({"choices": [{"message": {"content": "{\"ok\":true}"}}]})

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.llm.json"
            _write_config(path)
            client = SemanticAgentClient.from_config(path, transport=transport, timeout_seconds=12)
            self.assertEqual(client.analyze_dataset({"dataset": "demo"}), {"ok": True})

        serialized = json.dumps(captured["body"])
        self.assertFalse("test-secret-key" in serialized)
        self.assertEqual(captured["body"]["stream"], False)
        self.assertEqual(captured["body"]["response_format"], {"type": "json_object"})
        self.assertEqual(captured["body"]["model"], "test-model")
        self.assertEqual(captured["timeout"], 12.0)
        self.assertEqual(captured["authorization"], "Bearer test-secret-key")

    def test_rejects_invalid_json_object_and_redacts_http_error_body(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.llm.json"
            _write_config(path)
            invalid = SemanticAgentClient.from_config(
                path,
                transport=lambda request, timeout: _Response(
                    {"choices": [{"message": {"content": "[\"not an object\"]"}}]}
                ),
            )
            with self.assertRaisesRegex(SemanticAgentError, "must be an object"):
                invalid.match_task({"task": "demo"})

            malformed = SemanticAgentClient.from_config(
                path,
                transport=lambda request, timeout: _Response(
                    {"choices": [{"message": {"content": "{\"truncated\":"}}]}
                ),
            )
            with self.assertRaisesRegex(SemanticAgentError, "not valid JSON"):
                malformed.match_task({"task": "demo"})

            error = SemanticAgentClient.from_config(
                path,
                transport=lambda request, timeout: (_ for _ in ()).throw(
                    HTTPError(
                        "https://llm.example.invalid",
                        429,
                        "rate limited",
                        None,
                        None,
                    )
                ),
            )
            with self.assertRaises(SemanticAgentError) as ctx:
                error.analyze_dataset({"dataset": "demo"})

        self.assertEqual(str(ctx.exception), "semantic Agent request failed with HTTP 429")
        self.assertNotIn("test-secret-key", str(ctx.exception))

    def test_retries_one_transient_transport_failure(self) -> None:
        calls = 0

        def transport(request, timeout):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise OSError("connection reset")
            return _Response({"choices": [{"message": {"content": "{\"ok\":true}"}}]})

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.llm.json"
            _write_config(path)
            client = SemanticAgentClient.from_config(path, transport=transport)
            self.assertEqual(client.match_task({"task": "demo"}), {"ok": True})

        self.assertEqual(calls, 2)
