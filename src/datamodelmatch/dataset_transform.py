"""Create managed datasets adapted to a model input contract.

The transformation is intentionally conservative: it copies the source
snapshot, rewrites supported tabular files using the compatibility field
mapping, and never executes source repository code.
"""

from __future__ import annotations

import csv
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Sequence, Tuple

from .resource_store import ResourceStore
from .resource_types import ResourceRecord

Emit = Callable[[str, Dict[str, Any]], None]


class DatasetTransformError(ValueError):
    """Raised when a dataset cannot be adapted safely."""


def transform_dataset(
    store: ResourceStore,
    dataset_resource_id: str,
    model_resource_id: str,
    report: Mapping[str, Any],
    destination: Path,
    resource_id: str,
    emit: Emit | None = None,
) -> Tuple[ResourceRecord, Dict[str, Any]]:
    """Transform a managed dataset and return a new managed dataset record/profile.

    ``report.fieldMappings`` must contain mappings with ``datasetField`` and
    ``modelField``. Existing fields are retained; mapped fields are emitted
    under the model field name. The source snapshot is never modified.
    """
    dataset = store.get(dataset_resource_id)
    model = store.get(model_resource_id)
    if dataset.kind != "dataset" or model.kind != "model":
        raise DatasetTransformError("转换需要一个数据集和一个模型")
    if not isinstance(report, Mapping):
        raise DatasetTransformError("兼容性报告格式无效")
    if report.get("status") != "adaptable":
        raise DatasetTransformError("只有状态为“转换后可用”的报告可以执行转换")
    mappings = _mappings(report.get("fieldMappings", report.get("field_mappings", [])))
    if not mappings:
        raise DatasetTransformError("兼容性报告没有可执行的字段映射")

    source = (store.root / dataset.local_path).resolve()
    if not source.is_dir():
        raise DatasetTransformError("源数据集本地快照不存在")
    target = Path(destination).resolve()
    if target == source or source in target.parents:
        raise DatasetTransformError("转换目标不能位于源数据集目录内")

    _emit(emit, "stage", {"name": "prepare", "status": "started", "message": "准备转换任务"})
    if target.exists():
        shutil.rmtree(target)
    target.mkdir(parents=True, exist_ok=True)
    files = [path for path in source.rglob("*") if path.is_file() and not path.is_symlink()]
    _emit(emit, "stage", {"name": "prepare", "status": "completed", "fileCount": len(files)})

    transformed = 0
    skipped = 0
    _emit(emit, "stage", {"name": "transform", "status": "started"})
    for index, path in enumerate(files, start=1):
        relative = path.relative_to(source)
        destination_path = target / relative
        destination_path.parent.mkdir(parents=True, exist_ok=True)
        if _is_transformable_data_file(path):
            _transform_file(path, destination_path, mappings)
            transformed += 1
        else:
            shutil.copy2(path, destination_path)
            skipped += 1
        _emit(
            emit,
            "progress",
            {
                "progress": index / max(1, len(files)),
                "fileCount": index,
                "totalFiles": len(files),
                "message": f"已处理 {index}/{len(files)} 个文件",
            },
        )
    _emit(emit, "stage", {"name": "transform", "status": "completed", "fileCount": transformed})

    provenance = {
        "sourceDatasetId": dataset.id,
        "sourceDatasetName": dataset.name,
        "targetModelId": model.id,
        "targetModelName": model.name,
        "transformStatus": "completed",
    }
    manifest = {
        "version": 1,
        "provenance": provenance,
        "fieldMappings": list(mappings),
        "transformedFiles": transformed,
        "copiedFiles": skipped,
        "createdAt": _now(),
    }
    (target / "datamodelmatch-transform.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    profile = _build_profile(store.load_profile(dataset.id), model, resource_id, provenance, mappings, target)
    record = ResourceRecord(
        id=resource_id,
        kind="dataset",
        source_type="derived",
        source=f"derived:{dataset.id}",
        revision=dataset.resolved_revision or dataset.revision,
        resolved_revision=f"transform-{_now().replace(':', '').replace('-', '')}",
        name=f"{dataset.name} · 适配 {model.name}",
        status="ready",
        local_path=str(target.relative_to(store.root)),
        profile_path=f"profiles/datasets/{resource_id}.json",
        file_count=sum(1 for path in target.rglob("*") if path.is_file()),
        size_bytes=sum(path.stat().st_size for path in target.rglob("*") if path.is_file()),
        created_at=_now(),
        updated_at=_now(),
        warnings=[],
        provenance=provenance,
    )
    store.save(record, profile)
    _emit(emit, "stage", {"name": "complete", "status": "completed", "message": "适配数据集已生成"})
    return record, profile


def _mappings(value: object) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        raise DatasetTransformError("字段映射必须是数组")
    result: List[Dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            continue
        source = item.get("datasetField")
        target = item.get("modelField")
        if isinstance(source, str) and source.strip() and isinstance(target, str) and target.strip():
            result.append({
                "datasetField": source.strip(),
                "modelField": target.strip(),
                "kind": item.get("kind", "transform"),
                "confidence": item.get("confidence", 1),
                "reason": item.get("reason", "来自兼容性分析"),
            })
    return result


def _is_tabular(path: Path) -> bool:
    return path.suffix.lower() in {".csv", ".json", ".jsonl", ".ndjson", ".parquet"}


def _is_transformable_data_file(path: Path) -> bool:
    """Keep repository metadata intact while adapting sample files."""

    if path.suffix.lower() != ".json":
        return _is_tabular(path)
    name = path.name.lower()
    return name not in {
        "dataset-metadata.json",
        "dataset_info.json",
        "dataset_infos.json",
        "datamodelmatch-transform.json",
    }


def _transform_file(source: Path, target: Path, mappings: Sequence[Mapping[str, Any]]) -> None:
    rename = {str(item["datasetField"]): str(item["modelField"]) for item in mappings}
    suffix = source.suffix.lower()
    if suffix == ".csv":
        with source.open("r", encoding="utf-8-sig", newline="", errors="replace") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                shutil.copy2(source, target)
                return
            fields = [rename.get(field, field) for field in reader.fieldnames]
            with target.open("w", encoding="utf-8", newline="") as output:
                writer = csv.DictWriter(output, fieldnames=fields)
                writer.writeheader()
                for row in reader:
                    writer.writerow({rename.get(key, key): value for key, value in row.items()})
        return
    if suffix in {".jsonl", ".ndjson"}:
        with source.open("r", encoding="utf-8", errors="replace") as handle, target.open("w", encoding="utf-8") as output:
            for line in handle:
                if not line.strip():
                    continue
                value = json.loads(line)
                output.write(json.dumps(_rename_row(value, rename), ensure_ascii=False) + "\n")
        return
    if suffix == ".json":
        value = json.loads(source.read_text(encoding="utf-8"))
        if isinstance(value, list):
            value = [_rename_row(row, rename) for row in value]
        elif isinstance(value, dict):
            rows = value.get("data") if isinstance(value.get("data"), list) else None
            if rows is not None:
                value = dict(value)
                value["data"] = [_rename_row(row, rename) for row in rows]
            elif _looks_like_row(value):
                value = _rename_row(value, rename)
        target.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        return
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
        table = pq.read_table(source)
        names = [rename.get(name, name) for name in table.column_names]
        table = table.rename_columns(names)
        pq.write_table(table, target)
    except ImportError as exc:
        raise DatasetTransformError("转换 Parquet 需要安装 pyarrow") from exc


def _rename_row(value: object, rename: Mapping[str, str]) -> object:
    if not isinstance(value, dict):
        return value
    return {rename.get(str(key), str(key)): item for key, item in value.items()}


def _looks_like_row(value: Mapping[str, Any]) -> bool:
    return any(not isinstance(item, (dict, list)) for item in value.values())


def _build_profile(
    source_profile: Mapping[str, Any],
    model: ResourceRecord,
    resource_id: str,
    provenance: Mapping[str, Any],
    mappings: Sequence[Mapping[str, Any]],
    target: Path,
) -> Dict[str, Any]:
    profile = dict(source_profile)
    profile["resourceId"] = resource_id
    profile["name"] = f"{provenance['sourceDatasetName']} · 适配 {provenance['targetModelName']}"
    profile["description"] = f"由 {provenance['sourceDatasetName']} 转换生成，适配模型 {provenance['targetModelName']}。"
    features = []
    rename = {item["datasetField"]: item["modelField"] for item in mappings}
    for feature in profile.get("features", []):
        item = dict(feature)
        item["name"] = rename.get(item.get("name"), item.get("name"))
        features.append(item)
    profile["features"] = features
    profile["source"] = {"type": "derived", "location": f"derived:{provenance['sourceDatasetId']}", "revision": "transform"}
    profile["provenance"] = dict(provenance)
    profile["transform"] = {"fieldMappings": list(mappings), "generatedFiles": sum(1 for p in target.rglob("*") if p.is_file())}
    return profile


def _emit(emit: Emit | None, event: str, data: Dict[str, Any]) -> None:
    if emit:
        emit(event, data)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()
