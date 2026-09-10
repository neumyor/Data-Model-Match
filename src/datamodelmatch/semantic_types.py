"""Closed runtime types for frozen semantic artifact contracts v1."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Literal, Mapping, Optional, Tuple


JobStatus = Literal[
    "queued",
    "running",
    "partially_completed",
    "completed",
    "failed",
    "cancelled",
    "superseded",
]
EventType = Literal["stage", "progress", "evidence", "warning", "result", "error", "end"]
ErrorCode = Literal[
    "SCHEMA_VALIDATION_FAILED",
    "UNSUPPORTED_SCHEMA_VERSION",
    "RESOURCE_NOT_FOUND",
    "SNAPSHOT_NOT_FOUND",
    "REVISION_CONFLICT",
    "PROFILE_NOT_FOUND",
    "TASK_PROFILE_NOT_FOUND",
    "JOB_NOT_FOUND",
    "JOB_NOT_CANCELLABLE",
    "IDEMPOTENCY_KEY_CONFLICT",
    "STALE_JOB_SUPERSEDED",
    "VLM_CONFIG_INVALID",
    "VLM_UNAVAILABLE",
    "VLM_TIMEOUT",
    "VLM_EMPTY_RESPONSE",
    "VLM_INVALID_RESPONSE",
    "UNSUPPORTED_MEDIA",
    "MEDIA_READ_FAILED",
    "INSUFFICIENT_EVIDENCE",
    "ACCESS_DENIED",
    "RATE_LIMITED",
    "INTERNAL_ERROR",
]

_ID = re.compile(r"^[A-Za-z][A-Za-z0-9_-]{2,127}$")
_FINGERPRINT = re.compile(r"^sha256:[a-f0-9]{64}$")
_VERSION = 1
_PROFILE_FIELDS = frozenset(
    {
        "version",
        "resourceId",
        "snapshotRevision",
        "generator",
        "structuralSemantics",
        "contentSemantics",
        "sampleRefs",
        "observations",
        "samplingSummary",
        "claims",
        "evidence",
        "unresolved",
        "generatedAt",
    }
)


class SemanticContractError(ValueError):
    """Raised when a frozen semantic artifact contract is violated."""


class SemanticJobNotFoundError(KeyError):
    """Raised when a durable semantic job cannot be found."""


class SemanticIdempotencyConflictError(SemanticContractError):
    """Raised for a reused explicit idempotency key with different input."""

    code: ErrorCode = "IDEMPOTENCY_KEY_CONFLICT"


class SemanticJobTransitionError(SemanticContractError):
    """Raised when a job state cannot transition to the requested state."""


class SemanticJobNotCancellableError(SemanticJobTransitionError):
    """Raised when cancellation is not legal for the current job state."""

    code: ErrorCode = "JOB_NOT_CANCELLABLE"


class SemanticStorageSafetyError(SemanticContractError):
    """Raised when artifact storage would leave the managed semantic root."""


def validate_id(value: object, field: str) -> str:
    if not isinstance(value, str) or not _ID.fullmatch(value):
        raise SemanticContractError(f"{field} must match the frozen semantic ID format")
    return value


def validate_revision(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or len(value) > 256:
        raise SemanticContractError(f"{field} must be a non-empty revision up to 256 characters")
    return value


def validate_fingerprint(value: object, field: str) -> str:
    if not isinstance(value, str) or not _FINGERPRINT.fullmatch(value):
        raise SemanticContractError(f"{field} must be a sha256 fingerprint")
    return value


def _validate_timestamp(value: object, field: str) -> str:
    if not isinstance(value, str) or not value or "T" not in value:
        raise SemanticContractError(f"{field} must be an RFC 3339 timestamp")
    return value


@dataclass(frozen=True)
class ProfileJobRequest:
    """Closed profile-job request required by the public v1 contract."""

    resource_id: str
    snapshot_revision: str
    configuration_fingerprint: str
    idempotency_key: Optional[str] = None
    version: Literal[1] = 1
    profile_schema_version: Literal[1] = 1

    def __post_init__(self) -> None:
        validate_id(self.resource_id, "resource_id")
        validate_revision(self.snapshot_revision, "snapshot_revision")
        validate_fingerprint(self.configuration_fingerprint, "configuration_fingerprint")
        if self.version != _VERSION or self.profile_schema_version != _VERSION:
            raise SemanticContractError("only semantic schema version 1 is supported")
        if self.idempotency_key is not None:
            if not isinstance(self.idempotency_key, str) or not self.idempotency_key or len(self.idempotency_key) > 512:
                raise SemanticContractError("idempotency_key must be a non-empty string up to 512 characters")

    def canonical_tuple(self) -> Tuple[str, str, int, str]:
        return (
            self.resource_id,
            self.snapshot_revision,
            self.profile_schema_version,
            self.configuration_fingerprint,
        )

    def to_dict(self) -> dict[str, object]:
        value: dict[str, object] = {
            "version": self.version,
            "resourceId": self.resource_id,
            "snapshotRevision": self.snapshot_revision,
            "profileSchemaVersion": self.profile_schema_version,
            "configurationFingerprint": self.configuration_fingerprint,
        }
        if self.idempotency_key is not None:
            value["idempotencyKey"] = self.idempotency_key
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "ProfileJobRequest":
        expected = {
            "version",
            "resourceId",
            "snapshotRevision",
            "profileSchemaVersion",
            "configurationFingerprint",
            "idempotencyKey",
        }
        unknown = set(value).difference(expected)
        required = expected.difference({"idempotencyKey"})
        if unknown or required.difference(value):
            raise SemanticContractError("profile job request has unexpected or missing fields")
        return cls(
            resource_id=validate_id(value["resourceId"], "resourceId"),
            snapshot_revision=validate_revision(value["snapshotRevision"], "snapshotRevision"),
            configuration_fingerprint=validate_fingerprint(
                value["configurationFingerprint"], "configurationFingerprint"
            ),
            idempotency_key=value.get("idempotencyKey") if isinstance(value.get("idempotencyKey"), str) else None,
            version=value["version"] if value["version"] == 1 else 0,  # type: ignore[arg-type]
            profile_schema_version=(
                value["profileSchemaVersion"] if value["profileSchemaVersion"] == 1 else 0
            ),  # type: ignore[arg-type]
        )


@dataclass(frozen=True)
class SemanticJobError:
    code: ErrorCode
    message: str
    retryable: bool

    def __post_init__(self) -> None:
        if self.code not in ErrorCode.__args__:
            raise SemanticContractError("error code is not frozen")
        if not isinstance(self.message, str) or not self.message or len(self.message) > 1024:
            raise SemanticContractError("error message must be a non-empty string up to 1024 characters")

    def to_dict(self) -> dict[str, object]:
        return {"code": self.code, "message": self.message, "retryable": self.retryable}

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "SemanticJobError":
        if set(value) != {"code", "message", "retryable"}:
            raise SemanticContractError("job error has unexpected or missing fields")
        return cls(
            code=value["code"],  # type: ignore[arg-type]
            message=value["message"] if isinstance(value["message"], str) else "",
            retryable=value["retryable"] if isinstance(value["retryable"], bool) else False,
        )


@dataclass(frozen=True)
class SemanticJob:
    job_id: str
    status: JobStatus
    request: ProfileJobRequest
    created_at: str
    updated_at: str
    attempt: int
    max_attempts: int
    idempotency_key: str
    result_ref: Optional[str] = None
    error: Optional[SemanticJobError] = None

    def __post_init__(self) -> None:
        validate_id(self.job_id, "job_id")
        if self.status not in JobStatus.__args__:
            raise SemanticContractError("job status is not frozen")
        _validate_timestamp(self.created_at, "created_at")
        _validate_timestamp(self.updated_at, "updated_at")
        if not isinstance(self.attempt, int) or self.attempt < 0:
            raise SemanticContractError("attempt must be a non-negative integer")
        if not isinstance(self.max_attempts, int) or self.max_attempts < 0:
            raise SemanticContractError("max_attempts must be a non-negative integer")
        if not isinstance(self.idempotency_key, str) or not self.idempotency_key:
            raise SemanticContractError("idempotency_key must be present on persisted jobs")
        if self.status == "completed" and not self.result_ref:
            raise SemanticContractError("completed job must have a result reference")
        if self.status != "completed" and self.result_ref is not None:
            raise SemanticContractError("only completed job may have a result reference")

    def to_dict(self) -> dict[str, object]:
        value: dict[str, object] = {
            "version": 1,
            "jobId": self.job_id,
            "jobType": "profile",
            "status": self.status,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "attempt": self.attempt,
            "maxAttempts": self.max_attempts,
            "idempotencyKey": self.idempotency_key,
            "request": self.request.to_dict(),
        }
        if self.result_ref is not None:
            value["resultRef"] = self.result_ref
        if self.error is not None:
            value["error"] = self.error.to_dict()
        return value

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "SemanticJob":
        expected = {
            "version",
            "jobId",
            "jobType",
            "status",
            "createdAt",
            "updatedAt",
            "attempt",
            "maxAttempts",
            "idempotencyKey",
            "request",
            "resultRef",
            "error",
        }
        required = expected.difference({"resultRef", "error"})
        if set(value).difference(expected) or required.difference(value):
            raise SemanticContractError("stored job has unexpected or missing fields")
        if value["version"] != 1 or value["jobType"] != "profile":
            raise SemanticContractError("stored job has incompatible version or type")
        raw_request = value["request"]
        if not isinstance(raw_request, Mapping):
            raise SemanticContractError("stored job request must be an object")
        raw_error = value.get("error")
        if raw_error is not None and not isinstance(raw_error, Mapping):
            raise SemanticContractError("stored job error must be an object")
        result_ref = value.get("resultRef")
        if result_ref is not None and not isinstance(result_ref, str):
            raise SemanticContractError("stored job result reference must be a string")
        return cls(
            job_id=validate_id(value["jobId"], "jobId"),
            status=value["status"],  # type: ignore[arg-type]
            request=ProfileJobRequest.from_dict(raw_request),
            created_at=_validate_timestamp(value["createdAt"], "createdAt"),
            updated_at=_validate_timestamp(value["updatedAt"], "updatedAt"),
            attempt=value["attempt"] if isinstance(value["attempt"], int) else -1,
            max_attempts=value["maxAttempts"] if isinstance(value["maxAttempts"], int) else -1,
            idempotency_key=value["idempotencyKey"] if isinstance(value["idempotencyKey"], str) else "",
            result_ref=result_ref,
            error=SemanticJobError.from_dict(raw_error) if isinstance(raw_error, Mapping) else None,
        )


@dataclass(frozen=True)
class SemanticJobEvent:
    job_id: str
    event_id: int
    timestamp: str
    event_type: EventType
    data_json: str

    def __post_init__(self) -> None:
        validate_id(self.job_id, "job_id")
        if not isinstance(self.event_id, int) or self.event_id < 1:
            raise SemanticContractError("event_id must be a positive integer")
        _validate_timestamp(self.timestamp, "timestamp")
        if self.event_type not in EventType.__args__:
            raise SemanticContractError("event_type is not frozen")
        try:
            decoded = json.loads(self.data_json)
        except json.JSONDecodeError as exc:
            raise SemanticContractError("event data must be JSON") from exc
        if not isinstance(decoded, dict):
            raise SemanticContractError("event data must be an object")

    def to_dict(self) -> dict[str, object]:
        return {
            "version": 1,
            "jobId": self.job_id,
            "eventId": self.event_id,
            "timestamp": self.timestamp,
            "eventType": self.event_type,
            "data": json.loads(self.data_json),
        }

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "SemanticJobEvent":
        expected = {"version", "jobId", "eventId", "timestamp", "eventType", "data"}
        if set(value) != expected or value["version"] != 1:
            raise SemanticContractError("stored event has unexpected fields or an incompatible version")
        if not isinstance(value["data"], Mapping):
            raise SemanticContractError("stored event data must be an object")
        return cls(
            job_id=validate_id(value["jobId"], "jobId"),
            event_id=value["eventId"] if isinstance(value["eventId"], int) else 0,
            timestamp=_validate_timestamp(value["timestamp"], "timestamp"),
            event_type=value["eventType"],  # type: ignore[arg-type]
            data_json=json.dumps(value["data"], ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )


@dataclass(frozen=True)
class DatasetSemanticProfile:
    """Closed v1 profile wrapper with canonical JSON retained for durability."""

    resource_id: str
    snapshot_revision: str
    configuration_fingerprint: str
    document_json: str

    @classmethod
    def from_dict(cls, value: Mapping[str, object]) -> "DatasetSemanticProfile":
        if set(value) != _PROFILE_FIELDS:
            raise SemanticContractError("semantic profile has unexpected or missing top-level fields")
        if value.get("version") != 1:
            raise SemanticContractError("semantic profile version must be 1")
        resource_id = validate_id(value.get("resourceId"), "resourceId")
        snapshot_revision = validate_revision(value.get("snapshotRevision"), "snapshotRevision")
        generator = value.get("generator")
        if not isinstance(generator, Mapping) or set(generator) != {
            "profileBuilderVersion",
            "samplingPolicyVersion",
            "aggregationRuleVersion",
            "configurationFingerprint",
        }:
            raise SemanticContractError("semantic profile generator must be a closed v1 object")
        fingerprint = validate_fingerprint(
            generator.get("configurationFingerprint"), "generator.configurationFingerprint"
        )
        for version_name in (
            "profileBuilderVersion",
            "samplingPolicyVersion",
            "aggregationRuleVersion",
        ):
            version = generator.get(version_name)
            if not isinstance(version, str) or not re.fullmatch(r"1\.\d+\.\d+", version):
                raise SemanticContractError(f"generator.{version_name} must be a v1 semantic version")
        for field in (
            "structuralSemantics",
            "contentSemantics",
            "samplingSummary",
        ):
            if not isinstance(value.get(field), Mapping):
                raise SemanticContractError(f"{field} must be an object")
        for field in ("sampleRefs", "observations", "claims", "evidence", "unresolved"):
            if not isinstance(value.get(field), list):
                raise SemanticContractError(f"{field} must be an array")
        if not value["claims"] or not value["evidence"]:
            raise SemanticContractError("semantic profile claims and evidence must not be empty")
        _validate_timestamp(value.get("generatedAt"), "generatedAt")
        _validate_profile_references(value, resource_id, snapshot_revision)
        return cls(
            resource_id=resource_id,
            snapshot_revision=snapshot_revision,
            configuration_fingerprint=fingerprint,
            document_json=json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )

    def to_dict(self) -> dict[str, object]:
        value = json.loads(self.document_json)
        if not isinstance(value, dict):
            raise SemanticContractError("stored semantic profile is not an object")
        return value


def _validate_profile_references(
    value: Mapping[str, object],
    resource_id: str,
    snapshot_revision: str,
) -> None:
    del resource_id
    sample_refs = value["sampleRefs"]
    evidence = value["evidence"]
    claims = value["claims"]
    if not isinstance(sample_refs, list) or not isinstance(evidence, list) or not isinstance(claims, list):
        raise SemanticContractError("semantic profile reference collections are malformed")
    sample_ids = _unique_ids(sample_refs, "sampleRefs")
    evidence_ids = _unique_ids(evidence, "evidence")
    claim_ids = _unique_ids(claims, "claims")
    for raw_evidence in evidence:
        if not isinstance(raw_evidence, Mapping):
            raise SemanticContractError("evidence entry must be an object")
        if raw_evidence.get("snapshotRevision") != snapshot_revision:
            raise SemanticContractError("evidence must bind to the profile snapshot revision")
        locator = raw_evidence.get("locator")
        if not isinstance(locator, Mapping):
            raise SemanticContractError("evidence locator must be an object")
        kind = locator.get("kind")
        if kind == "sample" and locator.get("sampleRef") not in sample_ids:
            raise SemanticContractError("evidence sample reference does not resolve")
        if kind == "text":
            path = locator.get("path")
            if not isinstance(path, str) or not _safe_relative_path(path):
                raise SemanticContractError("evidence text path must be a safe relative path")
    for raw_claim in claims:
        if not isinstance(raw_claim, Mapping):
            raise SemanticContractError("claim entry must be an object")
        status = raw_claim.get("status")
        if status not in {"VERIFIED", "SUPPORTED", "OBSERVED", "UNKNOWN"}:
            raise SemanticContractError("claim status is not frozen")
        refs = raw_claim.get("evidenceRefs")
        if not isinstance(refs, list) or not refs or any(item not in evidence_ids for item in refs):
            raise SemanticContractError("claim evidence references do not resolve")
        if status == "UNKNOWN":
            if raw_claim.get("unknownReason") is None or "value" in raw_claim or "valueDistribution" in raw_claim:
                raise SemanticContractError("UNKNOWN claim has invalid value or reason")
        elif "value" not in raw_claim and "valueDistribution" not in raw_claim:
            raise SemanticContractError("non-UNKNOWN claim requires a value")
        if status == "SUPPORTED" and raw_claim.get("aggregationRef") is None:
            raise SemanticContractError("SUPPORTED claim requires aggregationRef")
    structural = value["structuralSemantics"]
    content = value["contentSemantics"]
    if not isinstance(structural, Mapping) or not isinstance(content, Mapping):
        raise SemanticContractError("semantic profile sections are malformed")
    for field in ("annotationSemantics",):
        refs = structural.get(field)
        if not isinstance(refs, list) or any(item not in claim_ids for item in refs):
            raise SemanticContractError(f"{field} contains an unresolved claim")
    for field in (
        "objectCategories",
        "environments",
        "viewpoints",
        "targetScale",
        "objectDensity",
        "occlusion",
        "illumination",
        "cameraMotion",
        "targetMotion",
    ):
        refs = content.get(field)
        candidates = refs if isinstance(refs, list) else [refs]
        if any(item not in claim_ids for item in candidates):
            raise SemanticContractError(f"contentSemantics.{field} contains an unresolved claim")


def _unique_ids(items: list[object], field: str) -> set[str]:
    identifiers: set[str] = set()
    for item in items:
        if not isinstance(item, Mapping):
            raise SemanticContractError(f"{field} entry must be an object")
        identifier = validate_id(item.get("id"), f"{field}.id")
        if identifier in identifiers:
            raise SemanticContractError(f"{field} IDs must be unique")
        identifiers.add(identifier)
    return identifiers


def _safe_relative_path(value: str) -> bool:
    return bool(value) and not value.startswith("/") and ".." not in value.split("/")
