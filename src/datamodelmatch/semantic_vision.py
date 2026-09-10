"""Bounded VLM configuration, media preparation, and observation validation."""

from __future__ import annotations

import base64
import hashlib
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Mapping, Optional, Protocol

from .semantic_sampling import SampleRef


class VisionError(ValueError):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class VlmBudgetError(VisionError):
    """Controlled fail-closed error for unknown or exhausted model cost."""

    def __init__(self, reason: str):
        super().__init__("VLM_UNAVAILABLE", reason)
        self.reason = reason


_FORMATS = {"jpeg", "png", "webp"}
_VIDEO_FORMATS = {"mp4", "webm", "mov"}
_FIELDS = {
    "objectCategories",
    "environments",
    "viewpoints",
    "targetScale",
    "objectDensity",
    "occlusion",
    "illumination",
    "cameraMotion",
    "targetMotion",
}
_SCALES = {"UNKNOWN", "tiny", "small", "medium", "large", "mixed"}
_DENSITIES = {"UNKNOWN", "low", "medium", "high", "mixed"}
_OCCLUSION = {"UNKNOWN", "rare", "moderate", "frequent"}
_MOTION = {"UNKNOWN", "static", "moving"}
_TARGET_MOTION = {"UNKNOWN", "slow", "moderate", "fast", "mixed"}


@dataclass(frozen=True)
class VlmConfig:
    version: int
    provider: str
    endpoint: str
    api_key: str
    model: str
    image_formats: tuple[str, ...]
    image_max_bytes: int
    video_mode: str
    video_formats: tuple[str, ...]
    video_max_bytes: int
    video_max_duration_ms: int
    timeout_ms: int
    max_calls_per_stage: int
    max_cost_usd_per_job: float
    max_attempts: int
    base_delay_ms: int
    fingerprint: str


@dataclass(frozen=True)
class PreparedMedia:
    media_type: str
    source_path: str
    data_url: str
    byte_count: int
    provenance: Mapping[str, object] = field(default_factory=dict)


@dataclass(frozen=True)
class CostEstimate:
    estimated_usd: float
    bounded: bool
    basis: str

    def __post_init__(self) -> None:
        if isinstance(self.estimated_usd, bool) or not isinstance(self.estimated_usd, (int, float)):
            raise ValueError("estimated_usd must be numeric")
        if self.estimated_usd < 0 or not self.basis or len(self.basis) > 256:
            raise ValueError("cost estimate is invalid")
        if not self.bounded and self.estimated_usd != 0:
            raise ValueError("unbounded estimates cannot carry a guessed nonzero cost")
        if not self.bounded and self.basis == "provider_declares_free":
            raise ValueError("free basis must be bounded")


class CostEstimator(Protocol):
    def estimate(self, *, media: PreparedMedia, prompt: str, model: str) -> CostEstimate:
        """Return a bounded estimate for one outbound attempt."""


@dataclass(frozen=True)
class FixedCostEstimator:
    """Explicit estimator for an approved provider/rate card or controlled test."""

    estimated_usd: float
    basis: str = "approved_fixed_rate"

    def estimate(self, *, media: PreparedMedia, prompt: str, model: str) -> CostEstimate:
        return CostEstimate(self.estimated_usd, True, self.basis)


@dataclass
class VlmBudgetTracker:
    budget_usd: float
    spent_usd: float = 0.0

    def __post_init__(self) -> None:
        if isinstance(self.budget_usd, bool) or not isinstance(self.budget_usd, (int, float)) or self.budget_usd <= 0:
            raise ValueError("budget_usd must be positive")
        if self.spent_usd < 0 or self.spent_usd > self.budget_usd:
            raise ValueError("spent_usd is outside the budget")

    def reserve(self, estimate: CostEstimate) -> None:
        if not estimate.bounded:
            raise VlmBudgetError("VLM_COST_UNBOUNDED")
        next_spent = self.spent_usd + estimate.estimated_usd
        if next_spent > self.budget_usd + 1e-12:
            raise VlmBudgetError("VLM_COST_BUDGET_EXHAUSTED")
        self.spent_usd = next_spent

    @property
    def remaining_usd(self) -> float:
        return max(0.0, self.budget_usd - self.spent_usd)


@dataclass(frozen=True)
class DecodedFrame:
    image_bytes: bytes
    image_format: str
    decoder_id: str


class FrameDecoder(Protocol):
    def decode(self, source_path: Path, sample_ref: SampleRef) -> DecodedFrame:
        """Decode one validated temporal sample without choosing an output path."""


@dataclass(frozen=True)
class VisualObservation:
    id: str
    sample_ref: str
    object_categories: tuple[str, ...]
    environments: tuple[str, ...]
    viewpoints: tuple[str, ...]
    target_scale: str
    object_density: str
    occlusion: str
    illumination: tuple[str, ...]
    camera_motion: str
    target_motion: str
    vlm_model: str
    configuration_fingerprint: str
    status: str
    evidence_refs: tuple[str, ...]
    failure_code: Optional[str] = None

    def to_dict(self) -> dict[str, object]:
        result = {
            "id": self.id,
            "sampleRef": self.sample_ref,
            "objectCategories": list(self.object_categories),
            "environments": list(self.environments),
            "viewpoints": list(self.viewpoints),
            "targetScale": self.target_scale,
            "objectDensity": self.object_density,
            "occlusion": self.occlusion,
            "illumination": list(self.illumination),
            "cameraMotion": self.camera_motion,
            "targetMotion": self.target_motion,
            "vlmModel": self.vlm_model,
            "configurationFingerprint": self.configuration_fingerprint,
            "status": self.status,
            "evidenceRefs": list(self.evidence_refs),
        }
        if self.failure_code is not None:
            result["failureCode"] = self.failure_code
        return result


def load_vlm_config(path: Path | str = "config.llm.json") -> VlmConfig:
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise VisionError("VLM_CONFIG_INVALID", "VLM configuration file is unreadable") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("vlm"), dict):
        raise VisionError("VLM_CONFIG_INVALID", "explicit vlm configuration is required")
    value = raw["vlm"]
    expected = {"version", "provider", "endpoint", "apiKey", "model", "imageInput", "videoInput", "limits", "retry"}
    if set(value) != expected:
        raise VisionError("VLM_CONFIG_INVALID", "vlm configuration fields are not closed")
    try:
        image = value["imageInput"]
        video = value["videoInput"]
        limits = value["limits"]
        retry = value["retry"]
        if value["version"] != 1 or not all(isinstance(value[key], str) and value[key] for key in ("provider", "endpoint", "apiKey", "model")):
            raise ValueError
        if not isinstance(image, dict) or set(image) != {"formats", "maxBytes"}:
            raise ValueError
        if not isinstance(video, dict) or set(video) != {"mode", "formats", "maxBytes", "maxDurationMs"}:
            raise ValueError
        if video["mode"] != "frames_only":
            raise ValueError
        if not isinstance(limits, dict) or set(limits) != {"timeoutMs", "maxCallsPerStage", "maxCostUsdPerJob"}:
            raise ValueError
        if not isinstance(retry, dict) or set(retry) != {"maxAttempts", "baseDelayMs"}:
            raise ValueError
        if not isinstance(image["formats"], list) or not image["formats"] or not set(image["formats"]) <= _FORMATS:
            raise ValueError
        if not isinstance(video["formats"], list) or not set(video["formats"]) <= _VIDEO_FORMATS:
            raise ValueError
        _bounded_int(image["maxBytes"], 1, 52_428_800)
        _bounded_int(video["maxBytes"], 1, 524_288_000)
        _bounded_int(video["maxDurationMs"], 1, 600_000)
        timeout = _bounded_int(limits["timeoutMs"], 1000, 300_000)
        calls = _bounded_int(limits["maxCallsPerStage"], 1, 1000)
        cost = limits["maxCostUsdPerJob"]
        if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not 0 < cost <= 1000:
            raise ValueError
        attempts = _bounded_int(retry["maxAttempts"], 0, 5)
        delay = _bounded_int(retry["baseDelayMs"], 100, 60_000)
        endpoint = value["endpoint"]
        if not endpoint.startswith("https://"):
            raise ValueError
    except (KeyError, TypeError, ValueError) as exc:
        raise VisionError("VLM_CONFIG_INVALID", "VLM configuration values are invalid") from exc
    redacted = dict(value)
    redacted["apiKey"] = "<redacted>"
    fingerprint = "sha256:" + hashlib.sha256(
        json.dumps(redacted, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return VlmConfig(
        1,
        value["provider"],
        value["endpoint"],
        value["apiKey"],
        value["model"],
        tuple(value["imageInput"]["formats"]),
        value["imageInput"]["maxBytes"],
        "frames_only",
        tuple(value["videoInput"]["formats"]),
        value["videoInput"]["maxBytes"],
        value["videoInput"]["maxDurationMs"],
        timeout,
        calls,
        float(cost),
        attempts,
        delay,
        fingerprint,
    )


def prepare_image(root: Path | str, relative_path: str, config: VlmConfig) -> PreparedMedia:
    path = _safe_media_path(root, relative_path, config.image_max_bytes, config.image_formats)
    suffix = path.suffix.lower().lstrip(".")
    normalized_suffix = "jpeg" if suffix == "jpg" else suffix
    content = _read(path)
    if not _looks_like_image(content, normalized_suffix):
        raise VisionError("MEDIA_READ_FAILED", "media header is invalid")
    media = normalized_suffix
    return PreparedMedia("image", relative_path, f"data:image/{media};base64,{base64.b64encode(content).decode('ascii')}", len(content))


def prepare_video_frame(
    root: Path | str,
    sample_ref: SampleRef,
    config: VlmConfig,
    safe_temp_root: Path | str,
    decoder: Optional[FrameDecoder] = None,
) -> PreparedMedia:
    if config.video_mode != "frames_only":
        raise VisionError("UNSUPPORTED_MEDIA", "native video input is not enabled")
    _validate_temporal_sample(sample_ref, config.video_max_duration_ms)
    if decoder is None:
        raise VisionError("UNSUPPORTED_MEDIA", "approved video decoder is unavailable")
    source = _safe_media_path(root, sample_ref.video_path or sample_ref.path, config.video_max_bytes, config.video_formats)
    temp_root = Path(safe_temp_root).expanduser()
    if temp_root.exists() and temp_root.is_symlink():
        raise VisionError("MEDIA_READ_FAILED", "derived media root cannot be a symbolic link")
    if not temp_root.exists():
        try:
            temp_root.mkdir(parents=True)
        except OSError as exc:
            raise VisionError("MEDIA_READ_FAILED", "derived media root cannot be created") from exc
    temp_root = temp_root.resolve()
    if not temp_root.is_dir():
        raise VisionError("MEDIA_READ_FAILED", "derived media root must be a directory")
    try:
        decoded = decoder.decode(source, sample_ref)
    except Exception as exc:
        raise VisionError("MEDIA_READ_FAILED", "approved decoder failed") from exc
    if not isinstance(decoded, DecodedFrame) or decoded.image_format not in config.image_formats:
        raise VisionError("UNSUPPORTED_MEDIA", "decoder returned an unsupported image format")
    if not isinstance(decoded.image_bytes, bytes) or not decoded.image_bytes or len(decoded.image_bytes) > config.image_max_bytes:
        raise VisionError("MEDIA_READ_FAILED", "decoder output exceeds configured bounds")
    if not _looks_like_image(decoded.image_bytes, decoded.image_format):
        raise VisionError("MEDIA_READ_FAILED", "decoder output has an invalid image header")
    suffix = "jpeg" if decoded.image_format == "jpeg" else decoded.image_format
    filename = "sample_" + hashlib.sha256(sample_ref.id.encode("utf-8")).hexdigest()[:24] + "." + suffix
    output = temp_root / filename
    if not _is_relative_to(output, temp_root):
        raise VisionError("MEDIA_READ_FAILED", "derived media path escapes safe root")
    try:
        output.write_bytes(decoded.image_bytes)
    except OSError as exc:
        raise VisionError("MEDIA_READ_FAILED", "derived media cannot be written") from exc
    provenance = {
        "kind": "derived_video_sample",
        "decoderId": decoded.decoder_id,
        "sampleRef": sample_ref.id,
        "videoPath": sample_ref.video_path or sample_ref.path,
        "startMs": sample_ref.start_ms,
        "endMs": sample_ref.end_ms,
        "frameStart": sample_ref.frame_start,
        "frameEnd": sample_ref.frame_end,
        "samplingFps": sample_ref.sampling_fps,
    }
    return PreparedMedia(
        "image",
        output.relative_to(temp_root).as_posix(),
        f"data:image/{suffix};base64,{base64.b64encode(decoded.image_bytes).decode('ascii')}",
        len(decoded.image_bytes),
        provenance,
    )


def prepare_sample_media(
    root: Path | str,
    relative_path: str | SampleRef,
    config: VlmConfig,
    media_kind: str,
    safe_temp_root: Optional[Path | str] = None,
    decoder: Optional[FrameDecoder] = None,
) -> PreparedMedia:
    if media_kind == "image":
        return prepare_image(root, relative_path, config)
    if media_kind in {"frame", "clip"}:
        if not isinstance(relative_path, SampleRef) or safe_temp_root is None:
            raise VisionError("UNSUPPORTED_MEDIA", "temporal samples require a SampleRef, safe temp root, and decoder")
        return prepare_video_frame(root, relative_path, config, safe_temp_root, decoder)
    if media_kind == "video":
        return prepare_video_frame(root, relative_path, config)
    raise VisionError("UNSUPPORTED_MEDIA", "sample media kind is unsupported")


def validate_visual_observation(
    value: Mapping[str, object],
    sample_ref: str,
    observation_id: str,
    vlm_model: str,
    configuration_fingerprint: str,
    evidence_ref: str,
) -> VisualObservation:
    if set(value) != _FIELDS:
        raise VisionError("VLM_INVALID_RESPONSE", "model response fields do not match the observation schema")
    try:
        result = VisualObservation(
            observation_id,
            sample_ref,
            _strings(value["objectCategories"]),
            _strings(value["environments"]),
            _strings(value["viewpoints"]),
            _enum(value["targetScale"], _SCALES),
            _enum(value["objectDensity"], _DENSITIES),
            _enum(value["occlusion"], _OCCLUSION),
            _strings(value["illumination"]),
            _enum(value["cameraMotion"], _MOTION),
            _enum(value["targetMotion"], _TARGET_MOTION),
            vlm_model,
            configuration_fingerprint,
            "COMPLETED",
            (evidence_ref,),
        )
    except (TypeError, ValueError) as exc:
        raise VisionError("VLM_INVALID_RESPONSE", "model response values do not match the observation schema") from exc
    return result


def failed_observation(
    sample_ref: str,
    observation_id: str,
    config: VlmConfig,
    failure_code: str,
    evidence_ref: str,
) -> VisualObservation:
    if failure_code not in {"VLM_TIMEOUT", "VLM_EMPTY_RESPONSE", "VLM_INVALID_RESPONSE", "UNSUPPORTED_MEDIA", "MEDIA_READ_FAILED", "CANCELLED"}:
        raise ValueError("failure code is not frozen")
    return VisualObservation(
        observation_id, sample_ref, tuple(), tuple(), tuple(), "UNKNOWN", "UNKNOWN",
        "UNKNOWN", tuple(), "UNKNOWN", "UNKNOWN", config.model, config.fingerprint,
        "UNSUPPORTED" if failure_code == "UNSUPPORTED_MEDIA" else "FAILED",
        (evidence_ref,), failure_code,
    )


class VlmClient:
    def __init__(
        self,
        config: VlmConfig,
        opener: Optional[Callable[..., object]] = None,
        sleep: Callable[[float], None] = time.sleep,
        cost_estimator: Optional[CostEstimator] = None,
        budget_tracker: Optional[VlmBudgetTracker] = None,
    ):
        self.config = config
        self.opener = opener or urllib.request.urlopen
        self.sleep = sleep
        self.calls = 0
        self.cost_estimator = cost_estimator
        self.budget_tracker = budget_tracker or VlmBudgetTracker(config.max_cost_usd_per_job)

    def observe_image(
        self,
        media: PreparedMedia,
        sample_ref: str,
        observation_id: str,
        evidence_ref: str,
        prompt: str = "Return only the required JSON observation object.",
    ) -> VisualObservation:
        if self.calls >= self.config.max_calls_per_stage:
            return failed_observation(sample_ref, observation_id, self.config, "VLM_TIMEOUT", evidence_ref)
        if self.cost_estimator is None:
            raise VlmBudgetError("VLM_COST_UNBOUNDED")
        self.calls += 1
        payload = {
            "model": self.config.model,
            "stream": False,
            "messages": [{
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": media.data_url}},
                ],
            }],
        }
        encoded = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        for attempt in range(self.config.max_attempts + 1):
            estimate = self.cost_estimator.estimate(media=media, prompt=prompt, model=self.config.model)
            self.budget_tracker.reserve(estimate)
            request = urllib.request.Request(
                self.config.endpoint,
                data=encoded,
                headers={"Content-Type": "application/json", "Authorization": f"Bearer {self.config.api_key}"},
                method="POST",
            )
            try:
                response = self.opener(request, timeout=self.config.timeout_ms / 1000)
                raw = response.read()
                if not raw:
                    raise VisionError("VLM_EMPTY_RESPONSE", "VLM returned an empty response")
                if len(raw) > 1_000_000:
                    raise VisionError("VLM_INVALID_RESPONSE", "VLM response exceeded the bounded response size")
                decoded = json.loads(raw.decode("utf-8"))
                content = decoded["choices"][0]["message"]["content"]
                if isinstance(content, list):
                    content = "".join(item.get("text", "") for item in content if isinstance(item, dict))
                if not isinstance(content, str) or not content.strip():
                    raise VisionError("VLM_EMPTY_RESPONSE", "VLM returned no content")
                return validate_visual_observation(
                    _decode_model_json(content),
                    sample_ref,
                    observation_id,
                    self.config.model,
                    self.config.fingerprint,
                    evidence_ref,
                )
            except VisionError as exc:
                if exc.code == "VLM_INVALID_RESPONSE" and attempt < self.config.max_attempts:
                    break
                return failed_observation(sample_ref, observation_id, self.config, exc.code, evidence_ref)
            except urllib.error.HTTPError:
                return failed_observation(sample_ref, observation_id, self.config, "VLM_INVALID_RESPONSE", evidence_ref)
            except (TimeoutError, urllib.error.URLError, OSError):
                if attempt < self.config.max_attempts:
                    self.sleep(self.config.base_delay_ms / 1000 * (2**attempt))
                    continue
                return failed_observation(sample_ref, observation_id, self.config, "VLM_TIMEOUT", evidence_ref)
            except (KeyError, TypeError, ValueError, UnicodeError):
                return failed_observation(sample_ref, observation_id, self.config, "VLM_INVALID_RESPONSE", evidence_ref)
        return failed_observation(sample_ref, observation_id, self.config, "VLM_INVALID_RESPONSE", evidence_ref)


def _validate_temporal_sample(sample_ref: SampleRef, max_duration_ms: int) -> None:
    if sample_ref.kind not in {"frame", "clip"}:
        raise VisionError("UNSUPPORTED_MEDIA", "sample is not a temporal frame or clip")
    if not sample_ref.video_path or sample_ref.start_ms is None or sample_ref.end_ms is None:
        raise VisionError("MEDIA_READ_FAILED", "temporal sample is missing video bounds")
    if sample_ref.start_ms < 0 or sample_ref.end_ms <= sample_ref.start_ms or sample_ref.end_ms > max_duration_ms:
        raise VisionError("MEDIA_READ_FAILED", "temporal sample time bounds are invalid")
    if sample_ref.frame_start is None or sample_ref.frame_end is None or sample_ref.frame_start < 0 or sample_ref.frame_end < sample_ref.frame_start:
        raise VisionError("MEDIA_READ_FAILED", "temporal sample frame bounds are invalid")
    if sample_ref.sampling_fps is None or not 0 < sample_ref.sampling_fps <= 240:
        raise VisionError("MEDIA_READ_FAILED", "temporal sample FPS is invalid")


def _bounded_int(value: object, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError
    return value


def _decode_model_json(content: str) -> Mapping[str, object]:
    candidate = content.strip()
    if candidate.startswith("```"):
        lines = candidate.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        candidate = "\n".join(lines).strip()
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        start, end = candidate.find("{"), candidate.rfind("}")
        if start < 0 or end <= start:
            raise ValueError("model response does not contain a JSON object")
        value = json.loads(candidate[start : end + 1])
    if not isinstance(value, Mapping):
        raise ValueError("model response JSON must be an object")
    return value


def _strings(value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or any(not isinstance(item, str) or not item for item in value) or len(set(value)) != len(value):
        raise ValueError
    return tuple(value)


def _enum(value: object, choices: set[str]) -> str:
    if not isinstance(value, str) or value not in choices:
        raise ValueError
    return value


def _safe_media_path(root: Path | str, relative_path: str, maximum: int, formats: tuple[str, ...]) -> Path:
    root_path = Path(root).expanduser()
    path = Path(relative_path)
    suffix = path.suffix.lower().lstrip(".")
    normalized_suffix = "jpeg" if suffix == "jpg" else suffix
    if path.is_absolute() or ".." in path.parts or normalized_suffix not in formats:
        raise VisionError("UNSUPPORTED_MEDIA", "media path or format is not allowed")
    root_path = root_path.resolve()
    target = (root_path / path).resolve(strict=False)
    if not _is_relative_to(target, root_path):
        raise VisionError("MEDIA_READ_FAILED", "media path escapes snapshot root")
    current = root_path
    for part in path.parts:
        current = current / part
        if current.is_symlink():
            raise VisionError("MEDIA_READ_FAILED", "symbolic links are not allowed")
    if not target.is_file():
        raise VisionError("MEDIA_READ_FAILED", "media file is unavailable")
    try:
        if target.stat().st_size > maximum:
            raise VisionError("MEDIA_READ_FAILED", "media exceeds configured byte limit")
    except OSError as exc:
        raise VisionError("MEDIA_READ_FAILED", "media metadata is unavailable") from exc
    return target


def _read(path: Path) -> bytes:
    try:
        return path.read_bytes()
    except OSError as exc:
        raise VisionError("MEDIA_READ_FAILED", "media could not be read") from exc


def _looks_like_image(content: bytes, suffix: str) -> bool:
    if suffix == "png":
        return content.startswith(b"\x89PNG\r\n\x1a\n")
    if suffix == "jpeg":
        return content.startswith(b"\xff\xd8\xff")
    if suffix == "webp":
        return content.startswith(b"RIFF") and len(content) >= 12 and content[8:12] == b"WEBP"
    return False


def _is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True
