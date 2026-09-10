"""Deterministic, fact-only inventory of a managed dataset snapshot.

The survey deliberately stops at file and directory evidence.  It does not
interpret filenames as task or content semantics and never follows symlinks.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence, Tuple


SENSITIVE_NAMES = frozenset(
    {
        ".env",
        ".env.local",
        ".env.production",
        "config.llm.json",
        "credentials.json",
        "secrets.json",
        "id_rsa",
    }
)
DOC_NAMES = frozenset({"readme", "readme.md", "readme.txt", "license", "changelog"})
IMAGE_SUFFIXES = frozenset({".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff"})
VIDEO_SUFFIXES = frozenset({".mp4", ".avi", ".mov", ".mkv", ".webm", ".mpeg", ".mpg"})
STRUCTURED_SUFFIXES = frozenset({".csv", ".tsv", ".json", ".jsonl", ".ndjson", ".parquet"})
ANNOTATION_SUFFIXES = frozenset({".xml", ".json", ".jsonl", ".ndjson", ".csv", ".tsv", ".txt"})


class SurveyError(ValueError):
    """Raised when the survey root or limits are invalid."""


@dataclass(frozen=True)
class SurveyLimits:
    max_files: int = 10_000
    max_depth: int = 32
    max_file_bytes: int = 256 * 1024 * 1024
    max_total_bytes: int = 2 * 1024 * 1024 * 1024
    max_representative_paths: int = 100

    def __post_init__(self) -> None:
        for name in (
            "max_files",
            "max_depth",
            "max_file_bytes",
            "max_total_bytes",
            "max_representative_paths",
        ):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise SurveyError(f"{name} must be a positive integer")


@dataclass(frozen=True)
class SurveyWarning:
    code: str
    path: str
    reason: str

    def to_dict(self) -> Dict[str, str]:
        return {"code": self.code, "path": self.path, "reason": self.reason}


@dataclass(frozen=True)
class SkippedPath:
    path: str
    reason_code: str
    reason: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "path": self.path,
            "reasonCode": self.reason_code,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class DatasetSketch:
    version: int
    file_count: int
    total_bytes: int
    directory_patterns: Tuple[str, ...]
    file_type_distribution: Tuple[Tuple[str, int], ...]
    representative_paths: Tuple[str, ...]
    documentation_candidates: Tuple[str, ...]
    image_candidates: Tuple[str, ...]
    video_candidates: Tuple[str, ...]
    annotation_candidates: Tuple[str, ...]
    structured_metadata_candidates: Tuple[str, ...]
    skipped_paths: Tuple[SkippedPath, ...]
    warnings: Tuple[SurveyWarning, ...]

    def to_dict(self) -> Dict[str, object]:
        return {
            "version": self.version,
            "fileCount": self.file_count,
            "totalBytes": self.total_bytes,
            "directoryPatterns": list(self.directory_patterns),
            "fileTypeDistribution": {
                key: value for key, value in self.file_type_distribution
            },
            "representativePaths": list(self.representative_paths),
            "documentationCandidates": list(self.documentation_candidates),
            "imageCandidates": list(self.image_candidates),
            "videoCandidates": list(self.video_candidates),
            "annotationCandidates": list(self.annotation_candidates),
            "structuredMetadataCandidates": list(self.structured_metadata_candidates),
            "skippedPaths": [item.to_dict() for item in self.skipped_paths],
            "warnings": [item.to_dict() for item in self.warnings],
        }


def survey_snapshot(root: Path | str, limits: Optional[SurveyLimits] = None) -> DatasetSketch:
    """Inventory one previously safe snapshot without reading file contents."""

    policy = limits or SurveyLimits()
    root_path = Path(root).expanduser()
    if root_path.is_symlink() or not root_path.is_dir():
        raise SurveyError("snapshot root must be an existing non-symlink directory")
    root_path = root_path.resolve()

    file_count = 0
    total_bytes = 0
    directories: set[str] = set()
    type_counts: Dict[str, int] = {}
    representative: List[str] = []
    docs: List[str] = []
    images: List[str] = []
    videos: List[str] = []
    annotations: List[str] = []
    structured: List[str] = []
    skipped: List[SkippedPath] = []
    warnings: List[SurveyWarning] = []

    def add_skip(relative: str, code: str, reason: str) -> None:
        item = SkippedPath(relative or ".", code, reason)
        skipped.append(item)
        warnings.append(SurveyWarning(code, relative or ".", reason))

    def walk(directory: Path, depth: int) -> None:
        nonlocal file_count, total_bytes
        try:
            entries = sorted(os.scandir(directory), key=lambda item: item.name)
        except OSError as exc:
            relative = _safe_relative(directory, root_path)
            add_skip(relative, "READ_FAILED", f"directory cannot be read: {exc.__class__.__name__}")
            return
        for entry in entries:
            candidate = Path(entry.path)
            relative = _safe_relative(candidate, root_path)
            if entry.is_symlink():
                add_skip(relative, "SYMLINK_SKIPPED", "symbolic links are never followed")
                continue
            if _is_sensitive(relative):
                add_skip(relative, "SENSITIVE_FILE_SKIPPED", "sensitive file is excluded")
                continue
            try:
                if entry.is_dir(follow_symlinks=False):
                    directories.add(relative)
                    if depth >= policy.max_depth:
                        add_skip(relative, "DEPTH_LIMIT", "directory depth limit reached")
                    else:
                        walk(candidate, depth + 1)
                    continue
                if not entry.is_file(follow_symlinks=False):
                    add_skip(relative, "NON_REGULAR_SKIPPED", "only regular files are inspected")
                    continue
                stat = entry.stat(follow_symlinks=False)
            except OSError as exc:
                add_skip(relative, "READ_FAILED", f"file metadata unavailable: {exc.__class__.__name__}")
                continue
            if stat.st_size > policy.max_file_bytes:
                add_skip(relative, "FILE_SIZE_LIMIT", "file exceeds max_file_bytes")
                continue
            if file_count >= policy.max_files:
                add_skip(relative, "FILE_COUNT_LIMIT", "file count limit reached")
                continue
            if total_bytes + stat.st_size > policy.max_total_bytes:
                add_skip(relative, "TOTAL_SIZE_LIMIT", "snapshot byte limit reached")
                continue
            resolved = candidate.resolve(strict=False)
            if not _is_relative_to(resolved, root_path):
                add_skip(relative, "PATH_ESCAPE", "path resolves outside snapshot root")
                continue
            file_count += 1
            total_bytes += stat.st_size
            suffix = candidate.suffix.lower() or "<no_extension>"
            type_counts[suffix] = type_counts.get(suffix, 0) + 1
            if len(representative) < policy.max_representative_paths:
                representative.append(relative)
            lower_name = candidate.name.lower()
            if lower_name in DOC_NAMES or lower_name.startswith("readme."):
                docs.append(relative)
            if suffix in IMAGE_SUFFIXES:
                images.append(relative)
            if suffix in VIDEO_SUFFIXES:
                videos.append(relative)
            if suffix in ANNOTATION_SUFFIXES and _looks_like_annotation(relative):
                annotations.append(relative)
            if suffix in STRUCTURED_SUFFIXES:
                structured.append(relative)

    walk(root_path, 0)
    return DatasetSketch(
        version=1,
        file_count=file_count,
        total_bytes=total_bytes,
        directory_patterns=tuple(sorted(directories)),
        file_type_distribution=tuple(sorted(type_counts.items())),
        representative_paths=tuple(representative),
        documentation_candidates=tuple(docs),
        image_candidates=tuple(images),
        video_candidates=tuple(videos),
        annotation_candidates=tuple(annotations),
        structured_metadata_candidates=tuple(structured),
        skipped_paths=tuple(skipped),
        warnings=tuple(warnings),
    )


def _safe_relative(path: Path, root: Path) -> str:
    try:
        relative = path.relative_to(root)
    except ValueError as exc:
        raise SurveyError("path is outside snapshot root") from exc
    value = relative.as_posix()
    if value.startswith("/") or any(part in {"", ".."} for part in relative.parts):
        raise SurveyError("unsafe relative path")
    return value


def _is_sensitive(relative: str) -> bool:
    name = Path(relative).name.lower()
    return name in SENSITIVE_NAMES or name.startswith(".env.")


def _looks_like_annotation(relative: str) -> bool:
    tokens = set()
    for part in Path(relative).parts:
        stem = Path(part).stem
        tokens.update(stem.lower().replace("-", "_").split("_"))
    return bool(tokens & {"annotation", "annotations", "label", "labels", "mask", "masks", "bbox", "boxes", "track", "tracks", "keypoint", "keypoints"})


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
