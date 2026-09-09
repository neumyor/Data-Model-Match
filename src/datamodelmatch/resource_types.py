"""Typed contracts for managed datasets, models, and compatibility reports."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List


class ResourceValidationError(ValueError):
    """Raised when a managed resource contract is invalid."""


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResourceValidationError(f"{name} must be a non-empty string")
    return value.strip()


def _score(value: object, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ResourceValidationError(f"{name} must be a number")
    result = float(value)
    if not 0 <= result <= 1:
        raise ResourceValidationError(f"{name} must be between 0 and 1")
    return result


@dataclass(frozen=True)
class SourceRef:
    type: str
    location: str
    revision: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "type", _text(self.type, "source.type"))
        object.__setattr__(self, "location", _text(self.location, "source.location"))
        object.__setattr__(self, "revision", _text(self.revision, "source.revision"))

    def to_dict(self) -> Dict[str, str]:
        return {"type": self.type, "location": self.location, "revision": self.revision}


@dataclass(frozen=True)
class Evidence:
    kind: str
    source: str
    detail: str

    def to_dict(self) -> Dict[str, str]:
        return {"kind": self.kind, "source": self.source, "detail": self.detail}


@dataclass(frozen=True)
class DatasetFeature:
    name: str
    data_type: str
    semantic_role: str = "unknown"
    nullable: bool = True
    shape: List[object] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "dataType": self.data_type,
            "semanticRole": self.semantic_role,
            "nullable": self.nullable,
            "shape": list(self.shape),
            "description": self.description,
        }


@dataclass(frozen=True)
class DatasetSplit:
    name: str
    row_count: int | None = None

    def to_dict(self) -> Dict[str, Any]:
        return {"name": self.name, "rowCount": self.row_count}


@dataclass(frozen=True)
class DatasetProfile:
    resource_id: str
    name: str
    description: str
    source: SourceRef
    modalities: List[str]
    task_hints: List[str]
    splits: List[DatasetSplit]
    features: List[DatasetFeature]
    formats: List[str]
    sample_count: int
    license: str
    languages: List[str]
    evidence: List[Evidence]
    warnings: List[str]
    completeness: float
    trace: List[Dict[str, Any]] = field(default_factory=list)
    version: int = 1
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "resourceId": self.resource_id,
            "name": self.name,
            "description": self.description,
            "source": self.source.to_dict(),
            "modalities": list(self.modalities),
            "taskHints": list(self.task_hints),
            "splits": [item.to_dict() for item in self.splits],
            "features": [item.to_dict() for item in self.features],
            "formats": list(self.formats),
            "sampleCount": self.sample_count,
            "license": self.license,
            "languages": list(self.languages),
            "evidence": [item.to_dict() for item in self.evidence],
            "warnings": list(self.warnings),
            "completeness": _score(self.completeness, "dataset.completeness"),
            "trace": list(self.trace),
            "provenance": dict(self.provenance),
        }


@dataclass(frozen=True)
class ContractField:
    name: str
    data_type: str
    required: bool = True
    shape: List[object] = field(default_factory=list)
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "dataType": self.data_type,
            "required": self.required,
            "shape": list(self.shape),
            "description": self.description,
        }


@dataclass(frozen=True)
class ModelContract:
    modalities: List[str]
    fields: List[ContractField]
    preprocessing: List[str] = field(default_factory=list)
    constraints: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "modalities": list(self.modalities),
            "fields": [item.to_dict() for item in self.fields],
            "preprocessing": list(self.preprocessing),
            "constraints": list(self.constraints),
        }


@dataclass(frozen=True)
class ModelProfile:
    resource_id: str
    name: str
    description: str
    source: SourceRef
    frameworks: List[str]
    architectures: List[str]
    tasks: List[str]
    input_contract: ModelContract
    output_contract: ModelContract
    entrypoints: List[str]
    dependency_files: List[str]
    license: str
    evidence: List[Evidence]
    warnings: List[str]
    completeness: float
    trace: List[Dict[str, Any]] = field(default_factory=list)
    version: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "version": self.version,
            "resourceId": self.resource_id,
            "name": self.name,
            "description": self.description,
            "source": self.source.to_dict(),
            "frameworks": list(self.frameworks),
            "architectures": list(self.architectures),
            "tasks": list(self.tasks),
            "inputContract": self.input_contract.to_dict(),
            "outputContract": self.output_contract.to_dict(),
            "entrypoints": list(self.entrypoints),
            "dependencyFiles": list(self.dependency_files),
            "license": self.license,
            "evidence": [item.to_dict() for item in self.evidence],
            "warnings": list(self.warnings),
            "completeness": _score(self.completeness, "model.completeness"),
            "trace": list(self.trace),
        }


@dataclass(frozen=True)
class ResourceRecord:
    id: str
    kind: str
    source_type: str
    source: str
    revision: str
    resolved_revision: str
    name: str
    status: str
    local_path: str
    profile_path: str
    file_count: int
    size_bytes: int
    created_at: str
    updated_at: str
    warnings: List[str] = field(default_factory=list)
    provenance: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "kind": self.kind,
            "sourceType": self.source_type,
            "source": self.source,
            "revision": self.revision,
            "resolvedRevision": self.resolved_revision,
            "name": self.name,
            "status": self.status,
            "localPath": self.local_path,
            "profilePath": self.profile_path,
            "fileCount": self.file_count,
            "sizeBytes": self.size_bytes,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "warnings": list(self.warnings),
            "provenance": dict(self.provenance),
        }

    @classmethod
    def from_dict(cls, value: Dict[str, Any]) -> "ResourceRecord":
        return cls(
            id=_text(value.get("id"), "record.id"),
            kind=_text(value.get("kind"), "record.kind"),
            source_type=_text(value.get("sourceType"), "record.sourceType"),
            source=_text(value.get("source"), "record.source"),
            revision=_text(value.get("revision"), "record.revision"),
            resolved_revision=_text(value.get("resolvedRevision"), "record.resolvedRevision"),
            name=_text(value.get("name"), "record.name"),
            status=_text(value.get("status"), "record.status"),
            local_path=_text(value.get("localPath"), "record.localPath"),
            profile_path=_text(value.get("profilePath"), "record.profilePath"),
            file_count=int(value.get("fileCount", 0)),
            size_bytes=int(value.get("sizeBytes", 0)),
            created_at=_text(value.get("createdAt"), "record.createdAt"),
            updated_at=_text(value.get("updatedAt"), "record.updatedAt"),
            warnings=list(value.get("warnings", [])),
            provenance=dict(value.get("provenance", {})),
        )


@dataclass(frozen=True)
class CompatibilityDimension:
    name: str
    status: str
    score: float
    reason: str
    evidence: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "score": _score(self.score, f"dimension.{self.name}.score"),
            "reason": self.reason,
            "evidence": list(self.evidence),
        }


@dataclass(frozen=True)
class CompatibilityReport:
    dataset_resource_id: str
    model_resource_id: str
    status: str
    score: float
    summary: str
    dimensions: List[CompatibilityDimension]
    field_mappings: List[Dict[str, Any]]
    transforms: List[str]
    blockers: List[str]
    warnings: List[str]
    model: str
    deployment: str = ""
    attempt_count: int = 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "datasetResourceId": self.dataset_resource_id,
            "modelResourceId": self.model_resource_id,
            "status": self.status,
            "score": _score(self.score, "compatibility.score"),
            "summary": self.summary,
            "dimensions": [item.to_dict() for item in self.dimensions],
            "fieldMappings": list(self.field_mappings),
            "transforms": list(self.transforms),
            "blockers": list(self.blockers),
            "warnings": list(self.warnings),
            "meta": {
                "model": self.model,
                "deployment": self.deployment or self.model,
                "attemptCount": self.attempt_count,
            },
        }
