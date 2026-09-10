# Phase 7 Benchmark 稳健性 消融与最终 UI 回归执行记录

## Governance Fields

```text
phaseId: PHASE-7
status: PLANNED
requirementSourceSha256: a2c4f4d2d53e7d1156f171b15f00def54f44b6ac89c761a9fae8eb0ee12dffa5
inputArtifacts: final approved benchmark manifest; Ground Truth; perturbations; threshold manifest; integrated WP2 through WP7 capabilities
codeRevision: PENDING_FROZEN_BASELINE
workPackageStatus: WP8=PLANNED; WP7=INTEGRATED_REQUIRED
responsibleAgent: WP8_OWNER
independentAcceptor: UNASSIGNED_INDEPENDENT_ACCEPTOR
verificationCommands: benchmark validator; all focused suites; web build; browser screenshot suite; real LLM/VLM acceptance; Phase 7 reproducibility run
workDirectory: /Users/yimingniu/Code/DataModelMatch
startedAt: PENDING_AFTER_INTEGRATED_PRODUCT
finishedAt: PENDING
exitCode: PENDING
environmentVersion: PENDING_CAPTURED_AT_EXECUTION
configurationFingerprint: PENDING_REDACTED
realModelSummary: PENDING_REAL_LLM_AND_VLM_SUCCESS_AND_FAILURE_EVIDENCE
sanitizedEvidence: .datamodelmatch/semantic-benchmark/<run-id>/; .datamodelmatch/ui-acceptance/<run-id>/
riskItems: dataset identity leakage; unverified license/revision; post-result threshold changes; unpinned browser artifacts; non-repeatable model results
blockers: real manifest absent; final thresholds absent; product not integrated; browser harness or baselines absent; no independent acceptor
rollbackOrReopen: reopen on benchmark provenance failure, threshold governance breach, named-adapter finding, UI regression, or RQ conclusion without evidence
approvedAt: PENDING
```

**目标**：以真实、匿名化且可复现的 benchmark 验证结构理解、少样本内容、检索和双层分解，并完成所有用户可见流程回归。

**完成门禁**：15–30 数据集、4–6 任务族、50–100 查询；所有扰动、五项消融与两条研究基线；RQ1–RQ4 预注册阈值与重复/置信规则；真实模型、API、UI 截图和全量回归均通过。
