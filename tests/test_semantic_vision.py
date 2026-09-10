import base64
import json
import os
import struct
import tempfile
import time
import unittest
import zlib
from pathlib import Path

from datamodelmatch.semantic_vision import (
    CostEstimate,
    DecodedFrame,
    FixedCostEstimator,
    PreparedMedia,
    VlmClient,
    VlmBudgetError,
    VisionError,
    failed_observation,
    load_vlm_config,
    prepare_image,
    prepare_video_frame,
    validate_visual_observation,
)
from datamodelmatch.semantic_sampling import SampleRef


def _config(path: Path, vlm: dict):
    path.write_text(json.dumps({
        "endpoint": "https://text.invalid",
        "apiKey": "text-secret",
        "model": "text-model",
        "stream": False,
        "vlm": vlm,
    }), encoding="utf-8")


def _vlm():
    return {
        "version": 1,
        "provider": "test",
        "endpoint": "https://vision.invalid/v1/chat/completions",
        "apiKey": "vision-secret",
        "model": "MiniCPM-V-4.5",
        "imageInput": {"formats": ["png"], "maxBytes": 1024 * 1024},
        "videoInput": {"mode": "frames_only", "formats": ["mp4"], "maxBytes": 1024 * 1024, "maxDurationMs": 60000},
        "limits": {"timeoutMs": 1000, "maxCallsPerStage": 3, "maxCostUsdPerJob": 1.0},
        "retry": {"maxAttempts": 1, "baseDelayMs": 100},
    }


def _png():
    return b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR" + (16).to_bytes(4, "big") + (16).to_bytes(4, "big") + bytes([8, 2]) + b"\x00" * 4


def _result():
    return {
        "objectCategories": ["person"],
        "environments": ["indoor"],
        "viewpoints": ["front"],
        "targetScale": "medium",
        "objectDensity": "low",
        "occlusion": "rare",
        "illumination": ["daylight"],
        "cameraMotion": "static",
        "targetMotion": "slow",
    }


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def read(self):
        return json.dumps(self.payload).encode()


class _UnboundedEstimator:
    def estimate(self, **kwargs):
        return CostEstimate(0, False, "unknown")


def _client(config, payload, **kwargs):
    return VlmClient(
        config,
        opener=lambda request, timeout: _Response(payload),
        cost_estimator=FixedCostEstimator(0.1),
        **kwargs,
    )


class SemanticVisionTests(unittest.TestCase):
    def test_explicit_config_and_safe_image_preparation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "config.llm.json"
            _config(config_path, _vlm())
            config = load_vlm_config(config_path)
            (root / "frame.png").write_bytes(_png())
            media = prepare_image(root, "frame.png", config)
        self.assertEqual(config.model, "MiniCPM-V-4.5")
        self.assertTrue(config.fingerprint.startswith("sha256:"))
        self.assertEqual(media.media_type, "image")
        self.assertTrue(media.data_url.startswith("data:image/png;base64,"))
        self.assertEqual(base64.b64decode(media.data_url.split(",", 1)[1]), _png())
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "config.llm.json"
            vlm = _vlm()
            vlm["imageInput"]["formats"] = ["png", "jpeg"]
            _config(config_path, vlm)
            config = load_vlm_config(config_path)
            (root / "frame.jpg").write_bytes(b"\xff\xd8\xff" + b"jpeg")
            media = prepare_image(root, "frame.jpg", config)
        self.assertTrue(media.data_url.startswith("data:image/jpeg;base64,"))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "config.llm.json"
            _config(config_path, _vlm())
            config = load_vlm_config(config_path)
            (root / "broken.png").write_bytes(b"not-an-image")
            with self.assertRaises(VisionError) as ctx:
                prepare_image(root, "broken.png", config)
        self.assertEqual(ctx.exception.code, "MEDIA_READ_FAILED")

    def test_missing_vlm_never_falls_back_to_text_config(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.llm.json"
            path.write_text(json.dumps({"endpoint": "https://x", "apiKey": "a", "model": "m", "stream": False}), encoding="utf-8")
            with self.assertRaises(VisionError) as ctx:
                load_vlm_config(path)
        self.assertEqual(ctx.exception.code, "VLM_CONFIG_INVALID")

    def test_strict_observation_validation_and_controlled_failures(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.llm.json"
            _config(path, _vlm())
            config = load_vlm_config(path)
        observation = validate_visual_observation(_result(), "sample_1", "observation_1", config.model, config.fingerprint, "evidence_1")
        self.assertEqual(observation.status, "COMPLETED")
        with self.assertRaises(VisionError):
            validate_visual_observation({**_result(), "extra": True}, "sample_1", "observation_2", config.model, config.fingerprint, "evidence_2")
        failed = failed_observation("sample_1", "observation_3", config, "VLM_EMPTY_RESPONSE", "evidence_3")
        self.assertEqual(failed.status, "FAILED")
        self.assertEqual(failed.failure_code, "VLM_EMPTY_RESPONSE")

    def test_client_success_empty_malformed_and_timeout(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.llm.json"
            _config(path, _vlm())
            config = load_vlm_config(path)
            media = PreparedMedia("image", "frame.png", "data:image/png;base64,AA==", 1)
        valid_payload = {"choices": [{"message": {"content": json.dumps(_result())}}]}
        client = _client(config, valid_payload)
        self.assertEqual(client.observe_image(media, "s1", "o1", "e1").status, "COMPLETED")
        empty = _client(config, {"choices": [{"message": {"content": ""}}]})
        self.assertEqual(empty.observe_image(media, "s1", "o2", "e2").failure_code, "VLM_EMPTY_RESPONSE")
        malformed = _client(config, {"choices": [{"message": {"content": "{}"}}]})
        self.assertEqual(malformed.observe_image(media, "s1", "o3", "e3").failure_code, "VLM_INVALID_RESPONSE")
        timed = VlmClient(
            config,
            opener=lambda request, timeout: (_ for _ in ()).throw(TimeoutError()),
            sleep=lambda _: None,
            cost_estimator=FixedCostEstimator(0.1),
        )
        self.assertEqual(timed.observe_image(media, "s1", "o4", "e4").failure_code, "VLM_TIMEOUT")

    def test_cost_is_explicit_bounded_and_budget_is_per_job(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.llm.json"
            _config(path, _vlm())
            config = load_vlm_config(path)
        media = PreparedMedia("image", "frame.png", "data:image/png;base64,AA==", 1)
        payload = {"choices": [{"message": {"content": json.dumps(_result())}}]}
        unbounded = VlmClient(config, opener=lambda request, timeout: _Response(payload))
        with self.assertRaises(VlmBudgetError) as ctx:
            unbounded.observe_image(media, "s1", "o1", "e1")
        self.assertEqual(ctx.exception.reason, "VLM_COST_UNBOUNDED")
        bounded = _client(config, payload)
        bounded.budget_tracker.budget_usd = 0.15
        self.assertEqual(bounded.observe_image(media, "s1", "o2", "e2").status, "COMPLETED")
        with self.assertRaises(VlmBudgetError) as ctx:
            bounded.observe_image(media, "s2", "o3", "e3")
        self.assertEqual(ctx.exception.reason, "VLM_COST_BUDGET_EXHAUSTED")
        unbounded_estimator = VlmClient(
            config,
            opener=lambda request, timeout: _Response(payload),
            cost_estimator=_UnboundedEstimator(),
        )
        with self.assertRaises(VlmBudgetError):
            unbounded_estimator.observe_image(media, "s3", "o4", "e4")

    def test_https_endpoint_is_required(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.llm.json"
            value = _vlm()
            value["endpoint"] = "http://vision.invalid/v1"
            _config(path, value)
            with self.assertRaises(VisionError) as ctx:
                load_vlm_config(path)
        self.assertEqual(ctx.exception.code, "VLM_CONFIG_INVALID")

    def test_video_decoder_success_provenance_and_failure_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            config_path = root / "config.llm.json"
            _config(config_path, _vlm())
            config = load_vlm_config(config_path)
            video = root / "clip.mp4"
            video.write_bytes(b"video")
            sample = SampleRef("sample_video", "clip", "clip.mp4", "sha256:" + "a" * 64, "clip.mp4", 100, 900, 1, 9, 10.0)
            derived_root = root / "derived"

            class Decoder:
                def decode(self, source_path, sample_ref):
                    self.seen = (source_path, sample_ref.id)
                    return DecodedFrame(_png(), "png", "approved-test-decoder-1")

            decoder = Decoder()
            prepared = prepare_video_frame(root, sample, config, derived_root, decoder)
            self.assertEqual(prepared.media_type, "image")
            self.assertEqual(prepared.provenance["decoderId"], "approved-test-decoder-1")
            self.assertEqual(prepared.provenance["startMs"], 100)
            self.assertTrue((derived_root / prepared.source_path).is_file())
            self.assertEqual(decoder.seen[1], "sample_video")
            with self.assertRaises(VisionError) as ctx:
                prepare_video_frame(root, sample, config, root / "unsupported", None)
            self.assertEqual(ctx.exception.code, "UNSUPPORTED_MEDIA")

            class BrokenDecoder:
                def decode(self, source_path, sample_ref):
                    raise RuntimeError("decoder failed")

            with self.assertRaises(VisionError) as ctx:
                prepare_video_frame(root, sample, config, root / "broken", BrokenDecoder())
            self.assertEqual(ctx.exception.code, "MEDIA_READ_FAILED")

    def test_video_temporal_validation_and_derived_root_safety(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            _config(root / "config.llm.json", _vlm())
            config = load_vlm_config(root / "config.llm.json")
            (root / "clip.mp4").write_bytes(b"video")
            decoder = type("Decoder", (), {"decode": lambda self, source, sample: DecodedFrame(_png(), "png", "decoder")})()
            invalid = SampleRef("sample_invalid", "clip", "clip.mp4", "sha256:" + "b" * 64, "clip.mp4", 900, 100, 1, 0, 10.0)
            with self.assertRaises(VisionError) as ctx:
                prepare_video_frame(root, invalid, config, root / "derived", decoder)
            self.assertEqual(ctx.exception.code, "MEDIA_READ_FAILED")
            outside = root.parent / ("outside-derived-" + root.name)
            outside.mkdir(exist_ok=True)
            link = root / "derived-link"
            try:
                link.symlink_to(outside, target_is_directory=True)
            except OSError:
                self.skipTest("symlink creation unavailable")
            with self.assertRaises(VisionError) as ctx:
                prepare_video_frame(root, SampleRef("sample_valid", "clip", "clip.mp4", "sha256:" + "c" * 64, "clip.mp4", 0, 100, 0, 1, 10.0), config, link, decoder)
            self.assertEqual(ctx.exception.code, "MEDIA_READ_FAILED")

    @unittest.skipUnless(os.environ.get("RUN_REAL_VLM_TESTS") == "1", "set RUN_REAL_VLM_TESTS=1 for the approved provider")
    def test_real_vlm_generated_image_success(self):
        def chunk(kind, payload):
            return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF)

        rows = b"".join(b"\x00" + b"\xff\x00\x00\xff" * 16 for _ in range(16))
        png = (
            b"\x89PNG\r\n\x1a\n"
            + chunk(b"IHDR", struct.pack(">IIBBBBB", 16, 16, 8, 6, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(rows))
            + chunk(b"IEND", b"")
        )
        prompt = (
            "Return ONLY one valid JSON object, no markdown and no explanation. "
            'Copy this exact shape and replace values only: {"objectCategories":[],"environments":[],"viewpoints":[],"targetScale":"UNKNOWN","objectDensity":"UNKNOWN","occlusion":"UNKNOWN","illumination":[],"cameraMotion":"UNKNOWN","targetMotion":"UNKNOWN"}. '
            "The first three and illumination MUST remain JSON arrays of strings. Do not use strings for arrays."
        )
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "probe.png").write_bytes(png)
            config = load_vlm_config("config.llm.json")
            started = time.monotonic()
            result = VlmClient(config, cost_estimator=FixedCostEstimator(0.1)).observe_image(
                prepare_image(root, "probe.png", config),
                "sample_real_probe",
                "observation_real_probe",
                "evidence_real_probe",
                prompt=prompt,
            )
        self.assertEqual(result.status, "COMPLETED")
        self.assertIsNone(result.failure_code)
