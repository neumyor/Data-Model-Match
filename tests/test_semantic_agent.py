import json
import tempfile
import unittest
from pathlib import Path
from urllib.error import HTTPError

from datamodelmatch.semantic_agent import SemanticAgentClient, SemanticAgentError
from datamodelmatch.semantic_code import CodeExecution, DatasetCodeError, SelectedImage


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


def _dataset_profile(summary: str) -> dict[str, object]:
    return {
        "summary": summary,
        "semanticDescription": summary,
        "capabilities": [],
        "characteristics": [],
        "limitations": [],
        "evidenceRefs": [],
        "unknowns": [],
    }


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

    def test_uses_the_last_of_concatenated_json_corrections(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.llm.json"
            _write_config(path)
            client = SemanticAgentClient.from_config(
                path,
                transport=lambda request, timeout: _Response(
                    {"choices": [{"message": {"content": '{"draft":true}\n{"final":true}'}}]}
                ),
            )
            self.assertEqual(client.analyze_dataset({"dataset": "demo"}), {"final": True})

    def test_extracts_json_after_model_prose(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.llm.json"
            _write_config(path)
            client = SemanticAgentClient.from_config(
                path,
                transport=lambda request, timeout: _Response(
                    {"choices": [{"message": {"content": 'Final response:\n```json\n{"outer":{"nested":true},"final":true}\n```'}}]}
                ),
            )
            self.assertEqual(
                client.analyze_dataset({"dataset": "demo"}),
                {"outer": {"nested": True}, "final": True},
            )

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

    def test_multimodal_agent_must_run_its_own_code_and_receives_selected_images(self) -> None:
        captured = []
        responses = iter(
            [
                _Response({"choices": [{"message": {"content": None, "tool_calls": [{"id": "call_1", "type": "function", "function": {"name": "run_dataset_python", "arguments": json.dumps({"code": "print('inspect')"})}}]}}]}),
                _Response({"choices": [{"message": {"content": json.dumps(_dataset_profile("ok"))}}]}),
                _Response({"choices": [{"message": {"content": json.dumps(_dataset_profile("ok"))}}]}),
            ]
        )

        def transport(request, timeout):
            captured.append(json.loads(request.data.decode("utf-8")))
            return next(responses)

        class Executor:
            def run(self, code):
                self.code = code
                return CodeExecution(
                    "Found one image.",
                    (SelectedImage("image.png", "png", "data:image/png;base64,AA==", 1),),
                    "",
                )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.llm.json"
            _write_config(path)
            result, executions = SemanticAgentClient.from_config(path, transport=transport).analyze_dataset_with_code(
                {"dataset": "demo"}, Executor()
            )

        self.assertEqual(result["summary"], "ok")
        self.assertEqual(len(executions), 1)
        self.assertEqual(captured[0]["tools"][0]["function"]["name"], "run_dataset_python")
        self.assertEqual(captured[1]["messages"][-1]["content"][1]["image_url"]["url"], "data:image/png;base64,AA==")

    def test_multimodal_agent_can_iterate_code_before_returning_json(self) -> None:
        def tool_call(call_id):
            return {"choices": [{"message": {"content": None, "tool_calls": [{"id": call_id, "type": "function", "function": {"name": "run_dataset_python", "arguments": json.dumps({"code": "pass"})}}]}}]}

        responses = iter([
            _Response(tool_call("call_1")),
            _Response(tool_call("call_2")),
            _Response({"choices": [{"message": {"content": json.dumps(_dataset_profile("done"))}}]}),
            _Response({"choices": [{"message": {"content": json.dumps(_dataset_profile("done"))}}]}),
        ])

        class Executor:
            calls = 0

            def run(self, code):
                self.calls += 1
                if self.calls == 1:
                    return CodeExecution("Found Parquet.", tuple(), "")
                return CodeExecution(
                    "Decoded one image.",
                    (SelectedImage("work/decoded.png", "png", "data:image/png;base64,AA==", 1),),
                    "",
                )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.llm.json"
            _write_config(path)
            executor = Executor()
            captured = []
            result, executions = SemanticAgentClient.from_config(
                path,
                transport=lambda request, timeout: (
                    captured.append(json.loads(request.data.decode("utf-8"))) or next(responses)
                ),
            ).analyze_dataset_with_code(
                {"dataset": "demo", "survey": {"imageCandidates": ["records.parquet"]}},
                executor,
            )

        self.assertEqual(result["summary"], "done")
        self.assertEqual(executor.calls, 2)
        self.assertEqual(len(executions), 2)
        self.assertEqual(executions[1].images[0].path, "work/decoded.png")
        self.assertIn("does not yet satisfy the image delivery requirement", captured[1]["messages"][-1]["content"])

    def test_multimodal_agent_executes_multiple_code_calls_from_one_response(self) -> None:
        tool_calls = [
            {
                "id": "call_1",
                "type": "function",
                "function": {"name": "run_dataset_python", "arguments": json.dumps({"code": "first"})},
            },
            {
                "id": "call_2",
                "type": "function",
                "function": {"name": "run_dataset_python", "arguments": json.dumps({"code": "second"})},
            },
        ]
        responses = iter([
            _Response({"choices": [{"message": {"content": None, "tool_calls": tool_calls}}]}),
            _Response({"choices": [{"message": {"content": json.dumps(_dataset_profile("done"))}}]}),
            _Response({"choices": [{"message": {"content": json.dumps(_dataset_profile("done"))}}]}),
        ])

        class Executor:
            def __init__(self):
                self.codes = []

            def run(self, code):
                self.codes.append(code)
                if code == "first":
                    return CodeExecution("Located the container.", tuple(), "")
                return CodeExecution(
                    "Decoded one image.",
                    (SelectedImage("work/decoded.png", "png", "data:image/png;base64,AA==", 1),),
                    "",
                )

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.llm.json"
            _write_config(path)
            executor = Executor()
            result, executions = SemanticAgentClient.from_config(
                path, transport=lambda request, timeout: next(responses)
            ).analyze_dataset_with_code(
                {"dataset": "demo", "survey": {"imageCandidates": ["records.parquet"]}},
                executor,
            )

        self.assertEqual(result["summary"], "done")
        self.assertEqual(executor.codes, ["first", "second"])
        self.assertEqual(len(executions), 2)

    def test_multimodal_agent_can_fix_a_failed_code_attempt(self) -> None:
        def tool_call(call_id):
            return {"choices": [{"message": {"content": None, "tool_calls": [{"id": call_id, "type": "function", "function": {"name": "run_dataset_python", "arguments": json.dumps({"code": "pass"})}}]}}]}

        responses = iter([
            _Response(tool_call("call_1")),
            _Response(tool_call("call_2")),
            _Response({"choices": [{"message": {"content": json.dumps(_dataset_profile("recovered"))}}]}),
            _Response({"choices": [{"message": {"content": json.dumps(_dataset_profile("recovered"))}}]}),
        ])

        class Executor:
            calls = 0

            def run(self, code):
                self.calls += 1
                if self.calls == 1:
                    raise DatasetCodeError("result manifest missing")
                return CodeExecution("Recovered.", tuple(), "")

        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.llm.json"
            _write_config(path)
            result, executions = SemanticAgentClient.from_config(
                path, transport=lambda request, timeout: next(responses)
            ).analyze_dataset_with_code({"dataset": "demo"}, Executor())

        self.assertEqual(result["summary"], "recovered")
        self.assertEqual(len(executions), 1)
