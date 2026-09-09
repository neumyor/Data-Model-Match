"""LLM-powered matching between versioned data model documents."""

from __future__ import annotations

import json
from typing import Any, Dict, Iterable, Union

from .llm import LLMClient
from .models import DataModel, Entity, Field, ModelDocument
from .results import FieldRef, Match, MatchMeta, MatchResult, ResultValidationError


class MatchError(ValueError):
    """Raised when the LLM result violates the matching contract."""


ModelInput = Union[ModelDocument, DataModel]


def match_models(
    source_model: ModelInput,
    target_model: ModelInput,
    client: LLMClient,
) -> MatchResult:
    """Ask the LLM for field mappings and derive unmatched fields locally."""
    source = _as_document(source_model)
    target = _as_document(target_model)
    source_fields = _field_index(source)
    target_fields = _field_index(target)
    raw_result = client.complete_json(_system_prompt(), _user_prompt(source, target))
    raw_matches = _raw_matches(raw_result)

    matches = tuple(
        _parse_match(raw_match, source_fields, target_fields)
        for raw_match in raw_matches
    )
    matched_sources = {item.source for item in matches}
    matched_targets = {item.target for item in matches}
    unmatched_sources = tuple(
        ref for ref in source_fields if ref not in matched_sources
    )
    unmatched_targets = tuple(
        ref for ref in target_fields if ref not in matched_targets
    )
    try:
        return MatchResult(
            source_model_id=source.id,
            target_model_id=target.id,
            matches=matches,
            unmatched_source_fields=unmatched_sources,
            unmatched_target_fields=unmatched_targets,
            meta=MatchMeta(
                model=client.config.model,
                attempt_count=(
                    client.attempt_count
                    if isinstance(getattr(client, "attempt_count", None), int)
                    else 1
                ),
            ),
        )
    except ResultValidationError as exc:
        raise MatchError(str(exc)) from exc


def _as_document(model: ModelInput) -> ModelDocument:
    if isinstance(model, ModelDocument):
        return model
    if isinstance(model, DataModel):
        entity_id = "legacy"
        fields = tuple(
            Field(
                name=field.name,
                id=field.id,
                data_type=field.data_type,
                nullable=field.nullable,
                description=field.description or f"Legacy field '{field.name}'",
            )
            for field in model.fields
        )
        return ModelDocument(
            version="legacy",
            id=model.name,
            name=model.name,
            entities=(
                Entity(
                    id=entity_id,
                    name=model.name,
                    description=f"Legacy model '{model.name}'",
                    fields=fields,
                ),
            ),
        )
    raise MatchError("Model input must be a ModelDocument or DataModel")


def _field_index(model: ModelDocument) -> Dict[FieldRef, Field]:
    return {
        FieldRef(entity.id, field.id): field
        for entity in model.entities
        for field in entity.fields
    }


def _system_prompt() -> str:
    return (
        "You match fields between two data models. Return only one JSON object with exactly "
        "one key: matches. Each match must contain exactly source, target, kind, confidence, "
        "and reason. source and target must each contain exactly entityId and fieldId. "
        "kind must be exact, semantic, or transform. confidence must be a number from 0 to 1. "
        "A source or target field may appear in at most one match. Do not invent references. "
        "Unmatched fields are calculated by the application and must not be returned."
    )


def _user_prompt(source: ModelDocument, target: ModelDocument) -> str:
    return json.dumps(
        {
            "sourceModel": _document_payload(source),
            "targetModel": _document_payload(target),
        },
        ensure_ascii=False,
    )


def _document_payload(model: ModelDocument) -> Dict[str, Any]:
    return {
        "version": model.version,
        "id": model.id,
        "name": model.name,
        "description": model.description,
        "entities": [
            {
                "id": entity.id,
                "name": entity.name,
                "description": entity.description,
                "fields": [
                    {
                        "id": field.id,
                        "name": field.name,
                        "dataType": field.data_type,
                        "nullable": field.nullable,
                        "description": field.description,
                    }
                    for field in entity.fields
                ],
            }
            for entity in model.entities
        ],
    }


def _raw_matches(raw_result: object) -> Iterable[object]:
    if not isinstance(raw_result, dict) or set(raw_result) != {"matches"}:
        raise MatchError("LLM result must contain exactly the 'matches' key")
    matches = raw_result["matches"]
    if not isinstance(matches, list):
        raise MatchError("LLM result 'matches' must be an array")
    return matches


def _parse_match(
    raw_match: object,
    source_fields: Dict[FieldRef, Field],
    target_fields: Dict[FieldRef, Field],
) -> Match:
    if not isinstance(raw_match, dict):
        raise MatchError("Each LLM match must be an object")
    if set(raw_match) != {"source", "target", "kind", "confidence", "reason"}:
        raise MatchError("Each LLM match must contain exactly five required keys")
    source = _parse_ref(raw_match["source"], "source")
    target = _parse_ref(raw_match["target"], "target")
    if source not in source_fields:
        raise MatchError(f"Unknown source field reference: {source.to_dict()}")
    if target not in target_fields:
        raise MatchError(f"Unknown target field reference: {target.to_dict()}")
    try:
        return Match(
            source=source,
            target=target,
            kind=raw_match["kind"],
            confidence=raw_match["confidence"],
            reason=raw_match["reason"],
        )
    except ResultValidationError as exc:
        raise MatchError(str(exc)) from exc


def _parse_ref(value: object, label: str) -> FieldRef:
    if not isinstance(value, dict) or set(value) != {"entityId", "fieldId"}:
        raise MatchError(f"{label} must contain exactly entityId and fieldId")
    entity_id = value["entityId"]
    field_id = value["fieldId"]
    if not isinstance(entity_id, str) or not entity_id.strip():
        raise MatchError(f"{label}.entityId must be a non-empty string")
    if not isinstance(field_id, str) or not field_id.strip():
        raise MatchError(f"{label}.fieldId must be a non-empty string")
    return FieldRef(entity_id.strip(), field_id.strip())
