"""Bounded, deterministic inspection facts for managed visual snapshots."""

from __future__ import annotations

import csv
import hashlib
import json
import struct
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

from .semantic_survey import SENSITIVE_NAMES, _is_relative_to


class InspectionError(ValueError):
    """Raised for invalid inspection arguments."""


@dataclass(frozen=True)
class InspectionLimits:
    max_bytes: int = 64 * 1024 * 1024
    max_rows: int = 1_000
    max_columns: int = 256
    max_xml_elements: int = 50_000

    def __post_init__(self) -> None:
        for name in ("max_bytes", "max_rows", "max_columns", "max_xml_elements"):
            value = getattr(self, name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                raise InspectionError(f"{name} must be a positive integer")


@dataclass(frozen=True)
class InspectionWarning:
    code: str
    path: str
    reason: str

    def to_dict(self) -> Dict[str, str]:
        return {"code": self.code, "path": self.path, "reason": self.reason}


@dataclass(frozen=True)
class ColumnFact:
    name: str
    observed_types: Tuple[str, ...]
    nullable: bool

    def to_dict(self) -> Dict[str, object]:
        return {
            "name": self.name,
            "observedTypes": list(self.observed_types),
            "nullable": self.nullable,
        }


@dataclass(frozen=True)
class InspectionFact:
    path: str
    format: str
    status: str
    error_code: Optional[str] = None
    warnings: Tuple[InspectionWarning, ...] = field(default_factory=tuple)

    def to_dict(self) -> Dict[str, object]:
        return {
            "path": self.path,
            "format": self.format,
            "status": self.status,
            "errorCode": self.error_code,
            "warnings": [item.to_dict() for item in self.warnings],
        }


@dataclass(frozen=True)
class ImageInspectionFact(InspectionFact):
    width: Optional[int] = None
    height: Optional[int] = None
    channels: Optional[int] = None
    bit_depth: Optional[int] = None
    container: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        result = super().to_dict()
        result.update(
            {
                "width": self.width,
                "height": self.height,
                "channels": self.channels,
                "bitDepth": self.bit_depth,
                "container": self.container,
            }
        )
        return result


@dataclass(frozen=True)
class VideoInspectionFact(InspectionFact):
    container: Optional[str] = None
    duration_ms: Optional[int] = None
    frame_count: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None

    def to_dict(self) -> Dict[str, object]:
        result = super().to_dict()
        result.update(
            {
                "container": self.container,
                "durationMs": self.duration_ms,
                "frameCount": self.frame_count,
                "width": self.width,
                "height": self.height,
            }
        )
        return result


@dataclass(frozen=True)
class DelimitedTableInspectionFact(InspectionFact):
    delimiter: Optional[str] = None
    columns: Tuple[ColumnFact, ...] = field(default_factory=tuple)
    row_count: int = 0
    truncated: bool = False

    def to_dict(self) -> Dict[str, object]:
        result = super().to_dict()
        result.update(
            {
                "delimiter": self.delimiter,
                "columns": [item.to_dict() for item in self.columns],
                "rowCount": self.row_count,
                "truncated": self.truncated,
            }
        )
        return result


@dataclass(frozen=True)
class JsonInspectionFact(InspectionFact):
    root_kind: Optional[str] = None
    fields: Tuple[ColumnFact, ...] = field(default_factory=tuple)
    row_count: int = 0
    invalid_rows: int = 0
    truncated: bool = False

    def to_dict(self) -> Dict[str, object]:
        result = super().to_dict()
        result.update(
            {
                "rootKind": self.root_kind,
                "fields": [item.to_dict() for item in self.fields],
                "rowCount": self.row_count,
                "invalidRows": self.invalid_rows,
                "truncated": self.truncated,
            }
        )
        return result


@dataclass(frozen=True)
class XmlInspectionFact(InspectionFact):
    root_tag: Optional[str] = None
    element_count: int = 0
    element_names: Tuple[Tuple[str, int], ...] = field(default_factory=tuple)
    attribute_names: Tuple[str, ...] = field(default_factory=tuple)
    truncated: bool = False

    def to_dict(self) -> Dict[str, object]:
        result = super().to_dict()
        result.update(
            {
                "rootTag": self.root_tag,
                "elementCount": self.element_count,
                "elementNames": {key: value for key, value in self.element_names},
                "attributeNames": list(self.attribute_names),
                "truncated": self.truncated,
            }
        )
        return result


@dataclass(frozen=True)
class ParquetInspectionFact(InspectionFact):
    columns: Tuple[ColumnFact, ...] = field(default_factory=tuple)
    row_count: int = 0
    physical_row_count: Optional[int] = None
    truncated: bool = False

    def to_dict(self) -> Dict[str, object]:
        result = super().to_dict()
        result.update(
            {
                "columns": [item.to_dict() for item in self.columns],
                "rowCount": self.row_count,
                "physicalRowCount": self.physical_row_count,
                "truncated": self.truncated,
            }
        )
        return result


InspectionResult = Union[
    ImageInspectionFact,
    VideoInspectionFact,
    DelimitedTableInspectionFact,
    JsonInspectionFact,
    XmlInspectionFact,
    ParquetInspectionFact,
    InspectionFact,
]


def inspect_file(
    path: Path | str,
    limits: Optional[InspectionLimits] = None,
    snapshot_root: Optional[Path | str] = None,
) -> InspectionResult:
    """Inspect one regular file without leaving the optional snapshot root."""

    policy = limits or InspectionLimits()
    file_path = Path(path).expanduser()
    relative = _validate_file_path(file_path, snapshot_root)
    suffix = file_path.suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff"}:
        return inspect_image(file_path, policy, relative)
    if suffix in {".mp4", ".avi", ".mov", ".mkv", ".webm", ".mpeg", ".mpg"}:
        return inspect_video(file_path, policy, relative)
    if suffix in {".csv", ".tsv"}:
        return inspect_table(file_path, policy, relative)
    if suffix in {".json", ".jsonl", ".ndjson"}:
        return inspect_json(file_path, policy, relative)
    if suffix == ".xml":
        return inspect_xml(file_path, policy, relative)
    if suffix == ".parquet":
        return inspect_parquet(file_path, policy, relative)
    return InspectionFact(relative, suffix.lstrip(".") or "unknown", "UNSUPPORTED", "UNSUPPORTED_FORMAT")


def inspect_image(
    path: Path | str,
    limits: Optional[InspectionLimits] = None,
    relative_path: Optional[str] = None,
) -> ImageInspectionFact:
    policy = limits or InspectionLimits()
    file_path = Path(path)
    relative = relative_path or file_path.name
    raw, warning = _read_bounded(file_path, policy.max_bytes, relative)
    if warning:
        return ImageInspectionFact(relative, "image", "FAILED", warning.code, (warning,))
    assert raw is not None
    parsed = _parse_image_header(raw)
    if parsed is None:
        warning = _warning("INVALID_MEDIA", relative, "image header is invalid or unsupported")
        return ImageInspectionFact(relative, "image", "FAILED", warning.code, (warning,))
    width, height, channels, bit_depth, container = parsed
    return ImageInspectionFact(
        relative,
        "image",
        "COMPLETED",
        None,
        tuple(),
        width,
        height,
        channels,
        bit_depth,
        container,
    )


def inspect_video(
    path: Path | str,
    limits: Optional[InspectionLimits] = None,
    relative_path: Optional[str] = None,
) -> VideoInspectionFact:
    policy = limits or InspectionLimits()
    file_path = Path(path)
    relative = relative_path or file_path.name
    raw, warning = _read_bounded(file_path, min(policy.max_bytes, 4096), relative)
    if warning:
        return VideoInspectionFact(relative, "video", "FAILED", warning.code, (warning,))
    assert raw is not None
    container = _video_container(raw)
    if container is None:
        warning = _warning("INVALID_MEDIA", relative, "video container header is invalid or unknown")
        return VideoInspectionFact(relative, "video", "FAILED", warning.code, (warning,))
    warning = _warning(
        "VIDEO_METADATA_UNSUPPORTED",
        relative,
        "safe video metadata extraction is unavailable in this environment",
    )
    return VideoInspectionFact(relative, "video", "UNSUPPORTED", warning.code, (warning,), container)


def inspect_table(
    path: Path | str,
    limits: Optional[InspectionLimits] = None,
    relative_path: Optional[str] = None,
) -> DelimitedTableInspectionFact:
    policy = limits or InspectionLimits()
    file_path = Path(path)
    relative = relative_path or file_path.name
    raw, warning = _read_bounded(file_path, policy.max_bytes, relative)
    if warning:
        return DelimitedTableInspectionFact(relative, file_path.suffix.lstrip("."), "FAILED", warning.code, (warning,))
    assert raw is not None
    delimiter = "\t" if file_path.suffix.lower() == ".tsv" else _detect_delimiter(raw)
    try:
        text = raw.decode("utf-8-sig")
        rows = list(_limited_rows(csv.reader(text.splitlines(), delimiter=delimiter), policy.max_rows + 2))
    except (UnicodeDecodeError, csv.Error) as exc:
        warning = _warning("TABLE_PARSE_FAILED", relative, f"delimited table parse failed: {exc.__class__.__name__}")
        return DelimitedTableInspectionFact(relative, file_path.suffix.lstrip("."), "FAILED", warning.code, (warning,))
    if not rows:
        return DelimitedTableInspectionFact(relative, file_path.suffix.lstrip("."), "COMPLETED", None, tuple(), delimiter, tuple(), 0, False)
    header = _unique_headers(rows[0], policy.max_columns)
    data = rows[1 : policy.max_rows + 1]
    columns = tuple(
        ColumnFact(
            name,
            tuple(sorted(_observed_types(row[index] if index < len(row) else None for row in data))),
            any(index >= len(row) or not row[index].strip() for row in data),
        )
        for index, name in enumerate(header)
    )
    truncated = len(rows) > policy.max_rows
    warnings = (
        (_warning("ROW_LIMIT", relative, "row limit reached"),)
        if truncated
        else tuple()
    )
    return DelimitedTableInspectionFact(
        relative,
        file_path.suffix.lstrip("."),
        "COMPLETED",
        None,
        warnings,
        delimiter,
        columns,
        len(data),
        truncated,
    )


def inspect_json(
    path: Path | str,
    limits: Optional[InspectionLimits] = None,
    relative_path: Optional[str] = None,
) -> JsonInspectionFact:
    policy = limits or InspectionLimits()
    file_path = Path(path)
    relative = relative_path or file_path.name
    raw, warning = _read_bounded(file_path, policy.max_bytes, relative)
    if warning:
        return JsonInspectionFact(relative, file_path.suffix.lstrip("."), "FAILED", warning.code, (warning,))
    assert raw is not None
    if file_path.suffix.lower() in {".jsonl", ".ndjson"}:
        return _inspect_jsonl(raw, relative, policy)
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        warning = _warning("JSON_PARSE_FAILED", relative, f"JSON parse failed: {exc.__class__.__name__}")
        return JsonInspectionFact(relative, "json", "FAILED", warning.code, (warning,))
    rows = _json_rows(value)
    fields = _fields_from_rows(rows[: policy.max_rows], policy.max_columns)
    return JsonInspectionFact(
        relative,
        "json",
        "COMPLETED",
        None,
        tuple(),
        _json_kind(value),
        fields,
        min(len(rows), policy.max_rows),
        0,
        len(rows) > policy.max_rows,
    )


def inspect_xml(
    path: Path | str,
    limits: Optional[InspectionLimits] = None,
    relative_path: Optional[str] = None,
) -> XmlInspectionFact:
    policy = limits or InspectionLimits()
    file_path = Path(path)
    relative = relative_path or file_path.name
    raw, warning = _read_bounded(file_path, policy.max_bytes, relative)
    if warning:
        return XmlInspectionFact(relative, "xml", "FAILED", warning.code, (warning,))
    assert raw is not None
    upper = raw[: policy.max_bytes].upper()
    if b"<!DOCTYPE" in upper or b"<!ENTITY" in upper:
        warning = _warning("XML_DOCTYPE_REJECTED", relative, "DOCTYPE and ENTITY declarations are forbidden")
        return XmlInspectionFact(relative, "xml", "FAILED", warning.code, (warning,))
    try:
        root = ET.fromstring(raw)
    except (ET.ParseError, ValueError) as exc:
        warning = _warning("XML_PARSE_FAILED", relative, f"XML parse failed: {exc.__class__.__name__}")
        return XmlInspectionFact(relative, "xml", "FAILED", warning.code, (warning,))
    counts: Dict[str, int] = {}
    attrs: set[str] = set()
    count = 0
    truncated = False
    for element in root.iter():
        count += 1
        if count > policy.max_xml_elements:
            truncated = True
            break
        counts[element.tag] = counts.get(element.tag, 0) + 1
        attrs.update(element.attrib.keys())
    warnings = (
        (_warning("ELEMENT_LIMIT", relative, "XML element limit reached"),)
        if truncated
        else tuple()
    )
    return XmlInspectionFact(
        relative,
        "xml",
        "COMPLETED",
        None,
        warnings,
        root.tag,
        min(count, policy.max_xml_elements),
        tuple(sorted(counts.items())),
        tuple(sorted(attrs)),
        truncated,
    )


def inspect_parquet(
    path: Path | str,
    limits: Optional[InspectionLimits] = None,
    relative_path: Optional[str] = None,
) -> ParquetInspectionFact:
    policy = limits or InspectionLimits()
    file_path = Path(path)
    relative = relative_path or file_path.name
    try:
        if file_path.is_symlink():
            warning = _warning("SYMLINK_SKIPPED", relative, "symbolic links are never followed")
            return ParquetInspectionFact(relative, "parquet", "FAILED", warning.code, (warning,))
        if file_path.stat().st_size < 8:
            raise OSError("file is too small")
        with file_path.open("rb") as handle:
            raw = handle.read(4)
    except OSError as exc:
        warning = _warning("READ_FAILED", relative, f"file read failed: {exc.__class__.__name__}")
        return ParquetInspectionFact(relative, "parquet", "FAILED", warning.code, (warning,))
    if raw != b"PAR1":
        warning = _warning("INVALID_PARQUET", relative, "Parquet magic bytes are missing")
        return ParquetInspectionFact(relative, "parquet", "FAILED", warning.code, (warning,))
    try:
        import pyarrow.parquet as pq
    except ImportError:
        warning = _warning("PARQUET_UNAVAILABLE", relative, "pyarrow is unavailable")
        return ParquetInspectionFact(relative, "parquet", "UNSUPPORTED", warning.code, (warning,))
    try:
        parquet = pq.ParquetFile(file_path)
        schema = parquet.schema_arrow
        physical_rows = int(parquet.metadata.num_rows)
        columns = tuple(
            ColumnFact(field.name, (str(field.type),), field.nullable)
            for field in list(schema)[: policy.max_columns]
        )
    except Exception as exc:
        warning = _warning("PARQUET_PARSE_FAILED", relative, f"Parquet inspection failed: {exc.__class__.__name__}")
        return ParquetInspectionFact(relative, "parquet", "FAILED", warning.code, (warning,))
    truncated = physical_rows > policy.max_rows
    warnings = (
        (_warning("ROW_LIMIT", relative, "row limit reached"),)
        if truncated
        else tuple()
    )
    return ParquetInspectionFact(
        relative,
        "parquet",
        "COMPLETED",
        None,
        warnings,
        columns,
        min(physical_rows, policy.max_rows),
        physical_rows,
        truncated,
    )


def _validate_file_path(path: Path, snapshot_root: Optional[Path | str]) -> str:
    if path.is_symlink():
        raise InspectionError("symbolic links are never inspected")
    if snapshot_root is not None:
        root = Path(snapshot_root).expanduser()
        if root.is_symlink() or not root.is_dir():
            raise InspectionError("snapshot root must be an existing non-symlink directory")
        root = root.resolve()
        resolved = path.resolve(strict=False)
        if not _is_relative_to(resolved, root):
            raise InspectionError("file path escapes snapshot root")
        relative = resolved.relative_to(root).as_posix()
        if not relative or ".." in Path(relative).parts:
            raise InspectionError("unsafe relative file path")
        current = root
        for part in Path(relative).parts:
            current = current / part
            if current.is_symlink():
                raise InspectionError("symbolic links are never followed")
    else:
        relative = path.name
    if path.name.lower() in SENSITIVE_NAMES or path.name.lower().startswith(".env."):
        raise InspectionError("sensitive files must be skipped by survey")
    if not path.is_file():
        raise InspectionError("inspection target must be a regular file")
    return relative


def _read_bounded(path: Path, maximum: int, relative: str) -> Tuple[Optional[bytes], Optional[InspectionWarning]]:
    try:
        if path.is_symlink():
            return None, _warning("SYMLINK_SKIPPED", relative, "symbolic links are never followed")
        size = path.stat().st_size
        if size > maximum:
            warning = _warning("BYTE_LIMIT", relative, "file exceeds max_bytes")
            return None, warning
        return path.read_bytes(), None
    except OSError as exc:
        warning = _warning("READ_FAILED", relative, f"file read failed: {exc.__class__.__name__}")
        return None, warning


def _warning(code: str, path: str, reason: str) -> InspectionWarning:
    return InspectionWarning(code, path, reason)


def _parse_image_header(raw: bytes) -> Optional[Tuple[int, int, int, int, str]]:
    if raw.startswith(b"\x89PNG\r\n\x1a\n") and len(raw) >= 26 and raw[12:16] == b"IHDR":
        width, height = struct.unpack(">II", raw[16:24])
        bit_depth, color_type = raw[24], raw[25]
        channels = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}.get(color_type)
        if width and height and channels:
            return width, height, channels, bit_depth, "png"
    if raw[:3] == b"\xff\xd8\xff":
        parsed = _jpeg_size(raw)
        if parsed:
            width, height, channels, bit_depth = parsed
            return width, height, channels, bit_depth, "jpeg"
    if raw.startswith((b"GIF87a", b"GIF89a")) and len(raw) >= 10:
        width, height = struct.unpack("<HH", raw[6:10])
        if width and height:
            return width, height, 3, 8, "gif"
    if raw.startswith(b"BM") and len(raw) >= 30:
        width, height = struct.unpack("<ii", raw[18:26])
        bit_depth = struct.unpack("<H", raw[28:30])[0]
        if width > 0 and height != 0 and bit_depth > 0:
            return width, abs(height), 4 if bit_depth >= 32 else 3, bit_depth, "bmp"
    if raw.startswith(b"RIFF") and len(raw) >= 16 and raw[8:12] == b"WEBP":
        if raw[12:16] == b"VP8X" and len(raw) >= 30:
            width = 1 + int.from_bytes(raw[24:27], "little")
            height = 1 + int.from_bytes(raw[27:30], "little")
            return width, height, 4, 8, "webp"
    return None


def _jpeg_size(raw: bytes) -> Optional[Tuple[int, int, int, int]]:
    index = 2
    while index + 9 < len(raw):
        if raw[index] != 0xFF:
            index += 1
            continue
        marker = raw[index + 1]
        index += 2
        if marker in {0xD8, 0xD9} or 0xD0 <= marker <= 0xD7:
            continue
        if index + 2 > len(raw):
            return None
        length = int.from_bytes(raw[index : index + 2], "big")
        if length < 2 or index + length > len(raw):
            return None
        if marker in set(range(0xC0, 0xC4)) | set(range(0xC5, 0xC8)) | set(range(0xC9, 0xCC)) | set(range(0xCD, 0xD0)):
            if length < 8:
                return None
            bit_depth = raw[index + 2]
            height = int.from_bytes(raw[index + 3 : index + 5], "big")
            width = int.from_bytes(raw[index + 5 : index + 7], "big")
            channels = raw[index + 7]
            return (width, height, channels, bit_depth) if width and height else None
        index += length
    return None


def _video_container(raw: bytes) -> Optional[str]:
    if raw.startswith(b"RIFF") and len(raw) >= 12 and raw[8:12] == b"AVI ":
        return "avi"
    if len(raw) >= 12 and raw[4:8] == b"ftyp":
        return "mp4"
    if raw.startswith(b"\x1a\x45\xdf\xa3"):
        return "webm_or_mkv"
    return None


def _detect_delimiter(raw: bytes) -> str:
    first = raw.decode("utf-8-sig", errors="replace").splitlines()[:1]
    if not first:
        return ","
    line = first[0]
    return "\t" if line.count("\t") > line.count(",") else ","


def _limited_rows(reader: Iterable[List[str]], limit: int) -> List[List[str]]:
    rows: List[List[str]] = []
    for row in reader:
        rows.append(row)
        if len(rows) >= limit:
            break
    return rows


def _unique_headers(values: Sequence[str], maximum: int) -> List[str]:
    result: List[str] = []
    used: Dict[str, int] = {}
    for index, value in enumerate(values[:maximum]):
        base = value.strip() or f"column_{index + 1}"
        count = used.get(base, 0)
        used[base] = count + 1
        result.append(base if count == 0 else f"{base}_{count + 1}")
    return result


def _observed_types(values: Iterable[object]) -> set[str]:
    result: set[str] = set()
    for value in values:
        if value is None or (isinstance(value, str) and not value.strip()):
            continue
        text = str(value).strip()
        try:
            int(text)
        except ValueError:
            try:
                float(text)
            except ValueError:
                result.add("string")
            else:
                result.add("number")
        else:
            result.add("integer")
    return result or {"unknown"}


def _json_rows(value: object) -> List[object]:
    if isinstance(value, list):
        return value
    if isinstance(value, dict):
        for key in ("records", "data", "items", "rows"):
            candidate = value.get(key)
            if isinstance(candidate, list):
                return candidate
        return [value]
    return [{"value": value}]


def _inspect_jsonl(raw: bytes, relative: str, policy: InspectionLimits) -> JsonInspectionFact:
    rows: List[object] = []
    invalid = 0
    truncated = False
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        warning = _warning("JSON_PARSE_FAILED", relative, "JSONL is not UTF-8")
        return JsonInspectionFact(relative, "jsonl", "FAILED", warning.code, (warning,))
    for line in text.splitlines():
        if not line.strip():
            continue
        if len(rows) >= policy.max_rows:
            truncated = True
            break
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            invalid += 1
    warnings: Tuple[InspectionWarning, ...] = tuple()
    if invalid:
        warnings += (_warning("INVALID_JSONL_ROW", relative, f"{invalid} JSONL rows were invalid"),)
    if truncated:
        warnings += (_warning("ROW_LIMIT", relative, "row limit reached"),)
    return JsonInspectionFact(
        relative,
        "jsonl",
        "COMPLETED",
        None,
        warnings,
        "lines",
        _fields_from_rows(rows, policy.max_columns),
        len(rows),
        invalid,
        truncated,
    )


def _fields_from_rows(rows: Sequence[object], maximum: int) -> Tuple[ColumnFact, ...]:
    names: List[str] = []
    values: Dict[str, List[object]] = {}
    nullable: Dict[str, bool] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        for name, value in list(row.items())[:maximum]:
            key = str(name)
            if key not in values:
                names.append(key)
                values[key] = []
                nullable[key] = False
            values[key].append(value)
            nullable[key] = nullable[key] or value is None
    return tuple(
        ColumnFact(name, tuple(sorted(_observed_types(values[name]))), nullable[name])
        for name in names[:maximum]
    )


def _json_kind(value: object) -> str:
    if isinstance(value, dict):
        return "object"
    if isinstance(value, list):
        return "array"
    if value is None:
        return "null"
    return type(value).__name__
