"""LLM-powered data model matching."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from .llm import LLMClient, LLMError
from .models import DataModel


class MatchError(ValueError):
    """Raised when the LLM result violates the matching result contract."""


@dataclass(frozen=True)
class FieldMatch:
    """One source-to-target field mapping."""

    source_field: str
    target_field: str
    confidence: float
    reason: str


@dataclass(frozen=True)
class MatchResult:
    """Validated model matching result."""

    matches: tuple[FieldMatch, ...]
    unmatched_source_fields: tuple[str, ...]
    unmatched_target_fields: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        """Serialize the result to a JSON-compatible dictionary."""
        return {
            "matches": [asdict(item) for item in self.matches],
            "unmatched_source_fields": list(self.unmatched_source_fields),
            "unmatched_target_fields": list(self.unmatched_target_fields),
        }


def match_models(
    source_model: DataModel,
    target_model: DataModel,
    client: LLMClient,
) -> MatchResult:
    """Ask the LLM to map source fields to target fields and validate its result."""
    source_payload = [
        {"name": field.name, "type": field.type, "description": field.description}
        for field in source_model.fields
    ]
    target_payload = [
        {"name": field.name, "type": field.type, "description": field.description}
        for field in target_model.fields
    ]
    system_prompt = (
        "You match fields between data models. Return only one valid JSON object with exactly "
        "these keys: matches, unmatched_source_fields, unmatched_target_fields. Each match must "
        "contain source_field, target_field, confidence (number from 0 to 1), and reason. "
        "A field may appear in at most one match. Do not invent field names."
    )
    user_prompt = json.dumps(
        {
            "source_model": source_model.name,
            "source_fields": source_payload,
            "target_model": target_model.name,
            "target_fields": target_payload,
        },
        ensure_ascii=False,
    )
    try:
        raw_result = client.complete_json(system_prompt, user_prompt)
    except LLMError:
        raise
    return _validate_result(raw_result, source_model, target_model)


def _validate_result(
    raw_result: dict[str, Any],
    source_model: DataModel,
    target_model: DataModel,
) -> MatchResult:
    expected_keys = {
        "matches",
        "unmatched_source_fields",
        "unmatched_target_fields",
    }
    if set(raw_result) != expected_keys:
        raise MatchError(f"LLM result must contain exactly: {sorted(expected_keys)}")

    source_names = {field.name for field in source_model.fields}
    target_names = {field.name for field in target_model.fields}
    matches: list[FieldMatch] = []
    matched_sources: set[str] = set()
    matched_targets: set[str] = set()

    raw_matches = raw_result["matches"]
    if not isinstance(raw_matches, list):
        raise MatchError("'matches' must be an array")
    for raw_match in raw_matches:
        if not isinstance(raw_match, dict):
            raise MatchError("Each match must be an object")
        source_field = _required_string(raw_match, "source_field")
        target_field = _required_string(raw_match, "target_field")
        reason = _required_string(raw_match, "reason")
        confidence = raw_match.get("confidence")
        if not isinstance(confidence, (int, float)) or isinstance(confidence, bool):
            raise MatchError("Match confidence must be a number")
        if not 0 <= confidence <= 1:
            raise MatchError("Match confidence must be between 0 and 1")
        if source_field not in source_names or target_field not in target_names:
            raise MatchError("LLM result contains a field not present in the input models")
        if source_field in matched_sources or target_field in matched_targets:
            raise MatchError("A source or target field may only appear in one match")
        matched_sources.add(source_field)
        matched_targets.add(target_field)
        matches.append(FieldMatch(source_field, target_field, float(confidence), reason))

    unmatched_sources = _validate_unmatched(raw_result["unmatched_source_fields"], source_names, matched_sources)
    unmatched_targets = _validate_unmatched(raw_result["unmatched_target_fields"], target_names, matched_targets)
    if set(unmatched_sources) | matched_sources != source_names:
        raise MatchError("Every source field must be matched or listed as unmatched")
    if set(unmatched_targets) | matched_targets != target_names:
        raise MatchError("Every target field must be matched or listed as unmatched")

    return MatchResult(tuple(matches), tuple(unmatched_sources), tuple(unmatched_targets))


def _validate_unmatched(
    value: object,
    all_names: set[str],
    matched_names: set[str],
) -> list[str]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise MatchError("Unmatched fields must be an array of strings")
    names = list(value)
    if len(names) != len(set(names)):
        raise MatchError("Unmatched fields must not contain duplicates")
    if any(name not in all_names or name in matched_names for name in names):
        raise MatchError("Unmatched fields must refer only to unmatched input fields")
    return names


def _required_string(raw: dict[str, Any], name: str) -> str:
    value = raw.get(name)
    if not isinstance(value, str) or not value.strip():
        raise MatchError(f"Match field '{name}' must be a non-empty string")
    return value.strip()
