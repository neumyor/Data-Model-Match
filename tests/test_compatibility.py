import unittest
import socket
from typing import Optional
from unittest.mock import Mock

from datamodelmatch.compatibility import CompatibilityError, analyze_compatibility
from datamodelmatch.config import LLMConfig
from datamodelmatch.llm import LLMClient


class CompatibilityTests(unittest.TestCase):
    def test_returns_adaptable_report_with_valid_llm_supplement(self) -> None:
        client = _client({
            "summary": "文本字段可映射到模型输入。",
            "fieldMappings": [{
                "datasetField": "body",
                "modelField": "text",
                "kind": "semantic",
                "confidence": 0.94,
                "reason": "两者都是待分类文本。",
            }],
            "transforms": ["使用模型 tokenizer 对 body 分词。"],
            "warnings": [],
        })

        report = analyze_compatibility(_dataset(features=[_feature("body", "string"), _label()]), _model(), client)

        self.assertEqual(report.status, "adaptable")
        self.assertFalse(report.blockers)
        self.assertIn(("body", "text"), {(item["datasetField"], item["modelField"]) for item in report.field_mappings})
        self.assertFalse(any("等待 LLM" in item for item in report.warnings))
        dimensions = {item.name: item for item in report.dimensions}
        self.assertEqual(dimensions["data_types"].status, "compatible")
        self.assertEqual(dimensions["shape"].status, "compatible")
        self.assertEqual(client.complete_json.call_count, 1)

    def test_deterministic_modality_blocker_cannot_be_overridden_by_llm(self) -> None:
        client = _client(_supplement())
        dataset = _dataset(modalities=["image"], features=[_feature("image", "image"), _label()])

        report = analyze_compatibility(dataset, _model(), client)

        self.assertEqual(report.status, "blocked")
        self.assertTrue(any("缺少模型要求的模态" in item for item in report.blockers))
        client.complete_json.assert_not_called()

    def test_rejects_invalid_llm_output_and_keeps_deterministic_report(self) -> None:
        client = _client({"summary": "缺键"})

        report = analyze_compatibility(_dataset(features=[_feature("text", "string"), _label()]), _model(), client)

        self.assertEqual(report.status, "adaptable")
        self.assertTrue(any("LLM 补充分析不可用" in item for item in report.warnings))

    def test_discards_llm_mapping_with_incompatible_types(self) -> None:
        client = _client({
            "summary": "不安全映射。",
            "fieldMappings": [{
                "datasetField": "image",
                "modelField": "text",
                "kind": "semantic",
                "confidence": 0.9,
                "reason": "错误建议。",
            }],
            "transforms": [],
            "warnings": [],
        })
        dataset = _dataset(modalities=["text"], features=[_feature("image", "image"), _label()])

        report = analyze_compatibility(dataset, _model(), client)

        self.assertFalse(report.field_mappings)
        self.assertTrue(any("忽略 LLM 建议" in item for item in report.warnings))

    def test_rejects_llm_mapping_that_invents_a_field(self) -> None:
        client = _client({
            "summary": "错误字段。",
            "fieldMappings": [{
                "datasetField": "invented",
                "modelField": "text",
                "kind": "semantic",
                "confidence": 0.9,
                "reason": "错误建议。",
            }],
            "transforms": [],
            "warnings": [],
        })

        report = analyze_compatibility(
            _dataset(features=[_feature("body", "string"), _label()]),
            _model(),
            client,
        )

        self.assertEqual(report.status, "unknown")
        self.assertTrue(any("LLM 补充分析不可用" in item for item in report.warnings))

    def test_rejects_invalid_profile_before_llm_call(self) -> None:
        client = _client(_supplement())
        dataset = _dataset()
        del dataset["resourceId"]

        with self.assertRaisesRegex(CompatibilityError, "resourceId"):
            analyze_compatibility(dataset, _model(), client)
        client.complete_json.assert_not_called()

    def test_keeps_deterministic_report_when_llm_transport_times_out(self) -> None:
        client = _client(_supplement())
        client.complete_json.side_effect = socket.timeout("read timed out")

        report = analyze_compatibility(
            _dataset(features=[_feature("text", "string"), _label()]),
            _model(),
            client,
        )

        self.assertEqual(report.status, "adaptable")
        self.assertTrue(any("LLM 补充分析不可用" in item for item in report.warnings))

    def test_emits_auditable_stage_events(self) -> None:
        client = _client(_supplement())
        events = []

        analyze_compatibility(_dataset(features=[_feature("text", "string"), _label()]), _model(), client, events.append)

        self.assertEqual(
            [(item["stage"], item["status"]) for item in events],
            [
                ("deterministic", "started"),
                ("deterministic", "completed"),
                ("llm", "started"),
                ("llm", "completed"),
                ("result", "completed"),
            ],
        )

    def test_validates_all_llm_field_references_before_mutating_report(self) -> None:
        client = _client({
            "summary": "包含一条有效映射和一条虚构映射。",
            "fieldMappings": [
                {
                    "datasetField": "body",
                    "modelField": "text",
                    "kind": "semantic",
                    "confidence": 0.9,
                    "reason": "语义一致。",
                },
                {
                    "datasetField": "invented",
                    "modelField": "text",
                    "kind": "semantic",
                    "confidence": 0.9,
                    "reason": "虚构字段。",
                },
            ],
            "transforms": [],
            "warnings": [],
        })

        report = analyze_compatibility(
            _dataset(features=[_feature("body", "string"), _label()]),
            _model(),
            client,
        )

        self.assertFalse(report.field_mappings)

    def test_normalizes_structured_llm_transform(self) -> None:
        client = _client({
            "summary": "需要分词。",
            "fieldMappings": [],
            "transforms": [{
                "name": "tokenize",
                "appliesTo": "body -> text",
                "reason": "模型要求 token 输入。",
            }],
            "warnings": [],
        })

        report = analyze_compatibility(
            _dataset(features=[_feature("text", "string"), _label()]),
            _model(),
            client,
        )

        self.assertTrue(any("tokenize（body -> text）" in item for item in report.transforms))


def _client(response: dict) -> Mock:
    client = Mock(spec=LLMClient)
    client.config = LLMConfig("https://example.com/v1/chat/completions", "secret", "test-model")
    client.complete_json.return_value = response
    return client


def _dataset(
    *,
    modalities=None,
    task_hints=None,
    features=None,
) -> dict:
    return {
        "resourceId": "dataset_demo",
        "name": "演示文本数据集",
        "modalities": modalities if modalities is not None else ["text"],
        "taskHints": task_hints if task_hints is not None else ["text-classification"],
        "features": features if features is not None else [_feature("text", "string"), _label()],
        "license": "apache-2.0",
        "warnings": [],
    }


def _model() -> dict:
    return {
        "resourceId": "model_demo",
        "name": "演示文本分类模型",
        "tasks": ["text-classification"],
        "frameworks": ["pytorch"],
        "license": "apache-2.0",
        "warnings": [],
        "inputContract": {
            "modalities": ["text"],
            "fields": [_feature("text", "string", required=True)],
            "preprocessing": ["tokenize"],
            "constraints": [],
        },
    }


def _feature(name: str, data_type: str, required: Optional[bool] = None) -> dict:
    value = {"name": name, "dataType": data_type, "shape": []}
    if required is not None:
        value["required"] = required
    return value


def _label() -> dict:
    return {
        "name": "label",
        "dataType": "classlabel",
        "semanticRole": "label",
        "nullable": False,
        "shape": [],
    }


def _supplement() -> dict:
    return {"summary": "确定性检查已完成。", "fieldMappings": [], "transforms": [], "warnings": []}
