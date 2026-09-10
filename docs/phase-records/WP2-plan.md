# WP2 Plan: Dataset Survey and Deterministic Inspection

## Governance Fields

```text
workPackageId: WP2
phase: Phase 2
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
sanitizedEvidence: PENDING; synthetic evidence is recorded in WP2-report.md
riskItems: managed snapshot binding, five-category sample comparison, job evidence, UI wiring, and independent acceptance missing
rollbackOrReopen: REOPEN_WP2_ON_SNAPSHOT_BOUNDARY_OR_FACT_ONLY_FAILURE; no rollback executed
approvedAt: PENDING
goal: Produce a deterministic DatasetSketch and bounded fact-only inspection results for safe managed visual dataset snapshots.
nonGoals: Open semantic claims, dataset code execution, model calls, snapshot mutation, shared-path wiring, and dataset-name-specific adapters.
sourceRequirementIds: [SRC-04, SRC-05, SRC-08, SRC-16, SRC-19]
derivedRequirementIds: [DER-04, DER-05]
inputArtifacts: see Input Artifacts
outputArtifacts: see Output Artifacts
dependencies: see Dependencies
ownedPaths: see Ownership and Isolation
readOnlyPaths: see Ownership and Isolation
generatedPaths: []
forbiddenPaths: see Ownership and Isolation
baseRevision: 3ab448b5c3449f4d14287076cc187591f2f8aa92
responsibleAgent: WP2 implementation agent
modelTier: Luna Medium
independentAcceptor: PENDING_UNASSIGNED
approvalStatus: PENDING
verificationCommands: see Verification Commands
acceptanceDeliverables: see Acceptance Deliverables
failureAndRollback: see Failure and Rollback
handoffConsumer: Main Agent; WP3 structural analysis, WP4 sampling, and Phase 2 wiring
```

## Goal and Scope

For an already safe, managed raw visual dataset snapshot, produce a
deterministic `DatasetSketch` and bounded, fact-only inspection results for
image, video, CSV/table, JSON/JSONL, XML, and Parquet files. Every result must
be traceable to a safe relative path and the fixed snapshot supplied by the
caller.

WP2 is an isolated capability package. It is not Phase 2 product completion
until the main Agent binds it to managed resource snapshots, profile-job
events/evidence, UI states, and the required real-sample comparison.

## Non-goals

- No open semantic claims such as city, road, aerial, task, object category,
  environment, or scene.
- No LLM/VLM calls, dataset code execution, dependency installation, model
  weight access, or mutation of the snapshot.
- No changes to frozen contracts or shared ResourceStore/CLI/Web paths.
- No dataset-name-specific branches or adapters.

## Input Artifacts

| path | version | sha256 | role |
| --- | --- | --- | --- |
| `docs/semantic-contracts/semantic-contract-rfc.md` | v1 | `037b0093ead76511ac2b12f2067f445e13041418f5917056121cc490b3298e98` | Survey and inspection boundary |
| `docs/semantic-contracts/common.schema.json` | v1 | `38d3da804426a9ec49db08b0b939b5e580d5debd7f0389773f8ec167056131fe` | Evidence, path, and revision types |
| `docs/dataset-management-ui-phased-acceptance.md` | governance candidate | `PENDING_HASH_CONFIRMATION_BY_MAIN_AGENT` | Phase 2 limits and acceptance gates |
| `src/datamodelmatch/resource_store.py` | current baseline input | `PENDING_HASH_CONFIRMATION_BY_MAIN_AGENT` | Managed snapshot composition dependency |
| `src/datamodelmatch/resource_types.py` | current baseline input | `PENDING_HASH_CONFIRMATION_BY_MAIN_AGENT` | Resource/revision type dependency |

## Output Artifacts

| path | version | sha256WhenAccepted | current evidence |
| --- | --- | --- | --- |
| `src/datamodelmatch/semantic_survey.py` | v1 | `f7aa6ac534b34007c7666a7cac68748d32a354815bed0ea506ab8fadb2060e18` | Present; isolated implementation |
| `src/datamodelmatch/semantic_inspection.py` | v1 | `77eb267f99ed79496e43597d66c3576de1f3b08f8d1c529713eb7ee88425a17` | Present; isolated implementation |
| `tests/test_semantic_survey.py` | current | `e47b69880a455ebf08f0497d0a4563aa5e3d32c5c07830419990a60be17cebf8` | Focused tests present |
| `tests/test_semantic_inspection.py` | current | `dd91f7efe6e9679b9d7263600305d4736b634d2b40f57cdaf85dfb67039f09c2` | Focused tests present |
| `docs/phase-records/WP2-report.md` | governance record | `PENDING_AFTER_THIS_EDIT` | This execution report |

## Dependencies

- The caller must provide a managed snapshot root and fixed
  `resolvedRevision`; WP2 must not discover or mutate resources outside it.
- Phase 0 safety, contract, and path-boundary artifacts must be hash-stable.
- WP2 is the required upstream input for WP3 and WP4. WP3 is not a dependency
  of WP2.
- Product-level acceptance additionally depends on WP1 job wiring and WP7 UI
  integration, but those are downstream dependencies rather than WP2 module
  inputs.

## Ownership and Isolation

```text
ownedPaths:
  - src/datamodelmatch/semantic_survey.py
  - src/datamodelmatch/semantic_inspection.py
  - tests/test_semantic_survey.py
  - tests/test_semantic_inspection.py
  - docs/phase-records/WP2-plan.md
  - docs/phase-records/WP2-report.md
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

## Interface and Safety Rules

`semantic_survey.py` exposes explicit `SurveyLimits`, deterministic
`DatasetSketch`, `SkippedPath`, and `SurveyWarning` values. Survey limits cover
depth, file count, per-file bytes, total bytes, and representative paths.

`semantic_inspection.py` exposes explicit `InspectionLimits` and typed facts
for image, video, delimited table, JSON/JSONL, XML, and Parquet input.

Symlinks, sensitive files, unsafe relative paths, and out-of-root paths are
never followed or read. Corrupt or unsupported inputs return typed controlled
results. XML with `DOCTYPE` or `ENTITY` is rejected before parsing. Video
metadata that cannot be safely established remains `UNSUPPORTED` or
`INSPECTION_FAILED`; no value is guessed.

## Verification Commands

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  uv run --no-project --with pytest --with pyarrow \
  pytest -q tests/test_semantic_survey.py tests/test_semantic_inspection.py
git diff --check
```

Required fixture coverage includes missing documentation, renamed directories,
irrelevant files, corrupted annotations, bounded large files, sensitive files,
symlinks/path escape, image headers, unsupported/invalid video, CSV/TSV, JSON,
JSONL, XML/DOCTYPE, Parquet, deterministic repeatability, and absence of open
semantic fields.

## Acceptance Deliverables

- Focused test output with command, exit code, revision, environment, and
  output hashes.
- Real or approved representative sample fixtures covering classification,
  detection, tracking, segmentation, and video, with field-level manual
  comparison evidence. Current evidence is missing and therefore blocking.
- Main Agent wiring evidence showing snapshot binding, `survey`/`inspection`
  events, evidence artifacts, controlled API/UI warnings, and legacy workflow
  regression.
- Independent acceptance by an agent who did not implement this package.

## Failure and Rollback

On path, limit, parse, or media failure, return a diagnosable controlled
warning/fact and never infer a replacement value. If integration violates the
snapshot boundary or changes a public contract, stop integration and revert
only the unaccepted WP2 composition; do not delete or mutate the underlying
managed snapshot.
