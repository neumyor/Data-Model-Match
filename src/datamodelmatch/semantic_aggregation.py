"""Conservative aggregation of validated sample-level visual observations."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Iterable, Mapping, Optional, Sequence

from .semantic_vision import VisualObservation


@dataclass(frozen=True)
class ValueDistribution:
    value: str
    observation_count: int
    eligible_observation_count: int
    proportion: float
    is_dominant: bool
    evidence_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "value": self.value,
            "observationCount": self.observation_count,
            "eligibleObservationCount": self.eligible_observation_count,
            "proportion": self.proportion,
            "isDominant": self.is_dominant,
            "evidenceRefs": list(self.evidence_refs),
        }


@dataclass(frozen=True)
class AggregationResult:
    id: str
    field: str
    status: str
    distributions: tuple[ValueDistribution, ...]
    unknown_reason: Optional[str]
    aggregation_ref: str
    coverage: float
    candidate_count: int
    selected_count: int
    completed_count: int
    failed_count: int
    evidence_refs: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        result = {
            "id": self.id,
            "field": self.field,
            "status": self.status,
            "distributions": [item.to_dict() for item in self.distributions],
            "aggregationRef": self.aggregation_ref,
            "coverage": self.coverage,
            "candidateCount": self.candidate_count,
            "selectedCount": self.selected_count,
            "completedCount": self.completed_count,
            "failedCount": self.failed_count,
            "evidenceRefs": list(self.evidence_refs),
        }
        if self.unknown_reason:
            result["unknownReason"] = self.unknown_reason
        return result


class AggregationError(ValueError):
    pass


FIELDS = {
    "objectCategories": "object_categories",
    "environments": "environments",
    "viewpoints": "viewpoints",
    "targetScale": "target_scale",
    "objectDensity": "object_density",
    "occlusion": "occlusion",
    "illumination": "illumination",
    "cameraMotion": "camera_motion",
    "targetMotion": "target_motion",
}


def aggregate_field(
    observations: Sequence[VisualObservation],
    field: str,
    candidate_count: int,
    selected_count: int,
    aggregation_id: Optional[str] = None,
) -> AggregationResult:
    if field not in FIELDS:
        raise AggregationError("field is not a frozen visual observation field")
    if candidate_count < 0 or selected_count < 0 or selected_count > candidate_count:
        raise AggregationError("sampling counts are invalid")
    if len({item.id for item in observations}) != len(observations):
        raise AggregationError("observation IDs must be unique")
    completed = [item for item in observations if item.status == "COMPLETED"]
    failed = [item for item in observations if item.status != "COMPLETED"]
    if any(item.status not in {"COMPLETED", "FAILED", "UNSUPPORTED", "CANCELLED"} for item in observations):
        raise AggregationError("observation status is not frozen")
    if any(not item.evidence_refs for item in observations):
        raise AggregationError("every observation requires evidence")
    coverage = selected_count / candidate_count if candidate_count else 0.0
    ref = aggregation_id or "aggregation_" + hashlib.sha256(
        f"{field}|{candidate_count}|{selected_count}|{','.join(item.id for item in observations)}".encode()
    ).hexdigest()[:16]
    evidence_refs = tuple(sorted({ref for item in observations for ref in item.evidence_refs}))
    if not completed:
        return AggregationResult(
            ref, field, "UNKNOWN", tuple(), "NO_EVIDENCE", ref, coverage,
            candidate_count, selected_count, 0, len(failed), evidence_refs,
        )
    counts: dict[str, int] = {}
    value_refs: dict[str, set[str]] = {}
    for observation in completed:
        values = getattr(observation, FIELDS[field])
        if isinstance(values, str):
            values = (values,)
        for value in values:
            if value == "UNKNOWN":
                continue
            counts[value] = counts.get(value, 0) + 1
            value_refs.setdefault(value, set()).update(observation.evidence_refs)
    eligible = len(completed)
    if not counts:
        return AggregationResult(
            ref, field, "UNKNOWN", tuple(), "NO_EVIDENCE", ref, coverage,
            candidate_count, selected_count, eligible, len(failed), evidence_refs,
        )
    maximum = max(counts.values())
    dominant = {value for value, count in counts.items() if count == maximum}
    distributions = tuple(
        ValueDistribution(
            value,
            count,
            eligible,
            count / eligible,
            value in dominant,
            tuple(sorted(value_refs[value])),
        )
        for value, count in sorted(counts.items())
    )
    if len(dominant) > 1 and maximum / eligible >= 0.4:
        status = "UNKNOWN"
        reason = "CONFLICTING_EVIDENCE"
    elif maximum >= 3 and maximum / eligible >= 0.60 and coverage >= 0.60:
        status = "SUPPORTED"
        reason = None
    else:
        status = "OBSERVED"
        reason = None
    return AggregationResult(
        ref, field, status, distributions, reason, ref, coverage,
        candidate_count, selected_count, eligible, len(failed), evidence_refs,
    )


def aggregate_observations(
    observations: Sequence[VisualObservation],
    fields: Iterable[str],
    candidate_count: int,
    selected_count: int,
) -> tuple[AggregationResult, ...]:
    return tuple(
        aggregate_field(observations, field, candidate_count, selected_count)
        for field in fields
    )
