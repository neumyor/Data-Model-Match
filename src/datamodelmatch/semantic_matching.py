"""Agent-led task discovery over durable dataset semantic profiles.

The program deliberately does not infer task semantics from a keyword list or
compare profile fields mechanically. It prepares bounded evidence for the
Agent, validates the returned decision, and keeps its reasoning inspectable.
"""

from __future__ import annotations

from typing import Iterable, Mapping

from .semantic_agent import SemanticAgentClient, SemanticAgentError


class TaskProfileError(ValueError):
    """Raised when a task discovery request or Agent decision is malformed."""


_VERDICTS = frozenset(
    {"recommended", "possible", "not_recommended", "unknown"}
)
_MAX_TEXT = 2_000
_MAX_ITEMS = 12


def parse_task(text: str) -> dict[str, object]:
    """Keep the user's requirement intact for Agent interpretation."""

    if not isinstance(text, str) or not text.strip():
        raise TaskProfileError("任务描述不能为空")
    if len(text.strip()) > _MAX_TEXT:
        raise TaskProfileError("任务描述不能超过 2000 个字符")
    return {
        "version": 2,
        "rawText": text.strip(),
        "interpretation": "由语义 Agent 在检索时结合候选数据集证据理解。",
    }


def match_task(
    task: Mapping[str, object],
    profiles: Iterable[Mapping[str, object]],
    agent: SemanticAgentClient,
) -> list[dict[str, object]]:
    """Ask one Agent to interpret the task and rank all provided candidates."""

    if not isinstance(task, Mapping):
        raise TaskProfileError("任务档案必须是对象")
    task_text = task.get("rawText")
    if not isinstance(task_text, str) or not task_text.strip():
        raise TaskProfileError("任务档案缺少 rawText")

    candidates = [_candidate(profile) for profile in profiles]
    if not candidates:
        return []
    context = {
        "task": task_text,
        "candidates": candidates,
        "requiredResponse": {
            "taskInterpretation": "string",
            "matches": [
                {
                    "resourceId": "one provided candidate id",
                    "verdict": "recommended | possible | not_recommended | unknown",
                    "score": "number from 0 to 1",
                    "explanation": "concise Chinese explanation grounded in supplied evidence",
                    "concerns": ["string"],
                    "evidenceRefs": ["only allowedEvidenceRefs for that candidate"],
                    "missingInformation": ["string"],
                }
            ],
        },
        "rules": [
            "Return exactly one match for every candidate and no other resourceId.",
            "Rank the matches from best to worst.",
            "Use semantic meaning, not literal keyword overlap.",
            "Do not invent facts. Cite only the supplied allowedEvidenceRefs.",
            "A lack of evidence must be represented as unknown or missingInformation.",
        ],
    }
    try:
        raw = agent.match_task(context)
    except SemanticAgentError as exc:
        raise TaskProfileError("语义 Agent 未能完成任务匹配") from exc
    return _validate_matches(raw, candidates)


def _candidate(profile: Mapping[str, object]) -> dict[str, object]:
    resource_id = profile.get("resourceId")
    if not isinstance(resource_id, str) or not resource_id:
        raise TaskProfileError("数据集语义档案缺少 resourceId")
    evidence = profile.get("evidence")
    allowed_evidence: list[str] = []
    if isinstance(evidence, list):
        for item in evidence:
            if isinstance(item, Mapping) and isinstance(item.get("id"), str):
                allowed_evidence.append(f"{resource_id}:{item['id']}")
    agent_analysis = profile.get("agentAnalysis")
    if not isinstance(agent_analysis, Mapping):
        agent_analysis = {}
    return {
        "resourceId": resource_id,
        "name": profile.get("name") if isinstance(profile.get("name"), str) else resource_id,
        "summary": _text(profile.get("summary"), 800),
        "semanticDescription": _text(profile.get("semanticDescription"), 3_000),
        "capabilities": _texts(agent_analysis.get("capabilities")),
        "characteristics": _texts(agent_analysis.get("characteristics")),
        "limitations": _texts(agent_analysis.get("limitations")),
        "unknowns": _texts(profile.get("unresolved")),
        "allowedEvidenceRefs": allowed_evidence,
    }


def _validate_matches(
    raw: Mapping[str, object],
    candidates: list[dict[str, object]],
) -> list[dict[str, object]]:
    if not isinstance(raw, Mapping):
        raise TaskProfileError("语义 Agent 返回不是对象")
    if set(raw) != {"taskInterpretation", "matches"}:
        raise TaskProfileError("语义 Agent 返回的任务匹配字段不完整")
    interpretation = raw.get("taskInterpretation")
    matches = raw.get("matches")
    if not isinstance(interpretation, str) or not interpretation.strip():
        raise TaskProfileError("语义 Agent 未提供任务理解")
    if not isinstance(matches, list) or len(matches) != len(candidates):
        raise TaskProfileError("语义 Agent 未返回完整候选集")

    candidate_by_id = {
        item["resourceId"]: item
        for item in candidates
        if isinstance(item.get("resourceId"), str)
    }
    decisions: list[dict[str, object]] = []
    seen: set[str] = set()
    previous_score = 1.0
    for item in matches:
        if not isinstance(item, Mapping):
            raise TaskProfileError("语义 Agent 返回了无效候选项")
        if set(item) != {
            "resourceId",
            "verdict",
            "score",
            "explanation",
            "concerns",
            "evidenceRefs",
            "missingInformation",
        }:
            raise TaskProfileError("语义 Agent 候选项字段不完整")
        resource_id = item.get("resourceId")
        verdict = item.get("verdict")
        score = item.get("score")
        if not isinstance(resource_id, str) or resource_id not in candidate_by_id or resource_id in seen:
            raise TaskProfileError("语义 Agent 返回了未知或重复数据集")
        if not isinstance(verdict, str) or verdict not in _VERDICTS:
            raise TaskProfileError("语义 Agent 返回了无效推荐结论")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 1:
            raise TaskProfileError("语义 Agent 返回了无效推荐分数")
        if float(score) > previous_score + 1e-9:
            raise TaskProfileError("语义 Agent 返回结果未按分数排序")
        previous_score = float(score)
        explanation = _required_text(item.get("explanation"), "推荐理由")
        concerns = _texts(item.get("concerns"))
        missing = _texts(item.get("missingInformation"))
        refs = _texts(item.get("evidenceRefs"))
        allowed = set(candidate_by_id[resource_id]["allowedEvidenceRefs"])
        if any(reference not in allowed for reference in refs):
            raise TaskProfileError("语义 Agent 引用了不属于该数据集的证据")
        seen.add(resource_id)
        decisions.append(
            {
                "resourceId": resource_id,
                "name": candidate_by_id[resource_id]["name"],
                "verdict": verdict,
                "score": round(float(score), 3),
                "explanation": explanation,
                "concerns": concerns,
                "evidenceRefs": refs,
                "missingInformation": missing,
                "taskInterpretation": interpretation.strip(),
            }
        )
    return decisions


def _required_text(value: object, label: str) -> str:
    result = _text(value, _MAX_TEXT)
    if not result:
        raise TaskProfileError(f"语义 Agent 未提供{label}")
    return result


def _text(value: object, maximum: int) -> str:
    return value.strip()[:maximum] if isinstance(value, str) else ""


def _texts(value: object) -> list[str]:
    if not isinstance(value, list):
        raise TaskProfileError("语义 Agent 列表字段无效")
    result = [_text(item, 400) for item in value]
    if any(not item for item in result) or len(result) > _MAX_ITEMS:
        raise TaskProfileError("语义 Agent 列表字段内容无效")
    return result
