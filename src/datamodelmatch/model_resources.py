"""Safe, static import and profiling for managed deep-learning model resources.

This module never executes repository code, installs dependencies, or reads model
weights.  GitHub repositories are resolved to a commit SHA before downloading a
source archive; local directories are copied without following symbolic links.
"""

from __future__ import annotations

import base64
import io
import json
import os
import re
import shutil
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Tuple

from .resource_types import (
    ContractField,
    Evidence,
    ModelContract,
    ModelProfile,
    ResourceRecord,
    SourceRef,
)


GITHUB_API = "https://api.github.com"
GITHUB_WEB = "https://github.com"
GITHUB_CODELOAD = "https://codeload.github.com"
DEFAULT_MAX_BYTES = 50 * 1024 * 1024
TEXT_FILE_LIMIT = 512 * 1024
GITHUB_SAMPLE_FILE_LIMIT = 12
WEIGHT_SUFFIXES = {
    ".bin", ".ckpt", ".h5", ".keras", ".onnx", ".pb", ".pt", ".pth",
    ".safetensors", ".tflite", ".weights", ".msgpack",
}
IGNORED_DIRS = {
    ".git", ".ssh", ".aws", ".gnupg", ".kube", "__pycache__",
    ".venv", "venv", "node_modules",
}
IGNORED_FILENAMES = {
    ".env", ".env.local", ".env.production", "config.llm.json",
    "credentials.json", "secrets.json",
}
DEPENDENCY_FILENAMES = {
    "requirements.txt", "requirements-dev.txt", "pyproject.toml", "setup.py",
    "setup.cfg", "environment.yml", "environment.yaml", "pipfile",
}
ENTRYPOINT_FILENAMES = {
    "app.py", "main.py", "serve.py", "inference.py", "predict.py", "train.py",
    "run.py", "cli.py",
}


class ModelResourceError(ValueError):
    """Raised when a model resource cannot safely be discovered or imported."""


Emit = Optional[Callable[[Dict[str, Any]], None]]


def search_github_models(query: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Return lightweight GitHub model repository candidates without downloading.

    The GitHub unauthenticated search API is intentionally used here.  Callers
    receive a clear error for rate limiting or network failures rather than a
    misleading empty result.
    """

    query = _required_text(query, "query")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100:
        raise ModelResourceError("limit must be an integer between 1 and 100")
    encoded = urllib.parse.urlencode({
        "q": f"{query} (machine-learning OR deep-learning)",
        "sort": "stars",
        "order": "desc",
        "per_page": limit,
    })
    payload = _github_json(f"{GITHUB_API}/search/repositories?{encoded}")
    items = payload.get("items")
    if not isinstance(items, list):
        raise ModelResourceError("GitHub search returned an invalid response")
    results: List[Dict[str, Any]] = []
    for item in items[:limit]:
        if not isinstance(item, Mapping):
            continue
        full_name = item.get("full_name")
        html_url = item.get("html_url")
        if not isinstance(full_name, str) or not isinstance(html_url, str):
            continue
        results.append({
            "id": full_name,
            "name": item.get("name") if isinstance(item.get("name"), str) else full_name.rsplit("/", 1)[-1],
            "fullName": full_name,
            "url": html_url,
            "description": item.get("description") if isinstance(item.get("description"), str) else "",
            "defaultBranch": item.get("default_branch") if isinstance(item.get("default_branch"), str) else "",
            "stars": item.get("stargazers_count") if isinstance(item.get("stargazers_count"), int) else 0,
            "updatedAt": item.get("updated_at") if isinstance(item.get("updated_at"), str) else "",
        })
    return results


def import_model(
    source_type: str,
    source: str,
    revision: Optional[str],
    destination: str | Path,
    resource_id: str,
    download_mode: str,
    max_bytes: int,
    emit: Emit = None,
) -> Tuple[ResourceRecord, Dict[str, Any]]:
    """Import a GitHub or local model source and build a static ModelProfile.

    ``destination`` is the final resource directory.  It is replaced atomically
    only after a complete safe copy/download succeeds.  ``download_mode`` accepts
    ``metadata``, ``sample``, and ``full``.  Model source profiling needs text
    files, so metadata imports create an inventory-only snapshot; sample and full
    both fetch source files while always excluding weights and ``.git``.
    """

    source_type = _required_text(source_type, "source_type").lower()
    source = _required_text(source, "source")
    resource_id = _required_text(resource_id, "resource_id")
    destination_path = Path(destination)
    _validate_download_mode(download_mode)
    _validate_max_bytes(max_bytes)
    if source_type not in {"github", "local"}:
        raise ModelResourceError("source_type must be 'github' or 'local'")

    _emit(emit, "stage", stage="discovering", status="started")
    if source_type == "github":
        owner, repo = _parse_github_source(source)
        requested_revision = revision.strip() if isinstance(revision, str) and revision.strip() else "HEAD"
        resolved_revision = _resolve_github_revision(owner, repo, requested_revision)
        canonical_source = f"{owner}/{repo}"
        name = repo
        _emit(
            emit,
            "evidence",
            kind="resolved_revision",
            source=canonical_source,
            detail=resolved_revision,
        )
        _emit(emit, "stage", stage="discovering", status="completed")
        with tempfile.TemporaryDirectory(prefix="datamodelmatch-model-") as temp_dir:
            staging = Path(temp_dir) / "snapshot"
            _emit(emit, "stage", stage="downloading", status="started")
            _download_github_archive(
                owner,
                repo,
                resolved_revision,
                staging,
                max_bytes,
                download_mode,
                emit,
            )
            _emit(emit, "stage", stage="downloading", status="completed")
            _replace_destination(staging, destination_path)
    else:
        source_path = Path(source).expanduser()
        if not source_path.is_dir():
            raise ModelResourceError("local source must be an existing directory")
        if source_path.is_symlink():
            raise ModelResourceError("local source directory must not be a symbolic link")
        canonical_source = str(source_path.resolve())
        requested_revision = revision.strip() if isinstance(revision, str) and revision.strip() else "local"
        resolved_revision = _local_revision(source_path)
        name = source_path.name
        _emit(emit, "stage", stage="discovering", status="completed")
        _emit(emit, "stage", stage="scanning", status="started")
        with tempfile.TemporaryDirectory(prefix="datamodelmatch-model-") as temp_dir:
            staging = Path(temp_dir) / "snapshot"
            _copy_local_tree(source_path, staging, max_bytes, download_mode, emit)
            _replace_destination(staging, destination_path)
        _emit(emit, "stage", stage="scanning", status="completed")

    _emit(emit, "stage", stage="profiling", status="started")
    profile = _profile_model(
        destination_path,
        resource_id=resource_id,
        name=name,
        source_type=source_type,
        source=canonical_source,
        revision=resolved_revision,
    )
    _emit(emit, "stage", stage="profiling", status="completed")
    file_count, size_bytes = _inventory(destination_path)
    now = _utc_now()
    record = ResourceRecord(
        id=resource_id,
        kind="model",
        source_type=source_type,
        source=canonical_source,
        revision=requested_revision,
        resolved_revision=resolved_revision,
        name=name,
        status="ready",
        local_path=str(destination_path),
        profile_path=f"profiles/models/{resource_id}.json",
        file_count=file_count,
        size_bytes=size_bytes,
        created_at=now,
        updated_at=now,
        warnings=list(profile["warnings"]),
    )
    _emit(emit, "result", record=record.to_dict(), profile=profile)
    _emit(emit, "end", status="completed")
    return record, profile


def _parse_github_source(source: str) -> Tuple[str, str]:
    """Parse an owner/repository pair or canonical GitHub URL."""

    value = source.strip()
    if value.startswith("git@github.com:"):
        value = value[len("git@github.com:"):]
    elif value.startswith(("http://", "https://")):
        parsed = urllib.parse.urlparse(value)
        if parsed.scheme != "https" or parsed.netloc.lower() != "github.com":
            raise ModelResourceError("GitHub source URL must use https://github.com")
        value = parsed.path.lstrip("/")
    value = value.rstrip("/")
    if value.endswith(".git"):
        value = value[:-4]
    parts = value.split("/")
    if len(parts) != 2 or not all(_github_name_part(part) for part in parts):
        raise ModelResourceError("GitHub source must be owner/repository or an https://github.com URL")
    return parts[0], parts[1]


def _github_name_part(value: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value))


def _resolve_github_revision(owner: str, repo: str, revision: str) -> str:
    if re.fullmatch(r"[0-9a-fA-F]{40}", revision):
        return revision.lower()
    encoded = urllib.parse.quote(revision, safe="")
    payload = _github_json(f"{GITHUB_API}/repos/{owner}/{repo}/commits/{encoded}")
    sha = payload.get("sha")
    if not isinstance(sha, str) or not re.fullmatch(r"[0-9a-fA-F]{7,64}", sha):
        raise ModelResourceError("GitHub did not return a valid commit SHA")
    return sha.lower()


def _download_github_archive(
    owner: str,
    repo: str,
    revision: str,
    destination: Path,
    max_bytes: int,
    download_mode: str,
    emit: Emit,
) -> None:
    if download_mode == "metadata":
        destination.mkdir(parents=True, exist_ok=True)
        metadata = _github_json(f"{GITHUB_API}/repos/{owner}/{repo}")
        _write_text(destination / "README.metadata.json", json.dumps({
            "full_name": metadata.get("full_name"),
            "description": metadata.get("description"),
            "license": (metadata.get("license") or {}).get("spdx_id")
            if isinstance(metadata.get("license"), Mapping) else None,
        }, indent=2))
        return
    if download_mode == "sample":
        _download_github_sample_files(
            owner,
            repo,
            revision,
            destination,
            max_bytes,
            emit,
        )
        return
    url = f"{GITHUB_CODELOAD}/{owner}/{repo}/zip/{revision}"
    archive = _read_limited(url, max_bytes)
    _emit(emit, "progress", downloadedBytes=len(archive), maxBytes=max_bytes)
    try:
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            _extract_safe_archive(bundle, destination, max_bytes, download_mode, emit)
    except zipfile.BadZipFile as error:
        raise ModelResourceError("GitHub archive was not a valid ZIP file") from error


def _download_github_sample_files(
    owner: str,
    repo: str,
    revision: str,
    destination: Path,
    max_bytes: int,
    emit: Emit,
) -> None:
    payload = _github_json(
        f"{GITHUB_API}/repos/{owner}/{repo}/git/trees/{revision}?recursive=1"
    )
    tree = payload.get("tree")
    if not isinstance(tree, list):
        raise ModelResourceError("GitHub tree API returned an invalid response")
    candidates: List[Tuple[int, str, str, int]] = []
    for item in tree:
        if not isinstance(item, Mapping) or item.get("type") != "blob":
            continue
        path_value, sha = item.get("path"), item.get("sha")
        size = item.get("size", 0)
        if (
            not isinstance(path_value, str)
            or not isinstance(sha, str)
            or not isinstance(size, int)
            or size < 0
        ):
            continue
        relative = Path(PurePosixPath(path_value))
        if (
            PurePosixPath(path_value).is_absolute()
            or ".." in relative.parts
            or _should_ignore(relative)
            or _is_weight_path(relative)
            or not _is_sample_file(relative)
            or size > TEXT_FILE_LIMIT
        ):
            continue
        candidates.append((_sample_priority(relative), path_value, sha, size))
    candidates.sort(key=lambda item: (item[0], item[3], item[1]))
    selected = candidates[:GITHUB_SAMPLE_FILE_LIMIT]
    if not selected:
        raise ModelResourceError("no safe source files were available through the GitHub API")

    destination.mkdir(parents=True, exist_ok=True)
    total = 0
    for file_count, (_, path_value, sha, declared_size) in enumerate(selected, start=1):
        blob = _github_json(f"{GITHUB_API}/repos/{owner}/{repo}/git/blobs/{sha}")
        content = blob.get("content")
        if blob.get("encoding") != "base64" or not isinstance(content, str):
            raise ModelResourceError("GitHub blob API returned an unsupported response")
        try:
            data = base64.b64decode(re.sub(r"\s+", "", content), validate=True)
        except ValueError as error:
            raise ModelResourceError("GitHub blob API returned invalid base64 content") from error
        if len(data) != declared_size:
            raise ModelResourceError("GitHub blob size did not match repository metadata")
        if total + len(data) > max_bytes:
            raise ModelResourceError("model resource exceeds max_bytes")
        relative = Path(PurePosixPath(path_value))
        target = destination / relative
        _ensure_within(destination, target)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        total += len(data)
        _emit(
            emit,
            "progress",
            fileCount=file_count,
            downloadedBytes=total,
            maxBytes=max_bytes,
        )


def _sample_priority(path: Path) -> int:
    name = path.name.lower()
    if name.startswith("readme") or name.startswith("license") or name == "copying":
        return 0
    if name in DEPENDENCY_FILENAMES:
        return 1
    if name in ENTRYPOINT_FILENAMES:
        return 2
    return 3


def _extract_safe_archive(
    bundle: zipfile.ZipFile,
    destination: Path,
    max_bytes: int,
    download_mode: str,
    emit: Emit,
) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    total = 0
    copied = 0
    for entry in bundle.infolist():
        relative = _archive_relative_path(entry.filename)
        if relative is None or entry.is_dir() or _should_ignore(relative):
            continue
        if _is_weight_path(relative):
            continue
        if download_mode == "sample" and not _is_sample_file(relative):
            continue
        if entry.file_size > max_bytes or total + entry.file_size > max_bytes:
            raise ModelResourceError("model resource exceeds max_bytes")
        target = destination / relative
        _ensure_within(destination, target)
        target.parent.mkdir(parents=True, exist_ok=True)
        with bundle.open(entry) as input_file, target.open("wb") as output_file:
            shutil.copyfileobj(input_file, output_file, length=64 * 1024)
        total += entry.file_size
        copied += 1
        _emit(emit, "progress", fileCount=copied, downloadedBytes=total, maxBytes=max_bytes)
    if copied == 0:
        raise ModelResourceError("no safe source files were available in the model archive")


def _archive_relative_path(name: str) -> Optional[Path]:
    parts = PurePosixPath(name).parts
    if len(parts) < 2 or any(part in {"", ".", ".."} for part in parts):
        return None
    return Path(*parts[1:])


def _copy_local_tree(
    source: Path,
    destination: Path,
    max_bytes: int,
    download_mode: str,
    emit: Emit,
) -> None:
    root = source.resolve()
    destination.mkdir(parents=True, exist_ok=True)
    total = 0
    copied = 0
    for current, dirs, files in os.walk(root, followlinks=False):
        current_path = Path(current)
        safe_dirs = []
        for name in dirs:
            candidate = current_path / name
            if name in IGNORED_DIRS:
                continue
            if candidate.is_symlink():
                _reject_external_symlink(root, candidate)
                continue
            safe_dirs.append(name)
        dirs[:] = safe_dirs
        for filename in files:
            origin = current_path / filename
            if origin.is_symlink():
                _reject_external_symlink(root, origin)
                continue
            try:
                resolved = origin.resolve(strict=True)
            except OSError:
                continue
            if not _is_within(root, resolved):
                raise ModelResourceError("local source contains a file symlink outside its root")
            relative = resolved.relative_to(root)
            if _should_ignore(relative) or _is_weight_path(relative):
                continue
            if download_mode == "metadata":
                continue
            if download_mode == "sample" and not _is_sample_file(relative):
                continue
            size = resolved.stat().st_size
            if size > max_bytes or total + size > max_bytes:
                raise ModelResourceError("model resource exceeds max_bytes")
            target = destination / relative
            _ensure_within(destination, target)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(resolved, target)
            total += size
            copied += 1
            _emit(emit, "progress", fileCount=copied, downloadedBytes=total, maxBytes=max_bytes)
    if download_mode == "metadata":
        _write_text(destination / "LOCAL.metadata.json", json.dumps({"source": str(root)}, indent=2))
    elif copied == 0:
        raise ModelResourceError("no safe source files were available in the local directory")


def _reject_external_symlink(root: Path, link: Path) -> None:
    try:
        resolved = link.resolve(strict=True)
    except OSError as error:
        raise ModelResourceError("local source contains an unreadable symbolic link") from error
    if not _is_within(root, resolved):
        raise ModelResourceError("local source contains a symbolic link outside its root")


def _should_ignore(path: Path) -> bool:
    name = path.name.lower()
    return (
        any(part in IGNORED_DIRS for part in path.parts)
        or name in IGNORED_FILENAMES
        or name.startswith(".env.")
    )


def _is_weight_path(path: Path) -> bool:
    return path.suffix.lower() in WEIGHT_SUFFIXES


def _is_sample_file(path: Path) -> bool:
    name = path.name.lower()
    return (
        name in {"readme.md", "readme.rst", "readme.txt", "license", "license.md", "copying"}
        or name in DEPENDENCY_FILENAMES
        or name in ENTRYPOINT_FILENAMES
        or path.suffix.lower() in {".md", ".rst", ".txt", ".json", ".yaml", ".yml", ".toml", ".py"}
    )


def _profile_model(
    root: Path,
    resource_id: str,
    name: str,
    source_type: str,
    source: str,
    revision: str,
) -> Dict[str, Any]:
    texts = _read_profile_texts(root)
    all_text = "\n".join(text for _, text in texts).lower()
    implementation_text = "\n".join(
        text
        for path, text in texts
        if not path.name.lower().startswith(("readme", "license", "copying"))
    ).lower()
    evidence: List[Evidence] = []
    warnings: List[str] = []

    readme_paths = [path for path, _ in texts if path.name.lower().startswith("readme")]
    if readme_paths:
        evidence.append(Evidence("readme", str(readme_paths[0]), "已完成 README 静态检查"))
    else:
        warnings.append("未找到 README，模型用途的静态推断可能不完整")

    dependency_files = sorted(
        str(path.relative_to(root))
        for path, _ in texts
        if path.name.lower() in DEPENDENCY_FILENAMES
    )
    for path in dependency_files:
        evidence.append(Evidence("dependency_file", path, "已检查依赖声明"))
    framework_patterns = {
        "pytorch": (r"\btorch\b", r"\bpytorch\b"),
        "tensorflow": (r"\btensorflow\b", r"\btf\.keras\b"),
        "keras": (r"\bkeras\b",),
        "transformers": (r"\btransformers\b", r"\bautotokenizer\b", r"\bautomodel\b"),
        "onnx": (r"\bonnx\b",),
        "jax": (r"\bjax\b",),
        "flax": (r"\bflax\b",),
    }
    frameworks = _find_terms(implementation_text, framework_patterns)
    if not frameworks:
        frameworks = _find_terms(all_text, framework_patterns)
    architectures = _find_terms(all_text, {
        "transformer": (r"\btransformer\b", r"\bbert\b", r"\bgpt\b", r"\bllama\b"),
        "cnn": (r"\bcnn\b", r"\bconvolutional\b", r"\bconv2d\b"),
        "resnet": (r"\bresnet\b",),
        "unet": (r"\bu-?net\b",),
        "rnn": (r"\b(?:lstm|gru|rnn)\b",),
        "diffusion": (r"\bdiffusion\b",),
    })
    tasks = _find_terms(all_text, {
        "text-generation": (r"\btext generation\b", r"\bcausal language model", r"\blanguage modeling\b"),
        "text-classification": (
            r"\btext classification\b",
            r"\bsequence classification\b",
            r"\bautomodelforsequenceclassification\b",
            r"文本分类",
            r"分类模型",
        ),
        "token-classification": (r"\btoken classification\b", r"\bner\b"),
        "question-answering": (r"\bquestion answering\b", r"\bqa\b"),
        "image-classification": (r"\bimage classification\b",),
        "object-detection": (r"\bobject detection\b",),
        "image-segmentation": (r"\b(?:image|semantic) segmentation\b",),
        "speech-recognition": (r"\b(?:speech recognition|automatic speech recognition|asr)\b",),
        "image-to-text": (r"\b(?:image captioning|visual question answering|image-to-text)\b",),
    })
    if "image-classification" not in tasks and re.search(
        r"\b(?:cifar-?(?:10|100)|imagenet)\b",
        all_text,
    ) and re.search(
        r"\b(?:crossentropyloss|num_classes|classifier|test accuracy)\b",
        implementation_text,
    ):
        tasks.append("image-classification")
    vision_tasks = {"image-classification", "object-detection", "image-segmentation"}
    if vision_tasks.intersection(tasks):
        strong_text_generation = re.search(
            r"\b(?:gpt(?:-?2)?|causallm|causal language model)\b.*\bgenerate\s*\("
            r"|\bgenerate\s*\(.*\b(?:gpt(?:-?2)?|causallm|causal language model)\b",
            implementation_text,
        )
        if not strong_text_generation:
            tasks = [task for task in tasks if task != "text-generation"]
        if "image-to-text" in tasks and not re.search(
            r"\b(?:image captioning|visual question answering|image-to-text)\b",
            all_text,
        ):
            tasks = [task for task in tasks if task != "image-to-text"]
    if not tasks:
        warnings.append("未能从静态文本中确定模型任务")

    entrypoints = sorted(
        str(path.relative_to(root))
        for path, _ in texts
        if path.name.lower() in ENTRYPOINT_FILENAMES
    )
    for framework in frameworks:
        evidence.append(Evidence("framework", "静态分析", framework))
    for task in tasks:
        evidence.append(Evidence("task_hint", "静态分析", task))

    modalities = _modalities_for(tasks, all_text)
    preprocessing = _preprocessing_for(all_text, modalities)
    input_fields = _input_fields(modalities, all_text)
    output_fields = _output_fields(tasks)
    license_name = _find_license(root, texts)
    if license_name == "unknown":
        warnings.append("未找到可识别的许可证")
    completeness = _completeness(readme_paths, dependency_files, frameworks, tasks, entrypoints, license_name)
    description = _description_from_readme(texts) or f"静态导入的模型资源 {name}"
    profile = ModelProfile(
        resource_id=resource_id,
        name=name,
        description=description,
        source=SourceRef(source_type, source, revision),
        frameworks=frameworks,
        architectures=architectures,
        tasks=tasks,
        input_contract=ModelContract(
            modalities=modalities,
            fields=input_fields,
            preprocessing=preprocessing,
            constraints=[],
        ),
        output_contract=ModelContract(
            modalities=modalities,
            fields=output_fields,
        ),
        entrypoints=entrypoints,
        dependency_files=dependency_files,
        license=license_name,
        evidence=evidence,
        warnings=warnings,
        completeness=completeness,
    )
    return profile.to_dict()


def _read_profile_texts(root: Path) -> List[Tuple[Path, str]]:
    texts: List[Tuple[Path, str]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink() or _should_ignore(path.relative_to(root)):
            continue
        if path.stat().st_size > TEXT_FILE_LIMIT:
            continue
        if path.name.lower() in DEPENDENCY_FILENAMES or path.name.lower() in ENTRYPOINT_FILENAMES or (
            path.name.lower().startswith("readme") or path.name.lower().startswith("license")
            or path.suffix.lower() in {".md", ".rst", ".txt", ".py", ".toml", ".yml", ".yaml", ".json"}
        ):
            try:
                texts.append((path, path.read_text(encoding="utf-8", errors="replace")))
            except OSError:
                continue
    return texts


def _find_terms(text: str, patterns: Mapping[str, Iterable[str]]) -> List[str]:
    return [name for name, values in patterns.items() if any(re.search(value, text) for value in values)]


def _modalities_for(tasks: List[str], text: str) -> List[str]:
    modalities: List[str] = []
    image_tasks = {"image-classification", "object-detection", "image-segmentation", "image-to-text"}
    text_tasks = {
        "text-generation", "text-classification", "token-classification",
        "question-answering",
    }
    if any(task in tasks for task in image_tasks) or (
        not tasks
        and re.search(
            r"\b(?:pixel_values|torchvision|computer vision|vision transformer|image_size)\b",
            text,
        )
    ):
        modalities.append("image")
    if any(task in tasks for task in text_tasks) or (
        not tasks and re.search(r"\b(?:text|tokenizer|input_ids)\b", text)
    ):
        modalities.append("text")
    if "speech-recognition" in tasks:
        modalities.append("audio")
    if not tasks:
        if re.search(r"\b(?:text|tokenizer|input_ids)\b", text):
            modalities.append("text")
        if re.search(r"\b(?:audio|waveform|sampling_rate)\b", text):
            modalities.append("audio")
    return modalities or ["unknown"]


def _preprocessing_for(text: str, modalities: List[str]) -> List[str]:
    result: List[str] = []
    checks: List[Tuple[str, str]] = []
    if "text" in modalities:
        checks.append(("tokenize", r"\b(?:tokenize|tokenizer|input_ids)\b"))
    if "image" in modalities:
        checks.extend([
            ("normalize", r"\b(?:normaliz[ez]|mean\s*=|std\s*=)\b"),
            ("resize", r"\b(?:resize|image_size|resolution)\b"),
            ("padding", r"\b(?:padding|pad_to)\b"),
        ])
    if "audio" in modalities:
        checks.append(("resample", r"\b(?:resample|sampling_rate)\b"))
    for name, pattern in checks:
        if re.search(pattern, text):
            result.append(name)
    if "text" in modalities and "tokenize" not in result:
        result.append("tokenize")
    return result


def _input_fields(modalities: List[str], text: str) -> List[ContractField]:
    fields: List[ContractField] = []
    if "text" in modalities:
        fields.append(ContractField("text", "string", True, description="原始文本或经 tokenizer 处理的文本输入"))
    if "image" in modalities:
        fields.append(ContractField("image", "image", True, description="图像输入"))
    if "audio" in modalities:
        fields.append(ContractField("audio", "audio", True, description="音频波形或音频文件输入"))
    if re.search(r"\binput_ids\b", text) and not fields:
        fields.append(ContractField("input_ids", "integer", True, shape=["batch", "sequence"]))
    return fields or [ContractField("input", "unknown", True, description="未能从静态信息确定输入结构")]


def _output_fields(tasks: List[str]) -> List[ContractField]:
    outputs: List[Tuple[str, str, List[object], str]] = []
    if "text-generation" in tasks:
        outputs.append(("tokens", "integer", ["batch", "sequence"], "文本生成任务输出"))
    if any(task in tasks for task in {"text-classification", "image-classification"}):
        outputs.append(("logits", "number", ["batch", "classes"], "分类任务输出"))
    if "object-detection" in tasks:
        outputs.append(("detections", "object", [], "目标检测任务输出"))
    if "image-segmentation" in tasks:
        outputs.append(("mask", "image", [], "图像分割任务输出"))
    if "image-to-text" in tasks:
        outputs.append(("text", "string", [], "图像到文本任务输出"))
    if "speech-recognition" in tasks:
        outputs.append(("text", "string", [], "语音识别任务输出"))
    if not outputs:
        return [ContractField("output", "unknown", True, description="未能从静态信息确定输出结构")]
    required = len(outputs) == 1
    unique: Dict[str, ContractField] = {}
    for name, data_type, shape, description in outputs:
        unique.setdefault(
            name,
            ContractField(name, data_type, required, shape=shape, description=description),
        )
    return list(unique.values())


def _find_license(root: Path, texts: List[Tuple[Path, str]]) -> str:
    for path, text in texts:
        if path.name.lower().startswith(("license", "copying")):
            return _license_from_text(text)
    for path, text in texts:
        if path.name.lower().startswith("readme"):
            match = re.search(r"(?:license|licence)\s*[:#-]?\s*([A-Za-z0-9 .+-]{3,40})", text, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip()
    return "unknown"


def _license_from_text(text: str) -> str:
    lowered = text.lower()
    for name, markers in {
        "Apache-2.0": ("apache license", "version 2.0"),
        "MIT": ("mit license",),
        "BSD-3-Clause": ("redistribution and use in source and binary forms",),
        "GPL-3.0": ("gnu general public license", "version 3"),
        "CC-BY-4.0": ("creative commons attribution 4.0",),
    }.items():
        if all(marker in lowered for marker in markers):
            return name
    return "unknown"


def _description_from_readme(texts: List[Tuple[Path, str]]) -> str:
    for path, text in texts:
        if path.name.lower().startswith("readme"):
            for line in text.splitlines():
                clean = line.strip().lstrip("#").strip()
                if clean and not clean.startswith(("[", "!", "<")):
                    return clean[:500]
    return ""


def _completeness(
    readmes: List[Path],
    dependency_files: List[str],
    frameworks: List[str],
    tasks: List[str],
    entrypoints: List[str],
    license_name: str,
) -> float:
    signals = [
        bool(readmes), bool(dependency_files), bool(frameworks), bool(tasks),
        bool(entrypoints), license_name != "unknown",
    ]
    return round(sum(signals) / len(signals), 2)


def _github_json(url: str) -> Dict[str, Any]:
    request = urllib.request.Request(url, headers={
        "Accept": "application/vnd.github+json",
        "User-Agent": "DataModelMatch/0.1",
    })
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = response.read()
    except urllib.error.HTTPError as error:
        if error.code == 404:
            raise ModelResourceError("GitHub repository or revision was not found") from error
        if error.code in {401, 403}:
            raise ModelResourceError("GitHub request was denied or rate limited") from error
        raise ModelResourceError(f"GitHub request failed with HTTP {error.code}") from error
    except OSError as error:
        raise ModelResourceError("GitHub request failed") from error
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ModelResourceError("GitHub returned invalid JSON") from error
    if not isinstance(decoded, dict):
        raise ModelResourceError("GitHub returned an invalid response")
    return decoded


def _read_limited(url: str, max_bytes: int) -> bytes:
    request = urllib.request.Request(url, headers={"User-Agent": "DataModelMatch/0.1"})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            chunks: List[bytes] = []
            total = 0
            while True:
                chunk = response.read(64 * 1024)
                if not chunk:
                    break
                total += len(chunk)
                if total > max_bytes:
                    raise ModelResourceError("model resource exceeds max_bytes")
                chunks.append(chunk)
            return b"".join(chunks)
    except urllib.error.HTTPError as error:
        raise ModelResourceError(f"GitHub archive download failed with HTTP {error.code}") from error
    except OSError as error:
        raise ModelResourceError("GitHub archive download failed") from error


def _replace_destination(staging: Path, destination: Path) -> None:
    if destination.exists() and destination.is_symlink():
        raise ModelResourceError("destination must not be a symbolic link")
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.parent / f".{destination.name}.staging"
    shutil.rmtree(temporary, ignore_errors=True)
    shutil.copytree(staging, temporary)
    if destination.exists():
        shutil.rmtree(destination)
    temporary.replace(destination)


def _inventory(root: Path) -> Tuple[int, int]:
    count = 0
    size = 0
    for path in root.rglob("*"):
        if path.is_file() and not path.is_symlink():
            count += 1
            size += path.stat().st_size
    return count, size


def _local_revision(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    root = path.resolve()
    for item in sorted(root.rglob("*")):
        if not item.is_file() or item.is_symlink() or _should_ignore(item.relative_to(root)) or _is_weight_path(item.relative_to(root)):
            continue
        relative = item.relative_to(root).as_posix().encode("utf-8")
        stat = item.stat()
        digest.update(relative)
        digest.update(str(stat.st_size).encode("ascii"))
        digest.update(str(stat.st_mtime_ns).encode("ascii"))
    return f"local-{digest.hexdigest()[:16]}"


def _ensure_within(root: Path, candidate: Path) -> None:
    if not _is_within(root.resolve(), candidate.resolve(strict=False)):
        raise ModelResourceError("resource path escapes destination")


def _is_within(root: Path, candidate: Path) -> bool:
    try:
        candidate.relative_to(root)
        return True
    except ValueError:
        return False


def _required_text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ModelResourceError(f"{name} must be a non-empty string")
    return value.strip()


def _validate_download_mode(value: str) -> None:
    if value not in {"metadata", "sample", "full"}:
        raise ModelResourceError("download_mode must be metadata, sample, or full")


def _validate_max_bytes(value: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ModelResourceError("max_bytes must be a positive integer")


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _emit(emit: Emit, event_type: str, **payload: Any) -> None:
    if emit is not None:
        emit({"type": event_type, **payload})


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
