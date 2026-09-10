# WP1 Plan: Semantic Artifact and Profile Job Foundation

## Governance Fields

```text
workPackageId: WP1
phase: Phase 1
status: PENDING_MAIN_AGENT_ACCEPTANCE
requirementSourceSha256: a2c4f4d2d53e7d1156f171b15f00def54f44b6ac89c761a9fae8eb0ee12dffa5
workPackageStatus: PENDING_MAIN_AGENT_ACCEPTANCE
verificationCommands: see Verification Commands
workDirectory: /Users/yimingniu/Code/DataModelMatch
startedAt: PENDING_NOT_RECORDED
finishedAt: PENDING
exitCode: PENDING
environmentVersion: uv 0.12.10; Python 3.9.6; exact environment fingerprint PENDING
realModelSummary: NOT_APPLICABLE_NO_MODEL_CALL
sanitizedEvidence: PENDING; focused evidence is recorded in WP1-report.md
riskItems: P0.1 runtime not implemented in isolated package; shared wiring and UI acceptance missing
rollbackOrReopen: REOPEN_WP1_ON_CONTRACT_HASH_OR_PATH_OWNERSHIP_DRIFT; no rollback executed
approvedAt: PENDING
goal: Provide an isolated durable foundation for versioned DatasetSemanticProfile artifacts and profile-job lifecycle records.
nonGoals: ResourceStore wiring, legacy catalog mutation, CLI/HTTP/SSE/UI exposure, semantic analysis, VLM/LLM calls, and task matching.
sourceRequirementIds: [SRC-06, SRC-07, SRC-16, SRC-19]
derivedRequirementIds: [DER-01, DER-02, DER-04, DER-05]
inputArtifacts: see Input Artifacts
outputArtifacts: see Output Artifacts
dependencies: see Dependencies
ownedPaths: see Ownership and Isolation
readOnlyPaths: see Ownership and Isolation
generatedPaths: []
forbiddenPaths: see Ownership and Isolation
baseRevision: 3ab448b5c3449f4d14287076cc187591f2f8aa92
responsibleAgent: WP1 implementation agent
modelTier: Terra Medium
independentAcceptor: PENDING_UNASSIGNED
approvalStatus: PENDING
verificationCommands: see Verification Commands
acceptanceDeliverables: see Acceptance Deliverables
failureAndRollback: see Failure and Rollback
handoffConsumer: Main Agent; later profile builder, HTTP/SSE adapter, and WP7 UI
```

## Goal and Scope

WP1 implements the independent durable foundation consumed by later
structural, sampling, fusion, API, and UI work. It persists version 1
`DatasetSemanticProfile` artifacts and profile-job lifecycle records below the
existing ignored `ResourceStore.root`, without changing `ResourceStore`,
legacy resource records, legacy `DatasetProfile`, CLI, HTTP routes, SSE
transport, or web files.

This plan describes the isolated work package. Passing its focused tests does
not prove Phase 1 product completion; shared-path wiring and the UI states in
the phase acceptance document remain separate gates.

## Non-goals

- No HTTP/SSE endpoint, CLI command, or UI wiring.
- No LLM/VLM call, VLM configuration parsing, survey/inspection, fusion,
  aggregation, or match-job execution.
- No change to frozen public schemas, RFCs, runtime policy, or legacy resource
  records.
- No claim that the isolated store implements the complete P0.1 worker lease,
  retry, recovery, retention, or SSE transport runtime.

## Input Artifacts

| path | version | sha256 | role |
| --- | --- | --- | --- |
| `docs/semantic-contracts/contract-manifest.json` | 1 | `5a21d7dfafb8909307067b7f103937d5ecbbcbcd481d9cf355a868f4bcba4ed5` | Contract catalog |
| `docs/semantic-contracts/semantic-contract-rfc.md` | v1 | `037b0093ead76511ac2b12f2067f445e13041418f5917056121cc490b3298e98` | Public API and migration rules |
| `docs/semantic-contracts/profile-job.schema.json` | v1 | `4aee0befc7732e78f89248f5933cbbcfa8b0a9ad95b363cd2187d1128ae9de81` | Profile job contract |
| `docs/semantic-contracts/dataset-semantic-profile.schema.json` | v1 | `8b3b1a9893bc253fa5b6263b31edcec623665318a6d47e5e0e598fc7a62bc288` | Profile artifact contract |
| `docs/semantic-contracts/common.schema.json` | v1 | `38d3da804426a9ec49db08b0b939b5e580d5debd7f0389773f8ec167056131fe` | Shared IDs, statuses, evidence, and revisions |
| `docs/semantic-contracts/job-runtime-semantics-v1.json` | 1.0.0 | `9c16628857b0e2c402da5fba31ab0146487315615b2881421ecd0090dbab5adc` | P0.1 job runtime semantics |
| `src/datamodelmatch/resource_store.py` | current baseline input | `PENDING_HASH_CONFIRMATION_BY_MAIN_AGENT` | Read-only composition dependency |

## Output Artifacts

| path | version | sha256WhenAccepted | current evidence |
| --- | --- | --- | --- |
| `src/datamodelmatch/semantic_types.py` | v1 | `f880882c3081106a24c3cd575c8d13672504b5d347e5509d1e876653719094a6` | Present; isolated implementation |
| `src/datamodelmatch/semantic_store.py` | v1 | `3933ee750a51a4c3da12a377967f257c8ad25cf40af6789e48c2ae98f4400a17` | Present; isolated implementation |
| `tests/test_semantic_store.py` | current | `aba586f9bb5ab54cd412c11ce59d5d391dba57993ef2189ad6366884a0b5b8a6` | Focused tests present |
| `docs/phase-records/WP1-report.md` | governance record | `PENDING_AFTER_THIS_EDIT` | This execution report |

## Dependencies

- Phase 0 contract and runtime artifacts listed above must remain hash-stable.
- The caller must provide a valid existing `ResourceStore` and resource
  snapshot/revision lookup.
- Main Agent wiring is a downstream dependency for any product-level Phase 1
  acceptance.

## Ownership and Isolation

```text
ownedPaths:
  - src/datamodelmatch/semantic_types.py
  - src/datamodelmatch/semantic_store.py
  - tests/test_semantic_store.py
  - docs/phase-records/WP1-plan.md
  - docs/phase-records/WP1-report.md
readOnlyPaths:
  - src/datamodelmatch/resource_store.py
  - src/datamodelmatch/resource_types.py
  - docs/semantic-contracts/**
  - docs/dataset-management-ui-phased-acceptance.md
  - docs/semantic-requirements-ledger.md
generatedPaths: []
forbiddenPaths:
  - src/datamodelmatch/resource_store.py
  - src/datamodelmatch/resource_types.py
  - src/datamodelmatch/resource_cli.py
  - web/**
  - pyproject.toml
  - config.llm.json
  - _reference_only/**
  - tests/semantic_ui_acceptance/**
  - tests/semantic_contracts/**
  - docs/semantic-contracts/**
```

Runtime artifacts under the caller-owned `ResourceStore.root` are not
versioned outputs of this work package. The implementation must keep them
under `semantic-artifacts/v1/` and must not write the legacy `profiles/`
directory.

## Interface and Behavior

`semantic_types.py` defines closed frozen dataclasses and typed exceptions for
profile-job requests, jobs, errors, ordered events, and durable
`DatasetSemanticProfile` documents.

`semantic_store.py` provides:

```text
create_profile_job(request) -> SemanticJob
get_job(job_id) -> SemanticJob
start_job(job_id) -> SemanticJob
mark_partially_completed(job_id) -> SemanticJob
fail_job(job_id, error) -> SemanticJob
cancel_job(job_id) -> SemanticJob
publish_profile(job_id, profile) -> SemanticJob
get_published_profile(resource_id) -> DatasetSemanticProfile | None
get_profile_for_job(job_id) -> DatasetSemanticProfile | None
list_events(job_id, after_event_id=0) -> tuple[SemanticJobEvent, ...]
```

The canonical idempotency key is exactly
`(resourceId, snapshotRevision, profileSchemaVersion, configurationFingerprint)`.
Publication must recheck the current resolved revision and preserve the last
complete profile when a job fails, is cancelled, is partial, or is stale.

## Verification Commands

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  uv run --no-project --with pytest --with pyarrow \
  pytest -q tests/test_semantic_store.py
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  uv run --no-project --with pytest --with pyarrow \
  pytest -q tests/test_semantic_store.py tests/test_resource_store.py tests/test_compatibility.py
git diff --check
```

Verification must cover normal lifecycle, invalid transitions, canonical and
explicit idempotency, cancellation, stale revision winner behavior, failure
and partial publication protection, reload, event ordering, malformed
artifacts, path/symlink safety, and unchanged legacy files.

## Acceptance Deliverables

- Focused test output with command, exit code, code revision, environment,
  and artifact hashes.
- Independent review of the implementation diff and public method behavior.
- Main Agent wiring evidence for ResourceStore composition, CLI/HTTP/SSE
  translation, runtime error handling, and UI integration.
- Phase 1 execution record updated by the main Agent; until then the work
  package is not a signed product acceptance.

## Failure and Rollback

Any contract or persistence validation failure must fail closed without
overwriting a complete profile. The main Agent must stop integration if an
output hash changes, a forbidden path changes, or a public field/enum changes.
Rollback means excluding the isolated artifacts from composition and retaining
the unchanged legacy catalog and profile files; no destructive rollback of
user data is permitted.
