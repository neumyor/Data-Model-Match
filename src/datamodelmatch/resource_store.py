"""Local persistence for imported resource snapshots and generated profiles."""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any, Dict, List

from .resource_types import ResourceRecord


class ResourceStore:
    """Persist resources under one ignored workspace directory."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self.catalog_path = root / "catalog.json"

    def ensure(self) -> None:
        for path in (
            self.root,
            self.root / "resources" / "datasets",
            self.root / "resources" / "models",
            self.root / "profiles" / "datasets",
            self.root / "profiles" / "models",
            self.root / "jobs",
        ):
            path.mkdir(parents=True, exist_ok=True)

    def list(self, kind: str | None = None) -> List[ResourceRecord]:
        records = [ResourceRecord.from_dict(item) for item in self._read_catalog()]
        if kind:
            records = [record for record in records if record.kind == kind]
        return sorted(records, key=lambda record: record.updated_at, reverse=True)

    def get(self, resource_id: str) -> ResourceRecord:
        for record in self.list():
            if record.id == resource_id:
                return record
        raise KeyError(f"Unknown resource: {resource_id}")

    def resource_path(self, resource_id: str) -> Path:
        """Return the validated local directory for a managed resource."""

        record = self.get(resource_id)
        return self._resource_path(record)

    def profile_path(self, resource_id: str) -> Path:
        """Return the validated profile path for a managed resource."""

        record = self.get(resource_id)
        return self._profile_path(record)

    def save(self, record: ResourceRecord, profile: Dict[str, Any]) -> None:
        self.ensure()
        self._resource_path(record)
        profile_path = self._profile_path(record)
        profile_path.parent.mkdir(parents=True, exist_ok=True)
        profile_path.write_text(
            json.dumps(profile, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        records = self._read_catalog()
        encoded = record.to_dict()
        for index, current in enumerate(records):
            if current.get("id") == record.id:
                records[index] = encoded
                break
        else:
            records.append(encoded)
        self.catalog_path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def load_profile(self, resource_id: str) -> Dict[str, Any]:
        record = self.get(resource_id)
        raw = json.loads(self._profile_path(record).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Resource profile must be an object")
        return raw

    def delete(self, resource_id: str) -> None:
        record = self.get(resource_id)
        resource_path = self._resource_path(record)
        profile_path = self._profile_path(record)
        shutil.rmtree(resource_path, ignore_errors=True)
        profile_path.unlink(missing_ok=True)
        remaining = [
            item for item in self._read_catalog()
            if item.get("id") != resource_id
        ]
        self.catalog_path.write_text(
            json.dumps(remaining, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    def _read_catalog(self) -> List[Dict[str, Any]]:
        self.ensure()
        if not self.catalog_path.is_file():
            return []
        raw = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        if not isinstance(raw, list):
            raise ValueError("Resource catalog must be an array")
        return [item for item in raw if isinstance(item, dict)]

    def _resource_path(self, record: ResourceRecord) -> Path:
        category = self._category(record)
        return self._managed_path(record.local_path, Path("resources") / category)

    def _profile_path(self, record: ResourceRecord) -> Path:
        category = self._category(record)
        return self._managed_path(record.profile_path, Path("profiles") / category)

    def _managed_path(self, relative: str, prefix: Path) -> Path:
        path = Path(relative)
        if path.is_absolute():
            raise ValueError("Managed resource paths must be relative")
        root = self.root.resolve()
        expected_root = (root / prefix).resolve()
        candidate = (root / path).resolve()
        try:
            candidate.relative_to(expected_root)
        except ValueError as exc:
            raise ValueError("Managed resource path escapes its allowed directory") from exc
        return candidate

    @staticmethod
    def _category(record: ResourceRecord) -> str:
        if record.kind == "dataset":
            return "datasets"
        if record.kind == "model":
            return "models"
        raise ValueError("Resource kind must be dataset or model")
