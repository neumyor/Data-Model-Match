# WP3 Plan: Isolated Structural Agent

## Governance Fields

```text
workPackageId: WP3
phase: Phase 3
status: PENDING_MAIN_AGENT_ACCEPTANCE
requirementSourceSha256: a2c4f4d2d53e7d1156f171b15f00def54f44b6ac89c761a9fae8eb0ee12dffa5
workPackageStatus: PENDING_MAIN_AGENT_ACCEPTANCE
verificationCommands: see Verification Commands
workDirectory: /Users/yimingniu/Code/DataModelMatch
startedAt: PENDING_NOT_RECORDED
finishedAt: PENDING
exitCode: PENDING
environmentVersion: uv 0.12.10; Python 3.9.6; exact environment fingerprint PENDING
realModelSummary: configured real LLM test required; execution evidence belongs to WP3-report.md and remains PENDING for independent acceptance
sanitizedEvidence: PENDING; no secret-bearing evidence included
riskItems: real-model reproducibility fingerprint, WP2 binding, fusion, runtime wiring, and independent acceptance incomplete
rollbackOrReopen: REOPEN_WP3_ON_MODEL_PROTOCOL_OR_EVIDENCE_BOUNDARY_FAILURE; no rollback executed
approvedAt: PENDING
goal: Infer conservative structural semantics from bounded WP2 facts and redacted documentation while preserving deterministic evidence boundaries.
nonGoals: Content/VLM analysis, profile publication, durable job wiring, shared API/UI changes, dataset code execution, and invented deterministic facts.
sourceRequirementIds: [SRC-04, SRC-05, SRC-07, SRC-09, SRC-16, SRC-19]
derivedRequirementIds: [DER-04, DER-05]
inputArtifacts: see Input Artifacts
outputArtifacts: see Output Artifacts
dependencies: see Dependencies
ownedPaths: see Ownership and Isolation
readOnlyPaths: see Ownership and Isolation
generatedPaths: []
forbiddenPaths: see Ownership and Isolation
baseRevision: 3ab448b5c3449f4d14287076cc187591f2f8aa92
responsibleAgent: WP3 implementation agent
modelTier: Terra Medium
independentAcceptor: PENDING_UNASSIGNED
approvalStatus: PENDING
verificationCommands: see Verification Commands
acceptanceDeliverables: see Acceptance Deliverables
failureAndRollback: see Failure and Rollback
handoffConsumer: Main Agent; WP5 fusion and profile-builder integration
```

## Goal and Scope

WP3 adds an isolated structural-analysis component that accepts only a
`DatasetSketch`, deterministic WP2 `InspectionFact` values, and bounded
redacted documentation excerpts. It produces closed structural-semantics
candidates, claim/evidence records, unresolved fields, and an auditable finite
inspection request list.

The model may classify the supplied evidence and request further allowlisted
inspection, but it must never invent deterministic facts. This work package
does not publish a profile or expose a user-facing route.

## Non-goals

- No VLM/content analysis, sample observation, aggregation, fusion, task
  matching, or profile publication.
- No modification to frozen schemas, persistence, ResourceStore, CLI, HTTP,
  SSE, UI, configuration, or `_reference_only`.
- No dataset-name branches, dataset code execution, unapproved file access,
  or raw prompt/model-response persistence.
- No claim that a successful real LLM call alone proves Phase 3 product
  acceptance.

## Input Artifacts

| path | version | sha256 | role |
| --- | --- | --- | --- |
| `docs/semantic-contracts/semantic-contract-rfc.md` | v1 | `037b0093ead76511ac2b12f2067f445e13041418f5917056121cc490b3298e98` | Structural protocol and evidence boundary |
| `docs/semantic-contracts/common.schema.json` | v1 | `38d3da804426a9ec49db08b0b939b5e580d5debd7f0389773f8ec167056131fe` | Closed types and evidence references |
| `docs/semantic-contracts/job-runtime-semantics-v1.json` | 1.0.0 | `9c16628857b0e2c402da5fba31ab0146487315615b2881421ecd0090dbab5adc` | Failure/retry boundary for later runtime |
| `src/datamodelmatch/semantic_survey.py` | v1 | `f7aa6ac534b34007c7666a7cac68748d32a354815bed0ea506ab8fadb2060e18` | WP2 sketch producer |
| `src/datamodelmatch/semantic_inspection.py` | v1 | `77eb267f99ed79496e43597d66c3576de1f3b08f8d1c529713eb7ee88425a17` | WP2 fact producer |
| `config.llm.json` | local ignored configuration | `REDACTED; hash not recorded to avoid credential fingerprint publication` | Required only for opt-in real LLM test |

## Output Artifacts

| path | version | sha256WhenAccepted | current evidence |
| --- | --- | --- | --- |
| `src/datamodelmatch/semantic_structural.py` | v1 | `4738f1635443bb8046efcb8cae3580c801efe57077a43f1b578e93798c7a7ea2` | Present; isolated implementation |
| `tests/test_semantic_structural.py` | current | `61d2c81965c4b0716c0c01f60dcc145b25d0603666991d25ce4052d828a06370` | Focused tests present |
| `docs/phase-records/WP3-report.md` | governance record | `PENDING_AFTER_THIS_EDIT` | This execution report |

## Dependencies

- WP2 `DatasetSketch` and deterministic inspection facts are required input.
- Documentation excerpts must be bounded, path-safe, redacted, and supplied by
  the caller; WP3 cannot read arbitrary documentation itself.
- The root `config.llm.json` is required for an actual text-model test, but
  its secret fields must never be copied into artifacts or logs.
- Main Agent wiring and WP5 validation are downstream dependencies for product
  acceptance.

## Ownership and Isolation

```text
ownedPaths:
  - src/datamodelmatch/semantic_structural.py
  - tests/test_semantic_structural.py
  - docs/phase-records/WP3-plan.md
  - docs/phase-records/WP3-report.md
readOnlyPaths:
  - src/datamodelmatch/semantic_survey.py
  - src/datamodelmatch/semantic_inspection.py
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
  - tests/semantic_contracts/**
  - tests/semantic_ui_acceptance/**
  - docs/semantic-contracts/**
```

## Interface and LLM Protocol

`StructuralAnalysisInput` contains a fixed snapshot revision, one WP2 sketch,
bounded inspection facts, bounded documentation excerpts, explicit initial
fact IDs, and a caller-provided `StructuralInspectionExecutor`.

`StructuralAnalysisResult` contains closed structural candidate fields, claims,
evidence, unresolved fields, accepted requests, warnings, model metadata, and
call count. A positive candidate must cite evidence. A `VERIFIED` claim
requires an inspection or documentation evidence record; insufficient or
contradictory evidence produces explicit `UNKNOWN` results.

The model receives a bounded redacted JSON projection and may return only
`final` or an allowlisted `inspect_file` request. The default extra-inspection
budget is two and the absolute maximum is four. Prompts, raw responses, API
keys, and authorization headers must not appear in results, errors, logs, or
reports.

## Verification Commands

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  uv run --no-project --with pytest --with pyarrow \
  pytest -q tests/test_semantic_structural.py
RUN_REAL_LLM_TESTS=1 PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src \
  uv run --no-project --with pytest --with pyarrow \
  pytest -q tests/test_semantic_structural.py -m real_llm
python3 -m py_compile src/datamodelmatch/semantic_structural.py
git check-ignore -q config.llm.json
git diff --check
```

The real-model gate must record a sanitized success and controlled timeout or
failure, model/configuration fingerprints without secrets, and exit codes. A
missing or invalid configuration is `BLOCKED`, not a pass.

## Acceptance Deliverables

- Focused and real-model verification output tied to a revision and hashes.
- Independent review of evidence-reference validation, redaction, bounded
  tool requests, conflict handling, and failure behavior.
- Main Agent wiring evidence binding WP2 facts to the profile job and
  preserving evidence/unresolved fields through fusion.
- WP5 integration evidence and Phase 3 execution record update.

## Failure and Rollback

Malformed or unsafe model output must produce a controlled failure or explicit
unknown result, never a guessed structural fact. A failed analysis must contain
no publishable candidate or claims. If the model contract, configuration
boundary, or path allowlist changes, stop acceptance and return to the frozen
input revision; do not expose raw prompts or responses while diagnosing.
