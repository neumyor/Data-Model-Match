# Phase 5 语义融合 证据与审阅体验执行记录

## Governance Fields

```text
phaseId: PHASE-5
status: PLANNED
requirementSourceSha256: a2c4f4d2d53e7d1156f171b15f00def54f44b6ac89c761a9fae8eb0ee12dffa5
inputArtifacts: WP0 contracts; WP1 store; WP3 structural artifacts; WP4 aggregation artifacts, all ACCEPTED at fixed revisions
codeRevision: PENDING_FROZEN_BASELINE
workPackageStatus: WP5=PLANNED
responsibleAgent: WP5_OWNER
independentAcceptor: UNASSIGNED_INDEPENDENT_ACCEPTOR
verificationCommands: pytest tests/test_semantic_evidence.py tests/test_semantic_fusion.py; Phase 5 API and UI acceptance
workDirectory: /Users/yimingniu/Code/DataModelMatch
startedAt: PENDING_AFTER_FROZEN_BASELINE
finishedAt: PENDING
exitCode: PENDING
environmentVersion: PENDING_CAPTURED_AT_EXECUTION
configurationFingerprint: PENDING_REDACTED
realModelSummary: PENDING_DEPENDENCY_MODEL_EVIDENCE_REFERENCE
sanitizedEvidence: .datamodelmatch/phase-5-evidence/<run-id>/
riskItems: dangling evidence references; hidden conflicts; invalid status escalation; stale snapshot publication; inaccessible long evidence
blockers: upstream artifacts not accepted; Phase 0 not frozen; WP7 not integrated; no independent acceptor
rollbackOrReopen: reopen on evidence traversal failure, conflict suppression, invalid UNKNOWN reason, or stale-artifact publication
approvedAt: PENDING
```

**目标**：融合文档、确定性事实、结构解释和视觉聚合，生成可审计的完整 `DatasetSemanticProfile`。

**完成门禁**：每个关键 claim 可导航到固定 revision 的 evidence；冲突和 UNKNOWN 不得隐藏；无媒体或不支持媒体可产生结构 Profile 但内容保持 UNKNOWN；详情页四个固定审阅区域在桌面与移动端通过验收。
