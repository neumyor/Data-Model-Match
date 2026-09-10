"""Command-line bridge for resource discovery, import, and compatibility jobs."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, List

from .config import load_llm_config
from .llm import LLMClient
from .resource_store import ResourceStore


EventEmitter = Callable[[str, Dict[str, Any]], None]


def _emit(event: str, data: Dict[str, Any]) -> None:
    print(json.dumps({"event": event, "data": data}, ensure_ascii=False), flush=True)


def _forward_module_event(*args: object) -> None:
    """Normalize both supported internal emitter call styles to one JSONL event."""
    normalized = _normalize_module_event(*args)
    if normalized is not None:
        _emit(*normalized)


def _normalize_module_event(*args: object) -> tuple[str, Dict[str, Any]] | None:
    event = ""
    data: Dict[str, Any] = {}
    if len(args) == 2 and isinstance(args[0], str) and isinstance(args[1], dict):
        event = args[0]
        data = dict(args[1])
    elif len(args) == 1 and isinstance(args[0], dict):
        raw = dict(args[0])
        event = str(raw.pop("type", "log"))
        data = raw
    else:
        raise ValueError("Resource module emitted an invalid event")
    if event in {"result", "end"}:
        return None
    if event == "stage":
        if "stage" not in data and isinstance(data.get("name"), str):
            data["stage"] = data.pop("name")
        label = _stage_label(str(data.get("stage", "")))
        data.setdefault("label", label)
        data.setdefault("message", _stage_message(label, str(data.get("status", ""))))
    elif event == "progress":
        data.setdefault("message", _progress_message(data))
    elif event == "evidence":
        data.setdefault("message", f"已记录解析证据：{data.get('detail', '发现新的结构信息')}")
    elif event == "warning":
        data.setdefault("message", f"需要关注：{data.get('detail', '资源解析产生警告')}")
    return event, data


def _trace_forwarder(trace: List[Dict[str, Any]]) -> Callable[..., None]:
    def forward(*args: object) -> None:
        normalized = _normalize_module_event(*args)
        if normalized is None:
            return
        event, data = normalized
        trace.append({"event": event, **data})
        _emit(event, data)

    return forward


def _stage_label(stage: str) -> str:
    return {
        "discovering": "识别资源来源",
        "downloading": "拉取原始资源",
        "scanning": "扫描资源结构",
        "profiling": "生成标准描述",
        "deterministic": "执行确定性检查",
        "llm": "智能体补充分析",
        "adapt_plan": "智能体生成适配计划",
        "execute": "执行受约束适配",
        "reprofile": "重新解析派生产物",
        "verify": "再次兼容性分析",
        "complete": "登记已验证数据集",
        "result": "生成兼容性报告",
    }.get(stage, stage or "处理资源")


def _stage_message(label: str, status: str) -> str:
    suffix = {
        "started": "开始",
        "completed": "完成",
        "failed": "失败",
    }.get(status, "进行中")
    return f"{label}：{suffix}"


def _progress_message(data: Dict[str, Any]) -> str:
    file_count = data.get("fileCount")
    current_bytes = data.get("downloadedBytes", data.get("bytesCopied"))
    if isinstance(file_count, int) and isinstance(current_bytes, int):
        return f"已处理 {file_count} 个文件，共 {current_bytes} 字节"
    if isinstance(current_bytes, int):
        return f"已处理 {current_bytes} 字节"
    if isinstance(file_count, int):
        return f"已处理 {file_count} 个文件"
    return "资源处理进度已更新"


def _resource_id(kind: str, source_type: str, source: str) -> str:
    digest = hashlib.sha256(
        f"{kind}\0{source_type}\0{source}".encode("utf-8")
    ).hexdigest()[:12]
    return f"{kind}_{digest}"


def _store(path: str) -> ResourceStore:
    return ResourceStore(Path(path).resolve())


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage dataset and model resources.")
    parser.add_argument(
        "--store",
        default=".datamodelmatch",
        help="Managed resource directory (default: .datamodelmatch)",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    search = subparsers.add_parser("search")
    search.add_argument("kind", choices=("dataset", "model"))
    search.add_argument("query")
    search.add_argument("--limit", type=int, default=8)

    listing = subparsers.add_parser("list")
    listing.add_argument("--kind", choices=("dataset", "model"))

    get = subparsers.add_parser("get")
    get.add_argument("resource_id")

    delete = subparsers.add_parser("delete")
    delete.add_argument("resource_id")

    reprofile = subparsers.add_parser("reprofile")
    reprofile.add_argument("resource_id")
    reprofile.add_argument("--max-bytes", type=int, default=500 * 1024 * 1024)

    importing = subparsers.add_parser("import")
    importing.add_argument("kind", choices=("dataset", "model"))
    importing.add_argument("source_type")
    importing.add_argument("source")
    importing.add_argument("--revision", default="")
    importing.add_argument(
        "--download-mode",
        choices=("metadata", "sample", "full"),
        default="sample",
    )
    importing.add_argument("--max-bytes", type=int, default=500 * 1024 * 1024)

    compatibility = subparsers.add_parser("compatibility")
    compatibility.add_argument("dataset_resource_id")
    compatibility.add_argument("model_resource_id")
    compatibility.add_argument("--config", default="config.llm.json")
    compatibility.add_argument("--timeout", type=float, default=90)
    transform = subparsers.add_parser("transform-dataset")
    transform.add_argument("dataset_resource_id")
    transform.add_argument("model_resource_id")
    transform.add_argument("report_json")
    transform.add_argument("--config", default="config.llm.json")
    transform.add_argument("--timeout", type=float, default=90)
    transform.add_argument("--max-attempts", type=int, default=3)
    semantic_profile = subparsers.add_parser("semantic-profile")
    semantic_profile.add_argument("resource_id")
    semantic_profile.add_argument("--force", action="store_true")
    semantic_get = subparsers.add_parser("semantic-profile-get")
    semantic_get.add_argument("resource_id")
    task_profile = subparsers.add_parser("task-profile")
    task_profile.add_argument("text")
    task_match = subparsers.add_parser("dataset-task-match")
    task_match.add_argument("text")
    return parser


def main(argv: List[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    store = _store(args.store)
    try:
        if args.command == "search":
            return _search(args)
        if args.command == "list":
            resources = [
                {
                    "resource": record.to_dict(),
                    "profile": store.load_profile(record.id),
                }
                for record in store.list(args.kind)
            ]
            print(json.dumps({"resources": resources}, ensure_ascii=False))
            return 0
        if args.command == "get":
            record = store.get(args.resource_id)
            print(json.dumps({
                "resource": record.to_dict(),
                "profile": store.load_profile(args.resource_id),
            }, ensure_ascii=False))
            return 0
        if args.command == "delete":
            store.delete(args.resource_id)
            print(json.dumps({"deleted": True, "id": args.resource_id}, ensure_ascii=False))
            return 0
        if args.command == "reprofile":
            return _reprofile(args, store)
        if args.command == "import":
            return _import(args, store)
        if args.command == "compatibility":
            return _compatibility(args, store)
        if args.command == "transform-dataset":
            return _transform_dataset(args, store)
        if args.command == "semantic-profile":
            return _semantic_profile(args, store)
        if args.command == "semantic-profile-get":
            return _semantic_profile_get(args, store)
        if args.command == "task-profile":
            return _task_profile(args)
        if args.command == "dataset-task-match":
            return _dataset_task_match(args, store)
    except Exception as exc:
        if args.command in {"import", "reprofile", "compatibility", "transform-dataset"}:
            _emit("error", {"code": _error_code(exc), "message": str(exc)})
            _emit("end", {"status": "failed"})
        else:
            print(json.dumps({
                "error": {"code": _error_code(exc), "message": str(exc)}
            }, ensure_ascii=False), file=sys.stderr)
        return 1
    return 2


def _search(args: argparse.Namespace) -> int:
    if args.kind == "dataset":
        from .dataset_resources import search_huggingface_datasets

        results = search_huggingface_datasets(args.query, args.limit)
    else:
        from .model_resources import search_github_models

        results = search_github_models(args.query, args.limit)
    print(json.dumps({"results": results}, ensure_ascii=False))
    return 0


def _import(args: argparse.Namespace, store: ResourceStore) -> int:
    source = args.source
    if args.source_type == "local":
        source = _validate_local_source(args.source, store)
    revision = args.revision or (
        "local"
        if args.source_type == "local"
        else "main" if args.kind == "dataset" else "HEAD"
    )
    resource_id = _resource_id(args.kind, args.source_type, source)
    category = "datasets" if args.kind == "dataset" else "models"
    destination = store.root / "resources" / category / resource_id
    trace: List[Dict[str, Any]] = []
    forward = _trace_forwarder(trace)
    if args.kind == "dataset":
        from .dataset_resources import import_dataset

        record, profile = import_dataset(
            args.source_type,
            source,
            revision,
            destination,
            resource_id,
            args.download_mode,
            args.max_bytes,
            forward,
        )
    else:
        from .model_resources import import_model

        record, profile = import_model(
            args.source_type,
            source,
            revision,
            destination,
            resource_id,
            args.download_mode,
            args.max_bytes,
            forward,
        )
    profile_dict = profile.to_dict() if hasattr(profile, "to_dict") else profile
    profile_dict = dict(profile_dict)
    profile_dict["trace"] = trace[-100:]
    local_path = destination.relative_to(store.root).as_posix()
    record = replace(
        record,
        local_path=local_path,
        profile_path=f"profiles/{category}/{resource_id}.json",
    )
    if args.kind == "dataset":
        from .semantic_runtime import build_semantic_profile

        previous_record = None
        previous_profile = None
        try:
            previous_record = store.get(record.id)
            previous_profile = store.load_profile(record.id)
        except KeyError:
            pass
        pending_record = replace(record, status="analyzing")
        store.save(pending_record, profile_dict)
        _emit("stage", {
            "stage": "llm",
            "status": "started",
            "message": "正在生成数据集语义分析",
        })
        try:
            semantic_profile = build_semantic_profile(store, pending_record.id)
        except Exception:
            if previous_record is not None and previous_profile is not None:
                store.save(previous_record, previous_profile)
            else:
                store.delete(pending_record.id)
            raise
        store.save(record, profile_dict)
        _emit("stage", {
            "stage": "llm",
            "status": "completed",
            "message": "数据集语义分析已完成",
        })
        profile_dict["semanticProfile"] = semantic_profile
    else:
        store.save(record, profile_dict)
    _emit("result", {"resource": record.to_dict(), "profile": profile_dict})
    _emit("end", {"status": "completed"})
    return 0


def _reprofile(args: argparse.Namespace, store: ResourceStore) -> int:
    record = store.get(args.resource_id)
    if record.kind != "dataset" or record.source_type != "local":
        raise ValueError("目前仅支持重新解析本地数据集资源")
    if isinstance(args.max_bytes, bool) or args.max_bytes < 1:
        raise ValueError("max_bytes 必须是正整数")
    from .dataset_resources import reprofile_dataset_snapshot

    _emit("stage", {"stage": "scanning", "status": "started"})
    profile, file_count, size_bytes = reprofile_dataset_snapshot(
        record.id,
        record.name,
        record.source_type,
        record.source,
        record.resolved_revision,
        store.resource_path(record.id),
        args.max_bytes,
    )
    _emit("stage", {"stage": "profiling", "status": "started"})
    profile["trace"] = [
        {"event": "stage", "stage": "scanning", "status": "completed", "message": "已重新扫描资源快照"},
        {"event": "stage", "stage": "profiling", "status": "completed", "message": "已使用当前静态适配器生成描述"},
    ]
    updated_record = replace(
        record,
        status="ready" if profile["completeness"] >= 0.5 else "needs_review",
        file_count=file_count,
        size_bytes=size_bytes,
        updated_at=_iso_now(),
        warnings=list(profile["warnings"]),
    )
    store.save(updated_record, profile)
    _emit("stage", {"stage": "profiling", "status": "completed"})
    _emit("result", {"resource": updated_record.to_dict(), "profile": profile})
    _emit("end", {"status": "completed"})
    return 0


def _iso_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _validate_local_source(source: str, store: ResourceStore) -> str:
    origin = Path(source).expanduser()
    if not origin.is_dir() or origin.is_symlink():
        raise ValueError("本地来源必须是存在且非符号链接的目录")
    origin = origin.resolve()
    workspace = Path.cwd().resolve()
    disallowed_exact = {
        Path("/").resolve(),
        Path.home().resolve(),
        workspace,
    }
    if origin in disallowed_exact:
        raise ValueError("该本地目录属于受保护路径，不能作为资源导入")
    if any(part in {".ssh", ".aws", ".gnupg", ".kube"} for part in origin.parts):
        raise ValueError("该本地目录属于敏感配置路径，不能作为资源导入")
    protected_subtrees = {
        (workspace / ".git").resolve(),
        (workspace / "_reference_only").resolve(),
        store.root.resolve(),
    }
    for protected in protected_subtrees:
        if origin == protected or protected in origin.parents:
            raise ValueError("该本地目录属于受保护路径，不能作为资源导入")
    return str(origin)


def _compatibility(args: argparse.Namespace, store: ResourceStore) -> int:
    from .compatibility import analyze_compatibility

    dataset = store.get(args.dataset_resource_id)
    model = store.get(args.model_resource_id)
    if dataset.kind != "dataset" or model.kind != "model":
        raise ValueError("Compatibility requires one dataset and one model resource")
    config = load_llm_config(Path(args.config))
    client = LLMClient(config, args.timeout)
    report = analyze_compatibility(
        store.load_profile(dataset.id),
        store.load_profile(model.id),
        client,
        _forward_module_event,
    )
    _emit("result", {"report": report.to_dict()})
    _emit("end", {"status": "completed"})
    return 0


def _transform_dataset(args: argparse.Namespace, store: ResourceStore) -> int:
    from .dataset_transform import transform_dataset

    report_path = Path(args.report_json)
    report = json.loads(report_path.read_text(encoding="utf-8"))
    dataset = store.get(args.dataset_resource_id)
    model = store.get(args.model_resource_id)
    resource_id = _resource_id(
        "dataset",
        "derived",
        f"{dataset.id}\0{model.id}\0{json.dumps(report, sort_keys=True, ensure_ascii=False)}",
    )
    destination = store.root / "resources" / "datasets" / resource_id
    config = load_llm_config(Path(args.config))
    client = LLMClient(config, args.timeout)
    record, profile = transform_dataset(
        store,
        dataset.id,
        model.id,
        report,
        destination,
        resource_id,
        _forward_module_event,
        client=client,
        max_attempts=args.max_attempts,
    )
    _emit("result", {"resource": record.to_dict(), "profile": profile})
    _emit("end", {"status": "completed"})
    return 0


def _semantic_profile(args: argparse.Namespace, store: ResourceStore) -> int:
    from .semantic_runtime import build_semantic_profile

    profile = build_semantic_profile(store, args.resource_id, force=bool(args.force))
    print(json.dumps({"profile": profile, "status": "completed"}, ensure_ascii=False))
    return 0


def _semantic_profile_get(args: argparse.Namespace, store: ResourceStore) -> int:
    from .semantic_runtime import get_semantic_profile

    print(json.dumps({"profile": get_semantic_profile(store, args.resource_id)}, ensure_ascii=False))
    return 0


def _task_profile(args: argparse.Namespace) -> int:
    from .semantic_matching import parse_task

    print(json.dumps({"task": parse_task(args.text)}, ensure_ascii=False))
    return 0


def _dataset_task_match(args: argparse.Namespace, store: ResourceStore) -> int:
    from .semantic_matching import match_task, parse_task
    from .semantic_agent import SemanticAgentClient
    from .semantic_runtime import build_semantic_profile

    task = parse_task(args.text)
    agent = SemanticAgentClient.from_config()
    profiles: List[Dict[str, Any]] = []
    for record in store.list("dataset"):
        if record.status == "failed":
            continue
        profile = build_semantic_profile(store, record.id, agent_client=agent)
        profile["name"] = record.name
        profiles.append(profile)
    matches = match_task(task, profiles, agent)
    if matches:
        task["interpretation"] = matches[0]["taskInterpretation"]
    print(
        json.dumps(
            {"task": task, "matches": matches},
            ensure_ascii=False,
        )
    )
    return 0


def _error_code(error: Exception) -> str:
    name = error.__class__.__name__.upper()
    if isinstance(error, KeyError):
        return "RESOURCE_NOT_FOUND"
    if isinstance(error, TimeoutError):
        return "TIMEOUT"
    if isinstance(error, ValueError):
        return "INVALID_INPUT"
    return name


if __name__ == "__main__":
    raise SystemExit(main())
