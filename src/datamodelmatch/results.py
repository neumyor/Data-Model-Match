"""Domain objects for validated model matching results."""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any, Literal


class ResultValidationError(ValueError):
    """Raised when a matching result does not satisfy its domain contract."""


MatchKind = Literal["exact", "semantic", "transform"]
_MATCH_KINDS = {"exact", "semantic", "transform"}


@dataclass(frozen=True)
class FieldRef:
    """A stable reference to a field within an entity."""

    entity_id: str
    field_id: str

    def __post_init__(self) -> None:
        _required_string(self.entity_id, "entity_id")
        _required_string(self.field_id, "field_id")

    def to_dict(self) -> dict[str, str]:
        return {"entityId": self.entity_id, "fieldId": self.field_id}


@dataclass(frozen=True, init=False)
class Match:
    """A validated source-to-target field match."""

    source: FieldRef
    target: FieldRef
    kind: MatchKind
    confidence: float
    reason: str

    def __init__(
        self,
        source: FieldRef | Mapping[str, Any] | None = None,
        target: FieldRef | Mapping[str, Any] | None = None,
        kind: MatchKind = "exact",
        confidence: float = 0.0,
        reason: str = "",
        *,
        source_entity_id: str | None = None,
        source_field_id: str | None = None,
        target_entity_id: str | None = None,
        target_field_id: str | None = None,
    ) -> None:
        if source is None:
            source = {"entity_id": source_entity_id, "field_id": source_field_id}
        elif source_entity_id is not None or source_field_id is not None:
            raise ResultValidationError("Match source must be supplied only once")
        if target is None:
            target = {"entity_id": target_entity_id, "field_id": target_field_id}
        elif target_entity_id is not None or target_field_id is not None:
            raise ResultValidationError("Match target must be supplied only once")

        object.__setattr__(self, "source", _field_ref(source, "source"))
        object.__setattr__(self, "target", _field_ref(target, "target"))
        object.__setattr__(self, "kind", _kind(kind))
        object.__setattr__(self, "confidence", _confidence(confidence))
        object.__setattr__(self, "reason", _required_string(reason, "reason"))

    def to_dict(self) -> dict[str, Any]:
        return {
            "source": self.source.to_dict(),
            "target": self.target.to_dict(),
            "kind": self.kind,
            "confidence": self.confidence,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class MatchMeta:
    """Metadata describing the model attempt that produced a result."""

    model: str
    attempt_count: int

    def __post_init__(self) -> None:
        _required_string(self.model, "model")
        if (
            not isinstance(self.attempt_count, int)
            or isinstance(self.attempt_count, bool)
            or self.attempt_count < 0
        ):
            raise ResultValidationError("attempt_count must be a non-negative integer")

    def to_dict(self) -> dict[str, Any]:
        return {"model": self.model, "attemptCount": self.attempt_count}


@dataclass(frozen=True)
class MatchResult:
    """A fully local, JSON-compatible matching result."""

    source_model_id: str
    target_model_id: str
    matches: tuple[Match, ...] | Sequence[Match]
    unmatched_source_fields: tuple[FieldRef, ...] | Sequence[FieldRef]
    unmatched_target_fields: tuple[FieldRef, ...] | Sequence[FieldRef]
    meta: MatchMeta | Mapping[str, Any]

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "source_model_id", _required_string(self.source_model_id, "source_model_id")
        )
        object.__setattr__(
            self, "target_model_id", _required_string(self.target_model_id, "target_model_id")
        )
        matches = tuple(_match(item) for item in _sequence(self.matches, "matches"))
        source_unmatched = tuple(
            _field_ref(item, "unmatched_source_fields")
            for item in _sequence(self.unmatched_source_fields, "unmatched_source_fields")
        )
        target_unmatched = tuple(
            _field_ref(item, "unmatched_target_fields")
            for item in _sequence(self.unmatched_target_fields, "unmatched_target_fields")
        )
        _ensure_unique((item.source for item in matches), "source match endpoints")
        _ensure_unique((item.target for item in matches), "target match endpoints")
        _ensure_unique(source_unmatched, "unmatched source fields")
        _ensure_unique(target_unmatched, "unmatched target fields")
        if set(source_unmatched) & {item.source for item in matches}:
            raise ResultValidationError("A source field cannot be both matched and unmatched")
        if set(target_unmatched) & {item.target for item in matches}:
            raise ResultValidationError("A target field cannot be both matched and unmatched")

        object.__setattr__(self, "matches", matches)
        object.__setattr__(self, "unmatched_source_fields", source_unmatched)
        object.__setattr__(self, "unmatched_target_fields", target_unmatched)
        object.__setattr__(self, "meta", _meta(self.meta))

    def to_dict(self) -> dict[str, Any]:
        """Serialize this result using the design document's field names."""
        return {
            "sourceModelId": self.source_model_id,
            "targetModelId": self.target_model_id,
            "matches": [item.to_dict() for item in self.matches],
            "unmatchedSourceFields": [item.to_dict() for item in self.unmatched_source_fields],
            "unmatchedTargetFields": [item.to_dict() for item in self.unmatched_target_fields],
            "meta": self.meta.to_dict(),
        }


def _field_ref(value: object, name: str) -> FieldRef:
    if isinstance(value, FieldRef):
        return value
    if not isinstance(value, Mapping):
        raise ResultValidationError(f"{name} must be a FieldRef or object")
    entity_id = value.get("entity_id", value.get("entityId"))
    field_id = value.get("field_id", value.get("fieldId"))
    return FieldRef(
        _required_string(entity_id, f"{name}.entity_id"),
        _required_string(field_id, f"{name}.field_id"),
    )


def _match(value: object) -> Match:
    if isinstance(value, Match):
        return value
    if not isinstance(value, Mapping):
        raise ResultValidationError("matches must contain Match objects or objects")
    return Match(
        source=value.get("source"),
        target=value.get("target"),
        kind=value.get("kind", "exact"),
        confidence=value.get("confidence"),
        reason=value.get("reason"),
        source_entity_id=value.get("sourceEntityId", value.get("source_entity_id")),
        source_field_id=value.get("sourceFieldId", value.get("source_field_id")),
        target_entity_id=value.get("targetEntityId", value.get("target_entity_id")),
        target_field_id=value.get("targetFieldId", value.get("target_field_id")),
    )


def _meta(value: object) -> MatchMeta:
    if isinstance(value, MatchMeta):
        return value
    if not isinstance(value, Mapping):
        raise ResultValidationError("meta must be a MatchMeta or object")
    return MatchMeta(
        model=_required_string(value.get("model"), "meta.model"),
        attempt_count=value.get("attempt_count", value.get("attemptCount")),
    )


def _sequence(value: object, name: str) -> Sequence[object]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise ResultValidationError(f"{name} must be an array")
    return value


def _required_string(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResultValidationError(f"{name} must be a non-empty string")
    return value.strip()


def _kind(value: object) -> MatchKind:
    if value not in _MATCH_KINDS:
        raise ResultValidationError("kind must be one of: exact, semantic, transform")
    return value  # type: ignore[return-value]


def _confidence(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ResultValidationError("confidence must be a number")
    if not math.isfinite(value) or not 0 <= value <= 1:
        raise ResultValidationError("confidence must be a finite number between 0 and 1")
    return float(value)


def _ensure_unique(values: Sequence[object], name: str) -> None:
    values = tuple(values)
    if len(values) != len(set(values)):
        raise ResultValidationError(f"{name} must not contain duplicates")
