import argparse
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from datamodelmatch.resource_cli import _dataset_task_match, _import, _validate_local_source, main
from datamodelmatch.resource_store import ResourceStore
from datamodelmatch.resource_types import ResourceRecord


class ResourceCliTests(unittest.TestCase):
    def test_task_match_stream_emits_safe_stages_and_result(self) -> None:
        now = "2026-09-10T00:00:00Z"
        record = ResourceRecord(
            id="dataset_streamed",
            kind="dataset",
            source_type="local",
            source="/source",
            revision="local",
            resolved_revision="local-test",
            name="道路数据",
            status="ready",
            local_path="resources/datasets/dataset_streamed",
            profile_path="profiles/datasets/dataset_streamed.json",
            file_count=1,
            size_bytes=1,
            created_at=now,
            updated_at=now,
        )
        profile = {
            "resourceId": record.id,
            "summary": "道路数据",
            "semanticDescription": "道路视觉数据",
            "agentAnalysis": {
                "capabilities": ["道路视觉理解"],
                "characteristics": ["真实图像"],
                "limitations": [],
            },
            "unresolved": [],
            "evidence": [{"id": "evidence_1", "kind": "inspection"}],
        }
        response = {
            "taskInterpretation": "道路任务",
            "matches": [{
                "resourceId": record.id,
                "verdict": "recommended",
                "score": 0.9,
                "explanation": "道路视觉数据与任务相符。",
                "concerns": [],
                "evidenceRefs": [f"{record.id}:evidence_1"],
                "missingInformation": [],
            }],
        }

        class Agent:
            def match_task(self, context):
                return response

        store = Mock()
        store.list.return_value = [record]
        arguments = argparse.Namespace(text="道路任务", stream=True)
        with patch("datamodelmatch.semantic_agent.SemanticAgentClient.from_config", return_value=Agent()), \
             patch("datamodelmatch.semantic_runtime.build_semantic_profile", side_effect=lambda *args, **kwargs: (
                 kwargs["progress_reporter"]("aggregation", "已找到当前快照的既有分析结果，正在载入。") or dict(profile)
             )), \
             patch("datamodelmatch.resource_cli._emit") as emit:
            self.assertEqual(_dataset_task_match(arguments, store), 0)

        events = [(call.args[0], call.args[1]) for call in emit.call_args_list]
        stages = [data["stage"] for event, data in events if event == "task-discovery-progress"]
        self.assertEqual(stages, ["profiles", "profile", "profile", "profile", "profiles", "agent", "validation", "validation", "complete"])
        self.assertEqual(events[-2][0], "result")
        self.assertEqual(events[-2][1]["matches"][0]["resourceId"], record.id)
        self.assertEqual(events[-1], ("end", {"status": "completed"}))

    def test_task_match_stream_handles_no_candidates_without_calling_agent(self) -> None:
        store = Mock()
        store.list.return_value = []
        arguments = argparse.Namespace(text="道路任务", stream=True)
        with patch("datamodelmatch.semantic_agent.SemanticAgentClient.from_config") as agent_factory, \
             patch("datamodelmatch.resource_cli._emit") as emit:
            self.assertEqual(_dataset_task_match(arguments, store), 0)

        agent_factory.assert_not_called()
        events = [(call.args[0], call.args[1]) for call in emit.call_args_list]
        stages = [data["stage"] for event, data in events if event == "task-discovery-progress"]
        self.assertEqual(stages, ["profiles", "profiles", "agent", "validation", "complete"])
        self.assertEqual(events[-2][1]["matches"], [])

    def test_task_match_stream_emits_error_and_end_on_agent_failure(self) -> None:
        with patch("datamodelmatch.resource_cli._store"), \
             patch("datamodelmatch.resource_cli._dataset_task_match", side_effect=ValueError("agent unavailable")), \
             patch("datamodelmatch.resource_cli._emit") as emit:
            self.assertEqual(main(["dataset-task-match", "--stream", "道路任务"]), 1)

        self.assertEqual(
            [(call.args[0], call.args[1]) for call in emit.call_args_list],
            [
                ("error", {"code": "INVALID_INPUT", "message": "agent unavailable"}),
                ("end", {"status": "failed"}),
            ],
        )

    def test_allows_workspace_child_and_rejects_protected_subtree(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            source = workspace / "fixtures" / "dataset"
            source.mkdir(parents=True)
            store = ResourceStore(workspace / ".datamodelmatch")
            store.ensure()

            with patch("datamodelmatch.resource_cli.Path.cwd", return_value=workspace):
                self.assertEqual(_validate_local_source(str(source), store), str(source.resolve()))
                with self.assertRaisesRegex(ValueError, "受保护路径"):
                    _validate_local_source(str(store.root), store)

    def test_dataset_import_requires_semantic_profile_before_result(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            (source / "data.csv").write_text("image,label\nx.png,car\n", encoding="utf-8")
            store = ResourceStore(root / "store")
            arguments = argparse.Namespace(
                kind="dataset",
                source_type="local",
                source=str(source),
                revision="",
                download_mode="sample",
                max_bytes=1024 * 1024,
            )
            now = "2026-09-10T00:00:00Z"
            record = ResourceRecord(
                id="dataset_semantic",
                kind="dataset",
                source_type="local",
                source=str(source),
                revision="local",
                resolved_revision="local-test",
                name="semantic",
                status="ready",
                local_path="placeholder",
                profile_path="placeholder",
                file_count=1,
                size_bytes=1,
                created_at=now,
                updated_at=now,
            )
            base_profile = {
                "version": 1,
                "resourceId": record.id,
                "name": record.name,
                "completeness": 1,
                "warnings": [],
            }
            semantic = {"resourceId": record.id, "summary": "语义结论"}

            with patch("datamodelmatch.resource_cli._validate_local_source", return_value=str(source)), \
                 patch("datamodelmatch.dataset_resources.import_dataset", return_value=(record, base_profile)), \
                 patch("datamodelmatch.semantic_runtime.build_semantic_profile", side_effect=lambda store, resource_id, **kwargs: (
                     self.assertEqual(store.get(resource_id).status, "analyzing") or semantic
                 )), \
                 patch("datamodelmatch.resource_cli._emit") as emit:
                self.assertEqual(_import(arguments, store), 0)

            events = [call.args[0] for call in emit.call_args_list]
            self.assertEqual(events[-2:], ["result", "end"])
            progress = [call.args[1] for call in emit.call_args_list if call.args[0] == "semantic-progress"]
            self.assertTrue(progress)
            self.assertEqual(progress[0]["phase"], "sampling")
            self.assertEqual(store.get(record.id).status, "ready")

    def test_dataset_import_rolls_back_when_semantic_analysis_fails(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / "source"
            source.mkdir()
            store = ResourceStore(root / "store")
            arguments = argparse.Namespace(
                kind="dataset",
                source_type="local",
                source=str(source),
                revision="",
                download_mode="sample",
                max_bytes=1024 * 1024,
            )
            now = "2026-09-10T00:00:00Z"
            record = ResourceRecord(
                id="dataset_failed_semantic",
                kind="dataset",
                source_type="local",
                source=str(source),
                revision="local",
                resolved_revision="local-test",
                name="semantic",
                status="ready",
                local_path="placeholder",
                profile_path="placeholder",
                file_count=1,
                size_bytes=1,
                created_at=now,
                updated_at=now,
            )
            base_profile = {
                "version": 1,
                "resourceId": record.id,
                "name": record.name,
                "completeness": 1,
                "warnings": [],
            }

            with patch("datamodelmatch.resource_cli._validate_local_source", return_value=str(source)), \
                 patch("datamodelmatch.dataset_resources.import_dataset", return_value=(record, base_profile)), \
                 patch("datamodelmatch.semantic_runtime.build_semantic_profile", side_effect=ValueError("agent unavailable")):
                with self.assertRaisesRegex(ValueError, "agent unavailable"):
                    _import(arguments, store)

            with self.assertRaises(KeyError):
                store.get(record.id)


if __name__ == "__main__":
    unittest.main()
