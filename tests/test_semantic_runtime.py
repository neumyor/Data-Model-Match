import json
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from datamodelmatch.resource_store import ResourceStore
from datamodelmatch.resource_types import ResourceRecord
from datamodelmatch.semantic_runtime import (
    SemanticRuntimeError,
    build_semantic_profile,
    get_semantic_profile,
)
from datamodelmatch.semantic_vision import VisualObservation


def _record(resource_id: str) -> ResourceRecord:
    now = (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )
    return ResourceRecord(
        id=resource_id,
        kind="dataset",
        source_type="local",
        source="/tmp/source",
        revision="local",
        resolved_revision="local",
        name="demo",
        status="ready",
        local_path=f"resources/datasets/{resource_id}",
        profile_path=f"profiles/datasets/{resource_id}.json",
        file_count=2,
        size_bytes=1,
        created_at=now,
        updated_at=now,
    )


class _Agent:
    def __init__(self) -> None:
        self.context = None

    def analyze_dataset(self, context):
        self.context = context
        refs = [item["id"] for item in context["evidence"]]
        return {
            "summary": "用于道路视觉任务的数据集。",
            "semanticDescription": "Agent 基于文档、文件检查和可用视觉观察生成的描述。",
            "capabilities": ["道路场景视觉分析"],
            "characteristics": ["包含图像及关联标注证据"],
            "limitations": ["标注语义仍需要按具体任务确认"],
            "evidenceRefs": refs[:2],
            "unknowns": ["未观察到的视觉变化"],
        }


class SemanticRuntimeTests(unittest.TestCase):
    def test_builds_cached_agent_profile_from_bounded_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ResourceStore(Path(directory) / "store")
            record = _record("dataset_demo")
            root = store.root / record.local_path
            root.mkdir(parents=True)
            (root / "image.png").write_bytes(
                b"\x89PNG\r\n\x1a\n"
                + b"\x00\x00\x00\rIHDR"
                + (20).to_bytes(4, "big")
                + (10).to_bytes(4, "big")
                + bytes([8, 2])
                + b"\x00\x00\x00\x00"
            )
            (root / "labels.csv").write_text(
                "image,annotation\n1.png,car\n",
                encoding="utf-8",
            )
            store.save(record, {"version": 1})
            agent = _Agent()

            profile = build_semantic_profile(
                store,
                record.id,
                config_path=Path(directory) / "missing-vlm.json",
                agent_client=agent,
            )
            cached = get_semantic_profile(store, record.id)

        self.assertEqual(profile["analysisMode"], "agent_evidence")
        self.assertEqual(profile["summary"], "用于道路视觉任务的数据集。")
        self.assertEqual(profile["agentAnalysis"]["capabilities"], ["道路场景视觉分析"])
        self.assertEqual(profile["content"]["source"], "semantic_agent")
        self.assertEqual(cached, profile)
        self.assertTrue(agent.context["inspections"])
        self.assertTrue(agent.context["evidence"][0]["id"].startswith("evidence_"))

    def test_agent_can_reference_all_bounded_snapshot_evidence(self) -> None:
        class AllEvidenceAgent(_Agent):
            def analyze_dataset(self, context):
                result = super().analyze_dataset(context)
                result["evidenceRefs"] = [item["id"] for item in context["evidence"]]
                return result

        with tempfile.TemporaryDirectory() as directory:
            store = ResourceStore(Path(directory) / "store")
            record = _record("dataset_all_evidence")
            root = store.root / record.local_path
            root.mkdir(parents=True)
            for index in range(13):
                (root / f"metadata_{index}.json").write_text("{}", encoding="utf-8")
            store.save(record, {"version": 1})

            profile = build_semantic_profile(
                store,
                record.id,
                config_path=Path(directory) / "missing-vlm.json",
                agent_client=AllEvidenceAgent(),
            )

        self.assertGreater(len(profile["agentAnalysis"]["evidenceRefs"]), 12)

    def test_agent_must_cite_only_this_snapshot_evidence(self) -> None:
        class InvalidAgent(_Agent):
            def analyze_dataset(self, context):
                result = super().analyze_dataset(context)
                result["evidenceRefs"] = ["not-an-evidence-id"]
                return result

        with tempfile.TemporaryDirectory() as directory:
            store = ResourceStore(Path(directory) / "store")
            record = _record("dataset_bad_agent")
            root = store.root / record.local_path
            root.mkdir(parents=True)
            (root / "README.md").write_text("dataset", encoding="utf-8")
            store.save(record, {"version": 1})

            with self.assertRaisesRegex(SemanticRuntimeError, "无效证据"):
                build_semantic_profile(
                    store,
                    record.id,
                    config_path=Path(directory) / "missing-vlm.json",
                    agent_client=InvalidAgent(),
                )

    def test_includes_vlm_observation_as_agent_evidence_without_keyword_rules(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            store = ResourceStore(Path(directory) / "store")
            record = _record("dataset_visual")
            root = store.root / record.local_path
            root.mkdir(parents=True)
            (root / "image.png").write_bytes(
                b"\x89PNG\r\n\x1a\n"
                + b"\x00\x00\x00\rIHDR"
                + (20).to_bytes(4, "big")
                + (10).to_bytes(4, "big")
                + bytes([8, 2])
                + b"\x00\x00\x00\x00"
            )
            store.save(record, {"version": 1})
            config_path = Path(directory) / "config.llm.json"
            config_path.write_text(
                json.dumps(
                    {
                        "vlm": {
                            "version": 1,
                            "provider": "test",
                            "endpoint": "https://vision.invalid/v1/chat/completions",
                            "apiKey": "not-a-real-key",
                            "model": "test-vision",
                            "imageInput": {"formats": ["png"], "maxBytes": 1024 * 1024},
                            "videoInput": {
                                "mode": "frames_only",
                                "formats": ["mp4"],
                                "maxBytes": 1024 * 1024,
                                "maxDurationMs": 60000,
                            },
                            "limits": {
                                "timeoutMs": 1000,
                                "maxCallsPerStage": 3,
                                "maxCostUsdPerJob": 1.0,
                            },
                            "retry": {"maxAttempts": 1, "baseDelayMs": 100},
                        }
                    }
                ),
                encoding="utf-8",
            )

            class FakeVlmClient:
                def __init__(self, config):
                    self.config = config

                def observe_image(self, media, sample_ref, observation_id, evidence_ref, prompt):
                    return VisualObservation(
                        observation_id,
                        sample_ref,
                        ("car",),
                        ("urban",),
                        ("front",),
                        "medium",
                        "low",
                        "rare",
                        ("night",),
                        "static",
                        "slow",
                        self.config.model,
                        self.config.fingerprint,
                        "COMPLETED",
                        (evidence_ref,),
                    )

            agent = _Agent()
            profile = build_semantic_profile(
                store,
                record.id,
                config_path=config_path,
                vlm_client_factory=FakeVlmClient,
                agent_client=agent,
            )

        self.assertEqual(profile["analysisMode"], "agent_evidence+vlm")
        self.assertEqual(profile["observations"][0]["status"], "COMPLETED")
        self.assertTrue(agent.context["visualEvidence"]["observations"])
