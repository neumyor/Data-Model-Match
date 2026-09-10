# Phase 4 代表性视觉采样 真实 VLM 与聚合执行记录

## Governance Fields

```text
phaseId: PHASE-4
status: PLANNED
requirementSourceSha256: a2c4f4d2d53e7d1156f171b15f00def54f44b6ac89c761a9fae8eb0ee12dffa5
inputArtifacts: WP0 accepted contracts; WP2 accepted Survey facts; approved version-locked decoder; approved VLM configuration
codeRevision: PENDING_FROZEN_BASELINE
workPackageStatus: WP4=PLANNED
responsibleAgent: WP4_OWNER
independentAcceptor: UNASSIGNED_INDEPENDENT_ACCEPTOR
verificationCommands: pytest tests/test_semantic_sampling.py tests/test_semantic_vision.py tests/test_semantic_aggregation.py; real VLM test entrypoint; Phase 4 integration acceptance
workDirectory: /Users/yimingniu/Code/DataModelMatch
startedAt: PENDING_AFTER_FROZEN_BASELINE
finishedAt: PENDING
exitCode: PENDING
environmentVersion: PENDING_CAPTURED_AT_EXECUTION
configurationFingerprint: PENDING_REDACTED
realModelSummary: PENDING_REAL_VLM_SUCCESS_AND_FAILURE_EVIDENCE
sanitizedEvidence: .datamodelmatch/phase-4-evidence/<run-id>/
riskItems: decoder drift; content-hash validation; sample coverage loss; VLM budget; external-media approval; video temporal provenance
blockers: Phase 0 not frozen; WP2 not accepted; decoder and production runner not approved; no independent acceptor
rollbackOrReopen: reopen on unsafe media handling, invalid SampleRef provenance, aggregation inflation, or VLM policy failure
approvedAt: PENDING
```

**目标**：产生有固定 SampleRef、覆盖说明、受控 VLM observation 与保守 dataset-level aggregation 的内容语义 artifact。

**完成门禁**：图像、视频/序列和视觉主导多模态真实样本；`frames_only` 视频传输；成功、空候选、损坏媒体、超时、格式异常、部分样本失败；单样本不得升级为 `SUPPORTED`；真实 VLM 验证；WP7 完成样本与聚合 UI 验收后才可为 `PASSED`。
