# Phase 3 结构语义理解执行记录

## Governance Fields

```text
phaseId: PHASE-3
status: PLANNED
requirementSourceSha256: a2c4f4d2d53e7d1156f171b15f00def54f44b6ac89c761a9fae8eb0ee12dffa5
inputArtifacts: WP0 accepted contracts; WP2 accepted survey and inspection artifacts
codeRevision: PENDING_FROZEN_BASELINE
workPackageStatus: WP3=PLANNED
responsibleAgent: WP3_OWNER
independentAcceptor: UNASSIGNED_INDEPENDENT_ACCEPTOR
verificationCommands: pytest tests/test_semantic_structural.py; real LLM test entrypoint; Phase 3 integration acceptance
workDirectory: /Users/yimingniu/Code/DataModelMatch
startedAt: PENDING_AFTER_FROZEN_BASELINE
finishedAt: PENDING
exitCode: PENDING
environmentVersion: PENDING_CAPTURED_AT_EXECUTION
configurationFingerprint: PENDING_REDACTED
realModelSummary: PENDING_REAL_LLM_SUCCESS_AND_FAILURE_EVIDENCE
sanitizedEvidence: .datamodelmatch/phase-3-evidence/<run-id>/
riskItems: model protocol drift; unbounded inspection loop; deterministic-fact hallucination; missing WP7 UI evidence
blockers: Phase 0 not frozen; WP2 not accepted; no independent acceptor
rollbackOrReopen: reopen on contract drift, invalid inspection request, deterministic-fact invention, or evidence-reference failure
approvedAt: PENDING
```

**目标**：从固定快照的 Survey、inspection facts 和受限文档片段推断保守的结构语义，不生成内容语义或发布完整 Profile。

**完成门禁**：有限 allowlist inspection loop；detection/tracking/segmentation 的正确、UNKNOWN、冲突路径；真实 LLM 的成功、超时、空响应、格式异常和无效工具请求；所有结构 claim 可追溯；WP7 完成字段、证据和 UNKNOWN 的 UI 验收后才可为 `PASSED`。
