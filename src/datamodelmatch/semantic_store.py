"""Durable isolated persistence for semantic profiles and profile-job lifecycle."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from contextlib import contextmanager
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Literal, Mapping, Optional, Tuple

from .resource_store import ResourceStore
from .semantic_types import (
    DatasetSemanticProfile,
    ProfileJobRequest,
    SemanticContractError,
    SemanticIdempotencyConflictError,
    SemanticJob,
    SemanticJobError,
    SemanticJobEvent,
    SemanticJobNotCancellableError,
    SemanticJobNotFoundError,
    SemanticJobTransitionError,
    SemanticStorageSafetyError,
    validate_id,
)

_TERMINAL: frozenset[str] = frozenset({"completed", "failed", "cancelled", "superseded"})
_TRANSITIONS: dict[str, frozenset[str]] = {
    "queued": frozenset({"running", "failed", "cancelled", "superseded"}),
    "running": frozenset({"partially_completed", "failed", "cancelled", "superseded"}),
    "partially_completed": frozenset({"running", "failed", "cancelled", "superseded"}),
    "completed": frozenset(),
    "failed": frozenset(),
    "cancelled": frozenset(),
    "superseded": frozenset(),
}


class SemanticArtifactStore:
    """Persist semantic artifacts beneath a legacy store without changing it."""

    def __init__(self, resource_store: ResourceStore) -> None:
        self._resource_store = resource_store
        self._resource_root = resource_store.root.absolute()
        self._root = self._resource_root / "semantic-artifacts" / "v1"

    def create_profile_job(self, request: ProfileJobRequest) -> SemanticJob:
        """Create or reuse the canonical profile job for one fixed snapshot."""

        with self._locked():
            record = self._resource_record(request.resource_id)
            if record.resolved_revision != request.snapshot_revision:
                raise SemanticContractError(
                    "snapshot revision is not the resource's current resolved revision"
                )
            index = self._read_index()
            canonical = self._canonical_request_key(request)
            explicit = request.idempotency_key
            if explicit is not None:
                existing = index["explicit"].get(explicit)
                if existing is not None:
                    if existing["canonical"] != canonical:
                        raise SemanticIdempotencyConflictError(
                            "explicit idempotency key was used for a different profile request"
                        )
                    return self._load_job(existing["jobId"])
            existing_job_id = index["canonical"].get(canonical)
            if existing_job_id is not None:
                job = self._load_job(existing_job_id)
                if explicit is not None:
                    index["explicit"][explicit] = {"canonical": canonical, "jobId": job.job_id}
                    self._write_index(index)
                return job

            job_id = f"job_{uuid.uuid4().hex}"
            idempotency_key = explicit or f"profile-{canonical}"
            now = _timestamp()
            job = SemanticJob(
                job_id=job_id,
                status="queued",
                request=request,
                created_at=now,
                updated_at=now,
                attempt=0,
                max_attempts=0,
                idempotency_key=idempotency_key,
            )
            self._write_job(job)
            index["canonical"][canonical] = job_id
            if explicit is not None:
                index["explicit"][explicit] = {"canonical": canonical, "jobId": job_id}
            self._write_index(index)
            return job

    def get_job(self, job_id: str) -> SemanticJob:
        validate_id(job_id, "job_id")
        with self._locked():
            return self._load_job(job_id)

    def start_job(self, job_id: str) -> SemanticJob:
        with self._locked():
            job = self._load_job(job_id)
            if job.status == "running":
                return job
            if job.status != "queued":
                raise SemanticJobTransitionError("only queued jobs can start")
            updated = replace(
                job,
                status="running",
                attempt=job.attempt + 1,
                updated_at=_timestamp(),
            )
            self._write_job(updated)
            return updated

    def mark_partially_completed(self, job_id: str) -> SemanticJob:
        return self._transition(job_id, "partially_completed")

    def fail_job(self, job_id: str, error: SemanticJobError) -> SemanticJob:
        with self._locked():
            job = self._load_job(job_id)
            updated = self._transition_locked(job, "failed", error=error)
            self._append_event_locked(
                updated,
                "error",
                {"version": 1, "error": error.to_dict()},
            )
            self._append_end_locked(updated, result_available=False)
            return updated

    def cancel_job(self, job_id: str) -> SemanticJob:
        with self._locked():
            job = self._load_job(job_id)
            if job.status == "cancelled":
                return job
            if job.status not in {"queued", "running", "partially_completed"}:
                raise SemanticJobNotCancellableError(
                    f"job {job.job_id} cannot be cancelled from {job.status}"
                )
            updated = self._transition_locked(job, "cancelled")
            self._append_end_locked(updated, result_available=False)
            return updated

    def publish_profile(self, job_id: str, profile: DatasetSemanticProfile) -> SemanticJob:
        """Atomically publish a complete profile only if its revision still wins."""

        with self._locked():
            job = self._load_job(job_id)
            if job.status != "running":
                raise SemanticJobTransitionError("only running jobs can publish a complete profile")
            self._validate_profile_binding(job, profile)
            record = self._resource_record(job.request.resource_id)
            if record.resolved_revision != job.request.snapshot_revision:
                updated = self._transition_locked(
                    job,
                    "superseded",
                    error=SemanticJobError(
                        code="STALE_JOB_SUPERSEDED",
                        message="The resource resolved revision changed before profile publication.",
                        retryable=False,
                    ),
                )
                self._append_event_locked(
                    updated,
                    "warning",
                    {"code": "STALE_REVISION", "message": "Profile publication was superseded."},
                )
                self._append_end_locked(updated, result_available=False)
                return updated

            profile_ref = self._profile_ref(job)
            self._write_json(self._root / profile_ref, profile.to_dict())
            self._write_json(
                self._published_path(job.request.resource_id),
                {"version": 1, "profileRef": profile_ref, "jobId": job.job_id},
            )
            updated = replace(
                job,
                status="completed",
                result_ref=profile_ref,
                updated_at=_timestamp(),
            )
            self._write_job(updated)
            self._append_event_locked(
                updated,
                "result",
                {"resultType": "dataset_semantic_profile", "resultId": updated.job_id},
            )
            self._append_end_locked(updated, result_available=True)
            return updated

    def get_profile_for_job(self, job_id: str) -> Optional[DatasetSemanticProfile]:
        with self._locked():
            job = self._load_job(job_id)
            if job.result_ref is None:
                return None
            return self._load_profile_ref(job.result_ref)

    def get_published_profile(self, resource_id: str) -> Optional[DatasetSemanticProfile]:
        validate_id(resource_id, "resource_id")
        with self._locked():
            path = self._published_path(resource_id)
            if not self._safe_exists(path):
                return None
            raw = self._read_json(path)
            if set(raw) != {"version", "profileRef", "jobId"} or raw.get("version") != 1:
                raise SemanticContractError("published profile pointer is malformed")
            profile_ref = raw.get("profileRef")
            if not isinstance(profile_ref, str):
                raise SemanticContractError("published profile pointer has no profile reference")
            return self._load_profile_ref(profile_ref)

    def list_events(self, job_id: str, after_event_id: int = 0) -> Tuple[SemanticJobEvent, ...]:
        validate_id(job_id, "job_id")
        if not isinstance(after_event_id, int) or after_event_id < 0:
            raise SemanticContractError("after_event_id must be a non-negative integer")
        with self._locked():
            self._load_job(job_id)
            return tuple(
                event
                for event in self._list_events_locked(job_id)
                if event.event_id > after_event_id
            )

    def emit_stage(
        self,
        job_id: str,
        stage: Literal["survey", "inspection", "structural", "sampling", "vision", "aggregation", "fusion", "matching"],
        status: Literal["started", "completed", "skipped"],
    ) -> SemanticJobEvent:
        return self._emit(job_id, "stage", {"stage": stage, "status": status})

    def emit_progress(
        self,
        job_id: str,
        stage: Literal["survey", "inspection", "structural", "sampling", "vision", "aggregation", "fusion", "matching"],
        completed: int,
        total: int,
    ) -> SemanticJobEvent:
        if not isinstance(completed, int) or not isinstance(total, int) or completed < 0 or total < 0 or completed > total:
            raise SemanticContractError("progress must be non-negative and completed cannot exceed total")
        return self._emit(
            job_id,
            "progress",
            {"stage": stage, "completed": completed, "total": total},
        )

    def emit_warning(
        self,
        job_id: str,
        code: Literal["SAMPLE_FAILURE", "INSUFFICIENT_COVERAGE", "UNSUPPORTED_MEDIA", "STALE_REVISION"],
        message: str,
    ) -> SemanticJobEvent:
        if not isinstance(message, str) or not message or len(message) > 1024:
            raise SemanticContractError("warning message must be a non-empty string up to 1024 characters")
        return self._emit(job_id, "warning", {"code": code, "message": message})

    def _emit(
        self,
        job_id: str,
        event_type: Literal["stage", "progress", "warning"],
        data: Mapping[str, object],
    ) -> SemanticJobEvent:
        with self._locked():
            job = self._load_job(job_id)
            if job.status in _TERMINAL:
                raise SemanticJobTransitionError("terminal jobs cannot emit new events")
            return self._append_event_locked(job, event_type, data)

    def _transition(self, job_id: str, target: Literal["partially_completed"]) -> SemanticJob:
        with self._locked():
            job = self._load_job(job_id)
            return self._transition_locked(job, target)

    def _transition_locked(
        self,
        job: SemanticJob,
        target: Literal["partially_completed", "failed", "cancelled", "superseded"],
        error: Optional[SemanticJobError] = None,
    ) -> SemanticJob:
        if target not in _TRANSITIONS[job.status]:
            raise SemanticJobTransitionError(f"illegal semantic job transition: {job.status} -> {target}")
        updated = replace(
            job,
            status=target,
            updated_at=_timestamp(),
            error=error,
        )
        self._write_job(updated)
        return updated

    def _append_end_locked(self, job: SemanticJob, result_available: bool) -> SemanticJobEvent:
        existing = self._list_events_locked(job.job_id)
        if existing and existing[-1].event_type == "end":
            raise SemanticContractError("terminal job already has an end event")
        return self._append_event_locked(
            job,
            "end",
            {"status": job.status, "resultAvailable": result_available},
        )

    def _append_event_locked(
        self,
        job: SemanticJob,
        event_type: Literal["stage", "progress", "warning", "result", "error", "end"],
        data: Mapping[str, object],
    ) -> SemanticJobEvent:
        prior = self._list_events_locked(job.job_id)
        event = SemanticJobEvent(
            job_id=job.job_id,
            event_id=len(prior) + 1,
            timestamp=_timestamp(),
            event_type=event_type,
            data_json=json.dumps(data, ensure_ascii=False, sort_keys=True, separators=(",", ":")),
        )
        path = self._event_path(job.job_id)
        self._ensure_root()
        self._ensure_parent(path.parent)
        flags = os.O_WRONLY | os.O_CREAT | os.O_APPEND
        descriptor = os.open(path, flags, 0o600)
        try:
            with os.fdopen(descriptor, "a", encoding="utf-8") as handle:
                handle.write(json.dumps(event.to_dict(), ensure_ascii=False, sort_keys=True))
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
        finally:
            try:
                os.close(descriptor)
            except OSError:
                pass
        return event

    def _list_events_locked(self, job_id: str) -> Tuple[SemanticJobEvent, ...]:
        path = self._event_path(job_id)
        if not self._safe_exists(path):
            return ()
        events: list[SemanticJobEvent] = []
        previous = 0
        for line in self._read_text(path).splitlines():
            try:
                raw = json.loads(line)
            except json.JSONDecodeError as exc:
                raise SemanticContractError("stored event log contains invalid JSON") from exc
            if not isinstance(raw, Mapping):
                raise SemanticContractError("stored event log contains a non-object event")
            event = SemanticJobEvent.from_dict(raw)
            if event.job_id != job_id or event.event_id != previous + 1:
                raise SemanticContractError("stored event log is not ordered and contiguous")
            previous = event.event_id
            events.append(event)
        return tuple(events)

    def _validate_profile_binding(self, job: SemanticJob, profile: DatasetSemanticProfile) -> None:
        if (
            profile.resource_id != job.request.resource_id
            or profile.snapshot_revision != job.request.snapshot_revision
            or profile.configuration_fingerprint != job.request.configuration_fingerprint
        ):
            raise SemanticContractError("profile bindings do not match the profile job request")

    def _resource_record(self, resource_id: str):
        try:
            return self._resource_store.get(resource_id)
        except KeyError as exc:
            raise SemanticContractError(f"resource {resource_id} does not exist") from exc

    def _load_job(self, job_id: str) -> SemanticJob:
        path = self._job_path(job_id)
        if not self._safe_exists(path):
            raise SemanticJobNotFoundError(job_id)
        return SemanticJob.from_dict(self._read_json(path))

    def _write_job(self, job: SemanticJob) -> None:
        self._write_json(self._job_path(job.job_id), job.to_dict())

    def _load_profile_ref(self, profile_ref: str) -> DatasetSemanticProfile:
        path = self._root / profile_ref
        self._assert_safe_path(path)
        return DatasetSemanticProfile.from_dict(self._read_json(path))

    def _read_index(self) -> dict[str, dict[str, object]]:
        path = self._index_path()
        if not self._safe_exists(path):
            return {"canonical": {}, "explicit": {}}
        raw = self._read_json(path)
        if set(raw) != {"version", "canonical", "explicit"} or raw.get("version") != 1:
            raise SemanticContractError("semantic idempotency index is malformed")
        canonical = raw["canonical"]
        explicit = raw["explicit"]
        if not isinstance(canonical, dict) or not isinstance(explicit, dict):
            raise SemanticContractError("semantic idempotency index entries are malformed")
        for key, job_id in canonical.items():
            if not isinstance(key, str) or not isinstance(job_id, str):
                raise SemanticContractError("semantic canonical idempotency index is malformed")
        for key, binding in explicit.items():
            if (
                not isinstance(key, str)
                or not isinstance(binding, dict)
                or set(binding) != {"canonical", "jobId"}
                or not isinstance(binding["canonical"], str)
                or not isinstance(binding["jobId"], str)
            ):
                raise SemanticContractError("semantic explicit idempotency index is malformed")
        return {"canonical": canonical, "explicit": explicit}

    def _write_index(self, index: Mapping[str, object]) -> None:
        self._write_json(self._index_path(), {"version": 1, **index})

    def _canonical_request_key(self, request: ProfileJobRequest) -> str:
        payload = json.dumps(request.canonical_tuple(), separators=(",", ":"), ensure_ascii=True)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def _profile_ref(self, job: SemanticJob) -> str:
        key = self._canonical_request_key(job.request)
        return f"profiles/{job.request.resource_id}/{key}.json"

    def _job_path(self, job_id: str) -> Path:
        return self._root / "jobs" / f"{validate_id(job_id, 'job_id')}.json"

    def _event_path(self, job_id: str) -> Path:
        return self._root / "events" / f"{validate_id(job_id, 'job_id')}.jsonl"

    def _published_path(self, resource_id: str) -> Path:
        return self._root / "published" / f"{validate_id(resource_id, 'resource_id')}.json"

    def _index_path(self) -> Path:
        return self._root / "idempotency.json"

    @contextmanager
    def _locked(self) -> Iterator[None]:
        self._ensure_root()
        path = self._root / ".lock"
        self._assert_safe_path(path.parent)
        descriptor = os.open(path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            if os.name == "nt":
                import msvcrt

                # msvcrt.locking() locks bytes starting at the current file
                # position and requires the range to exist.
                if os.path.getsize(path) == 0:
                    os.write(descriptor, b"\0")
                os.lseek(descriptor, 0, os.SEEK_SET)
                msvcrt.locking(descriptor, msvcrt.LK_LOCK, 1)
            else:
                import fcntl

                fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            try:
                if os.name == "nt":
                    import msvcrt

                    os.lseek(descriptor, 0, os.SEEK_SET)
                    msvcrt.locking(descriptor, msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(descriptor, fcntl.LOCK_UN)
            finally:
                os.close(descriptor)

    def _ensure_root(self) -> None:
        if not self._resource_root.exists():
            raise SemanticStorageSafetyError("resource store root must exist before semantic artifacts")
        self._assert_not_symlink(self._resource_root)
        current = self._resource_root
        for segment in ("semantic-artifacts", "v1", "jobs", "events", "profiles", "published"):
            if segment in {"jobs", "events", "profiles", "published"}:
                current = self._root / segment
            elif segment == "semantic-artifacts":
                current = self._resource_root / segment
            else:
                current = current / segment
            if current.exists():
                self._assert_not_symlink(current)
            else:
                current.mkdir(mode=0o700)

    def _write_json(self, path: Path, value: Mapping[str, object]) -> None:
        self._ensure_root()
        self._ensure_parent(path.parent)
        if path.exists():
            self._assert_not_symlink(path)
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")
        descriptor, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(encoded)
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, path)
        finally:
            if os.path.exists(temporary):
                os.unlink(temporary)

    def _read_json(self, path: Path) -> dict[str, object]:
        self._assert_safe_path(path)
        try:
            raw = json.loads(self._read_text(path))
        except json.JSONDecodeError as exc:
            raise SemanticContractError(f"semantic artifact {path.name} contains invalid JSON") from exc
        if not isinstance(raw, dict):
            raise SemanticContractError(f"semantic artifact {path.name} must be an object")
        return raw

    def _read_text(self, path: Path) -> str:
        self._assert_safe_path(path)
        if not path.is_file():
            raise SemanticStorageSafetyError(f"semantic artifact {path.name} is not a regular file")
        return path.read_text(encoding="utf-8")

    def _safe_exists(self, path: Path) -> bool:
        self._assert_safe_path(path, allow_missing=True)
        return path.exists()

    def _assert_safe_path(self, path: Path, allow_missing: bool = False) -> None:
        try:
            relative = path.absolute().relative_to(self._root.absolute())
        except ValueError as exc:
            raise SemanticStorageSafetyError("semantic artifact path escapes the semantic root") from exc
        if ".." in relative.parts:
            raise SemanticStorageSafetyError("semantic artifact path may not traverse parent directories")
        current = self._root
        if current.exists():
            self._assert_not_symlink(current)
        else:
            if allow_missing:
                return
            self._ensure_root()
        for segment in relative.parts:
            current = current / segment
            if current.exists():
                self._assert_not_symlink(current)
            elif not allow_missing:
                break

    def _ensure_parent(self, path: Path) -> None:
        self._assert_safe_path(path, allow_missing=True)
        relative = path.absolute().relative_to(self._root.absolute())
        current = self._root
        for segment in relative.parts:
            current = current / segment
            if current.exists():
                self._assert_not_symlink(current)
            else:
                current.mkdir(mode=0o700)

    @staticmethod
    def _assert_not_symlink(path: Path) -> None:
        if path.is_symlink():
            raise SemanticStorageSafetyError(f"semantic artifact path may not contain symlinks: {path.name}")


def _timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
