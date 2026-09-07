"""Data model loading and normalization."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


class ModelError(ValueError):
    """Raised when a data model cannot be normalized."""


@dataclass(frozen=True)
class Field:
    """A model field with its name, type and optional description."""

    name: str
    type: str
    description: str = ""


@dataclass(frozen=True)
class DataModel:
    """A normalized data model used by the matcher."""

    name: str
    fields: tuple[Field, ...]


def load_model(path: Path) -> DataModel:
    """Load a JSON Schema object or a JSON object sample from disk."""
    if not path.is_file():
        raise ModelError(f"Model file does not exist: {path}")

    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ModelError(f"Model file is not valid JSON: {path}") from exc

    if not isinstance(raw, dict):
        raise ModelError("Model must be a JSON object")

    name = path.stem
    properties = raw.get("properties")
    if properties is not None:
        if not isinstance(properties, dict):
            raise ModelError("Model field 'properties' must be an object")
        fields = tuple(_field_from_schema(field_name, definition) for field_name, definition in properties.items())
    else:
        fields = tuple(
            Field(name=field_name, type=_infer_type(value))
            for field_name, value in raw.items()
        )

    if not fields:
        raise ModelError(f"Model contains no fields: {path}")
    return DataModel(name=name, fields=fields)


def _field_from_schema(name: object, definition: object) -> Field:
    if not isinstance(name, str) or not name.strip():
        raise ModelError("Model property names must be non-empty strings")
    if not isinstance(definition, dict):
        raise ModelError(f"Schema for field '{name}' must be an object")
    field_type = definition.get("type", "unknown")
    if not isinstance(field_type, str) or not field_type.strip():
        raise ModelError(f"Schema type for field '{name}' must be a non-empty string")
    description = definition.get("description", "")
    if not isinstance(description, str):
        raise ModelError(f"Schema description for field '{name}' must be a string")
    return Field(name=name, type=field_type.strip(), description=description.strip())


def _infer_type(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return "unknown"
