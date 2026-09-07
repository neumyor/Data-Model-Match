"""Data model loading, normalization, and versioned document validation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional, Tuple


class ModelError(ValueError):
    """Raised when a data model cannot be normalized."""


@dataclass(frozen=True, init=False)
class Field:
    """A field in either a legacy model or a versioned entity.

    ``type`` remains available for the legacy matcher. New callers should use
    ``data_type`` (or the ``dataType`` read-only alias) and provide an explicit
    ``id`` when constructing fields for a versioned document.
    """

    id: str
    name: str
    data_type: str
    nullable: bool
    description: str

    def __init__(
        self,
        name: str,
        type: Optional[str] = None,
        description: str = "",
        *,
        id: Optional[str] = None,
        data_type: Optional[str] = None,
        dataType: Optional[str] = None,
        nullable: bool = True,
    ) -> None:
        supplied_types = [value for value in (type, data_type, dataType) if value is not None]
        if len(set(supplied_types)) > 1:
            raise ModelError("Field type, data_type, and dataType must match when jointly provided")

        field_id = name if id is None else id
        resolved_type = data_type if data_type is not None else dataType
        if resolved_type is None:
            resolved_type = type
        object.__setattr__(self, "id", _non_empty_string(field_id, "Field id"))
        object.__setattr__(self, "name", _non_empty_string(name, "Field name"))
        object.__setattr__(self, "data_type", _non_empty_string(resolved_type, "Field data type"))
        if not isinstance(nullable, bool):
            raise ModelError("Field nullable must be a boolean")
        if not isinstance(description, str):
            raise ModelError("Field description must be a string")
        object.__setattr__(self, "nullable", nullable)
        object.__setattr__(self, "description", description.strip())

    @property
    def type(self) -> str:
        """Legacy alias for ``data_type``."""
        return self.data_type

    @property
    def dataType(self) -> str:
        """JSON document alias for ``data_type``."""
        return self.data_type


@dataclass(frozen=True)
class Entity:
    """A named entity in a versioned model document."""

    id: str
    name: str
    description: str
    fields: Tuple[Field, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "id", _non_empty_string(self.id, "Entity id"))
        object.__setattr__(self, "name", _non_empty_string(self.name, "Entity name"))
        object.__setattr__(self, "description", _non_empty_string(self.description, "Entity description"))
        fields = _non_empty_tuple(self.fields, "Entity fields")
        if not all(isinstance(field, Field) for field in fields):
            raise ModelError("Entity fields must contain Field values")
        if any(not field.description.strip() for field in fields):
            raise ModelError("Field description must be a non-empty string")
        _ensure_unique_ids(fields, "Field")
        object.__setattr__(self, "fields", fields)


@dataclass(frozen=True)
class ModelDocument:
    """A versioned, multi-entity data model document."""

    version: str
    id: str
    name: str
    entities: Tuple[Entity, ...]
    description: str = ""

    def __post_init__(self) -> None:
        object.__setattr__(self, "version", _model_version(self.version))
        object.__setattr__(self, "id", _non_empty_string(self.id, "Model document id"))
        object.__setattr__(self, "name", _non_empty_string(self.name, "Model document name"))
        if not isinstance(self.description, str):
            raise ModelError("Model document description must be a string")
        object.__setattr__(self, "description", self.description.strip())
        entities = _non_empty_tuple(self.entities, "Model document entities")
        if not all(isinstance(entity, Entity) for entity in entities):
            raise ModelError("Model document entities must contain Entity values")
        _ensure_unique_ids(entities, "Entity")
        object.__setattr__(self, "entities", entities)


@dataclass(frozen=True)
class DataModel:
    """A normalized legacy data model used by the matcher."""

    name: str
    fields: Tuple[Field, ...]


def load_model(path: Path) -> DataModel:
    """Load a legacy JSON Schema object or JSON object sample from disk.

    Use :func:`load_model_document` to load the versioned multi-entity format.
    """
    raw = _load_json_object(path)
    return _legacy_model_from_raw(raw, path)


def load_model_document(path: Path) -> ModelDocument:
    """Load a versioned document or normalize a legacy model into one.

    An object containing ``entities`` is interpreted as a versioned document
    and must satisfy its complete schema. Other supported legacy inputs are
    normalized into one entity using the file stem for identifiers.
    """
    raw = _load_json_object(path)
    if "entities" in raw:
        return _document_from_raw(raw)

    legacy_model = _legacy_model_from_raw(raw, path)
    fields = tuple(
        Field(
            field.name,
            data_type=field.data_type,
            id=field.id,
            nullable=field.nullable,
            description=field.description or f"Legacy field '{field.name}'",
        )
        for field in legacy_model.fields
    )
    entity_id = _path_identifier(path)
    return ModelDocument(
        version="legacy",
        id=entity_id,
        name=legacy_model.name,
        entities=(
            Entity(
                id=entity_id,
                name=legacy_model.name,
                description=f"Legacy model loaded from '{path.name}'",
                fields=fields,
            ),
        ),
        description=f"Legacy model loaded from '{path.name}'",
    )


def _load_json_object(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise ModelError(f"Model file does not exist: {path}")

    try:
        raw: Any = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ModelError(f"Model file is not valid JSON: {path}") from exc

    if not isinstance(raw, dict):
        raise ModelError("Model must be a JSON object")
    return raw


def _legacy_model_from_raw(raw: dict[str, Any], path: Path) -> DataModel:
    name = path.stem
    properties = raw.get("properties")
    if properties is not None:
        if not isinstance(properties, dict):
            raise ModelError("Model field 'properties' must be an object")
        fields = tuple(_field_from_schema(field_name, definition) for field_name, definition in properties.items())
    else:
        fields = tuple(
            Field(name=field_name, data_type=_infer_type(value))
            for field_name, value in raw.items()
        )

    if not fields:
        raise ModelError(f"Model contains no fields: {path}")
    return DataModel(name=name, fields=fields)


def _document_from_raw(raw: dict[str, Any]) -> ModelDocument:
    return ModelDocument(
        version=_version(raw.get("version")),
        id=_required_string(raw, "id", "Model document"),
        name=_required_string(raw, "name", "Model document"),
        entities=tuple(
            _entity_from_raw(entity, index)
            for index, entity in enumerate(_required_non_empty_list(raw, "entities", "Model document"))
        ),
        description=_optional_string(raw.get("description", ""), "Model document description"),
    )


def _entity_from_raw(raw: object, index: int) -> Entity:
    if not isinstance(raw, dict):
        raise ModelError(f"Entity at index {index} must be an object")
    return Entity(
        id=_required_string(raw, "id", f"Entity at index {index}"),
        name=_required_string(raw, "name", f"Entity at index {index}"),
        description=_required_string(raw, "description", f"Entity at index {index}"),
        fields=tuple(
            _versioned_field_from_raw(field, index, field_index)
            for field_index, field in enumerate(
                _required_non_empty_list(raw, "fields", f"Entity at index {index}")
            )
        ),
    )


def _versioned_field_from_raw(raw: object, entity_index: int, field_index: int) -> Field:
    location = f"Field at entity index {entity_index}, field index {field_index}"
    if not isinstance(raw, dict):
        raise ModelError(f"{location} must be an object")
    nullable = raw.get("nullable")
    if not isinstance(nullable, bool):
        raise ModelError(f"{location} field 'nullable' must be a boolean")
    return Field(
        name=_required_string(raw, "name", location),
        id=_required_string(raw, "id", location),
        data_type=_required_string(raw, "dataType", location),
        nullable=nullable,
        description=_required_string(raw, "description", location),
    )


def _field_from_schema(name: object, definition: object) -> Field:
    field_name = _non_empty_string(name, "Model property name")
    if not isinstance(definition, dict):
        raise ModelError(f"Schema for field '{field_name}' must be an object")
    field_type = definition.get("type", "unknown")
    description = definition.get("description", "")
    return Field(
        field_name,
        data_type=_non_empty_string(field_type, f"Schema type for field '{field_name}'"),
        description=description,
    )


def _required_string(raw: dict[str, Any], key: str, context: str) -> str:
    if key not in raw:
        raise ModelError(f"{context} is missing required field '{key}'")
    return _non_empty_string(raw[key], f"{context} field '{key}'")


def _version(value: object) -> str:
    if isinstance(value, bool):
        raise ModelError("Model document version must be 1")
    if isinstance(value, int):
        if value != 1:
            raise ModelError("Model document version must be 1")
        return "1"
    if isinstance(value, str) and value.strip() == "1":
        return "1"
    raise ModelError("Model document version must be 1")


def _model_version(value: object) -> str:
    if value == "legacy":
        return "legacy"
    return _version(value)


def _optional_string(value: object, label: str) -> str:
    if not isinstance(value, str):
        raise ModelError(f"{label} must be a string")
    return value.strip()


def _required_non_empty_list(raw: dict[str, Any], key: str, context: str) -> list[Any]:
    if key not in raw:
        raise ModelError(f"{context} is missing required field '{key}'")
    value = raw[key]
    if not isinstance(value, list) or not value:
        raise ModelError(f"{context} field '{key}' must be a non-empty array")
    return value


def _non_empty_string(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ModelError(f"{label} must be a non-empty string")
    return value.strip()


def _non_empty_tuple(value: object, label: str) -> Tuple[Any, ...]:
    if not isinstance(value, tuple) or not value:
        raise ModelError(f"{label} must be a non-empty tuple")
    return value


def _ensure_unique_ids(values: Tuple[Any, ...], item_type: str) -> None:
    ids = [value.id for value in values]
    if len(ids) != len(set(ids)):
        raise ModelError(f"{item_type} ids must be unique within their scope")


def _path_identifier(path: Path) -> str:
    return _non_empty_string(path.stem, "Model file name")


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
