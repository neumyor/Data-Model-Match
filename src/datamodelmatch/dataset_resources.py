"""Safe, synchronous acquisition and static profiling of dataset resources.

This module intentionally uses only the Python standard library.  It never
executes downloaded code or dataset loading scripts: Hugging Face imports read
repository metadata and copy only recognised data files, while local imports
copy regular files and skip all symbolic links.
"""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
import shutil
import tempfile
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener

from .resource_types import (
    DatasetFeature,
    DatasetProfile,
    DatasetSplit,
    Evidence,
    ResourceRecord,
    SourceRef,
)


DEFAULT_DOWNLOAD_LIMIT = 50 * 1024 * 1024
DEFAULT_SEARCH_LIMIT = 20
DEFAULT_TIMEOUT_SECONDS = 20
SAMPLE_ROW_LIMIT = 100
SAMPLE_FILE_LIMIT = 8
CHUNK_SIZE = 64 * 1024
SUPPORTED_DOWNLOAD_MODES = frozenset({"metadata", "sample", "full"})
SUPPORTED_SOURCE_TYPES = frozenset({"huggingface", "local"})
DATA_SUFFIXES = frozenset({".csv", ".json", ".jsonl", ".ndjson", ".parquet"})
SENSITIVE_FILENAMES = frozenset({
    ".env",
    ".env.local",
    ".env.production",
    "config.llm.json",
    "credentials.json",
    "secrets.json",
})
IGNORED_DIR_NAMES = frozenset({
    ".git", ".ssh", ".aws", ".gnupg", ".kube", "__pycache__",
    ".venv", "venv", "node_modules",
})
_HF_WEB_HOSTS = frozenset({"huggingface.co", "www.huggingface.co"})
_HF_CONTENT_HOST_SUFFIXES = (".huggingface.co", ".xethub.hf.co", ".cdn.hf.co")
_SPLIT_RE = re.compile(r"(?:^|[_./-])(train|validation|valid|val|test|dev)(?:[_./-]|$)", re.I)

Emit = Callable[[str, Dict[str, Any]], None]


class DatasetResourceError(ValueError):
    """Raised when dataset acquisition or static analysis cannot proceed."""


@dataclass(frozen=True)
class _FileInfo:
    path: Path
    relative_path: str
    size_bytes: int


class _SafeRedirectHandler(HTTPRedirectHandler):
    """Reject redirects outside the Hugging Face first-party content domains."""

    def redirect_request(
        self,
        req: Request,
        fp: Any,
        code: int,
        msg: str,
        headers: Any,
        newurl: str,
    ) -> Request | None:
        _validate_huggingface_url(newurl, allow_content_hosts=True)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def search_huggingface_datasets(query: str, limit: int = DEFAULT_SEARCH_LIMIT) -> List[Dict[str, Any]]:
    """Search Hugging Face datasets without downloading repository contents.

    Returns compact, JSON-serialisable candidate dictionaries.  The API result
    is intentionally normalised so callers do not depend on Hugging Face's
    complete response schema.
    """

    if not isinstance(query, str) or not query.strip():
        raise DatasetResourceError("Search query must be a non-empty string")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise DatasetResourceError("Search limit must be an integer between 1 and 100")

    url = "https://huggingface.co/api/datasets?" + urlencode(
        {"search": query.strip(), "limit": str(limit)}
    )
    raw = _get_json(url)
    if not isinstance(raw, list):
        raise DatasetResourceError("Hugging Face search returned an unexpected response")

    results: List[Dict[str, Any]] = []
    for item in raw[:limit]:
        if not isinstance(item, Mapping):
            continue
        dataset_id = item.get("id") or item.get("_id")
        if not isinstance(dataset_id, str) or not dataset_id.strip():
            continue
        card_data = item.get("cardData")
        if not isinstance(card_data, Mapping):
            card_data = {}
        results.append(
            {
                "id": dataset_id.strip(),
                "name": dataset_id.strip().split("/")[-1],
                "author": _optional_text(item.get("author")),
                "lastModified": _optional_text(item.get("lastModified")),
                "downloads": _integer_or_none(item.get("downloads")),
                "likes": _integer_or_none(item.get("likes")),
                "tags": _string_list(item.get("tags")),
                "description": _optional_text(card_data.get("pretty_name"))
                or _optional_text(item.get("description")),
                "license": _license_from_card(card_data),
            }
        )
    return results


def import_dataset(
    source_type: str,
    source: str,
    revision: str,
    destination: Path | str,
    resource_id: str,
    download_mode: str,
    max_bytes: int,
    emit: Optional[Emit] = None,
) -> Tuple[ResourceRecord, Dict[str, Any]]:
    """Import one dataset into ``destination`` and return its record and profile.

    ``destination`` is the final directory for one resource snapshot.  Existing
    contents are replaced only after all required validation has succeeded.
    ``metadata`` never downloads repository data files, ``sample`` downloads a
    limited set of recognised data files, and ``full`` downloads every
    recognised static data file subject to ``max_bytes``.
    """

    source_type = _required_choice(source_type, "source_type", SUPPORTED_SOURCE_TYPES)
    if not isinstance(source, str) or not source.strip():
        raise DatasetResourceError("source must be a non-empty string")
    if not isinstance(revision, str) or not revision.strip():
        raise DatasetResourceError("revision must be a non-empty string")
    download_mode = _required_choice(download_mode, "download_mode", SUPPORTED_DOWNLOAD_MODES)
    if isinstance(max_bytes, bool) or not isinstance(max_bytes, int) or max_bytes < 1:
        raise DatasetResourceError("max_bytes must be a positive integer")
    resource_id = _safe_resource_id(resource_id)
    target = Path(destination).expanduser()
    if target.exists() and target.is_symlink():
        raise DatasetResourceError("destination must not be a symbolic link")
    target = target.resolve()

    _emit(emit, "stage", {"name": "discovering", "status": "started", "sourceType": source_type})
    if source_type == "huggingface":
        record, profile = _import_huggingface(
            source.strip(),
            revision.strip(),
            target,
            resource_id,
            download_mode,
            max_bytes,
            emit,
        )
    else:
        record, profile = _import_local(
            source.strip(),
            revision.strip(),
            target,
            resource_id,
            max_bytes,
            emit,
        )
    _emit(emit, "result", {"record": record.to_dict(), "profile": profile})
    return record, profile


def _import_huggingface(
    source: str,
    revision: str,
    target: Path,
    resource_id: str,
    download_mode: str,
    max_bytes: int,
    emit: Optional[Emit],
) -> Tuple[ResourceRecord, Dict[str, Any]]:
    dataset_id = _parse_huggingface_dataset(source)
    api_url = (
        "https://huggingface.co/api/datasets/"
        + quote(dataset_id, safe="/")
        + "/revision/"
        + quote(revision, safe="")
    )
    metadata = _get_json(api_url)
    if not isinstance(metadata, Mapping):
        raise DatasetResourceError("Hugging Face dataset metadata returned an unexpected response")
    resolved_revision = _optional_text(metadata.get("sha")) or revision
    siblings = metadata.get("siblings")
    if not isinstance(siblings, list):
        siblings = []
    files = _huggingface_files(siblings)
    card_data = metadata.get("cardData")
    if not isinstance(card_data, Mapping):
        card_data = {}
    _emit(
        emit,
        "evidence",
        {
            "kind": "repository_metadata",
            "source": f"huggingface:{dataset_id}@{resolved_revision}",
            "detail": f"Discovered {len(files)} recognised static data files",
        },
    )
    _emit(emit, "stage", {"name": "discovering", "status": "completed"})

    with _staging_directory(target) as staging:
        _write_json(staging / "dataset-metadata.json", dict(metadata))
        downloaded: List[str] = []
        if download_mode != "metadata":
            candidates = files if download_mode == "full" else files[:SAMPLE_FILE_LIMIT]
            _emit(emit, "stage", {"name": "downloading", "status": "started", "fileCount": len(candidates)})
            downloaded = _download_huggingface_files(
                dataset_id,
                resolved_revision,
                candidates,
                staging,
                max_bytes,
                emit,
            )
            _emit(emit, "stage", {"name": "downloading", "status": "completed", "fileCount": len(downloaded)})
        _emit(emit, "stage", {"name": "scanning", "status": "started"})
        file_infos, scan_warnings = _safe_inventory(staging, max_bytes)
        profile = _build_profile(
            resource_id=resource_id,
            name=_optional_text(metadata.get("id")) or dataset_id.split("/")[-1],
            description=_optional_text(metadata.get("description"))
            or _optional_text(card_data.get("pretty_name"))
            or f"Hugging Face dataset {dataset_id}",
            source_type="huggingface",
            source_location=dataset_id,
            revision=resolved_revision,
            file_infos=file_infos,
            source_metadata=metadata,
            source_warnings=scan_warnings
            + ([] if downloaded or download_mode != "metadata" else ["No recognised static sample files found"]),
        )
        _emit(emit, "stage", {"name": "scanning", "status": "completed", "fileCount": len(file_infos)})
        _replace_directory(staging, target)

    now = _iso_now()
    file_infos, scan_warnings = _safe_inventory(target, max_bytes)
    profile["warnings"] = _unique_strings(profile["warnings"] + scan_warnings)
    record = ResourceRecord(
        id=resource_id,
        kind="dataset",
        source_type="huggingface",
        source=dataset_id,
        revision=revision,
        resolved_revision=resolved_revision,
        name=profile["name"],
        status="ready" if profile["completeness"] >= 0.5 else "needs_review",
        local_path=str(target),
        profile_path=f"profiles/datasets/{resource_id}.json",
        file_count=len(file_infos),
        size_bytes=sum(item.size_bytes for item in file_infos),
        created_at=now,
        updated_at=now,
        warnings=list(profile["warnings"]),
    )
    return record, profile


def _import_local(
    source: str,
    revision: str,
    target: Path,
    resource_id: str,
    max_bytes: int,
    emit: Optional[Emit],
) -> Tuple[ResourceRecord, Dict[str, Any]]:
    origin = Path(source).expanduser()
    if not origin.exists():
        raise DatasetResourceError(f"Local dataset directory does not exist: {origin}")
    if origin.is_symlink() or not origin.is_dir():
        raise DatasetResourceError("Local dataset source must be a non-symbolic-link directory")
    origin = origin.resolve()
    if target == origin or _is_relative_to(target, origin):
        raise DatasetResourceError("destination must not be inside the source directory")
    resolved_revision = _local_revision(origin)
    _emit(emit, "stage", {"name": "discovering", "status": "completed"})

    with _staging_directory(target) as staging:
        _emit(emit, "stage", {"name": "downloading", "status": "started", "mode": "local-copy"})
        copied, copy_warnings = _copy_local_directory(origin, staging, max_bytes, emit)
        _emit(emit, "stage", {"name": "downloading", "status": "completed", "fileCount": copied})
        _emit(emit, "stage", {"name": "scanning", "status": "started"})
        file_infos, scan_warnings = _safe_inventory(staging, max_bytes)
        _emit(emit, "stage", {"name": "profiling", "status": "started"})
        profile = _build_profile(
            resource_id=resource_id,
            name=origin.name,
            description=f"从本地目录导入的数据集：{origin.name}",
            source_type="local",
            source_location=str(origin),
            revision=resolved_revision,
            file_infos=file_infos,
            source_metadata={},
            source_warnings=copy_warnings + scan_warnings,
        )
        _emit(emit, "stage", {"name": "profiling", "status": "completed"})
        _emit(emit, "stage", {"name": "scanning", "status": "completed", "fileCount": len(file_infos)})
        _replace_directory(staging, target)

    now = _iso_now()
    file_infos, scan_warnings = _safe_inventory(target, max_bytes)
    profile["warnings"] = _unique_strings(profile["warnings"] + scan_warnings)
    record = ResourceRecord(
        id=resource_id,
        kind="dataset",
        source_type="local",
        source=str(origin),
        revision=revision,
        resolved_revision=resolved_revision,
        name=profile["name"],
        status="ready" if profile["completeness"] >= 0.5 else "needs_review",
        local_path=str(target),
        profile_path=f"profiles/datasets/{resource_id}.json",
        file_count=len(file_infos),
        size_bytes=sum(item.size_bytes for item in file_infos),
        created_at=now,
        updated_at=now,
        warnings=list(profile["warnings"]),
    )
    return record, profile


def _build_profile(
    *,
    resource_id: str,
    name: str,
    description: str,
    source_type: str,
    source_location: str,
    revision: str,
    file_infos: Sequence[_FileInfo],
    source_metadata: Mapping[str, Any],
    source_warnings: Sequence[str],
) -> Dict[str, Any]:
    _ensure_no_unsafe_files(file_infos)
    analyses = [
        _analyse_file(item)
        for item in file_infos
        if _is_dataset_file(item.relative_path)
        and item.relative_path != "dataset-metadata.json"
    ]
    formats = _unique_strings([analysis["format"] for analysis in analyses])
    all_features = _merge_features(analyses)
    sample_count = sum(
        int(analysis["sampleCount"])
        for analysis in analyses
        if not analysis.get("metadataOnly")
    )
    split_counts = _split_counts(analyses)
    warnings = list(source_warnings)
    for analysis in analyses:
        warnings.extend(analysis["warnings"])
    if not analyses:
        warnings.append("没有可用于静态分析的已识别数据文件")

    structured_modalities = _unique_strings(
        modality
        for analysis in analyses
        for modality in analysis.get("modalities", [])
    )
    structured_tasks = _unique_strings(
        task
        for analysis in analyses
        for task in analysis.get("taskHints", [])
    )
    modalities = structured_modalities or _infer_modalities(all_features, file_infos, source_metadata)
    task_hints = structured_tasks or _infer_task_hints(all_features, source_metadata)
    languages = _languages_from_metadata(source_metadata)
    license_name = _license_from_card(source_metadata.get("cardData"))
    evidence: List[Evidence] = [
        Evidence(
            kind="inventory",
            source=source_location,
            detail=f"已扫描 {len(file_infos)} 个文件；识别格式：{', '.join(formats) or '无'}",
        )
    ]
    for analysis in analyses:
        evidence.append(
            Evidence(
                kind="static_schema",
                source=analysis["path"],
                detail=analysis["evidence"],
            )
        )
    completeness = _profile_completeness(all_features, analyses, warnings)
    profile = DatasetProfile(
        resource_id=resource_id,
        name=name,
        description=description,
        source=SourceRef(source_type, source_location, revision),
        modalities=modalities,
        task_hints=task_hints,
        splits=[DatasetSplit(split, count) for split, count in split_counts.items()],
        features=all_features,
        formats=formats,
        sample_count=sample_count,
        license=license_name,
        languages=languages,
        evidence=evidence,
        warnings=_unique_strings(warnings),
        completeness=completeness,
    )
    return profile.to_dict()


def _analyse_file(file_info: _FileInfo) -> Dict[str, Any]:
    suffix = Path(file_info.relative_path).suffix.lower()
    if suffix == ".csv":
        return _analyse_csv(file_info)
    if suffix in {".jsonl", ".ndjson"}:
        return _analyse_jsonl(file_info)
    if suffix == ".json":
        filename = Path(file_info.relative_path).name.lower()
        if filename == "dataset_infos.json":
            return _analyse_dataset_infos(file_info)
        if filename in {
            "dataset_dict.json",
            "id2label.json",
            "label2id.json",
            "state.json",
        }:
            return _metadata_json_analysis(file_info)
        return _analyse_json(file_info)
    if suffix == ".parquet":
        return _analyse_parquet(file_info)
    raise DatasetResourceError(f"Unsupported dataset file passed to analyser: {file_info.relative_path}")


def _analyse_csv(file_info: _FileInfo) -> Dict[str, Any]:
    observations: "OrderedDict[str, List[Any]]" = OrderedDict()
    count = 0
    warnings: List[str] = []
    try:
        with file_info.path.open("r", encoding="utf-8-sig", newline="", errors="replace") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames:
                warnings.append(f"CSV file has no header: {file_info.relative_path}")
            else:
                for field in reader.fieldnames:
                    observations[field] = []
                for row in reader:
                    if count >= SAMPLE_ROW_LIMIT:
                        break
                    for field, value in row.items():
                        observations.setdefault(field or "unnamed", []).append(value)
                    count += 1
    except (OSError, csv.Error) as exc:
        warnings.append(f"Could not analyse CSV file {file_info.relative_path}: {exc}")
    return _analysis_from_observations(file_info, "csv", observations, count, warnings)


def _analyse_jsonl(file_info: _FileInfo) -> Dict[str, Any]:
    observations: "OrderedDict[str, List[Any]]" = OrderedDict()
    count = 0
    warnings: List[str] = []
    try:
        with file_info.path.open("r", encoding="utf-8", errors="replace") as handle:
            for line_number, line in enumerate(handle, start=1):
                if count >= SAMPLE_ROW_LIMIT:
                    break
                if not line.strip():
                    continue
                try:
                    value = json.loads(line)
                except json.JSONDecodeError:
                    warnings.append(f"Invalid JSONL row {line_number} in {file_info.relative_path}")
                    continue
                _observe_json_row(value, observations)
                count += 1
    except OSError as exc:
        warnings.append(f"Could not analyse JSONL file {file_info.relative_path}: {exc}")
    return _analysis_from_observations(file_info, "jsonl", observations, count, warnings)


def _analyse_json(file_info: _FileInfo) -> Dict[str, Any]:
    observations: "OrderedDict[str, List[Any]]" = OrderedDict()
    warnings: List[str] = []
    count = 0
    try:
        with file_info.path.open("r", encoding="utf-8", errors="replace") as handle:
            raw = json.load(handle)
        rows = _json_rows(raw)
        for row in rows[:SAMPLE_ROW_LIMIT]:
            _observe_json_row(row, observations)
            count += 1
    except (OSError, json.JSONDecodeError) as exc:
        warnings.append(f"Could not analyse JSON file {file_info.relative_path}: {exc}")
    return _analysis_from_observations(file_info, "json", observations, count, warnings)


def _analyse_dataset_infos(file_info: _FileInfo) -> Dict[str, Any]:
    """Read Hugging Face's static schema manifest without loading dataset code."""

    warnings: List[str] = []
    features: List[DatasetFeature] = []
    split_counts: "OrderedDict[str, int | None]" = OrderedDict()
    modalities: List[str] = []
    task_hints: List[str] = []
    sample_count = 0
    try:
        with file_info.path.open("r", encoding="utf-8", errors="replace") as handle:
            raw = json.load(handle)
        configs = raw if isinstance(raw, Mapping) else {}
        config = next(
            (
                value
                for value in configs.values()
                if isinstance(value, Mapping)
                and isinstance(value.get("features"), Mapping)
            ),
            None,
        )
        if not isinstance(config, Mapping):
            warnings.append(f"未在 {file_info.relative_path} 中找到 Hugging Face 静态 schema")
        else:
            raw_features = config.get("features")
            if isinstance(raw_features, Mapping):
                for name, descriptor in raw_features.items():
                    if not isinstance(name, str) or not isinstance(descriptor, Mapping):
                        continue
                    data_type, semantic_role, shape, description = _dataset_info_feature(name, descriptor)
                    features.append(
                        DatasetFeature(
                            name=name,
                            data_type=data_type,
                            semantic_role=semantic_role,
                            nullable=True,
                            shape=shape,
                            description=description or f"在 {file_info.relative_path} 中识别",
                        )
                    )
                    if data_type == "image":
                        modalities.append("image")
                    elif data_type == "audio":
                        modalities.append("audio")
                    elif data_type == "video":
                        modalities.append("video")
                    elif data_type in {"string", "text"}:
                        modalities.append("text")
            templates = config.get("task_templates")
            if isinstance(templates, list):
                for template in templates:
                    if isinstance(template, Mapping) and isinstance(template.get("task"), str):
                        task_hints.append(template["task"].strip())
            raw_splits = config.get("splits")
            if isinstance(raw_splits, Mapping):
                for split_name, split_info in raw_splits.items():
                    if not isinstance(split_name, str) or not isinstance(split_info, Mapping):
                        continue
                    count = split_info.get("num_examples")
                    if isinstance(count, int) and not isinstance(count, bool) and count >= 0:
                        split_counts[split_name] = count
                        sample_count += min(count, SAMPLE_ROW_LIMIT)
                    else:
                        split_counts[split_name] = None
            if not features:
                warnings.append(f"{file_info.relative_path} 未包含可识别字段")
    except (OSError, json.JSONDecodeError) as exc:
        warnings.append(f"Could not analyse JSON file {file_info.relative_path}: {exc}")
    return {
        "path": file_info.relative_path,
        "format": "json",
        "features": features,
        "sampleCount": sample_count,
        "metadataOnly": True,
        "split": _split_name(file_info.relative_path),
        "splitCounts": split_counts,
        "modalities": _unique_strings(modalities),
        "taskHints": _unique_strings(task_hints),
        "warnings": warnings,
        "evidence": f"读取 Hugging Face 静态 schema 并识别出 {len(features)} 个字段",
    }


def _metadata_json_analysis(file_info: _FileInfo) -> Dict[str, Any]:
    return {
        "path": file_info.relative_path,
        "format": "json",
        "features": [],
        "sampleCount": 0,
        "metadataOnly": True,
        "split": _split_name(file_info.relative_path),
        "warnings": [],
        "evidence": "识别为数据集元数据文件，未作为训练样本字段分析",
    }


def _dataset_info_feature(name: str, descriptor: Mapping[str, Any]) -> Tuple[str, str, List[object], str]:
    kind = descriptor.get("_type")
    if kind == "Image":
        role = _semantic_role(name)
        description = "分割标签图或掩码" if role == "label" else "图像输入"
        return "image", role, [], description
    if kind == "Audio":
        return "audio", "input", [], "音频输入"
    if kind == "Video":
        return "video", "input", [], "视频输入"
    if kind == "ClassLabel":
        names = descriptor.get("names")
        label_count = len(names) if isinstance(names, list) else descriptor.get("num_classes")
        suffix = f"（{label_count} 个类别）" if isinstance(label_count, int) else ""
        return "classlabel", "label", [], f"分类标签{suffix}"
    if kind == "Value":
        dtype = descriptor.get("dtype")
        if isinstance(dtype, str) and dtype.strip():
            return _normalise_dataset_info_dtype(dtype), "input", [], ""
    return "object", "input", [], ""


def _normalise_dataset_info_dtype(dtype: str) -> str:
    lowered = dtype.lower().strip()
    if lowered in {"bool", "boolean"}:
        return "boolean"
    if lowered.startswith(("int", "uint")):
        return "integer"
    if lowered.startswith(("float", "double")):
        return "number"
    if lowered in {"string", "str"}:
        return "string"
    return lowered


def _analyse_parquet(file_info: _FileInfo) -> Dict[str, Any]:
    warnings: List[str] = []
    try:
        with file_info.path.open("rb") as handle:
            header = handle.read(4)
            if file_info.size_bytes >= 8:
                handle.seek(-4, os.SEEK_END)
                footer = handle.read(4)
            else:
                footer = b""
        if header != b"PAR1" or footer != b"PAR1":
            warnings.append(f"File has .parquet suffix but no Parquet magic bytes: {file_info.relative_path}")
        else:
            return _analyse_parquet_with_pyarrow(file_info)
    except OSError as exc:
        warnings.append(f"Could not inspect Parquet file {file_info.relative_path}: {exc}")
    return {
        "path": file_info.relative_path,
        "format": "parquet",
        "features": [],
        "sampleCount": 0,
        "split": _split_name(file_info.relative_path),
        "warnings": warnings,
        "evidence": "Recognised Parquet file by suffix and static magic-byte inspection",
    }


def _analyse_parquet_with_pyarrow(file_info: _FileInfo) -> Dict[str, Any]:
    try:
        import pyarrow as pa
        import pyarrow.parquet as pq
    except ImportError:
        return {
            "path": file_info.relative_path,
            "format": "parquet",
            "features": [],
            "sampleCount": 0,
            "split": _split_name(file_info.relative_path),
            "warnings": [
                f"Parquet schema could not be parsed because pyarrow is unavailable: {file_info.relative_path}"
            ],
            "evidence": "Recognised Parquet file by suffix and static magic-byte inspection",
        }

    warnings: List[str] = []
    try:
        parquet_file = pq.ParquetFile(file_info.path)
        schema = parquet_file.schema_arrow
        features = [
            _arrow_feature(field.name, field.type, field.nullable)
            for field in schema
        ]
        sample_count = min(int(parquet_file.metadata.num_rows), SAMPLE_ROW_LIMIT)
        modalities = _unique_strings(
            _arrow_modality(feature.name, feature.data_type)
            for feature in features
        )
        task_hints = _arrow_task_hints(schema, features, modalities)
        return {
            "path": file_info.relative_path,
            "format": "parquet",
            "features": features,
            "sampleCount": sample_count,
            "split": _split_name(file_info.relative_path),
            "modalities": modalities,
            "taskHints": task_hints,
            "warnings": warnings,
            "evidence": (
                f"通过 pyarrow 读取 schema，识别出 {len(features)} 个字段；"
                f"文件共 {parquet_file.metadata.num_rows} 条记录"
            ),
        }
    except (OSError, ValueError, pa.ArrowException) as exc:
        warnings.append(f"Could not analyse Parquet schema {file_info.relative_path}: {exc}")
        return {
            "path": file_info.relative_path,
            "format": "parquet",
            "features": [],
            "sampleCount": 0,
            "split": _split_name(file_info.relative_path),
            "warnings": warnings,
            "evidence": "Recognised Parquet file by suffix and static magic-byte inspection",
        }


def _arrow_feature(name: str, data_type: Any, nullable: bool) -> DatasetFeature:
    import pyarrow as pa

    lowered = name.lower()
    if _looks_like_image_field(lowered, data_type):
        role = _semantic_role(name)
        description = "分割标签图或掩码" if role == "label" else "图像输入"
        return DatasetFeature(name, "image", role, nullable, [], description)
    if _looks_like_audio_field(lowered, data_type):
        return DatasetFeature(name, "audio", _semantic_role(name), nullable, [], "音频输入")
    if _looks_like_video_field(lowered, data_type):
        return DatasetFeature(name, "video", _semantic_role(name), nullable, [], "视频输入")
    if _semantic_role(name) == "label" and (
        pa.types.is_integer(data_type)
        or pa.types.is_string(data_type)
        or pa.types.is_dictionary(data_type)
    ):
        return DatasetFeature(name, "classlabel", "label", nullable, [], "分类标签")
    return DatasetFeature(name, _arrow_type_name(data_type), _semantic_role(name), nullable, [], "")


def _arrow_task_hints(
    schema: Any,
    features: Sequence[DatasetFeature],
    modalities: Sequence[str],
) -> List[str]:
    if "image" not in modalities:
        return []
    hints: List[str] = []
    label_features = [feature for feature in features if feature.semantic_role == "label"]
    if any(feature.data_type == "image" for feature in label_features):
        hints.append("image-segmentation")
    if any(_looks_like_detection_field(field.name, field.type) for field in schema):
        hints.append("object-detection")
    if not hints and label_features:
        hints.append("image-classification")
    return _unique_strings(hints)


def _looks_like_detection_field(name: str, data_type: Any) -> bool:
    import pyarrow as pa

    lowered = name.lower()
    if lowered in {"bbox", "bboxes", "box", "boxes", "objects", "annotations", "detections"}:
        return True
    if not pa.types.is_struct(data_type):
        return False
    child_names = {field.name.lower() for field in data_type}
    return bool(child_names & {"bbox", "bboxes", "box", "boxes"}) and bool(
        child_names & {"category", "categories", "class", "classes", "label", "labels"}
    )


def _looks_like_image_field(name: str, data_type: Any) -> bool:
    import pyarrow as pa

    media_struct = (
        pa.types.is_struct(data_type)
        and {"bytes", "path"} <= {field.name.lower() for field in data_type}
    )
    return (
        (
            any(token in name for token in ("image", "img", "pixel", "photo"))
            or (name in {"label", "labels", "mask", "masks", "segmentation", "segmentation_map"} and media_struct)
        )
        and (
            pa.types.is_binary(data_type)
            or pa.types.is_large_binary(data_type)
            or pa.types.is_string(data_type)
            or media_struct
        )
    )


def _looks_like_audio_field(name: str, data_type: Any) -> bool:
    import pyarrow as pa

    return any(token in name for token in ("audio", "waveform", "speech")) and (
        pa.types.is_binary(data_type)
        or pa.types.is_large_binary(data_type)
        or pa.types.is_struct(data_type)
        or pa.types.is_list(data_type)
    )


def _looks_like_video_field(name: str, data_type: Any) -> bool:
    import pyarrow as pa

    return any(token in name for token in ("video", "frame")) and (
        pa.types.is_binary(data_type)
        or pa.types.is_large_binary(data_type)
        or pa.types.is_string(data_type)
        or pa.types.is_struct(data_type)
        or pa.types.is_list(data_type)
    )


def _arrow_type_name(data_type: Any) -> str:
    import pyarrow as pa

    if pa.types.is_boolean(data_type):
        return "boolean"
    if pa.types.is_integer(data_type):
        return "integer"
    if pa.types.is_floating(data_type) or pa.types.is_decimal(data_type):
        return "number"
    if pa.types.is_string(data_type) or pa.types.is_large_string(data_type):
        return "string"
    if pa.types.is_list(data_type) or pa.types.is_large_list(data_type):
        return "array"
    if pa.types.is_binary(data_type) or pa.types.is_large_binary(data_type):
        return "binary"
    if pa.types.is_struct(data_type) or pa.types.is_map(data_type):
        return "object"
    return "unknown"


def _arrow_modality(name: str, data_type: str) -> str:
    lowered = name.lower()
    if data_type == "image" or any(token in lowered for token in ("image", "img", "pixel", "photo")):
        return "image"
    if data_type == "audio" or any(token in lowered for token in ("audio", "waveform", "speech")):
        return "audio"
    if data_type == "video" or any(token in lowered for token in ("video", "frame")):
        return "video"
    return ""


def _analysis_from_observations(
    file_info: _FileInfo,
    file_format: str,
    observations: "OrderedDict[str, List[Any]]",
    count: int,
    warnings: List[str],
) -> Dict[str, Any]:
    features = [
        DatasetFeature(
            name=name,
            data_type=_infer_observed_type(values),
            semantic_role=_semantic_role(name),
            nullable=any(value is None or value == "" for value in values),
            shape=_infer_shape(values),
            description=f"在 {file_info.relative_path} 中识别",
        )
        for name, values in observations.items()
    ]
    return {
        "path": file_info.relative_path,
        "format": file_format,
        "features": features,
        "sampleCount": count,
        "split": _split_name(file_info.relative_path),
        "warnings": warnings,
        "evidence": f"读取 {count} 条样本并推断出 {len(features)} 个字段",
    }


def _json_rows(raw: Any) -> List[Any]:
    if isinstance(raw, list):
        return raw
    if isinstance(raw, Mapping):
        for key in ("data", "records", "items", "examples"):
            value = raw.get(key)
            if isinstance(value, list):
                return value
        return [raw]
    return [raw]


def _observe_json_row(value: Any, observations: "OrderedDict[str, List[Any]]") -> None:
    if isinstance(value, Mapping):
        for key, field_value in value.items():
            observations.setdefault(str(key), []).append(field_value)
    else:
        observations.setdefault("value", []).append(value)


def _merge_features(analyses: Sequence[Mapping[str, Any]]) -> List[DatasetFeature]:
    merged: "OrderedDict[str, Dict[str, Any]]" = OrderedDict()
    for analysis in analyses:
        for feature in analysis["features"]:
            current = merged.get(feature.name)
            if current is None:
                merged[feature.name] = {
                    "types": [feature.data_type],
                    "roles": [feature.semantic_role],
                    "nullable": feature.nullable,
                    "shapes": [feature.shape],
                    "descriptions": [feature.description],
                }
                continue
            current["types"].append(feature.data_type)
            current["roles"].append(feature.semantic_role)
            current["nullable"] = bool(current["nullable"] or feature.nullable)
            current["shapes"].append(feature.shape)
            current["descriptions"].append(feature.description)
    return [
        DatasetFeature(
            name=name,
            data_type=_combine_types(current["types"]),
            semantic_role="label" if "label" in current["roles"] else current["roles"][0],
            nullable=bool(current["nullable"]),
            shape=_common_shape(current["shapes"]),
            description=current["descriptions"][0],
        )
        for name, current in merged.items()
    ]


def _split_counts(analyses: Sequence[Mapping[str, Any]]) -> "OrderedDict[str, int | None]":
    structured = next(
        (
            analysis.get("splitCounts")
            for analysis in analyses
            if isinstance(analysis.get("splitCounts"), Mapping)
            and analysis.get("splitCounts")
        ),
        None,
    )
    if isinstance(structured, Mapping):
        return OrderedDict(
            (name, count)
            for name, count in structured.items()
            if isinstance(name, str)
            and (
                count is None
                or (isinstance(count, int) and not isinstance(count, bool) and count >= 0)
            )
        )

    counts: "OrderedDict[str, int | None]" = OrderedDict()
    for analysis in analyses:
        name = analysis["split"]
        sample_count = int(analysis["sampleCount"])
        existing = counts.get(name)
        if existing is None and name in counts:
            continue
        counts[name] = sample_count if existing is None else existing + sample_count
    if not counts:
        counts["unknown"] = None
    return counts


def _infer_observed_type(values: Sequence[Any]) -> str:
    types = [_json_type(value) for value in values if value is not None and value != ""]
    return _combine_types(types) if types else "unknown"


def _json_type(value: Any) -> str:
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, Mapping):
        return "object"
    if isinstance(value, list):
        return "array"
    if isinstance(value, str):
        return _string_scalar_type(value)
    return "unknown"


def _string_scalar_type(value: str) -> str:
    stripped = value.strip()
    if not stripped:
        return "string"
    if stripped.lower() in {"true", "false"}:
        return "boolean"
    try:
        int(stripped)
        return "integer"
    except ValueError:
        pass
    try:
        float(stripped)
        return "number"
    except ValueError:
        return "string"


def _combine_types(types: Sequence[str]) -> str:
    unique = set(types)
    if not unique:
        return "unknown"
    if unique <= {"integer", "number"}:
        return "number" if "number" in unique else "integer"
    return next(iter(unique)) if len(unique) == 1 else "mixed"


def _infer_shape(values: Sequence[Any]) -> List[object]:
    arrays = [value for value in values if isinstance(value, list)]
    if not arrays:
        return []
    lengths = {len(item) for item in arrays}
    return [lengths.pop()] if len(lengths) == 1 else ["variable"]


def _common_shape(shapes: Sequence[List[object]]) -> List[object]:
    first = list(shapes[0]) if shapes else []
    return first if all(list(shape) == first for shape in shapes) else []


def _semantic_role(name: str) -> str:
    lower = name.lower()
    if lower in {
        "label", "labels", "class", "class_id", "target", "target_id", "y",
        "category", "sentiment", "species", "objects", "annotations",
        "bbox", "bboxes", "boxes", "mask", "masks", "segmentation",
    }:
        return "label"
    if lower in {"id", "uuid", "index", "identifier"} or lower.endswith("_id"):
        return "identifier"
    return "input"


def _infer_modalities(
    features: Sequence[DatasetFeature],
    file_infos: Sequence[_FileInfo],
    metadata: Mapping[str, Any],
) -> List[str]:
    tags = " ".join(_string_list(metadata.get("tags"))).lower()
    names = " ".join(feature.name.lower() for feature in features)
    suffixes = {Path(item.relative_path).suffix.lower() for item in file_infos}
    modalities: List[str] = []
    if any(token in tags + " " + names for token in ("image", "pixel", "photo")) or suffixes & {".jpg", ".jpeg", ".png", ".webp"}:
        modalities.append("image")
    if any(token in tags + " " + names for token in ("audio", "speech", "waveform")) or suffixes & {".wav", ".mp3", ".flac"}:
        modalities.append("audio")
    if any(token in tags + " " + names for token in ("video", "frame")) or suffixes & {".mp4", ".avi", ".webm"}:
        modalities.append("video")
    if any(
        token in tags + " " + names
        for token in (
            "text", "sentence", "question", "caption", "review", "document",
            "body", "content", "title", "prompt", "instruction",
        )
    ):
        modalities.append("text")
    if not modalities and features:
        modalities.append("tabular")
    return modalities or ["unknown"]


def _infer_task_hints(features: Sequence[DatasetFeature], metadata: Mapping[str, Any]) -> List[str]:
    tags = [tag.lower() for tag in _string_list(metadata.get("tags"))]
    task_tags = [
        tag
        for tag in tags
        if tag
        in {
            "text-classification",
            "image-classification",
            "token-classification",
            "question-answering",
            "summarization",
            "translation",
            "automatic-speech-recognition",
            "object-detection",
            "image-segmentation",
        }
    ]
    if task_tags:
        return _unique_strings(task_tags)
    if any(feature.semantic_role == "label" for feature in features):
        return ["classification"]
    return []


def _languages_from_metadata(metadata: Mapping[str, Any]) -> List[str]:
    card_data = metadata.get("cardData")
    sources = [metadata, card_data if isinstance(card_data, Mapping) else {}]
    languages: List[str] = []
    for source in sources:
        language = source.get("language")
        if isinstance(language, str):
            languages.append(language)
        elif isinstance(language, list):
            languages.extend(item for item in language if isinstance(item, str))
    return _unique_strings(languages)


def _license_from_card(value: Any) -> str:
    if not isinstance(value, Mapping):
        return "unknown"
    license_value = value.get("license")
    if isinstance(license_value, str) and license_value.strip():
        return license_value.strip()
    return "unknown"


def _profile_completeness(
    features: Sequence[DatasetFeature],
    analyses: Sequence[Mapping[str, Any]],
    warnings: Sequence[str],
) -> float:
    score = 0.25
    if analyses:
        score += 0.25
    if features:
        score += 0.3
    if any(item["sampleCount"] for item in analyses):
        score += 0.15
    if warnings:
        score -= min(0.2, 0.03 * len(warnings))
    return max(0.0, min(1.0, round(score, 2)))


def _download_huggingface_files(
    dataset_id: str,
    revision: str,
    file_names: Sequence[str],
    staging: Path,
    max_bytes: int,
    emit: Optional[Emit],
) -> List[str]:
    downloaded: List[str] = []
    total = 0
    for index, file_name in enumerate(file_names, start=1):
        destination = _safe_child(staging, file_name)
        url = (
            "https://huggingface.co/datasets/"
            + quote(dataset_id, safe="/")
            + "/resolve/"
            + quote(revision, safe="")
            + "/"
            + quote(file_name, safe="/")
        )
        size = _download_file(url, destination, max_bytes - total)
        total += size
        downloaded.append(file_name)
        _emit(
            emit,
            "progress",
            {
                "currentFile": file_name,
                "fileCount": index,
                "totalFiles": len(file_names),
                "bytesDownloaded": total,
                "maxBytes": max_bytes,
            },
        )
    return downloaded


def _download_file(url: str, destination: Path, remaining_bytes: int) -> int:
    if remaining_bytes < 1:
        raise DatasetResourceError("Download byte limit exceeded")
    _validate_huggingface_url(url, allow_content_hosts=False)
    request = Request(url, headers={"User-Agent": "DataModelMatch/0.1"})
    opener = build_opener(_SafeRedirectHandler())
    try:
        with opener.open(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            final_url = response.geturl()
            _validate_huggingface_url(final_url, allow_content_hosts=True)
            content_length = response.headers.get("Content-Length")
            if content_length:
                try:
                    if int(content_length) > remaining_bytes:
                        raise DatasetResourceError("Download would exceed configured byte limit")
                except ValueError:
                    pass
            destination.parent.mkdir(parents=True, exist_ok=True)
            written = 0
            temporary = destination.with_name(destination.name + ".part")
            try:
                with temporary.open("wb") as handle:
                    while True:
                        chunk = response.read(CHUNK_SIZE)
                        if not chunk:
                            break
                        written += len(chunk)
                        if written > remaining_bytes:
                            raise DatasetResourceError("Download exceeded configured byte limit")
                        handle.write(chunk)
                temporary.replace(destination)
            except Exception:
                temporary.unlink(missing_ok=True)
                raise
            return written
    except HTTPError as exc:
        raise DatasetResourceError(f"Hugging Face download failed with HTTP {exc.code}") from exc
    except URLError as exc:
        raise DatasetResourceError("Hugging Face download request failed") from exc


def _get_json(url: str) -> Any:
    _validate_huggingface_url(url, allow_content_hosts=False)
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "DataModelMatch/0.1"})
    try:
        with build_opener(_SafeRedirectHandler()).open(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:
            _validate_huggingface_url(response.geturl(), allow_content_hosts=True)
            payload = response.read(DEFAULT_DOWNLOAD_LIMIT + 1)
    except HTTPError as exc:
        raise DatasetResourceError(f"Hugging Face API request failed with HTTP {exc.code}") from exc
    except URLError as exc:
        raise DatasetResourceError("Hugging Face API request failed") from exc
    if len(payload) > DEFAULT_DOWNLOAD_LIMIT:
        raise DatasetResourceError("Hugging Face API response exceeded the safety limit")
    try:
        return json.loads(payload.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise DatasetResourceError("Hugging Face API returned invalid JSON") from exc


def _huggingface_files(siblings: Sequence[Any]) -> List[str]:
    files: List[str] = []
    for item in siblings:
        if not isinstance(item, Mapping):
            continue
        filename = item.get("rfilename")
        if not isinstance(filename, str) or not _is_dataset_file(filename):
            continue
        if _is_unsafe_relative_path(filename):
            continue
        files.append(filename)
    return sorted(set(files))


def _safe_inventory(root: Path, max_bytes: int) -> Tuple[List[_FileInfo], List[str]]:
    root = root.resolve()
    files: List[_FileInfo] = []
    warnings: List[str] = []
    total = 0
    for current_root, directory_names, file_names in os.walk(root, followlinks=False):
        current = Path(current_root)
        kept_directories: List[str] = []
        for directory_name in directory_names:
            candidate = current / directory_name
            if directory_name in IGNORED_DIR_NAMES:
                continue
            if candidate.is_symlink():
                warnings.append(f"Skipped symbolic-link directory: {candidate.relative_to(root)}")
                continue
            kept_directories.append(directory_name)
        directory_names[:] = kept_directories
        for file_name in file_names:
            candidate = current / file_name
            relative = candidate.relative_to(root)
            if _is_sensitive_file(relative):
                warnings.append(f"已跳过敏感文件：{relative}")
                continue
            if candidate.is_symlink():
                warnings.append(f"Skipped symbolic-link file: {relative}")
                continue
            try:
                resolved = candidate.resolve(strict=True)
                if not _is_relative_to(resolved, root):
                    warnings.append(f"Skipped file resolving outside resource root: {relative}")
                    continue
                size = resolved.stat().st_size
            except OSError:
                warnings.append(f"Skipped unreadable file: {relative}")
                continue
            total += size
            if total > max_bytes:
                raise DatasetResourceError("Resource contents exceed configured byte limit")
            files.append(_FileInfo(resolved, relative.as_posix(), size))
    return sorted(files, key=lambda item: item.relative_path), warnings


def _copy_local_directory(origin: Path, staging: Path, max_bytes: int, emit: Optional[Emit]) -> Tuple[int, List[str]]:
    copied = 0
    copied_bytes = 0
    warnings: List[str] = []
    for current_root, directory_names, file_names in os.walk(origin, followlinks=False):
        current = Path(current_root)
        kept_directories: List[str] = []
        for directory_name in directory_names:
            candidate = current / directory_name
            relative = candidate.relative_to(origin)
            if directory_name in IGNORED_DIR_NAMES:
                continue
            if candidate.is_symlink():
                warnings.append(f"Skipped symbolic-link directory: {relative}")
                continue
            kept_directories.append(directory_name)
        directory_names[:] = kept_directories
        for file_name in file_names:
            candidate = current / file_name
            relative = candidate.relative_to(origin)
            if _is_sensitive_file(relative):
                warnings.append(f"已跳过敏感文件：{relative}")
                continue
            if candidate.is_symlink():
                warnings.append(f"Skipped symbolic-link file: {relative}")
                continue
            resolved = candidate.resolve(strict=True)
            if not _is_relative_to(resolved, origin):
                warnings.append(f"Skipped file resolving outside source directory: {relative}")
                continue
            size = resolved.stat().st_size
            copied_bytes += size
            if copied_bytes > max_bytes:
                raise DatasetResourceError("Local resource exceeds configured byte limit")
            target = _safe_child(staging, relative.as_posix())
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(resolved, target)
            copied += 1
            _emit(
                emit,
                "progress",
                {"fileCount": copied, "bytesCopied": copied_bytes, "maxBytes": max_bytes},
            )
    return copied, warnings


def _local_revision(origin: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(origin.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(origin)
        if any(part in IGNORED_DIR_NAMES for part in relative.parts) or _is_sensitive_file(relative):
            continue
        stat = path.stat()
        digest.update(relative.as_posix().encode("utf-8"))
        digest.update(str(stat.st_size).encode("ascii"))
        digest.update(str(stat.st_mtime_ns).encode("ascii"))
    return f"local-{digest.hexdigest()[:16]}"


def _is_sensitive_file(path: Path) -> bool:
    name = path.name.lower()
    return name in SENSITIVE_FILENAMES or name.startswith(".env.")


def _parse_huggingface_dataset(source: str) -> str:
    parsed = urlparse(source)
    if parsed.scheme or parsed.netloc:
        _validate_huggingface_url(source, allow_content_hosts=False)
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 3 and parts[0] == "datasets":
            parts = parts[1:3]
        elif len(parts) >= 2:
            parts = parts[:2]
        else:
            raise DatasetResourceError("Hugging Face dataset URL must identify a repository")
        dataset_id = "/".join(parts)
    else:
        dataset_id = source.strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]*(?:/[A-Za-z0-9][A-Za-z0-9._-]*)?", dataset_id):
        raise DatasetResourceError("Invalid Hugging Face dataset repository ID")
    return dataset_id


def _validate_huggingface_url(url: str, allow_content_hosts: bool) -> None:
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    valid_host = host in _HF_WEB_HOSTS
    if allow_content_hosts:
        valid_host = valid_host or host == "hf.co" or host.endswith(_HF_CONTENT_HOST_SUFFIXES)
    if parsed.scheme != "https" or not valid_host:
        raise DatasetResourceError("Only HTTPS Hugging Face official domains are allowed")


def _safe_child(root: Path, relative_path: str) -> Path:
    if _is_unsafe_relative_path(relative_path):
        raise DatasetResourceError("Resource path must be a safe relative path")
    result = (root / relative_path).resolve()
    if not _is_relative_to(result, root.resolve()):
        raise DatasetResourceError("Resource path escapes its destination")
    return result


def _is_unsafe_relative_path(path: str) -> bool:
    candidate = Path(path)
    return not path or candidate.is_absolute() or ".." in candidate.parts or "\\" in path


def _is_dataset_file(path: str) -> bool:
    return Path(path).suffix.lower() in DATA_SUFFIXES and not _is_unsafe_relative_path(path)


def _ensure_no_unsafe_files(file_infos: Sequence[_FileInfo]) -> None:
    for item in file_infos:
        if _is_unsafe_relative_path(item.relative_path):
            raise DatasetResourceError("Unsafe file path found in resource inventory")


def _staging_directory(target: Path) -> Iterable[Path]:
    parent = target.parent
    parent.mkdir(parents=True, exist_ok=True)

    class _Staging:
        def __enter__(self) -> Path:
            self.path = Path(tempfile.mkdtemp(prefix=f".{target.name}.", dir=parent))
            return self.path

        def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
            if hasattr(self, "path") and self.path.exists():
                shutil.rmtree(self.path, ignore_errors=True)

    return _Staging()


def _replace_directory(staging: Path, target: Path) -> None:
    backup = target.with_name(target.name + ".previous")
    if backup.exists():
        shutil.rmtree(backup, ignore_errors=True)
    if target.exists():
        target.replace(backup)
    try:
        staging.replace(target)
    except Exception:
        if backup.exists() and not target.exists():
            backup.replace(target)
        raise
    finally:
        shutil.rmtree(backup, ignore_errors=True)


def _emit(emit: Optional[Emit], event_name: str, data: Dict[str, Any]) -> None:
    if emit is not None:
        emit(event_name, data)


def _required_choice(value: str, label: str, choices: frozenset[str]) -> str:
    if not isinstance(value, str) or value not in choices:
        raise DatasetResourceError(f"{label} must be one of: {', '.join(sorted(choices))}")
    return value


def _safe_resource_id(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"dataset_[A-Za-z0-9][A-Za-z0-9_-]*", value):
        raise DatasetResourceError("resource_id must start with 'dataset_' and contain only letters, digits, '_' or '-'")
    return value


def _optional_text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def _string_list(value: Any) -> List[str]:
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [item.strip() for item in value if isinstance(item, str) and item.strip()]
    return []


def _integer_or_none(value: Any) -> Optional[int]:
    return value if isinstance(value, int) and not isinstance(value, bool) else None


def _split_name(path: str) -> str:
    match = _SPLIT_RE.search(path)
    if not match:
        return "unknown"
    name = match.group(1).lower()
    return {"valid": "validation", "val": "validation", "dev": "validation"}.get(name, name)


def _unique_strings(values: Sequence[str]) -> List[str]:
    return list(OrderedDict((value, None) for value in values if value))


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False


def _write_json(path: Path, value: Mapping[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
