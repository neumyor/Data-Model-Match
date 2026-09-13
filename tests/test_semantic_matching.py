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

    def test_reports_safe_agent_and_validation_milestones(self) -> None:
        profile = _profile("dataset_a", "甲", "道路数据", "evidence_1")
        agent = _Agent(
            {
                "taskInterpretation": "道路任务",
                "matches": [
                    {
                        "resourceId": "dataset_a",
                        "verdict": "recommended",
                        "score": 0.9,
                        "explanation": "道路场景与任务一致。",
                        "concerns": [],
                        "evidenceRefs": ["dataset_a:evidence_1"],
                        "missingInformation": [],
                    }
                ],
            }
        )
        progress = []

        match_task(
            parse_task("道路任务"),
            [profile],
            agent,
            progress_reporter=lambda stage, status, message: progress.append((stage, status, message)),
        )

        self.assertEqual([item[:2] for item in progress], [
            ("agent", "started"),
            ("validation", "started"),
            ("validation", "completed"),
        ])
        self.assertNotIn("prompt", " ".join(item[2] for item in progress).lower())

    def test_returns_only_the_top_three_after_comparing_all_candidates(self) -> None:
        profiles = [
            _profile(f"dataset_{index}", str(index), f"候选 {index}", "evidence_1")
            for index in range(4)
        ]
        agent = _Agent(
            {
                "taskInterpretation": "测试任务",
                "matches": [
                    {
                        "resourceId": f"dataset_{index}",
                        "verdict": "recommended",
                        "score": 0.9 - index / 10,
                        "explanation": f"候选 {index} 与任务相关。",
                        "concerns": [],
                        "evidenceRefs": [f"dataset_{index}:evidence_1"],
                        "missingInformation": [],
                    }
                    for index in range(3)
                ],
            }
        )

        result = match_task(parse_task("测试任务"), profiles, agent)

        self.assertEqual(len(result), 3)
        self.assertEqual(agent.context["maximumResults"], 3)
        self.assertIn("exactly the best 3 matches", agent.context["rules"][0])

    def test_repairs_one_incomplete_ranking_before_failing(self) -> None:
        profiles = [
            _profile("dataset_a", "甲", "道路数据", "evidence_1"),
            _profile("dataset_b", "乙", "行人数据", "evidence_1"),
        ]
        corrected = {
            "taskInterpretation": "行人识别任务",
            "matches": [
                {
                    "resourceId": "dataset_b",
                    "verdict": "recommended",
                    "score": 0.9,
                    "explanation": "候选描述表明包含行人场景。",
                    "concerns": [],
                    "evidenceRefs": ["dataset_b:evidence_1"],
                    "missingInformation": [],
                },
                {
                    "resourceId": "dataset_a",
                    "verdict": "possible",
                    "score": 0.5,
                    "explanation": "道路场景可能包含所需目标。",
                    "concerns": [],
                    "evidenceRefs": ["dataset_a:evidence_1"],
                    "missingInformation": [],
                },
            ],
        }

        class RepairAgent(_Agent):
            def repair_task_match(self, context, validation_error):
                self.repair_context = context
                self.validation_error = validation_error
                return corrected

        agent = RepairAgent({"taskInterpretation": "行人识别任务", "matches": []})
        progress = []
        result = match_task(
            parse_task("识别行人"),
            profiles,
            agent,
            progress_reporter=lambda stage, status, message: progress.append((stage, status, message)),
        )

        self.assertEqual([item["resourceId"] for item in result], ["dataset_b", "dataset_a"])
        self.assertIn("候选集", agent.validation_error)
        self.assertIn(("agent", "retrying", "首次排序结果未通过格式校验，Agent 正在依据候选与证据合同修正一次。"), progress)
        self.assertIn(("validation", "retrying", "正在校验修正后的排序结果与引用证据。"), progress)

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
        with self.assertRaisesRegex(TaskProfileError, "候选集"):
            match_task(parse_task("道路任务"), [profile], incomplete_agent)
