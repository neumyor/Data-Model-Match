"""Configuration loading and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse


class ConfigError(ValueError):
    """Raised when the LLM configuration is missing or invalid."""


@dataclass(frozen=True)
class LLMConfig:
    """Connection settings for an OpenAI-compatible Chat Completions API."""

    endpoint: str
    api_key: str
    model: str
    stream: bool = False


def load_llm_config(path: Path) -> LLMConfig:
    """Load and validate an LLM config from a JSON file."""
    if not path.is_file():
        raise ConfigError(f"LLM config file does not exist: {path}")

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ConfigError(f"LLM config is not valid JSON: {path}") from exc

    if not isinstance(raw, dict):
        raise ConfigError("LLM config must be a JSON object")

    endpoint = _required_string(raw, "endpoint")
    api_key = _required_string(raw, "apiKey")
    model = _required_string(raw, "model")
    parsed_endpoint = urlparse(endpoint)
    if parsed_endpoint.scheme != "https" or not parsed_endpoint.netloc:
        raise ConfigError("LLM endpoint must be an absolute HTTPS URL")

    stream = raw.get("stream", False)
    if not isinstance(stream, bool):
        raise ConfigError("LLM config field 'stream' must be boolean")
    if stream:
        raise ConfigError("streaming responses are not supported by this client")

    return LLMConfig(endpoint=endpoint, api_key=api_key, model=model, stream=stream)


def _required_string(raw: dict[str, object], name: str) -> str:
    value = raw.get(name)
    if not isinstance(value, str) or not value.strip():
        raise ConfigError(f"LLM config field '{name}' must be a non-empty string")
    return value.strip()
