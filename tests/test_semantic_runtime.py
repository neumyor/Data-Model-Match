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
            "semanticDescription": "Agent 基于文档、文件检查和本地代码执行生成的描述。",
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
        self.assertEqual(profile["agentCodeExecutions"], [])
        self.assertFalse({"sampling", "sampleRefs", "observations"} & set(profile))
        self.assertEqual(cached, profile)
        self.assertTrue(agent.context["inspections"])
        self.assertTrue(agent.context["evidence"][0]["id"].startswith("evidence_"))
        self.assertNotIn("visualEvidence", agent.context)

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
