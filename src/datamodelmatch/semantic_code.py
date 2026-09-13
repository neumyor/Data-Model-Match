"""Python execution for dataset-semantic Agent tool calls.

The model writes the inspection program.  This module deliberately does not
encode dataset-format-specific extraction rules: it runs the Agent's program
and validates the image paths selected by that program before any image can
leave the local machine.
"""

from __future__ import annotations

import base64
import json
import os
import re
import resource
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


class DatasetCodeError(ValueError):
    """Raised when an Agent-authored dataset inspection is unsafe or invalid."""


_MAX_CODE_BYTES = 24 * 1024
_MAX_OUTPUT_BYTES = 256 * 1024
_MAX_IMAGES = 5
_MAX_IMAGE_BYTES = 12 * 1024 * 1024
_IMAGE_PREFIXES = {
    b"\x89PNG\r\n\x1a\n": "png",
    b"\xff\xd8\xff": "jpeg",
    b"GIF87a": "gif",
    b"GIF89a": "gif",
    b"RIFF": "webp",
}


@dataclass(frozen=True)
class SelectedImage:
    path: str
    media_type: str
    data_url: str
    byte_count: int

    def to_dict(self) -> dict[str, object]:
        return {
            "path": self.path,
            "mediaType": self.media_type,
            "byteCount": self.byte_count,
        }


@dataclass(frozen=True)
class CodeExecution:
    summary: str
    images: tuple[SelectedImage, ...]
    stdout: str
    image_availability: str = "not_checked"

    def tool_result(self) -> dict[str, object]:
        return {
            "summary": self.summary,
            "images": [item.to_dict() for item in self.images],
            "imageAvailability": self.image_availability,
            "stdout": self.stdout,
        }


class DatasetCodeExecutor:
    """Run one Agent-written Python inspection as a normal local subprocess."""

    def __init__(self, snapshot_root: Path | str, *, python: str | None = None) -> None:
        root = Path(snapshot_root).resolve()
        if root.is_symlink() or not root.is_dir():
            raise DatasetCodeError("dataset snapshot must be a non-symbolic-link directory")
        self.root = root
        # Keep Agent-authored inspection in the same managed Python environment
        # as the semantic service. Falling back to a system ``python3`` can omit
        # declared readers such as pyarrow, which tempts the Agent to install
        # packages during a constrained inspection.
        self.python = python or os.environ.get("PYTHON") or sys.executable

    def run(self, code: object) -> CodeExecution:
        if not isinstance(code, str) or not code.strip() or len(code.encode("utf-8")) > _MAX_CODE_BYTES:
            raise DatasetCodeError("Agent Python code is missing or exceeds the size limit")
        with tempfile.TemporaryDirectory(prefix="datamodelmatch-agent-") as directory:
            # macOS commonly presents temporary directories through /var while
            # Path.resolve() returns /private/var. Keep the base canonical so
            # Agent-created files are not rejected by a false containment check.
            work = Path(directory).resolve()
            script = work / "inspect.py"
            result = work / "result.json"
            script.write_text(code, encoding="utf-8")
            environment = {
                "PATH": os.environ.get("PATH", ""),
                "PYTHONPATH": "",
                "PYTHONNOUSERSITE": "1",
                "DATASET_ROOT": str(self.root),
                "RESULT_PATH": str(result),
                "AGENT_WORKDIR": str(work),
            }
            try:
                completed = subprocess.run(
                    [self.python, "-I", str(script)],
                    cwd=work,
                    env=environment,
                    stdin=subprocess.DEVNULL,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    timeout=25,
                    check=False,
                    preexec_fn=_limit_resources,
                )
            except subprocess.TimeoutExpired as exc:
                raise DatasetCodeError("Agent Python inspection timed out") from exc
            if completed.returncode != 0:
                raise DatasetCodeError("Agent Python inspection failed")
            if not result.is_file() or result.is_symlink() or result.stat().st_size > _MAX_OUTPUT_BYTES:
                diagnostic = completed.stdout.decode("utf-8", errors="replace")[:4_000]
                raise DatasetCodeError(
                    "Agent Python inspection did not write a valid result"
                    + (f"; stdout: {diagnostic}" if diagnostic else "")
                )
            try:
                raw = json.loads(result.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                raise DatasetCodeError("Agent Python inspection result is not JSON") from exc
            return self._validate_result(raw, completed.stdout, work)

    def _validate_result(self, raw: object, stdout: bytes, work: Path) -> CodeExecution:
        if not isinstance(raw, Mapping) or set(raw) != {"summary", "images", "imageStatus"}:
            raise DatasetCodeError("Agent Python result must contain only summary, images, and imageStatus")
        summary = raw.get("summary")
        images = raw.get("images")
        image_status = raw.get("imageStatus")
        if not isinstance(summary, str) or not summary.strip() or len(summary) > 2_000:
            raise DatasetCodeError("Agent Python result summary is invalid")
        if not isinstance(images, list) or len(images) > _MAX_IMAGES:
            raise DatasetCodeError("Agent Python selected an invalid number of images")
        if image_status not in {"sampled", "not_checked", "none_found"}:
            raise DatasetCodeError("Agent Python imageStatus is invalid")
        if (bool(images) and image_status != "sampled") or (not images and image_status == "sampled"):
            raise DatasetCodeError("Agent Python imageStatus does not match selected images")
        selected: list[SelectedImage] = []
        seen: set[str] = set()
        for item in images:
            if not isinstance(item, str) or item in seen:
                raise DatasetCodeError("Agent Python image selection is invalid")
            seen.add(item)
            selected.append(self._read_image(item, work))
        text = stdout.decode("utf-8", errors="replace")[:4_000]
        return CodeExecution(summary.strip(), tuple(selected), text, image_status)

    def _read_image(self, relative: str, work: Path) -> SelectedImage:
        if not re.fullmatch(r"[^\x00]+", relative):
            raise DatasetCodeError("Agent Python selected an unsafe image path")
        requested = Path(relative)
        if requested.is_absolute():
            candidate = requested.resolve(strict=False)
            if not _is_relative_to(candidate, work):
                raise DatasetCodeError("Agent Python selected an unsafe image path")
            base = work
            output = True
        else:
            path = Path(relative.removeprefix("work/")) if relative.startswith("work/") else requested
            if ".." in path.parts:
                raise DatasetCodeError("Agent Python selected an unsafe image path")
            snapshot_candidate = (self.root / path).resolve(strict=False)
            work_candidate = (work / path).resolve(strict=False)
            if relative.startswith("work/") or (not snapshot_candidate.is_file() and work_candidate.is_file()):
                candidate = work_candidate
                base = work
                output = True
            else:
                candidate = snapshot_candidate
                base = self.root
                output = False
        if not _is_relative_to(candidate, base) or candidate.is_symlink() or not candidate.is_file():
            raise DatasetCodeError("Agent Python selected an unavailable image")
        try:
            content = candidate.read_bytes()
        except OSError as exc:
            raise DatasetCodeError("Agent Python selected an unreadable image") from exc
        if not content or len(content) > _MAX_IMAGE_BYTES:
            raise DatasetCodeError("Agent Python selected an oversized image")
        media_type = _image_type(content)
        if media_type is None:
            raise DatasetCodeError("Agent Python selected a file that is not a supported image")
        return SelectedImage(
            ("work/" if output else "") + candidate.relative_to(base).as_posix(),
            media_type,
            f"data:image/{media_type};base64,{base64.b64encode(content).decode('ascii')}",
            len(content),
        )


def _limit_resources() -> None:
    # macOS does not implement every POSIX resource limit.  Keep the limits
    # that are available without preventing the sandboxed child from starting.
    for limit, value in (
        (resource.RLIMIT_CPU, 20),
        (resource.RLIMIT_FSIZE, _MAX_OUTPUT_BYTES),
    ):
        try:
            resource.setrlimit(limit, (value, value))
        except (OSError, ValueError):
            continue


def _image_type(content: bytes) -> str | None:
    for prefix, media_type in _IMAGE_PREFIXES.items():
        if content.startswith(prefix):
            if media_type == "webp" and content[8:12] != b"WEBP":
                return None
            return media_type
    if content.startswith(b"BM"):
        return "bmp"
    return None


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
