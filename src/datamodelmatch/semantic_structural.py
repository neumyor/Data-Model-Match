"""Bounded structural semantic analysis over WP2 deterministic evidence.

This module intentionally has no persistence or HTTP dependency.  It accepts
only a survey, inspection facts, and pre-bounded documentation excerpts.  The
LLM may classify that supplied evidence and request a small number of approved
additional inspections, but it never receives raw files or determines facts.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal, Mapping, Optional, Protocol, Sequence, Tuple, Union

from .config import ConfigError, load_llm_config
from .llm import LLMClient, LLMError
from .semantic_inspection import (
    DelimitedTableInspectionFact,
    ImageInspectionFact,
    InspectionFact,
    InspectionResult,
    JsonInspectionFact,
    ParquetInspectionFact,
    XmlInspectionFact,
)
from .semantic_survey import DatasetSketch


TaskFamily = Literal[
    "image_classification",
    "object_detection",
    "multi_object_tracking",
    "semantic_segmentation",
    "instance_segmentation",
    "pose_keypoints",
    "action_video_understanding",
    "video_anomaly_detection",
    "reid_retrieval",
]
Modality = Literal["RGB", "infrared", "depth", "thermal", "multimodal"]
SampleOrganization = Literal["independent_image", "image_sequence", "video", "mixed", "UNKNOWN"]
TemporalStructure = Literal["none", "sequence", "video", "mixed", "UNKNOWN"]
Supervision = Literal[
    "class_label",
    "bbox",
    "track",
    "semantic_mask",
    "instance_mask",
    "keypoints",
    "action_label",
    "temporal_segment",
    "anomaly_label",
    "identity",
    "pair_ranking",
]
ResourceRole = Literal["media", "annotation", "metadata", "documentation", "split_definition"]
ResourceRelation = Literal[
    "image_to_annotation",
    "frame_to_track",
    "video_to_clip_label",
    "identity_to_camera",
    "UNKNOWN",
]
ClaimStatus = Literal["VERIFIED", "UNKNOWN"]
UnknownReason = Literal[
    "NO_EVIDENCE",
    "INSUFFICIENT_SAMPLE_COVERAGE",
    "UNSUPPORTED_MEDIA",
    "MODEL_FAILURE",
    "CONFLICTING_EVIDENCE",
    "INSPECTION_LIMIT",
    "ACCESS_DENIED",
    "CANCELLED",
]
AnalysisStatus = Literal["COMPLETED", "FAILED"]

_TASKS = frozenset(TaskFamily.__args__)
_MODALITIES = frozenset(Modality.__args__)
_ORGANIZATIONS = frozenset(SampleOrganization.__args__)
_TEMPORAL = frozenset(TemporalStructure.__args__)
_SUPERVISION = frozenset(Supervision.__args__)
_ROLES = frozenset(ResourceRole.__args__)
_RELATIONS = frozenset(ResourceRelation.__args__)
_UNKNOWN_REASONS = frozenset(UnknownReason.__args__)
_FIELDS = (
    "tasks",
    "modalities",
    "sampleOrganization",
    "temporalStructure",
    "supervision",
    "annotationSemantics",
    "resourceRoles",
    "resourceRelations",
)
_SENSITIVE_PATTERN = re.compile(
    r"(?i)(authorization\s*:\s*bearer\s+|api[_ -]?key\s*[=:]\s*|sk-[A-Za-z0-9_-]{8,})[^\s\"']+"
)
_SAFE_PATH = re.compile(r"^(?!/)(?!.*(?:^|/)\.\.(?:/|$))[A-Za-z0-9._/-]{1,4096}$")


class StructuralAnalysisError(ValueError):
    """Raised when callers provide inputs outside the structural contract."""


class StructuralResponseError(StructuralAnalysisError):
    """Raised when a model result violates the closed structural protocol."""


class StructuralInspectionExecutor(Protocol):
    """Executes one approved, fact-only inspection against a fixed snapshot."""

    def __call__(self, path: str) -> InspectionResult:
        """Return a WP2 inspection fact for one safe relative path."""


class StructuralLLM(Protocol):
    """The narrow LLM surface used by this module."""

    config: object
    last_model: str
    attempt_count: int

    def complete_json(self, system_prompt: str, user_prompt: str) -> dict[str, object]:
        """Return one parsed JSON object."""


@dataclass(frozen=True)
class DocumentationExcerpt:
    """A redacted, pre-bounded documentation fragment with stable line range."""

    path: str
    line_start: int
    line_end: int
    text: str

    def __post_init__(self) -> None:
        _validate_path(self.path, "documentation path")
        if not isinstance(self.line_start, int) or self.line_start < 1:
            raise StructuralAnalysisError("documentation line_start must be positive")
        if not isinstance(self.line_end, int) or self.line_end < self.line_start:
            raise StructuralAnalysisError("documentation line_end must not precede line_start")
        if not isinstance(self.text, str) or not self.text.strip() or len(self.text) > 12_000:
            raise StructuralAnalysisError("documentation text must be non-empty and at most 12000 characters")

    def redacted(self, maximum: int) -> str:
        return _redact(self.text)[:maximum]


@dataclass(frozen=True)
class StructuralAnalysisLimits:
    """Explicit upper bounds for model-visible evidence and inspection loops."""

    max_documentation_characters: int = 8_000
    max_documentation_excerpts: int = 8
    max_inspection_facts: int = 32
    max_tool_requests: int = 2
    max_model_calls: int = 3

    def __post_init__(self) -> None:
        for name in (
            "max_documentation_characters",
            "max_documentation_excerpts",
            "max_inspection_facts",
            "max_tool_requests",
            "max_model_calls",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise StructuralAnalysisError(f"{name} must be a positive integer")
        if self.max_tool_requests > 4:
            raise StructuralAnalysisError("max_tool_requests must not exceed the frozen budget of four")
        if self.max_model_calls < self.max_tool_requests + 1:
            raise StructuralAnalysisError("max_model_calls must permit one final response after tool requests")


@dataclass(frozen=True)
class StructuralAnalysisInput:
    """Closed inputs to one fixed-revision structural analysis attempt."""

    snapshot_revision: str
    sketch: DatasetSketch
    inspection_facts: Tuple[InspectionResult, ...]
    documentation_excerpts: Tuple[DocumentationExcerpt, ...]
    executor: StructuralInspectionExecutor
    limits: StructuralAnalysisLimits = StructuralAnalysisLimits()

    def __post_init__(self) -> None:
        if not isinstance(self.snapshot_revision, str) or not self.snapshot_revision or len(self.snapshot_revision) > 256:
            raise StructuralAnalysisError("snapshot_revision must be a non-empty string up to 256 characters")
        if not isinstance(self.sketch, DatasetSketch):
            raise StructuralAnalysisError("sketch must be a DatasetSketch")
        if len(self.inspection_facts) > self.limits.max_inspection_facts:
            raise StructuralAnalysisError("inspection facts exceed max_inspection_facts")
        if len(self.documentation_excerpts) > self.limits.max_documentation_excerpts:
            raise StructuralAnalysisError("documentation excerpts exceed max_documentation_excerpts")
        for fact in self.inspection_facts:
            if not isinstance(fact, InspectionFact):
                raise StructuralAnalysisError("inspection_facts must contain only WP2 InspectionFact values")
        for excerpt in self.documentation_excerpts:
            if not isinstance(excerpt, DocumentationExcerpt):
                raise StructuralAnalysisError("documentation_excerpts must be DocumentationExcerpt values")
        if not callable(self.executor):
            raise StructuralAnalysisError("executor must be callable")


@dataclass(frozen=True)
class StructuralSemanticsCandidate:
    """Closed structural fields that can later be fused into a profile."""

    tasks: Tuple[TaskFamily, ...]
    modalities: Tuple[Modality, ...]
    sample_organization: SampleOrganization
    temporal_structure: TemporalStructure
    supervision: Tuple[Supervision, ...]
    annotation_semantics: Tuple[str, ...]
    resource_roles: Tuple[ResourceRole, ...]
    resource_relations: Tuple[ResourceRelation, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "tasks": list(self.tasks),
            "modalities": list(self.modalities),
            "sampleOrganization": self.sample_organization,
            "temporalStructure": self.temporal_structure,
            "supervision": list(self.supervision),
            "annotationSemantics": list(self.annotation_semantics),
            "resourceRoles": list(self.resource_roles),
            "resourceRelations": list(self.resource_relations),
        }


@dataclass(frozen=True)
class StructuralEvidence:
    """Closed evidence projection compatible with the frozen Evidence contract."""

    id: str
    kind: Literal["README", "inspection", "LLM"]
    source_ref: str
    locator: Tuple[Tuple[str, object], ...]
    summary: str
    snapshot_revision: str

    def to_dict(self) -> dict[str, object]:
        return {
            "id": self.id,
            "kind": self.kind,
            "sourceRef": self.source_ref,
            "locator": dict(self.locator),
            "stage": "structural",
            "summary": self.summary,
            "snapshotRevision": self.snapshot_revision,
        }


@dataclass(frozen=True)
class StructuralClaim:
    """A closed structural claim with explicit evidence status."""

    id: str
    field: str
    value: Tuple[str, ...]
    status: ClaimStatus
    evidence_refs: Tuple[str, ...]
    unknown_reason: Optional[UnknownReason] = None
    conflict_refs: Tuple[str, ...] = ()

    def to_dict(self) -> dict[str, object]:
        result: dict[str, object] = {
            "id": self.id,
            "field": self.field,
            "scope": "structural",
            "status": self.status,
            "evidenceRefs": list(self.evidence_refs),
        }
        if self.status == "UNKNOWN":
            result["unknownReason"] = self.unknown_reason
            if self.conflict_refs:
                result["conflictRefs"] = list(self.conflict_refs)
        else:
            result["value"] = list(self.value) if len(self.value) != 1 else self.value[0]
        return result


@dataclass(frozen=True)
class StructuralUnresolvedField:
    """A frozen unresolved-field projection for later profile fusion."""

    field: str
    reason: UnknownReason
    attempted_evidence_refs: Tuple[str, ...]
    next_action: Literal["inspect_metadata", "inspect_annotation", "unsupported"]

    def to_dict(self) -> dict[str, object]:
        return {
            "field": self.field,
            "reason": self.reason,
            "attemptedEvidenceRefs": list(self.attempted_evidence_refs),
            "nextAction": self.next_action,
        }


@dataclass(frozen=True)
class StructuralInspectionRequest:
    """One accepted finite inspection request."""

    path: str

    def to_dict(self) -> dict[str, str]:
        return {"action": "inspect_file", "path": self.path}


@dataclass(frozen=True)
class StructuralAnalysisResult:
    """Non-persistent structural analysis artifact."""

    status: AnalysisStatus
    candidate: Optional[StructuralSemanticsCandidate]
    claims: Tuple[StructuralClaim, ...]
    evidence: Tuple[StructuralEvidence, ...]
    unresolved: Tuple[StructuralUnresolvedField, ...]
    inspection_requests: Tuple[StructuralInspectionRequest, ...]
    warnings: Tuple[str, ...]
    model: str
    deployment: str
    model_call_count: int

    def __post_init__(self) -> None:
        if self.status == "COMPLETED" and self.candidate is None:
            raise StructuralAnalysisError("completed result requires a structural candidate")
        if self.status == "FAILED" and (self.candidate is not None or self.claims):
            raise StructuralAnalysisError("failed result must not expose a partial structural candidate")


def analyze_structural_semantics(
    value: StructuralAnalysisInput,
    client: StructuralLLM,
) -> StructuralAnalysisResult:
    """Run a finite, redacted structural LLM loop over fact-only inputs."""

    if not isinstance(client, object) or not callable(getattr(client, "complete_json", None)):
        raise StructuralAnalysisError("client must provide complete_json")
    facts = list(value.inspection_facts)
    requests: list[StructuralInspectionRequest] = []
    model_calls = 0
    evidence = _build_evidence(value.snapshot_revision, facts, value.documentation_excerpts)
    allowed_paths = _allowed_inspection_paths(value.sketch)

    for _ in range(value.limits.max_model_calls):
        model_calls += 1
        try:
            response = client.complete_json(_system_prompt(), _user_prompt(value, facts, evidence))
        except (LLMError, OSError, TimeoutError, ValueError) as exc:
            return _failed_result(
                "model request failed: " + _safe_error_label(exc),
                _model_name(client),
                _deployment_name(client),
                model_calls,
            )
        try:
            action = _parse_action(response)
            if action == "inspect":
                request = _parse_inspection_request(response, allowed_paths)
                if len(requests) >= value.limits.max_tool_requests:
                    return _failed_result(
                        "model requested inspection beyond the approved budget",
                        _model_name(client),
                        _deployment_name(client),
                        model_calls,
                    )
                requests.append(request)
                try:
                    fact = value.executor(request.path)
                except (OSError, ValueError, StructuralAnalysisError) as exc:
                    return _failed_result(
                        "approved inspection failed: " + _safe_error_label(exc),
                        _model_name(client),
                        _deployment_name(client),
                        model_calls,
                    )
                if not isinstance(fact, InspectionFact) or fact.path != request.path:
                    return _failed_result(
                        "inspection executor returned an invalid fact",
                        _model_name(client),
                        _deployment_name(client),
                        model_calls,
                    )
                facts.append(fact)
                evidence = _build_evidence(value.snapshot_revision, facts, value.documentation_excerpts)
                continue
            candidate, references = _parse_final_response(response, evidence)
            deterministic = _deterministic_candidate(value.sketch, facts)
            conflict_fields = _conflicting_fields(candidate, deterministic)
            claims, unresolved = _claims_for_candidate(candidate, references, evidence, conflict_fields)
            if conflict_fields:
                candidate = _with_unknown_conflicts(candidate, conflict_fields)
            return StructuralAnalysisResult(
                status="COMPLETED",
                candidate=candidate,
                claims=tuple(claims),
                evidence=tuple(evidence),
                unresolved=tuple(unresolved),
                inspection_requests=tuple(requests),
                warnings=(
                    "conflicting deterministic and model classifications: " + ", ".join(conflict_fields),
                )
                if conflict_fields
                else tuple(),
                model=_model_name(client),
                deployment=_deployment_name(client),
                model_call_count=model_calls,
            )
        except StructuralResponseError as exc:
            return _failed_result(
                _safe_error_label(exc),
                _model_name(client),
                _deployment_name(client),
                model_calls,
            )
    return _failed_result(
        "model did not return a final response within the approved call budget",
        _model_name(client),
        _deployment_name(client),
        model_calls,
    )


def create_default_structural_client(config_path: Path | str = "config.llm.json", timeout_seconds: float = 60.0) -> LLMClient:
    """Load the required root text configuration without logging credentials."""

    if isinstance(timeout_seconds, bool) or not isinstance(timeout_seconds, (int, float)) or timeout_seconds <= 0:
        raise StructuralAnalysisError("timeout_seconds must be positive")
    try:
        config = load_llm_config(Path(config_path))
    except ConfigError as exc:
        raise StructuralAnalysisError("text LLM configuration is invalid") from exc
    return LLMClient(config, timeout_seconds=float(timeout_seconds))


def _parse_action(value: object) -> Literal["final", "inspect"]:
    if not isinstance(value, Mapping) or not isinstance(value.get("action"), str):
        raise StructuralResponseError("model response must be a closed action object")
    action = value["action"]
    if action not in {"final", "inspect"}:
        raise StructuralResponseError("model response action is not allowlisted")
    return action  # type: ignore[return-value]


def _parse_inspection_request(
    value: Mapping[str, object],
    allowed_paths: frozenset[str],
) -> StructuralInspectionRequest:
    if set(value) != {"action", "requests"} or value.get("action") != "inspect":
        raise StructuralResponseError("inspection response has unexpected fields")
    requests = value.get("requests")
    if not isinstance(requests, list) or len(requests) != 1 or not isinstance(requests[0], Mapping):
        raise StructuralResponseError("inspection response must contain exactly one request")
    request = requests[0]
    if set(request) != {"action", "path"} or request.get("action") != "inspect_file":
        raise StructuralResponseError("inspection action is not allowlisted")
    path = request.get("path")
    if not isinstance(path, str):
        raise StructuralResponseError("inspection request path is invalid")
    _validate_path(path, "inspection request path")
    if path not in allowed_paths:
        raise StructuralResponseError("inspection request path was not pre-authorized")
    return StructuralInspectionRequest(path)


def _parse_final_response(
    value: Mapping[str, object],
    evidence: Sequence[StructuralEvidence],
) -> tuple[StructuralSemanticsCandidate, dict[str, Tuple[str, ...]]]:
    if set(value) != {"action", "structural", "fieldEvidence"} or value.get("action") != "final":
        raise StructuralResponseError("final response has unexpected fields")
    raw = value.get("structural")
    if not isinstance(raw, Mapping) or set(raw) != set(_FIELDS):
        raise StructuralResponseError("structural response must contain exactly the frozen fields")
    candidate = StructuralSemanticsCandidate(
        tasks=_string_tuple(raw.get("tasks"), _TASKS, "tasks"),
        modalities=_string_tuple(raw.get("modalities"), _MODALITIES, "modalities"),
        sample_organization=_single_enum(raw.get("sampleOrganization"), _ORGANIZATIONS, "sampleOrganization"),
        temporal_structure=_single_enum(raw.get("temporalStructure"), _TEMPORAL, "temporalStructure"),
        supervision=_string_tuple(raw.get("supervision"), _SUPERVISION, "supervision"),
        annotation_semantics=_annotation_semantics(raw.get("annotationSemantics")),
        resource_roles=_string_tuple(raw.get("resourceRoles"), _ROLES, "resourceRoles"),
        resource_relations=_string_tuple(raw.get("resourceRelations"), _RELATIONS, "resourceRelations"),
    )
    known_evidence = {item.id for item in evidence}
    raw_refs = value.get("fieldEvidence")
    if not isinstance(raw_refs, list) or len(raw_refs) != len(_FIELDS):
        raise StructuralResponseError("fieldEvidence must contain one entry for every frozen field")
    references: dict[str, Tuple[str, ...]] = {}
    for item in raw_refs:
        if not isinstance(item, Mapping) or set(item) != {"field", "evidenceRefs"}:
            raise StructuralResponseError("fieldEvidence entry is malformed")
        field = item.get("field")
        refs = item.get("evidenceRefs")
        if not isinstance(field, str) or field not in _FIELDS or field in references:
            raise StructuralResponseError("fieldEvidence has an unknown or duplicate field")
        if not isinstance(refs, list) or any(not isinstance(ref, str) or ref not in known_evidence for ref in refs):
            raise StructuralResponseError("fieldEvidence references unknown evidence")
        if len(set(refs)) != len(refs):
            raise StructuralResponseError("fieldEvidence references must be unique")
        references[field] = tuple(refs)
    if set(references) != set(_FIELDS):
        raise StructuralResponseError("fieldEvidence does not cover all frozen fields")
    _validate_positive_evidence(candidate, references)
    return candidate, references


def _validate_positive_evidence(
    candidate: StructuralSemanticsCandidate,
    references: Mapping[str, Tuple[str, ...]],
) -> None:
    values = {
        "tasks": candidate.tasks,
        "modalities": candidate.modalities,
        "sampleOrganization": () if candidate.sample_organization == "UNKNOWN" else (candidate.sample_organization,),
        "temporalStructure": () if candidate.temporal_structure == "UNKNOWN" else (candidate.temporal_structure,),
        "supervision": candidate.supervision,
        "annotationSemantics": candidate.annotation_semantics,
        "resourceRoles": candidate.resource_roles,
        "resourceRelations": () if candidate.resource_relations == ("UNKNOWN",) else candidate.resource_relations,
    }
    for field, field_values in values.items():
        if field_values and not references[field]:
            raise StructuralResponseError(f"{field} has a value without evidence")


def _claims_for_candidate(
    candidate: StructuralSemanticsCandidate,
    references: Mapping[str, Tuple[str, ...]],
    evidence: Sequence[StructuralEvidence],
    conflict_fields: Sequence[str],
) -> tuple[list[StructuralClaim], list[StructuralUnresolvedField]]:
    del evidence
    values: dict[str, Tuple[str, ...]] = {
        "tasks": candidate.tasks,
        "modalities": candidate.modalities,
        "sampleOrganization": () if candidate.sample_organization == "UNKNOWN" else (candidate.sample_organization,),
        "temporalStructure": () if candidate.temporal_structure == "UNKNOWN" else (candidate.temporal_structure,),
        "supervision": candidate.supervision,
        "annotationSemantics": candidate.annotation_semantics,
        "resourceRoles": candidate.resource_roles,
        "resourceRelations": () if candidate.resource_relations == ("UNKNOWN",) else candidate.resource_relations,
    }
    claims: list[StructuralClaim] = []
    unresolved: list[StructuralUnresolvedField] = []
    for field in _FIELDS:
        refs = references[field]
        if field in conflict_fields:
            claims.append(
                StructuralClaim(
                    id=_claim_id(field),
                    field=field,
                    value=(),
                    status="UNKNOWN",
                    evidence_refs=refs,
                    unknown_reason="CONFLICTING_EVIDENCE",
                    conflict_refs=refs,
                )
            )
            unresolved.append(
                StructuralUnresolvedField(
                    field=field,
                    reason="CONFLICTING_EVIDENCE",
                    attempted_evidence_refs=refs,
                    next_action="inspect_annotation",
                )
            )
        elif values[field]:
            claims.append(StructuralClaim(_claim_id(field), field, values[field], "VERIFIED", refs))
        else:
            reason: UnknownReason = "NO_EVIDENCE" if not refs else "INSPECTION_LIMIT"
            claims.append(
                StructuralClaim(_claim_id(field), field, (), "UNKNOWN", refs, reason)
            )
            unresolved.append(
                StructuralUnresolvedField(
                    field=field,
                    reason=reason,
                    attempted_evidence_refs=refs,
                    next_action="inspect_annotation" if field in {"tasks", "supervision", "annotationSemantics"} else "inspect_metadata",
                )
            )
    return claims, unresolved


def _with_unknown_conflicts(
    candidate: StructuralSemanticsCandidate,
    conflict_fields: Sequence[str],
) -> StructuralSemanticsCandidate:
    return StructuralSemanticsCandidate(
        tasks=() if "tasks" in conflict_fields else candidate.tasks,
        modalities=() if "modalities" in conflict_fields else candidate.modalities,
        sample_organization="UNKNOWN" if "sampleOrganization" in conflict_fields else candidate.sample_organization,
        temporal_structure="UNKNOWN" if "temporalStructure" in conflict_fields else candidate.temporal_structure,
        supervision=() if "supervision" in conflict_fields else candidate.supervision,
        annotation_semantics=() if "annotationSemantics" in conflict_fields else candidate.annotation_semantics,
        resource_roles=() if "resourceRoles" in conflict_fields else candidate.resource_roles,
        resource_relations=("UNKNOWN",) if "resourceRelations" in conflict_fields else candidate.resource_relations,
    )


def _conflicting_fields(
    candidate: StructuralSemanticsCandidate,
    deterministic: StructuralSemanticsCandidate,
) -> Tuple[str, ...]:
    conflicts: list[str] = []
    comparable: tuple[tuple[str, Tuple[str, ...], Tuple[str, ...]], ...] = (
        ("tasks", candidate.tasks, deterministic.tasks),
        ("modalities", candidate.modalities, deterministic.modalities),
        ("sampleOrganization", (candidate.sample_organization,), (deterministic.sample_organization,)),
        ("temporalStructure", (candidate.temporal_structure,), (deterministic.temporal_structure,)),
        ("supervision", candidate.supervision, deterministic.supervision),
        ("annotationSemantics", candidate.annotation_semantics, deterministic.annotation_semantics),
        ("resourceRoles", candidate.resource_roles, deterministic.resource_roles),
        ("resourceRelations", candidate.resource_relations, deterministic.resource_relations),
    )
    for field, model_values, fact_values in comparable:
        fact_known = tuple(value for value in fact_values if value != "UNKNOWN")
        model_known = tuple(value for value in model_values if value != "UNKNOWN")
        if fact_known and model_known and not set(fact_known).issubset(set(model_known)):
            conflicts.append(field)
    return tuple(conflicts)


def _deterministic_candidate(
    sketch: DatasetSketch,
    facts: Sequence[InspectionResult],
) -> StructuralSemanticsCandidate:
    fields = _fact_field_names(facts)
    paths = tuple(_fact_paths(facts)) + sketch.annotation_candidates + sketch.structured_metadata_candidates
    lower_fields = {item.lower() for item in fields}
    lower_paths = " ".join(path.lower() for path in paths)
    has_bbox = (
        _contains_any(lower_fields, ("bbox", "bounding_box", "boundingbox", "box"))
        or (
            _contains_any(lower_fields, ("xmin", "left", "x_min"))
            and _contains_any(lower_fields, ("xmax", "right", "x_max"))
            and _contains_any(lower_fields, ("ymin", "top", "y_min"))
            and _contains_any(lower_fields, ("ymax", "bottom", "y_max"))
        )
        or (
            _contains_any(lower_fields, ("x_center", "center_x", "cx"))
            and _contains_any(lower_fields, ("y_center", "center_y", "cy"))
            and _contains_any(lower_fields, ("box_width", "bbox_width"))
            and _contains_any(lower_fields, ("box_height", "bbox_height"))
        )
    )
    has_track = _contains_any(lower_fields, ("track_id", "trackid", "track"))
    has_frame = _contains_any(lower_fields, ("frame_id", "frameid", "frame"))
    has_mask = _contains_any(lower_fields, ("mask", "segmentation", "polygon"))
    has_instance = _contains_any(lower_fields, ("instance", "instance_id"))
    has_keypoints = _contains_any(lower_fields, ("keypoints", "keypoint", "skeleton"))
    has_action = _contains_any(lower_fields, ("action", "activity", "clip_label"))
    has_anomaly = _contains_any(lower_fields, ("anomaly", "abnormal"))
    has_identity = _contains_any(lower_fields, ("identity", "person_id", "camera_id", "query_id", "gallery_id"))
    has_label = _contains_any(lower_fields, ("label", "class", "category"))
    tasks: list[TaskFamily] = []
    supervision: list[Supervision] = []
    annotations: list[str] = []
    if has_bbox:
        tasks.append("object_detection")
        supervision.append("bbox")
        annotations.append("claim_annotation_bbox")
    if has_track and has_frame and has_bbox:
        tasks.append("multi_object_tracking")
        supervision.extend(["track"])
        annotations.extend(["claim_annotation_track_id", "claim_annotation_frame_id"])
    if has_mask:
        tasks.append("instance_segmentation" if has_instance else "semantic_segmentation")
        supervision.append("instance_mask" if has_instance else "semantic_mask")
        annotations.append("claim_annotation_mask")
    if has_keypoints:
        tasks.append("pose_keypoints")
        supervision.append("keypoints")
        annotations.append("claim_annotation_keypoints")
    if has_action:
        tasks.append("action_video_understanding")
        supervision.append("action_label")
        annotations.append("claim_annotation_action_label")
    if has_anomaly:
        tasks.append("video_anomaly_detection")
        supervision.append("anomaly_label")
        annotations.append("claim_annotation_anomaly_label")
    if has_identity:
        tasks.append("reid_retrieval")
        supervision.append("identity")
        annotations.append("claim_annotation_identity")
    if has_label and not tasks:
        tasks.append("image_classification")
        supervision.append("class_label")
        annotations.append("claim_annotation_class_label")

    image_facts = [fact for fact in facts if isinstance(fact, ImageInspectionFact) and fact.status == "COMPLETED"]
    modalities: list[Modality] = ["RGB"] if any(fact.channels in {3, 4} for fact in image_facts) else []
    if sketch.video_candidates:
        organization: SampleOrganization = "video"
        temporal: TemporalStructure = "video"
    elif has_frame and sketch.image_candidates:
        organization = "image_sequence"
        temporal = "sequence"
    elif sketch.image_candidates:
        organization = "independent_image"
        temporal = "none"
    else:
        organization = "UNKNOWN"
        temporal = "UNKNOWN"
    roles: list[ResourceRole] = []
    if sketch.image_candidates or sketch.video_candidates:
        roles.append("media")
    if sketch.annotation_candidates:
        roles.append("annotation")
    if sketch.structured_metadata_candidates:
        roles.append("metadata")
    if sketch.documentation_candidates:
        roles.append("documentation")
    if _contains_any(lower_fields, ("split", "fold")) or "split" in lower_paths:
        roles.append("split_definition")
    relations: list[ResourceRelation] = []
    if sketch.image_candidates and sketch.annotation_candidates:
        relations.append("image_to_annotation")
    if has_track and has_frame:
        relations.append("frame_to_track")
    if sketch.video_candidates and (has_action or has_anomaly):
        relations.append("video_to_clip_label")
    if has_identity and _contains_any(lower_fields, ("camera_id", "camera")):
        relations.append("identity_to_camera")
    return StructuralSemanticsCandidate(
        tasks=tuple(_dedupe(tasks)),
        modalities=tuple(_dedupe(modalities)),
        sample_organization=organization,
        temporal_structure=temporal,
        supervision=tuple(_dedupe(supervision)),
        annotation_semantics=tuple(_dedupe(annotations)),
        resource_roles=tuple(_dedupe(roles)),
        resource_relations=tuple(_dedupe(relations)) or ("UNKNOWN",),
    )


def _build_evidence(
    snapshot_revision: str,
    facts: Sequence[InspectionResult],
    excerpts: Sequence[DocumentationExcerpt],
) -> list[StructuralEvidence]:
    result: list[StructuralEvidence] = []
    for index, fact in enumerate(facts, start=1):
        result.append(
            StructuralEvidence(
                id=f"evidence_inspection_{index:03d}",
                kind="inspection",
                source_ref=f"inspection:{fact.path}",
                locator=(("kind", "inspection"), ("inspectionRef", f"inspection_{index:03d}")),
                summary=_bounded_summary(f"inspection fact for {fact.path}: {fact.format}/{fact.status}"),
                snapshot_revision=snapshot_revision,
            )
        )
    for index, excerpt in enumerate(excerpts, start=1):
        result.append(
            StructuralEvidence(
                id=f"evidence_readme_{index:03d}",
                kind="README",
                source_ref=f"documentation:{excerpt.path}",
                locator=(
                    ("kind", "text"),
                    ("path", excerpt.path),
                    ("lineStart", excerpt.line_start),
                    ("lineEnd", excerpt.line_end),
                ),
                summary=_bounded_summary(f"documentation excerpt at {excerpt.path}:{excerpt.line_start}-{excerpt.line_end}"),
                snapshot_revision=snapshot_revision,
            )
        )
    return result


def _user_prompt(
    value: StructuralAnalysisInput,
    facts: Sequence[InspectionResult],
    evidence: Sequence[StructuralEvidence],
) -> str:
    doc_left = value.limits.max_documentation_characters
    docs: list[dict[str, object]] = []
    for index, excerpt in enumerate(value.documentation_excerpts, start=1):
        if doc_left <= 0:
            break
        text = excerpt.redacted(doc_left)
        doc_left -= len(text)
        docs.append(
            {
                "evidenceId": f"evidence_readme_{index:03d}",
                "path": excerpt.path,
                "lineStart": excerpt.line_start,
                "lineEnd": excerpt.line_end,
                "text": text,
            }
        )
    return json.dumps(
        {
            "snapshotRevision": value.snapshot_revision,
            "sketch": _sketch_projection(value.sketch),
            "inspectionFacts": [_fact_projection(item) for item in facts],
            "documentation": docs,
            "evidenceIds": [item.id for item in evidence],
            "allowedInspectionPaths": sorted(_allowed_inspection_paths(value.sketch)),
        },
        ensure_ascii=True,
        separators=(",", ":"),
    )


def _system_prompt() -> str:
    return (
        "You are a structural dataset semantics classifier. Return JSON only. "
        "You may classify tasks, modalities, sample organization, temporal structure, supervision, "
        "annotation semantics, resource roles, and resource relations only from supplied evidence. "
        "Do not infer content semantics. Do not determine or invent file counts, dimensions, FPS, "
        "row counts, field existence, media properties, or paths. If more deterministic evidence is "
        "necessary, request exactly one allowed inspect_file action. Otherwise return action=final. "
        "A final response must contain exactly action, structural, fieldEvidence. structural must "
        "contain exactly tasks, modalities, sampleOrganization, temporalStructure, supervision, "
        "annotationSemantics, resourceRoles, resourceRelations. Every non-empty/non-UNKNOWN field "
        "must cite supplied evidence IDs. Use only frozen enum values. annotationSemantics values "
        "must be stable claim IDs beginning claim_annotation_. Every one of tasks, modalities, "
        "supervision, annotationSemantics, resourceRoles, and resourceRelations MUST be a JSON "
        "array, including when empty. sampleOrganization and temporalStructure MUST be strings. "
        "Do not use null, prose, code fences, or a value named UNKNOWN in an array. "
        "For example: {\"action\":\"final\",\"structural\":{\"tasks\":[\"object_detection\"],"
        "\"modalities\":[\"RGB\"],\"sampleOrganization\":\"independent_image\","
        "\"temporalStructure\":\"none\",\"supervision\":[\"bbox\"],"
        "\"annotationSemantics\":[\"claim_annotation_bbox\"],"
        "\"resourceRoles\":[\"media\",\"annotation\",\"metadata\"],"
        "\"resourceRelations\":[\"image_to_annotation\"]},\"fieldEvidence\":["
        "{\"field\":\"tasks\",\"evidenceRefs\":[\"evidence_inspection_001\"]},"
        "{\"field\":\"modalities\",\"evidenceRefs\":[\"evidence_inspection_001\"]},"
        "{\"field\":\"sampleOrganization\",\"evidenceRefs\":[\"evidence_inspection_001\"]},"
        "{\"field\":\"temporalStructure\",\"evidenceRefs\":[\"evidence_inspection_001\"]},"
        "{\"field\":\"supervision\",\"evidenceRefs\":[\"evidence_inspection_001\"]},"
        "{\"field\":\"annotationSemantics\",\"evidenceRefs\":[\"evidence_inspection_001\"]},"
        "{\"field\":\"resourceRoles\",\"evidenceRefs\":[\"evidence_inspection_001\"]},"
        "{\"field\":\"resourceRelations\",\"evidenceRefs\":[\"evidence_inspection_001\"]}]}"
    )


def _sketch_projection(sketch: DatasetSketch) -> dict[str, object]:
    return {
        "fileTypeDistribution": list(sketch.file_type_distribution),
        "documentationCandidates": list(sketch.documentation_candidates),
        "imageCandidates": list(sketch.image_candidates),
        "videoCandidates": list(sketch.video_candidates),
        "annotationCandidates": list(sketch.annotation_candidates),
        "structuredMetadataCandidates": list(sketch.structured_metadata_candidates),
    }


def _fact_projection(fact: InspectionResult) -> dict[str, object]:
    result = fact.to_dict()
    result.pop("warnings", None)
    return _redact_object(result)


def _allowed_inspection_paths(sketch: DatasetSketch) -> frozenset[str]:
    return frozenset(sketch.annotation_candidates + sketch.structured_metadata_candidates)


def _fact_field_names(facts: Sequence[InspectionResult]) -> Tuple[str, ...]:
    values: list[str] = []
    for fact in facts:
        if isinstance(fact, (DelimitedTableInspectionFact, JsonInspectionFact, ParquetInspectionFact)):
            columns = fact.columns if hasattr(fact, "columns") else fact.fields
            values.extend(column.name for column in columns)
        elif isinstance(fact, XmlInspectionFact):
            values.extend(name for name, _ in fact.element_names)
            values.extend(fact.attribute_names)
    return tuple(values)


def _fact_paths(facts: Sequence[InspectionResult]) -> Tuple[str, ...]:
    return tuple(fact.path for fact in facts)


def _string_tuple(value: object, allowed: frozenset[str], field: str) -> Tuple[object, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or item not in allowed for item in value):
        raise StructuralResponseError(f"{field} must be a list of frozen values")
    if len(set(value)) != len(value):
        raise StructuralResponseError(f"{field} values must be unique")
    return tuple(value)


def _single_enum(value: object, allowed: frozenset[str], field: str) -> object:
    if not isinstance(value, str) or value not in allowed:
        raise StructuralResponseError(f"{field} is not a frozen value")
    return value


def _annotation_semantics(value: object) -> Tuple[str, ...]:
    if not isinstance(value, list) or any(
        not isinstance(item, str) or not re.fullmatch(r"claim_annotation_[a-z0-9_]{1,96}", item)
        for item in value
    ):
        raise StructuralResponseError("annotationSemantics must contain closed annotation claim IDs")
    if len(set(value)) != len(value):
        raise StructuralResponseError("annotationSemantics values must be unique")
    return tuple(value)


def _validate_path(value: str, label: str) -> None:
    if not _SAFE_PATH.fullmatch(value):
        raise StructuralAnalysisError(f"{label} must be a safe relative path")


def _contains_any(values: set[str], needles: Sequence[str]) -> bool:
    return any(value == needle or value.endswith("_" + needle) or needle in value for value in values for needle in needles)


def _dedupe(values: Sequence[object]) -> list[object]:
    return list(dict.fromkeys(values))


def _claim_id(field: str) -> str:
    return "claim_structural_" + {
        "tasks": "tasks",
        "modalities": "modalities",
        "sampleOrganization": "sample_organization",
        "temporalStructure": "temporal_structure",
        "supervision": "supervision",
        "annotationSemantics": "annotation_semantics",
        "resourceRoles": "resource_roles",
        "resourceRelations": "resource_relations",
    }[field]


def _bounded_summary(value: str) -> str:
    return _redact(value)[:512] or "redacted evidence"


def _redact(value: str) -> str:
    return _SENSITIVE_PATTERN.sub("[REDACTED]", value)


def _redact_object(value: object) -> object:
    if isinstance(value, str):
        return _redact(value)
    if isinstance(value, list):
        return [_redact_object(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _redact_object(item) for key, item in value.items()}
    return value


def _safe_error_label(exc: BaseException) -> str:
    name = exc.__class__.__name__
    text = _redact(str(exc))
    text = text[:180]
    return f"{name}: {text}" if text else name


def _failed_result(
    warning: str,
    model: str,
    deployment: str,
    calls: int,
) -> StructuralAnalysisResult:
    return StructuralAnalysisResult(
        status="FAILED",
        candidate=None,
        claims=(),
        evidence=(),
        unresolved=(),
        inspection_requests=(),
        warnings=(_redact(warning)[:512],),
        model=model,
        deployment=deployment,
        model_call_count=calls,
    )


def _model_name(client: StructuralLLM) -> str:
    config = getattr(client, "config", None)
    model = getattr(config, "model", "")
    return model if isinstance(model, str) else ""


def _deployment_name(client: StructuralLLM) -> str:
    deployment = getattr(client, "last_model", "")
    return deployment if isinstance(deployment, str) else ""
