import unittest

from datamodelmatch.semantic_matching import TaskProfileError, match_task, parse_task


class _Agent:
    def __init__(self, response):
        self.response = response
        self.context = None

    def match_task(self, context):
        self.context = context
        return self.response


def _profile(resource_id, name, description, evidence_id):
    return {
        "resourceId": resource_id,
        "name": name,
        "summary": name,
        "semanticDescription": description,
        "agentAnalysis": {
            "capabilities": ["可用于视觉理解任务"],
            "characteristics": ["包含真实图像与标注证据"],
            "limitations": [],
        },
        "unresolved": [],
        "evidence": [{"id": evidence_id, "kind": "inspection"}],
    }


class SemanticMatchingTests(unittest.TestCase):
    def test_keeps_task_text_for_agent_interpretation(self) -> None:
        task = parse_task("寻找有复杂遮挡的夜间道路视觉数据")
        self.assertEqual(task["rawText"], "寻找有复杂遮挡的夜间道路视觉数据")
        self.assertIn("Agent", task["interpretation"])

    def test_agent_controls_semantic_ranking_and_explanation(self) -> None:
        profiles = [
            _profile("dataset_a", "甲", "城市道路夜间数据", "evidence_1"),
            _profile("dataset_b", "乙", "室内货架图片", "evidence_1"),
        ]
        agent = _Agent(
            {
                "taskInterpretation": "用户要的是夜间道路场景，并关心遮挡。",
                "matches": [
                    {
                        "resourceId": "dataset_a",
                        "verdict": "recommended",
                        "score": 0.9,
                        "explanation": "描述和证据都指向夜间道路视觉场景。",
                        "concerns": ["遮挡程度尚需更多样本确认"],
                        "evidenceRefs": ["dataset_a:evidence_1"],
                        "missingInformation": [],
                    },
                    {
                        "resourceId": "dataset_b",
                        "verdict": "not_recommended",
                        "score": 0.2,
                        "explanation": "场景语义偏向室内货架，与目标不同。",
                        "concerns": [],
                        "evidenceRefs": ["dataset_b:evidence_1"],
                        "missingInformation": [],
                    },
                ],
            }
        )

        result = match_task(
            parse_task("寻找有复杂遮挡的夜间道路视觉数据"),
            profiles,
            agent,
        )

        self.assertEqual(result[0]["resourceId"], "dataset_a")
        self.assertEqual(result[0]["verdict"], "recommended")
        self.assertEqual(
            agent.context["rules"][2],
            "Use semantic meaning, not literal keyword overlap.",
        )

    def test_rejects_cross_dataset_evidence_and_incomplete_results(self) -> None:
        profile = _profile("dataset_a", "甲", "道路数据", "evidence_1")
        cross_dataset_agent = _Agent(
            {
                "taskInterpretation": "道路任务",
                "matches": [
                    {
                        "resourceId": "dataset_a",
                        "verdict": "recommended",
                        "score": 0.9,
                        "explanation": "道路语义相近。",
                        "concerns": [],
                        "evidenceRefs": ["dataset_b:evidence_1"],
                        "missingInformation": [],
                    }
                ],
            }
        )
        with self.assertRaisesRegex(TaskProfileError, "不属于该数据集"):
            match_task(parse_task("道路任务"), [profile], cross_dataset_agent)

        incomplete_agent = _Agent(
            {"taskInterpretation": "道路任务", "matches": []}
        )
        with self.assertRaisesRegex(TaskProfileError, "完整候选集"):
            match_task(parse_task("道路任务"), [profile], incomplete_agent)
