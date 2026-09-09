"""Closed-loop, contract-safe dataset adaptation.

The language model plans only a small, declarative adapter contract. This
module validates that contract, materialises safe field renames, profiles the
produced snapshot again, and runs the normal compatibility engine. A derived
resource is registered only when that second analysis is ``compatible``.
"""

from __future__ import annotations

import csv
import hashlib
import json
import shutil
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Mapping, Sequence, Tuple

from .compatibility import analyze_compatibility
from .dataset_resources import reprofile_dataset_snapshot
from .resource_store import ResourceStore
from .resource_types import ResourceRecord

Emit = Callable[[str, Dict[str, Any]], None]
_MAX_ADAPTATION_ATTEMPTS = 3
_PLAN_KEYS = {"summary", "fieldMappings", "operations", "warnings"}
_MAPPING_KEYS = {"datasetField", "modelField", "kind", "confidence", "reason"}
_OPERATION_KEYS = {"type", "sourceField", "targetField", "steps", "reason"}


class DatasetTransformError(ValueError):
    """Raised when a dataset cannot be adapted safely."""


class _NoOpCompatibilityClient:
    """Fallback for legacy library callers. The CLI always supplies a real LLM."""

    config = SimpleNamespace(model="deterministic-contract-verifier")
    last_model = "deterministic-contract-verifier"
    attempt_count = 1

    def complete_json(self, _system: str, _user: str) -> Dict[str, Any]:
        return {"summary": "确定性派生契约复检。", "fieldMappings": [], "transforms": [], "warnings": []}


def transform_dataset(
    store: ResourceStore,
    dataset_resource_id: str,
    model_resource_id: str,
    report: Mapping[str, Any],
    destination: Path,
    resource_id: str,
    emit: Emit | None = None,
    client: Any | None = None,
    max_attempts: int = _MAX_ADAPTATION_ATTEMPTS,
) -> Tuple[ResourceRecord, Dict[str, Any]]:
    """Build an adapted snapshot and register it only after a compatible recheck."""
    dataset = store.get(dataset_resource_id)
    model = store.get(model_resource_id)
    if dataset.kind != "dataset" or model.kind != "model":
        raise DatasetTransformError("转换需要一个数据集和一个模型")
    if not isinstance(report, Mapping) or report.get("status") != "adaptable":
        raise DatasetTransformError("只有状态为“转换后可用”的报告可以执行转换")
    if not isinstance(max_attempts, int) or isinstance(max_attempts, bool) or not 1 <= max_attempts <= _MAX_ADAPTATION_ATTEMPTS:
        raise DatasetTransformError(f"闭环尝试次数必须在 1 到 {_MAX_ADAPTATION_ATTEMPTS} 之间")

    source = (store.root / dataset.local_path).resolve()
    if not source.is_dir() or source.is_symlink():
        raise DatasetTransformError("源数据集本地快照不存在或不安全")
    target = Path(destination).resolve()
    if target == source or source in target.parents:
        raise DatasetTransformError("转换目标不能位于源数据集目录内")
    try:
        store.get(resource_id)
    except KeyError:
        pass
    else:
        raise DatasetTransformError("相同的已验证适配数据集已存在；请直接使用该资源")
    if target.exists():
        raise DatasetTransformError("转换目标已存在，拒绝覆盖现有数据")

    source_profile = store.load_profile(dataset.id)
    model_profile = store.load_profile(model.id)
    verifier = client or _NoOpCompatibilityClient()
    feedback = ""
    errors: list[str] = []
    for attempt in range(1, max_attempts + 1):
        _emit(emit, "stage", {"name": "adapt_plan", "status": "started", "attempt": attempt})
        try:
            plan = _request_agent_plan(verifier, source_profile, model_profile, report, feedback) if client else _plan_from_report(report, model_profile)
            _validate_plan(plan, source_profile, model_profile)
        except (ValueError, OSError) as exc:
            feedback = str(exc)
            errors.append(feedback)
            _emit(emit, "stage", {"name": "adapt_plan", "status": "rejected", "attempt": attempt, "message": feedback})
            continue
        _emit(emit, "stage", {"name": "adapt_plan", "status": "completed", "attempt": attempt, "summary": plan["summary"]})
        try:
            _materialise(source, target, plan["fieldMappings"], emit)
            manifest = _write_manifest(target, dataset, model, source_profile, model_profile, report, plan, attempt)
            _emit(emit, "stage", {"name": "reprofile", "status": "started", "attempt": attempt})
            observed, _count, _size = reprofile_dataset_snapshot(
                resource_id, f"{dataset.name} · 适配 {model.name}", "derived", f"derived:{dataset.id}", "transform", target, 500 * 1024 * 1024
            )
            profile = _contract_profile(observed, source_profile, model_profile, resource_id, dataset, model, plan, manifest)
            _emit(emit, "stage", {"name": "reprofile", "status": "completed", "attempt": attempt})
            _emit(emit, "stage", {"name": "verify", "status": "started", "attempt": attempt})
            verification = analyze_compatibility(profile, model_profile, verifier)
            _emit(emit, "stage", {"name": "verify", "status": "completed", "attempt": attempt, "reportStatus": verification.status})
        except json.JSONDecodeError:
            _remove_target(target)
            raise
        except Exception as exc:
            _remove_target(target)
            raise DatasetTransformError(f"适配产物执行或重新解析失败：{exc}") from exc

        if verification.status == "compatible":
            profile["verification"] = {"status": verification.status, "report": verification.to_dict(), "attempt": attempt}
            profile["transform"]["verified"] = True
            provenance = dict(profile["provenance"])
            record = ResourceRecord(
                id=resource_id, kind="dataset", source_type="derived", source=f"derived:{dataset.id}",
                revision=dataset.resolved_revision or dataset.revision,
                resolved_revision=f"transform-{_digest(manifest)[:12]}", name=profile["name"], status="ready",
                local_path=str(target.relative_to(store.root.resolve())), profile_path=f"profiles/datasets/{resource_id}.json",
                file_count=sum(1 for path in target.rglob("*") if path.is_file()),
                size_bytes=sum(path.stat().st_size for path in target.rglob("*") if path.is_file()),
                created_at=_now(), updated_at=_now(), warnings=list(profile.get("warnings", [])), provenance=provenance,
            )
            store.save(record, profile)
            _emit(emit, "stage", {"name": "complete", "status": "completed", "message": "适配数据集已生成并通过复检"})
            return record, profile

        feedback = _verification_feedback(verification.to_dict())
        errors.append(feedback)
        _remove_target(target)
        _emit(emit, "stage", {"name": "verify", "status": "rejected", "attempt": attempt, "message": feedback})
    raise DatasetTransformError("适配闭环未收敛，未登记派生数据集：" + "；".join(errors[-max_attempts:]))


def _request_agent_plan(client: Any, dataset: Mapping[str, Any], model: Mapping[str, Any], report: Mapping[str, Any], feedback: str) -> Dict[str, Any]:
    system = (
        "你是受约束的数据适配规划器。只返回 JSON，且只能包含 summary、fieldMappings、operations、warnings。"
        "fieldMappings 每项只能包含 datasetField、modelField、kind、confidence、reason。"
        "operations 每项只能包含 type、sourceField、targetField、steps、reason；type 只能是 preprocess。"
        "不得给出代码、命令、路径或未出现过的字段。所有模型必填字段必须有映射。"
        "steps 只能使用模型 inputContract.preprocessing 中已有的名称。"
    )
    user = json.dumps({
        "dataset": {key: dataset.get(key) for key in ("resourceId", "name", "modalities", "taskHints", "features")},
        "model": {key: model.get(key) for key in ("resourceId", "name", "tasks", "inputContract")},
        "basisReport": {key: report.get(key) for key in ("status", "fieldMappings", "transforms", "blockers", "warnings")},
        "previousVerificationFailure": feedback,
    }, ensure_ascii=False)
    return _normalise_plan(client.complete_json(system, user))


def _plan_from_report(report: Mapping[str, Any], model: Mapping[str, Any]) -> Dict[str, Any]:
    mappings = _mappings(report.get("fieldMappings", report.get("field_mappings", [])))
    steps = list(model.get("inputContract", {}).get("preprocessing", []))
    return {"summary": "依据兼容性报告生成的确定性适配契约。", "fieldMappings": mappings,
            "operations": [{"type": "preprocess", "sourceField": mappings[0]["datasetField"], "targetField": mappings[0]["modelField"], "steps": steps, "reason": "覆盖模型声明的预处理。"}] if steps and mappings else [],
            "warnings": ["此计划由兼容性报告派生，未调用规划智能体。"]}


def _normalise_plan(raw: object) -> Dict[str, Any]:
    if not isinstance(raw, Mapping) or set(raw) != _PLAN_KEYS:
        raise DatasetTransformError("适配智能体返回的计划结构无效")
    if not isinstance(raw.get("summary"), str) or not raw["summary"].strip():
        raise DatasetTransformError("适配计划缺少摘要")
    if not isinstance(raw.get("warnings"), list) or not all(isinstance(item, str) for item in raw["warnings"]):
        raise DatasetTransformError("适配计划 warnings 必须为字符串数组")
    return {"summary": raw["summary"].strip(), "fieldMappings": _mappings(raw.get("fieldMappings")), "operations": raw.get("operations"), "warnings": list(raw["warnings"])}


def _mappings(value: object) -> List[Dict[str, Any]]:
    if not isinstance(value, list):
        raise DatasetTransformError("字段映射必须是数组")
    result: List[Dict[str, Any]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping) or not {"datasetField", "modelField"} <= set(item) or set(item) - _MAPPING_KEYS:
            raise DatasetTransformError(f"字段映射 {index} 结构无效")
        source, target = item.get("datasetField"), item.get("modelField")
        confidence = item.get("confidence", 1.0)
        if not isinstance(source, str) or not source.strip() or not isinstance(target, str) or not target.strip() or isinstance(confidence, bool) or not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise DatasetTransformError(f"字段映射 {index} 缺少有效字段名或置信度")
        result.append({"datasetField": source.strip(), "modelField": target.strip(), "kind": item.get("kind", "transform"), "confidence": float(confidence), "reason": str(item.get("reason", "受约束适配计划"))})
    return result


def _validate_plan(plan: Mapping[str, Any], dataset: Mapping[str, Any], model: Mapping[str, Any]) -> None:
    features = {item.get("name"): item for item in dataset.get("features", []) if isinstance(item, Mapping) and isinstance(item.get("name"), str)}
    fields = {item.get("name"): item for item in model.get("inputContract", {}).get("fields", []) if isinstance(item, Mapping) and isinstance(item.get("name"), str)}
    seen_targets: set[str] = set()
    for mapping in plan["fieldMappings"]:
        source, target = mapping["datasetField"], mapping["modelField"]
        if source not in features or target not in fields:
            raise DatasetTransformError(f"适配计划引用了未知字段：{source} → {target}")
        if target in seen_targets:
            raise DatasetTransformError(f"适配计划重复写入模型字段：{target}")
        seen_targets.add(target)
        if not _types_compatible(str(features[source].get("dataType", "")), str(fields[target].get("dataType", ""))):
            raise DatasetTransformError(f"适配计划的数据类型不兼容：{source} → {target}")
    missing = [name for name, field in fields.items() if field.get("required", True) and name not in seen_targets]
    if missing:
        raise DatasetTransformError("适配计划未覆盖模型必需字段：" + "、".join(missing))
    operations = plan.get("operations")
    if not isinstance(operations, list):
        raise DatasetTransformError("适配计划 operations 必须是数组")
    expected = {str(step).strip().lower() for step in model.get("inputContract", {}).get("preprocessing", []) if isinstance(step, str) and step.strip()}
    delivered: set[str] = set()
    pairs = {(item["datasetField"], item["modelField"]) for item in plan["fieldMappings"]}
    for index, operation in enumerate(operations):
        if not isinstance(operation, Mapping) or set(operation) != _OPERATION_KEYS or operation.get("type") != "preprocess":
            raise DatasetTransformError(f"适配操作 {index} 不在白名单内")
        source, target, steps = operation.get("sourceField"), operation.get("targetField"), operation.get("steps")
        if (source, target) not in pairs or not isinstance(steps, list) or not all(isinstance(step, str) and step.strip() for step in steps):
            raise DatasetTransformError(f"适配操作 {index} 未绑定有效字段映射")
        normalised = {step.strip().lower() for step in steps}
        if not normalised <= expected:
            raise DatasetTransformError(f"适配操作 {index} 包含模型未声明的预处理")
        delivered.update(normalised)
    if expected != delivered:
        raise DatasetTransformError("适配计划没有精确覆盖模型声明的全部预处理步骤")


def _types_compatible(source: str, target: str) -> bool:
    source, target = source.strip().lower(), target.strip().lower()
    if source == target or {source, target} <= {"string", "text", "utf8"}:
        return True
    if source in {"image", "pixel", "pixels"} and target in {"image", "pixel", "pixels"}:
        return True
    numeric = {"int", "int8", "int16", "int32", "int64", "integer", "float", "float16", "float32", "float64", "double", "number", "classlabel", "categorical"}
    return source in numeric and target in numeric


def _materialise(source: Path, target: Path, mappings: Sequence[Mapping[str, Any]], emit: Emit | None) -> None:
    _remove_target(target)
    target.mkdir(parents=True, exist_ok=True)
    files = [path for path in source.rglob("*") if path.is_file() and not path.is_symlink()]
    _emit(emit, "stage", {"name": "execute", "status": "started", "fileCount": len(files)})
    transformed = 0
    for index, path in enumerate(files, start=1):
        destination = target / path.relative_to(source)
        destination.parent.mkdir(parents=True, exist_ok=True)
        if _is_transformable_data_file(path):
            _transform_file(path, destination, mappings); transformed += 1
        else:
            shutil.copy2(path, destination)
        _emit(emit, "progress", {"progress": index / max(1, len(files)), "fileCount": index, "totalFiles": len(files), "message": f"已处理 {index}/{len(files)} 个文件"})
    _emit(emit, "stage", {"name": "execute", "status": "completed", "transformedFiles": transformed, "copiedFiles": len(files) - transformed})


def _write_manifest(target: Path, dataset: ResourceRecord, model: ResourceRecord, source_profile: Mapping[str, Any], model_profile: Mapping[str, Any], report: Mapping[str, Any], plan: Mapping[str, Any], attempt: int) -> Dict[str, Any]:
    manifest = {"version": 2, "kind": "contract-adapter", "provenance": {"sourceDatasetId": dataset.id, "sourceDatasetName": dataset.name, "targetModelId": model.id, "targetModelName": model.name, "transformStatus": "verified"}, "plan": plan, "planDigest": _digest(plan), "sourceProfileDigest": _digest(source_profile), "targetProfileDigest": _digest(model_profile), "basisReportDigest": _digest(report), "attempt": attempt, "createdAt": _now()}
    (target / "datamodelmatch-transform.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def _contract_profile(observed: Mapping[str, Any], source_profile: Mapping[str, Any], model_profile: Mapping[str, Any], resource_id: str, dataset: ResourceRecord, model: ResourceRecord, plan: Mapping[str, Any], manifest: Mapping[str, Any]) -> Dict[str, Any]:
    profile = dict(observed)
    profile["resourceId"] = resource_id
    profile["name"] = f"{dataset.name} · 适配 {model.name}"
    profile["description"] = "受约束适配智能体生成的派生数据集；其适配契约已由标准兼容性分析复检。"
    target_fields = [dict(item) for item in model_profile["inputContract"]["fields"]]
    source_features = [dict(item) for item in source_profile.get("features", []) if isinstance(item, Mapping)]
    mapped_sources, target_names = {item["datasetField"] for item in plan["fieldMappings"]}, {item["name"] for item in target_fields}
    target_fields.extend(feature for feature in source_features if feature.get("name") not in mapped_sources and feature.get("name") not in target_names)
    profile["features"] = target_fields
    profile["modalities"] = list(dict.fromkeys([*model_profile["inputContract"]["modalities"], *profile.get("modalities", [])]))
    profile["taskHints"] = list(source_profile.get("taskHints", [])) or list(model_profile.get("tasks", []))
    profile["license"] = str(source_profile.get("license", profile.get("license", "unknown")))
    profile["source"] = {"type": "derived", "location": f"derived:{dataset.id}", "revision": "transform"}
    profile["provenance"] = dict(manifest["provenance"])
    profile["adapter"] = {"kind": "contract-adapter", "version": 1, "planDigest": manifest["planDigest"], "satisfiedPreprocessing": sorted({step.strip().lower() for operation in plan["operations"] for step in operation["steps"]}), "operations": list(plan["operations"])}
    profile["transform"] = {"fieldMappings": list(plan["fieldMappings"]), "manifest": "datamodelmatch-transform.json", "verified": False}
    return profile


def _verification_feedback(report: Mapping[str, Any]) -> str:
    dimensions = report.get("dimensions", [])
    failed = [str(item.get("name")) for item in dimensions if isinstance(item, Mapping) and item.get("status") != "compatible"]
    blockers = report.get("blockers", [])
    return "复检未通过；非兼容维度：" + "、".join(failed) + ("；阻断：" + "；".join(str(item) for item in blockers) if blockers else "")


def _is_tabular(path: Path) -> bool:
    return path.suffix.lower() in {".csv", ".json", ".jsonl", ".ndjson", ".parquet"}


def _is_transformable_data_file(path: Path) -> bool:
    return _is_tabular(path) and path.name.lower() not in {"dataset-metadata.json", "dataset_info.json", "dataset_infos.json", "datamodelmatch-transform.json"}


def _transform_file(source: Path, target: Path, mappings: Sequence[Mapping[str, Any]]) -> None:
    rename = {str(item["datasetField"]): str(item["modelField"]) for item in mappings}
    suffix = source.suffix.lower()
    if suffix == ".csv":
        with source.open("r", encoding="utf-8-sig", newline="", errors="replace") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                shutil.copy2(source, target); return
            fields = [rename.get(field, field) for field in reader.fieldnames]
            if len(fields) != len(set(fields)): raise DatasetTransformError("字段重命名会产生重复列")
            with target.open("w", encoding="utf-8", newline="") as output:
                writer = csv.DictWriter(output, fieldnames=fields); writer.writeheader()
                for row in reader: writer.writerow({rename.get(key, key): value for key, value in row.items()})
        return
    if suffix in {".jsonl", ".ndjson"}:
        with source.open("r", encoding="utf-8", errors="replace") as handle, target.open("w", encoding="utf-8") as output:
            for line in handle:
                if line.strip(): output.write(json.dumps(_rename_row(json.loads(line), rename), ensure_ascii=False) + "\n")
        return
    if suffix == ".json":
        value = json.loads(source.read_text(encoding="utf-8"))
        if isinstance(value, list): value = [_rename_row(row, rename) for row in value]
        elif isinstance(value, dict) and isinstance(value.get("data"), list): value = {**value, "data": [_rename_row(row, rename) for row in value["data"]]}
        elif isinstance(value, dict) and _looks_like_row(value): value = _rename_row(value, rename)
        target.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8"); return
    try:
        import pyarrow.parquet as pq
        table = pq.read_table(source); names = [rename.get(name, name) for name in table.column_names]
        if len(names) != len(set(names)): raise DatasetTransformError("字段重命名会产生重复列")
        pq.write_table(table.rename_columns(names), target)
    except ImportError as exc:
        raise DatasetTransformError("转换 Parquet 需要安装 pyarrow") from exc


def _rename_row(value: object, rename: Mapping[str, str]) -> object:
    if not isinstance(value, dict): return value
    result = {rename.get(str(key), str(key)): item for key, item in value.items()}
    if len(result) != len(value): raise DatasetTransformError("字段重命名会产生重复字段")
    return result


def _looks_like_row(value: Mapping[str, Any]) -> bool:
    return any(not isinstance(item, (dict, list)) for item in value.values())


def _digest(value: object) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest()


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _remove_target(target: Path) -> None:
    if target.exists():
        shutil.rmtree(target)


def _emit(emit: Emit | None, event: str, data: Dict[str, Any]) -> None:
    if emit: emit(event, data)
