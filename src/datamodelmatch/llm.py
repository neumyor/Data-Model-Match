"""OpenAI-compatible LLM transport and response decoding."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit, urlunsplit
from urllib.request import Request, urlopen

from .config import LLMConfig


class LLMError(RuntimeError):
    """Raised when the LLM cannot be called or returns an invalid response."""


@dataclass
class LLMClient:
    """Synchronous Chat Completions client with explicit deployment failover."""

    config: LLMConfig
    timeout_seconds: float = 60.0
    last_model: str = field(init=False, default="")
    attempt_count: int = field(init=False, default=0)
    _candidate_cache: tuple[str, ...] | None = field(init=False, default=None, repr=False)
    _rejected_models: set[str] = field(init=False, default_factory=set, repr=False)

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """Request one JSON object and validate the transport response."""
        deadline = time.monotonic() + self.timeout_seconds
        candidates = self._model_candidates(deadline)
        errors: list[str] = []
        self.last_model = ""
        self.attempt_count = 0
        for model in candidates:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break
            self.attempt_count += 1
            try:
                result = self._complete_with_model(
                    model,
                    system_prompt,
                    user_prompt,
                    min(30.0, remaining),
                )
                self.last_model = model
                return result
            except LLMError as exc:
                errors.append(f"{model}: {exc}")
                self._rejected_models.add(model)
        detail = errors[-1] if errors else "request timeout exhausted"
        raise LLMError(
            f"LLM request failed after {self.attempt_count} attempt(s): {detail}"
        )

    def _complete_with_model(
        self,
        model: str,
        system_prompt: str,
        user_prompt: str,
        timeout_seconds: float,
    ) -> dict[str, Any]:
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": self.config.stream,
            "temperature": 0,
        }
        request = Request(
            self.config.endpoint,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            },
            method="POST",
        )
        try:
            with urlopen(request, timeout=timeout_seconds) as response:
                raw_response = response.read()
        except HTTPError as exc:
            raise LLMError(f"LLM request failed with HTTP {exc.code}") from exc
        except URLError as exc:
            raise LLMError("LLM request failed due to a network error") from exc
        except TimeoutError as exc:
            raise LLMError("LLM request timed out") from exc
        except OSError as exc:
            raise LLMError("LLM response body could not be read") from exc

        try:
            envelope = json.loads(raw_response)
            content = envelope["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LLMError("LLM response does not contain choices[0].message.content") from exc

        if not isinstance(content, str) or not content.strip():
            raise LLMError("LLM response content must be a non-empty string")
        return _parse_json_content(content)

    def _model_candidates(self, deadline: float) -> tuple[str, ...]:
        if self._candidate_cache is not None:
            return tuple(
                model for model in self._candidate_cache
                if model not in self._rejected_models
            )
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            return (self.config.model,)
        deployments = self._discover_deployments(min(5.0, remaining))
        self._candidate_cache = tuple(dict.fromkeys([*deployments, self.config.model]))
        return tuple(
            model for model in self._candidate_cache
            if model not in self._rejected_models
        )

    def reject_last_model(self) -> None:
        """Exclude the last successful deployment after application-level rejection."""
        if self.last_model:
            self._rejected_models.add(self.last_model)

    def _discover_deployments(self, timeout_seconds: float) -> list[str]:
        models_endpoint = _models_endpoint(self.config.endpoint)
        if models_endpoint is None:
            return []
        deadline = time.monotonic() + timeout_seconds
        configured = self.config.model.lower()
        for page_number in range(1, 6):
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return []
            request = Request(
                f"{models_endpoint}?pageNum={page_number}&pageSize=100",
                headers={"Authorization": f"Bearer {self.config.api_key}"},
                method="GET",
            )
            try:
                with urlopen(request, timeout=remaining) as response:
                    envelope = json.loads(response.read())
            except (HTTPError, URLError, TimeoutError, OSError, json.JSONDecodeError):
                return []
            rows = envelope.get("data") if isinstance(envelope, dict) else None
            if not isinstance(rows, list):
                continue
            deployments: list[str] = []
            for row in rows:
                if not isinstance(row, dict):
                    continue
                deployment_id = row.get("id")
                names = (row.get("modelName"), row.get("root"), row.get("title"))
                if (
                    not isinstance(deployment_id, str)
                    or not deployment_id.strip()
                    or not any(
                        isinstance(name, str) and name.lower() == configured
                        for name in names
                    )
                    or row.get("status") not in (None, "START")
                    or not _supports_openai_chat(row)
                ):
                    continue
                deployments.append(deployment_id.strip())
            if deployments:
                return deployments
        return []


def _models_endpoint(chat_endpoint: str) -> str | None:
    parsed = urlsplit(chat_endpoint)
    suffix = "/chat/completions"
    if not parsed.path.endswith(suffix):
        return None
    path = parsed.path[: -len(suffix)] + "/models"
    return urlunsplit((parsed.scheme, parsed.netloc, path, "", ""))


def _supports_openai_chat(row: dict[str, Any]) -> bool:
    protocols = row.get("supported_protocols")
    if protocols is None:
        return True
    if not isinstance(protocols, list):
        return False
    return any(
        isinstance(protocol, dict)
        and (
            protocol.get("code") == "OPENAI_HTTP"
            or protocol.get("endpoint") == "/v1/chat/completions"
        )
        for protocol in protocols
    )


def _parse_json_content(content: str) -> dict[str, Any]:
    text = content.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        text = "\n".join(lines[1:-1]).strip()
        if text.lower().startswith("json\n"):
            text = text[5:].strip()
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError as exc:
        raise LLMError("LLM response content is not valid JSON") from exc
    if not isinstance(parsed, dict):
        raise LLMError("LLM response JSON must be an object")
    return parsed
