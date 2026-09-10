"""Deterministic representative sampling for visual dataset candidates."""

from __future__ import annotations

import hashlib
import math
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional, Sequence, Tuple


class SamplingError(ValueError):
    pass


@dataclass(frozen=True)
class ImageCandidate:
    path: str
    content_hash: str
    stratum: Optional[str] = None
    metadata_available: bool = False
    embedding_available: bool = False


@dataclass(frozen=True)
class VideoCandidate:
    path: str
    content_hash: str
    duration_ms: Optional[int] = None
    frame_count: Optional[int] = None
    fps: Optional[float] = None
    stratum: Optional[str] = None
    metadata_available: bool = False
    embedding_available: bool = False


@dataclass(frozen=True)
class SampleRef:
    id: str
    kind: str
    path: str
    content_hash: str
    video_path: Optional[str] = None
    start_ms: Optional[int] = None
    end_ms: Optional[int] = None
    frame_start: Optional[int] = None
    frame_end: Optional[int] = None
    sampling_fps: Optional[float] = None

    def to_dict(self) -> dict[str, object]:
        result = {
            "id": self.id,
            "kind": self.kind,
            "path": self.path,
            "contentHash": self.content_hash,
        }
        optional = {
            "videoPath": self.video_path,
            "startMs": self.start_ms,
            "endMs": self.end_ms,
            "frameStart": self.frame_start,
            "frameEnd": self.frame_end,
            "samplingFps": self.sampling_fps,
        }
        result.update({key: value for key, value in optional.items() if value is not None})
        return result


@dataclass(frozen=True)
class SamplingSummary:
    strategy: str
    strata: Tuple[str, ...]
    candidate_count: int
    selected_count: int
    successful_observation_count: int
    failed_observation_count: int
    coverage: float
    selection_seed: int
    metadata_available: bool
    embedding_available: bool
    fallback_reason: Optional[str] = None
    coverage_losses: Tuple[str, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy": self.strategy,
            "strata": list(self.strata),
            "candidateCount": self.candidate_count,
            "selectedCount": self.selected_count,
            "successfulObservationCount": self.successful_observation_count,
            "failedObservationCount": self.failed_observation_count,
            "coverage": self.coverage,
            "selectionSeed": self.selection_seed,
            "metadataAvailable": self.metadata_available,
            "embeddingAvailable": self.embedding_available,
            "fallbackReason": self.fallback_reason,
            "coverageLosses": list(self.coverage_losses),
        }


def sample_images(
    root: Path | str,
    candidates: Sequence[ImageCandidate],
    budget: int,
    seed: int,
) -> tuple[Tuple[SampleRef, ...], SamplingSummary]:
    _validate_common(root, budget, seed)
    normalized = _validate_candidates(root, candidates)
    return _stratified(normalized, budget, seed, prefix="image")


def sample_videos(
    root: Path | str,
    candidates: Sequence[VideoCandidate],
    video_budget: int,
    frames_per_video: int,
    seed: int,
    clip_duration_ms: Optional[int] = None,
) -> tuple[Tuple[SampleRef, ...], SamplingSummary]:
    _validate_common(root, video_budget, seed)
    if isinstance(frames_per_video, bool) or frames_per_video < 1:
        raise SamplingError("frames_per_video must be positive")
    if clip_duration_ms is not None and clip_duration_ms < 1:
        raise SamplingError("clip_duration_ms must be positive")
    normalized = _validate_candidates(root, candidates)
    selected_videos, image_summary = _stratified(normalized, video_budget, seed, prefix="video")
    refs: list[SampleRef] = []
    losses = list(image_summary.coverage_losses)
    for video in normalized:
        if video.path not in {item.path for item in selected_videos}:
            continue
        if video.duration_ms is None or video.frame_count is None or video.fps is None or video.fps <= 0:
            losses.append(f"{video.path}:temporal_metadata_unavailable")
            continue
        duration = max(1, video.duration_ms)
        for index in range(frames_per_video):
            start = int((index + 0.5) * duration / frames_per_video)
            start = min(start, max(0, duration - 1))
            if clip_duration_ms:
                end = min(duration, start + clip_duration_ms)
                kind = "clip"
            else:
                end = min(duration, start + max(1, math.ceil(1000 / video.fps)))
                kind = "frame"
            frame_start = min(video.frame_count - 1, max(0, round(start * video.fps / 1000)))
            frame_end = min(video.frame_count - 1, max(frame_start, round((end - 1) * video.fps / 1000)))
            digest = _digest(f"{seed}|{video.path}|{index}|{start}|{end}")
            refs.append(
                SampleRef(
                    id=f"sample_{digest[:16]}",
                    kind=kind,
                    path=video.path,
                    content_hash=video.content_hash,
                    video_path=video.path,
                    start_ms=start,
                    end_ms=max(start + 1, end),
                    frame_start=frame_start,
                    frame_end=frame_end,
                    sampling_fps=video.fps,
                )
            )
    selected_count = len(refs)
    candidate_count = len(normalized)
    summary = SamplingSummary(
        strategy="temporal_uniform",
        strata=image_summary.strata,
        candidate_count=candidate_count,
        selected_count=selected_count,
        successful_observation_count=0,
        failed_observation_count=0,
        coverage=(selected_count / candidate_count) if candidate_count else 0.0,
        selection_seed=seed,
        metadata_available=all(item.metadata_available for item in normalized) if normalized else False,
        embedding_available=all(item.embedding_available for item in normalized) if normalized else False,
        fallback_reason=image_summary.fallback_reason,
        coverage_losses=tuple(sorted(set(losses))),
    )
    return tuple(refs), summary


def _stratified(
    candidates: Sequence[ImageCandidate | VideoCandidate],
    budget: int,
    seed: int,
    prefix: str,
) -> tuple[Tuple[SampleRef, ...], SamplingSummary]:
    if not candidates:
        return tuple(), SamplingSummary(
            "deterministic_fallback",
            tuple(),
            0,
            0,
            0,
            0,
            0.0,
            seed,
            False,
            False,
            "empty_candidates",
            ("no_candidate_media",),
        )
    groups: dict[str, list[ImageCandidate | VideoCandidate]] = {}
    for item in candidates:
        groups.setdefault(item.stratum or f"format:{Path(item.path).suffix.lower().lstrip('.') or 'unknown'}", []).append(item)
    quotas = _quotas(groups, min(budget, len(candidates)))
    selected: list[SampleRef] = []
    for stratum in sorted(groups):
        ranked = sorted(groups[stratum], key=lambda item: _rank(seed, stratum, item))
        for item in ranked[: quotas[stratum]]:
            selected.append(
                SampleRef(
                    id=f"sample_{_digest(f'{seed}|{prefix}|{item.path}')[:16]}",
                    kind="image" if prefix == "image" else "clip",
                    path=item.path,
                    content_hash=item.content_hash,
                )
            )
    metadata = all(item.metadata_available for item in candidates)
    embeddings = all(item.embedding_available for item in candidates)
    losses = []
    fallback = None
    strategy = "stratified"
    if not metadata or not embeddings:
        fallback = "clustering_metadata_or_embedding_unavailable"
        strategy = "deterministic_fallback"
        losses.append("no_metadata_or_embedding_centers")
    if len(selected) < len(candidates):
        losses.append("budget_limited_candidate_coverage")
    return (
        tuple(sorted(selected, key=lambda item: item.id)),
        SamplingSummary(
            strategy,
            tuple(sorted(groups)),
            len(candidates),
            len(selected),
            0,
            0,
            len(selected) / len(candidates),
            seed,
            metadata,
            embeddings,
            fallback,
            tuple(sorted(losses)),
        ),
    )


def _quotas(groups: dict[str, list[object]], budget: int) -> dict[str, int]:
    if budget <= 0:
        return {key: 0 for key in groups}
    total = sum(len(items) for items in groups.values())
    raw = {key: budget * len(items) / total for key, items in groups.items()}
    result = {key: min(len(groups[key]), int(value)) for key, value in raw.items()}
    remaining = budget - sum(result.values())
    order = sorted(groups, key=lambda key: (-(raw[key] - int(raw[key])), key))
    for key in order:
        if remaining and result[key] < len(groups[key]):
            result[key] += 1
            remaining -= 1
    return result


def _rank(seed: int, stratum: str, item: object) -> str:
    return _digest(f"{seed}|{stratum}|{getattr(item, 'path')}|{getattr(item, 'content_hash')}")


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _validate_common(root: Path | str, budget: int, seed: int) -> None:
    root_path = Path(root).expanduser()
    if root_path.is_symlink() or not root_path.is_dir():
        raise SamplingError("root must be an existing non-symlink directory")
    if isinstance(budget, bool) or not isinstance(budget, int) or budget < 1:
        raise SamplingError("budget must be a positive integer")
    if isinstance(seed, bool) or not isinstance(seed, int) or not 0 <= seed <= 2147483647:
        raise SamplingError("seed is outside the frozen range")


def _validate_candidates(
    root: Path | str, candidates: Sequence[ImageCandidate | VideoCandidate]
) -> Tuple[ImageCandidate | VideoCandidate, ...]:
    root_path = Path(root).expanduser().resolve()
    result = []
    for item in candidates:
        path = Path(item.path)
        if path.is_absolute() or ".." in path.parts or not re.fullmatch(r"sha256:[0-9a-f]{64}", item.content_hash):
            raise SamplingError("candidate path or content hash is unsafe")
        target = (root_path / path).resolve(strict=False)
        if target.parent != root_path and not _is_relative_to(target, root_path):
            raise SamplingError("candidate path escapes root")
        current = root_path
        for part in path.parts:
            current = current / part
            if current.is_symlink():
                raise SamplingError("symbolic links are never sampled")
        if not target.is_file():
            raise SamplingError(f"candidate is not a regular file: {item.path}")
        result.append(item)
    return tuple(sorted(result, key=lambda item: item.path))


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
