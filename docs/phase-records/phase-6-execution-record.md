# Phase 6 自然语言任务解析与双层语义匹配执行记录

## Governance Fields

```text
phaseId: PHASE-6
status: PLANNED
requirementSourceSha256: a2c4f4d2d53e7d1156f171b15f00def54f44b6ac89c761a9fae8eb0ee12dffa5
inputArtifacts: WP0 contracts; WP5 accepted semantic profiles and evidence; frozen matching rule and weight fingerprints
codeRevision: PENDING_FROZEN_BASELINE
workPackageStatus: WP6=PLANNED
responsibleAgent: WP6_OWNER
independentAcceptor: UNASSIGNED_INDEPENDENT_ACCEPTOR
verificationCommands: pytest tests/test_semantic_task.py tests/test_semantic_matching.py; real task LLM test entrypoint; Phase 6 integration acceptance
workDirectory: /Users/yimingniu/Code/DataModelMatch
startedAt: PENDING_AFTER_FROZEN_BASELINE
finishedAt: PENDING
exitCode: PENDING
environmentVersion: PENDING_CAPTURED_AT_EXECUTION
configurationFingerprint: PENDING_REDACTED
realModelSummary: PENDING_REAL_TASK_LLM_SUCCESS_AND_FAILURE_EVIDENCE
sanitizedEvidence: .datamodelmatch/phase-6-evidence/<run-id>/
riskItems: required/preferred confusion; compatibility score leakage; weight drift; ambiguous task parsing; legacy workflow regression
blockers: Phase 0 not frozen; WP5 not accepted; no independent acceptor
rollbackOrReopen: reopen on ranking of non-compatible results, missing evidence, task-profile contract drift, or legacy API semantic regression
approvedAt: PENDING
```

**目标**：将自然语言需求解析为可审阅的 Task Profile，并用 Compatibility 与 Suitability 进行可解释的数据集发现。

**完成门禁**：required 冲突不被高内容分抵消；正式分数与默认排序仅用于 `COMPATIBLE`；结果包含命中、冲突、UNKNOWN、evidence 和版本；真实 LLM 成功与失败路径；新旧工作台均独立可用。
