# WP1 Report: Semantic Artifact and Profile Job Foundation

## Governance Fields

```text
workPackageId: WP1
phase: Phase 1
status: PENDING_MAIN_AGENT_WIRING_AND_INDEPENDENT_ACCEPTANCE
planPath: docs/phase-records/WP1-plan.md
verificationResults: see Verification Evidence
modelRunSummary: NOT_APPLICABLE_NO_MODEL_CALL
artifactHashes: see Actual Modified and Delivered Paths and artifact table
requirementSourceSha256: a2c4f4d2d53e7d1156f171b15f00def54f44b6ac89c761a9fae8eb0ee12dffa5
workPackageStatus: PENDING_MAIN_AGENT_WIRING_AND_INDEPENDENT_ACCEPTANCE
verificationCommands: see Verification Evidence
workDirectory: /Users/yimingniu/Code/DataModelMatch
startedAt: 2026-09-09; exact time PENDING
finishedAt: PENDING
exitCode: 0_RECORDED; independent rerun PENDING
environmentVersion: uv 0.12.10; Python 3.9.6; exact environment fingerprint PENDING
realModelSummary: NOT_APPLICABLE_NO_MODEL_CALL
sanitizedEvidence: see Verification Evidence; no secrets or model output
riskItems: P0.1 runtime, shared wiring, UI states, and independent acceptance remain incomplete
rollbackOrReopen: REOPEN_WP1_ON_CONTRACT_OR_LEGACY_REGRESSION; no rollback executed
approvedAt: PENDING
sourceRequirementIds: [SRC-06, SRC-07, SRC-16, SRC-19]
derivedRequirementIds: [DER-01, DER-02, DER-04, DER-05]
inputArtifacts: see Actual Modified and Delivered Paths and artifact table
outputArtifacts: see Actual Modified and Delivered Paths and artifact table
actualModifiedPaths: see Actual Modified and Delivered Paths
verificationCommands: see Verification Evidence
evidencePaths: see Verification Evidence
realModelSummary: not applicable; no model call
uncoveredItems: see Acceptance Matrix
approvalStatus: PENDING
approvalTime: PENDING
plannedBaseRevision: 3ab448b5c3449f4d14287076cc187591f2f8aa92
actualRevision: 3ab448b5c3449f4d14287076cc187591f2f8aa92
responsibleAgent: WP1 implementation agent
modelTier: Terra Medium
independentAcceptor: PENDING; not assigned
mainAgentReview: PENDING
```

## Current Result

The isolated WP1 implementation was reported as completed on 2026-09-09.
This is a work-package handoff only, not a Phase 1 sign-off. The main Agent
has not yet supplied evidence for shared ResourceStore composition, HTTP/CLI
translation, SSE replay/runtime semantics, or WP7 UI states; those gaps keep
the report in `PENDING_MAIN_AGENT_WIRING_AND_INDEPENDENT_ACCEPTANCE`.

## Actual Modified and Delivered Paths

```text
actualModifiedPaths:
  - src/datamodelmatch/semantic_types.py
  - src/datamodelmatch/semantic_store.py
  - tests/test_semantic_store.py
  - docs/phase-records/WP1-plan.md
  - docs/phase-records/WP1-report.md
forbiddenPathChangesObserved: none reported; independent path audit: PENDING
generatedPaths: []
```

| artifact | version | sha256 | evidence state |
| --- | --- | --- | --- |
| `src/datamodelmatch/semantic_types.py` | v1 | `f880882c3081106a24c3cd575c8d13672504b5d347e5509d1e876653719094a6` | Present |
| `src/datamodelmatch/semantic_store.py` | v1 | `3933ee750a51a4c3da12a377967f257c8ad25cf40af6789e48c2ae98f4400a17` | Present |
| `tests/test_semantic_store.py` | current | `aba586f9bb5ab54cd412c11ce59d5d391dba57993ef2189ad6366884a0b5b8a6` | Present |
| `docs/semantic-contracts/profile-job.schema.json` | v1 | `4aee0befc7732e78f89248f5933cbbcfa8b0a9ad95b363cd2187d1128ae9de81` | Input fingerprint |
| `docs/semantic-contracts/dataset-semantic-profile.schema.json` | v1 | `8b3b1a9893bc253fa5b6263b31edcec623665318a6d47e5e0e598fc7a62bc288` | Input fingerprint |
| `docs/semantic-contracts/job-runtime-semantics-v1.json` | 1.0.0 | `9c16628857b0e2c402da5fba31ab0146487315615b2881421ecd0090dbab5adc` | Input fingerprint |

## Interface Delivered

`SemanticArtifactStore(resource_store)` provides durable profile jobs,
canonical/explicit idempotency, lifecycle transitions, ordered event records,
profile reads, and atomic publication. Profiles are stored below
`<ResourceStore.root>/semantic-artifacts/v1/` and do not use the legacy
`profiles/` directory.

The implementation validates resource ID, snapshot revision, schema version,
configuration fingerprint, profile bindings, event order, safe paths, and
stale revision winner behavior. Partial, failed, and cancelled jobs do not
obtain or replace a complete profile.

## Verification Evidence

| command | exit code | observed result | time | environment |
| --- | ---: | --- | --- | --- |
| `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src uv run --no-project --with pytest --with pyarrow pytest -q tests/test_semantic_store.py` | 0 | `10 passed` | `2026-09-09; exact time PENDING` | `uv 0.12.10`, Python `3.9.6`, pyarrow via uv |
| `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src uv run --no-project --with pytest --with pyarrow pytest -q tests/test_semantic_store.py tests/test_resource_store.py tests/test_compatibility.py` | 0 | `23 passed` | `2026-09-09; exact time PENDING` | same environment |
| `git diff --check` | 0 | passed as previously recorded | `2026-09-09; exact time PENDING` | repository worktree |

No LLM/VLM call applies to this isolated package. No real-model evidence is
claimed here.

## Acceptance Matrix

| requirement/evidence | current state | authoritative evidence or gap |
| --- | --- | --- |
| Isolated persistence and lifecycle | SATISFIED AT SUBMODULE LEVEL | Focused tests above; independent rerun/signature PENDING |
| Legacy catalog/profile non-regression | PARTIAL | Regression command recorded; main Agent review and before/after artifact hashes PENDING |
| P0.1 worker lease/retry/recovery/retention | BLOCKED | Not implemented by isolated WP1; main Agent runtime work required |
| ResourceStore/CLI/HTTP/SSE wiring | BLOCKED | No shared-path integration evidence |
| Dataset detail UI states | BLOCKED | WP7 browser/UI evidence absent |
| Independent acceptance and signature | PENDING | Acceptor, run timestamp, environment digest, and approval time absent |

## Handoff and Main-Agent Actions

1. Review the diff independently and verify the exact owned-path set.
2. Instantiate and wire `SemanticArtifactStore` without changing legacy API
   semantics.
3. Implement the P0.1 durable worker/runtime behavior and map typed errors to
   the frozen envelope and SSE protocol.
4. Add WP7 UI states and run Phase 1 integration, legacy regression, and
   browser acceptance.
5. Replace `PENDING` fields with signed evidence only after independent
   reruns.

## Failure and Rollback

If any contract, path, or persistence check fails, do not publish a profile or
overwrite the last complete profile. Integration can be rolled back by
removing the semantic store from composition while retaining legacy catalog
and profile artifacts. No destructive data rollback was executed or claimed.
