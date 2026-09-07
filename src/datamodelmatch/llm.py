"""OpenAI-compatible LLM transport and response decoding."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from .config import LLMConfig


class LLMError(RuntimeError):
    """Raised when the LLM cannot be called or returns an invalid response."""


@dataclass(frozen=True)
class LLMClient:
    """Small synchronous client for one Chat Completions request."""

    config: LLMConfig
    timeout_seconds: float = 60.0

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        """Request one JSON object and validate the transport response."""
        payload = {
            "model": self.config.model,
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
            with urlopen(request, timeout=self.timeout_seconds) as response:
                raw_response = response.read()
        except HTTPError as exc:
            raise LLMError(f"LLM request failed with HTTP {exc.code}") from exc
        except URLError as exc:
            raise LLMError("LLM request failed due to a network error") from exc
        except TimeoutError as exc:
            raise LLMError("LLM request timed out") from exc

        try:
            envelope = json.loads(raw_response)
            content = envelope["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LLMError("LLM response does not contain choices[0].message.content") from exc

        if not isinstance(content, str) or not content.strip():
            raise LLMError("LLM response content must be a non-empty string")
        return _parse_json_content(content)


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
