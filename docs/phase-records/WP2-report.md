# WP2 Report: Dataset Survey and Deterministic Inspection

## Governance Fields

```text
workPackageId: WP2
phase: Phase 2
status: BLOCKED_REAL_SAMPLE_COMPARISON_AND_MAIN_AGENT_WIRING
planPath: docs/phase-records/WP2-plan.md
verificationResults: see Verification Evidence
modelRunSummary: NOT_APPLICABLE_NO_MODEL_CALL
artifactHashes: see Actual Modified and Delivered Paths and artifact table
requirementSourceSha256: a2c4f4d2d53e7d1156f171b15f00def54f44b6ac89c761a9fae8eb0ee12dffa5
workPackageStatus: BLOCKED_REAL_SAMPLE_COMPARISON_AND_MAIN_AGENT_WIRING
verificationCommands: see Verification Evidence
workDirectory: /Users/yimingniu/Code/DataModelMatch
startedAt: 2026-09-09; exact time PENDING
finishedAt: PENDING
exitCode: 0_RECORDED; independent rerun PENDING
environmentVersion: uv 0.12.10; Python 3.9.6; exact environment fingerprint PENDING
realModelSummary: NOT_APPLICABLE_NO_MODEL_CALL
sanitizedEvidence: see Verification Evidence; managed sample evidence PENDING
riskItems: managed snapshot binding, five-category manual comparison, API/SSE/UI wiring, and independent acceptance missing
rollbackOrReopen: REOPEN_WP2_ON_SNAPSHOT_BOUNDARY_OR_FACT_ONLY_FAILURE; no rollback executed
approvedAt: PENDING
sourceRequirementIds: [SRC-04, SRC-05, SRC-08, SRC-16, SRC-19]
derivedRequirementIds: [DER-04, DER-05]
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
responsibleAgent: WP2 implementation agent
modelTier: Luna Medium
independentAcceptor: PENDING; not assigned
mainAgentReview: PENDING
```

## Current Result

The isolated WP2 Survey/Inspection implementation is available and its
focused synthetic tests were reported as passing. This report is not a Phase
2 sign-off. The mandatory managed-snapshot wiring, five-category real-sample
comparison, evidence artifacts, UI states, and independent acceptance are
missing, so the work package remains
`BLOCKED_REAL_SAMPLE_COMPARISON_AND_MAIN_AGENT_WIRING`.

## Actual Modified and Delivered Paths

```text
actualModifiedPaths:
  - src/datamodelmatch/semantic_survey.py
  - src/datamodelmatch/semantic_inspection.py
  - tests/test_semantic_survey.py
  - tests/test_semantic_inspection.py
  - docs/phase-records/WP2-plan.md
  - docs/phase-records/WP2-report.md
forbiddenPathChangesObserved: none reported; independent path audit: PENDING
generatedPaths: []
```

| artifact | version | sha256 | evidence state |
| --- | --- | --- | --- |
| `src/datamodelmatch/semantic_survey.py` | v1 | `f7aa6ac534b34007c7666a7cac68748d32a354815bed0ea506ab8fadb2060e18` | Present |
| `src/datamodelmatch/semantic_inspection.py` | v1 | `77eb267f99ed79496e43597d66c3576de1f3b08f8d1c529713eb7ee88425a17` | Present |
| `tests/test_semantic_survey.py` | current | `e47b69880a455ebf08f0497d0a4563aa5e3d32c5c07830419990a60be17cebf8` | Present |
| `tests/test_semantic_inspection.py` | current | `dd91f7efe6e9679b9d7263600305d4736b634d2b40f57cdaf85dfb67039f09c2` | Present |
| `docs/semantic-contracts/semantic-contract-rfc.md` | v1 | `037b0093ead76511ac2b12f2067f445e13041418f5917056121cc490b3298e98` | Input fingerprint |
| `docs/semantic-contracts/common.schema.json` | v1 | `38d3da804426a9ec49db08b0b939b5e580d5debd7f0389773f8ec167056131fe` | Input fingerprint |

## Interface Delivered

`survey_snapshot(root, limits)` returns a deterministic `DatasetSketch` with
relative paths, file-type distributions, candidate categories, skipped paths,
and structured warnings. `inspect_file(path, limits, snapshot_root)` returns
typed facts for image, video, table, JSON/JSONL, XML, and Parquet inputs.

The implementation rejects unsafe roots, symlinks, sensitive files, path
escapes, bounded-read violations, and XML external-entity constructs. It
returns controlled unsupported or failed facts when media metadata cannot be
established and does not produce open semantic claims.

## Verification Evidence

| command | exit code | observed result | time | environment |
| --- | ---: | --- | --- | --- |
| `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src uv run --no-project --with pytest --with pyarrow pytest -q tests/test_semantic_survey.py tests/test_semantic_inspection.py` | 0 | `9 passed` | `2026-09-09; exact time PENDING` | `uv 0.12.10`, Python `3.9.6`, pyarrow via uv |
| `git diff --check` | 0 | passed as previously recorded | `2026-09-09; exact time PENDING` | repository worktree |

No LLM/VLM/API call, dataset code execution, or real managed-dataset scan is
claimed by this report.

## Acceptance Matrix

| requirement/evidence | current state | authoritative evidence or gap |
| --- | --- | --- |
| Bounded deterministic survey/inspection behavior | SATISFIED AT SUBMODULE LEVEL | Focused synthetic tests; independent rerun/signature PENDING |
| Safe path, sensitive-file, symlink, and unsupported-media handling | PARTIAL | Synthetic coverage recorded; managed snapshot integration PENDING |
| Fixed `resolvedRevision` and evidence binding | BLOCKED | No main Agent snapshot/job wiring evidence |
| Manual comparison for classification, detection, tracking, segmentation, video | BLOCKED | No approved sample manifest, field-level manual records, or evidence hashes |
| Profile job `survey`/`inspection` events and API/UI warnings | BLOCKED | WP1/main Agent/WP7 integration not completed |
| Legacy import and static Profile regression | PENDING | No independent integrated regression record |
| Independent acceptance and signature | PENDING | Acceptor, environment digest, evidence archive, and approval time absent |

## Handoff and Main-Agent Actions

1. Bind the module to a managed snapshot root and immutable
   `resolvedRevision`.
2. Freeze and use an approved de-identified sample manifest covering
   classification, detection, tracking, segmentation, and video; perform
   field-level manual comparison and retain evidence locators/hashes.
3. Emit survey/inspection events and evidence through the WP1 job runtime,
   preserving controlled warnings and cancellation limits.
4. Add UI states through WP7 and verify desktop/mobile behavior.
5. Independently rerun all commands and replace `PENDING` fields only with
   signed evidence.

## Failure and Rollback

Unsupported, corrupt, sensitive, or over-limit inputs must remain explicit
controlled outcomes. If a scan escapes the managed snapshot or invents an
open semantic field, reject the result and stop integration; do not mutate the
source snapshot or silently replace unknown values.
