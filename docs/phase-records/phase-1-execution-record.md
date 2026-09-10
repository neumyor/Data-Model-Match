# Phase 1 统一语义 Schema 与持久化执行记录

## Structured Record

```text
phaseId: PHASE-1
phase: Phase 1
status: BLOCKED_PENDING_SHARED_WIRING_UI_AND_INDEPENDENT_ACCEPTANCE
requirementSourceSha256: a2c4f4d2d53e7d1156f171b15f00def54f44b6ac89c761a9fae8eb0ee12dffa5
workPackageStatus: WP1=PENDING_MAIN_AGENT_WIRING_AND_INDEPENDENT_ACCEPTANCE
verificationCommands: see Verification Log
workDirectory: /Users/yimingniu/Code/DataModelMatch
startedAt: 2026-09-09; exact time PENDING
finishedAt: PENDING
exitCode: 0_RECORDED_SUBMODULE_COMMANDS; PHASE_GATE_PENDING
environmentVersion: uv 0.12.10; Python 3.9.6; exact environment fingerprint PENDING
realModelSummary: NOT_APPLICABLE_PHASE_1_NO_MODEL_CALL
sanitizedEvidence: see Verification Log; browser/UI evidence PENDING
riskItems: shared ResourceStore/HTTP/SSE wiring missing; P0.1 runtime integration missing; WP7 UI harness/evidence missing
rollbackOrReopen: REOPEN_PHASE_1_ON_CONTRACT_DRIFT_OR_LEGACY_REGRESSION; no rollback executed
approvedAt: PENDING
sourceRequirementIds: [SRC-06, SRC-07, SRC-16, SRC-19]
derivedRequirementIds: [DER-01, DER-02, DER-03, DER-04, DER-05]
inputArtifacts: see Entry Conditions and Frozen Inputs
outputArtifacts: see Output Artifacts
codeRevision: 3ab448b5c3449f4d14287076cc187591f2f8aa92
configurationFingerprint: PENDING
evidencePaths: see Verification Log
startTime: 2026-09-09; exact time PENDING
endTime: PENDING
blockers: see Blockers, Handoff, and Rollback
signoff: see Sign-off
baseRevision: 3ab448b5c3449f4d14287076cc187591f2f8aa92
responsibleAgent: Main Agent
independentAcceptor: PENDING; not assigned
approvalStatus: PENDING
approvalTime: PENDING
```

本记录对应
`docs/dataset-management-ui-phased-acceptance.md` 的 Phase 1。它只允许
使用 Phase 0 已冻结的契约、错误码、SSE 语义和迁移规则。当前记录区分
“独立后端能力已验证”和“产品接入门禁未完成”，不得将前者当作 Phase 1
通过。

## Entry Conditions and Frozen Inputs

| path | version | sha256 | state |
| --- | --- | --- | --- |
| `docs/semantic-contracts/contract-manifest.json` | 1 | `5a21d7dfafb8909307067b7f103937d5ecbbcbcd481d9cf355a868f4bcba4ed5` | Present |
| `docs/semantic-contracts/semantic-contract-rfc.md` | v1 | `037b0093ead76511ac2b12f2067f445e13041418f5917056121cc490b3298e98` | Present |
| `docs/semantic-contracts/profile-job.schema.json` | v1 | `4aee0befc7732e78f89248f5933cbbcfa8b0a9ad95b363cd2187d1128ae9de81` | Present |
| `docs/semantic-contracts/dataset-semantic-profile.schema.json` | v1 | `8b3b1a9893bc253fa5b6263b31edcec623665318a6d47e5e0e598fc7a62bc288` | Present |
| `docs/semantic-contracts/job-runtime-semantics-v1.json` | 1.0.0 | `9c16628857b0e2c402da5fba31ab0146487315615b2881421ecd0090dbab5adc` | Present |
| `docs/semantic-ui-acceptance/UI-ACCEPTANCE-SPEC.md` | Phase 0 contract | `14fd23630b6abc40627c561c16c340c7b34410f1941aea1c427c89a5e087f07d` | Present; no browser pass yet |
| `docs/semantic-ui-acceptance/dom-fixture-manifest.json` | 1 | `e6a5317a7f7ee7b430a2d14658c0bc2d384531185c77b22907c468beeda5d946` | Present; browser harness required |

## Work Packages and Ownership

| workPackageId | plan/report | owned implementation paths | status | current evidence |
| --- | --- | --- | --- | --- |
| WP1 | `WP1-plan.md` / `WP1-report.md` | `src/datamodelmatch/semantic_types.py`, `src/datamodelmatch/semantic_store.py`, `tests/test_semantic_store.py` | PENDING_MAIN_AGENT_WIRING_AND_INDEPENDENT_ACCEPTANCE | Isolated tests and hashes recorded in WP1 report |
| WP2 | `WP2-plan.md` / `WP2-report.md` | Phase 2 downstream; no Phase 1 implementation ownership | NOT_PHASE_1_SCOPE | WP2 report separately records its evidence |

Shared paths are reserved for the Main Agent:

```text
mainAgentOwnedPaths:
  - src/datamodelmatch/resource_store.py
  - src/datamodelmatch/resource_types.py
  - src/datamodelmatch/resource_cli.py
  - web/server.ts
  - web/app.js
  - web/index.html
  - web/styles.css
  - pyproject.toml
  - docs/phase-records/phase-1-execution-record.md
```

No child work package may modify these paths.

## Output Artifacts

| path | version | sha256 | state |
| --- | --- | --- | --- |
| `src/datamodelmatch/semantic_types.py` | v1 | `f880882c3081106a24c3cd575c8d13672504b5d347e5509d1e876653719094a6` | Isolated output |
| `src/datamodelmatch/semantic_store.py` | v1 | `3933ee750a51a4c3da12a377967f257c8ad25cf40af6789e48c2ae98f4400a17` | Isolated output |
| `tests/test_semantic_store.py` | current | `aba586f9bb5ab54cd412c11ce59d5d391dba57993ef2189ad6366884a0b5b8a6` | Focused evidence |
| `ResourceStore` composition/wiring | v1 | `PENDING` | Not implemented/evidenced |
| Phase 1 UI states and browser evidence | UI contract v1 | `PENDING` | WP7/harness not delivered |
| `docs/phase-records/phase-1-execution-record.md` | governance record | `PENDING_AFTER_THIS_EDIT` | Current record |

## Acceptance Matrix

| gate | owner | status | evidence / missing evidence |
| --- | --- | --- | --- |
| Profile/job artifacts separated from legacy `DatasetProfile` | WP1 + Main Agent | PARTIAL | WP1 isolated tests; integrated ResourceStore evidence PENDING |
| Required malformed/invalid/cross-resource/version/empty-evidence tests | WP1 + Main Agent | PARTIAL | WP1 focused evidence; independent rerun and complete contract matrix PENDING |
| Concurrent duplicate requests, old revision, cancellation | WP1 + Main Agent | PARTIAL | WP1 report records isolated coverage; runtime lease/recovery PENDING |
| Legacy import/list/detail/model compatibility regression | Main Agent | PENDING | No signed integrated regression record |
| ResourceStore, CLI, HTTP, SSE wiring | Main Agent | BLOCKED | No shared-path wiring evidence |
| Detail-page semantic entry and four required states | Main Agent/WP7 | BLOCKED | No browser harness, DOM, screenshots, or SSE evidence |
| Independent acceptance and signature | Independent acceptor | PENDING | Acceptor, run metadata, evidence hashes, and approval time absent |

## Verification Log

| command | exit code | result | timestamp | environment/config |
| --- | ---: | --- | --- | --- |
| `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src uv run --no-project --with pytest --with pyarrow pytest -q tests/test_semantic_store.py` | 0 | `10 passed` | `2026-09-09; exact time PENDING` | uv `0.12.10`, Python `3.9.6` |
| `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src uv run --no-project --with pytest --with pyarrow pytest -q tests/test_semantic_store.py tests/test_resource_store.py tests/test_compatibility.py` | 0 | `23 passed` | `2026-09-09; exact time PENDING` | same |
| UI browser acceptance | PENDING | Not run; absence blocks pass | PENDING | approved harness/browser/baselines not available |

## Blockers, Handoff, and Rollback

- Implement and independently verify P0.1 worker lease, retry, recovery,
  retention, crash reconciliation, cancellation/publication race, and SSE
  replay behavior before claiming product readiness.
- Wire the semantic store through ResourceStore, CLI, HTTP, SSE, and UI while
  preserving legacy APIs.
- Add the required UI fixture/browser evidence and independent review.
- If any public contract or legacy regression fails, stop Phase 1 and remove
  the new composition from the runtime; preserve all existing legacy
  artifacts. No rollback has been executed.

## Sign-off

```text
responsibleAgentSignoff: PENDING
independentAcceptorSignoff: PENDING
mainAgentIntegrationCommit: PENDING
environmentFingerprint: PENDING
evidenceBundleHash: PENDING
approvalTime: PENDING
conclusion: BLOCKED_PENDING_SHARED_WIRING_UI_AND_INDEPENDENT_ACCEPTANCE
```
