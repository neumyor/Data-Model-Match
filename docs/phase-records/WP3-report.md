# WP3 Report: Isolated Structural Agent

## Governance Fields

```text
workPackageId: WP3
phase: Phase 3
status: PENDING_INDEPENDENT_ACCEPTANCE_AND_MAIN_AGENT_WIRING
planPath: docs/phase-records/WP3-plan.md
verificationResults: see Verification Evidence
modelRunSummary: see Verification Evidence; sanitized real LLM success and timeout previously recorded
artifactHashes: see Actual Modified and Delivered Paths and artifact table
requirementSourceSha256: a2c4f4d2d53e7d1156f171b15f00def54f44b6ac89c761a9fae8eb0ee12dffa5
workPackageStatus: PENDING_INDEPENDENT_ACCEPTANCE_AND_MAIN_AGENT_WIRING
verificationCommands: see Verification Evidence
workDirectory: /Users/yimingniu/Code/DataModelMatch
startedAt: 2026-09-09; exact time PENDING
finishedAt: PENDING
exitCode: 0_RECORDED; independent rerun PENDING
environmentVersion: uv 0.12.10; Python 3.9.6; exact environment fingerprint PENDING
realModelSummary: glm-5.3-flash success and controlled timeout previously recorded; sanitized request/config fingerprint PENDING
sanitizedEvidence: see Verification Evidence; no credentials or full prompt/response
riskItems: independent real-model rerun, WP2 snapshot binding, fusion, runtime wiring, and UI acceptance incomplete
rollbackOrReopen: REOPEN_WP3_ON_MODEL_PROTOCOL_OR_EVIDENCE_BOUNDARY_FAILURE; no rollback executed
approvedAt: PENDING
sourceRequirementIds: [SRC-04, SRC-05, SRC-07, SRC-09, SRC-16, SRC-19]
derivedRequirementIds: [DER-04, DER-05]
inputArtifacts: see Actual Modified and Delivered Paths and artifact table
outputArtifacts: see Actual Modified and Delivered Paths and artifact table
actualModifiedPaths: see Actual Modified and Delivered Paths
verificationCommands: see Verification Evidence
evidencePaths: see Verification Evidence
realModelSummary: see Verification Evidence; sanitized only
uncoveredItems: see Acceptance Matrix
approvalStatus: PENDING
approvalTime: PENDING
plannedBaseRevision: 3ab448b5c3449f4d14287076cc187591f2f8aa92
actualRevision: 3ab448b5c3449f4d14287076cc187591f2f8aa92
responsibleAgent: WP3 implementation agent
modelTier: Terra Medium
independentAcceptor: PENDING; not assigned
mainAgentReview: PENDING
```

## Current Result

The isolated WP3 structural-analysis implementation was reported as complete
on 2026-09-09. This is a work-package handoff, not a Phase 3 product
sign-off. Main Agent wiring, evidence-preserving fusion, and independent
acceptance remain outstanding.

The real text-model evidence below proves only that the bounded isolated
client path can make one configured request and handle a controlled timeout.
It does not prove production job retry/recovery, managed-snapshot integration,
or user-visible delivery.

## Actual Modified and Delivered Paths

```text
actualModifiedPaths:
  - src/datamodelmatch/semantic_structural.py
  - tests/test_semantic_structural.py
  - docs/phase-records/WP3-plan.md
  - docs/phase-records/WP3-report.md
forbiddenPathChangesObserved: none reported; independent path audit: PENDING
generatedPaths: []
```

| artifact | version | sha256 | evidence state |
| --- | --- | --- | --- |
| `src/datamodelmatch/semantic_structural.py` | v1 | `4738f1635443bb8046efcb8cae3580c801efe57077a43f1b578e93798c7a7ea2` | Present |
| `tests/test_semantic_structural.py` | current | `61d2c81965c4b0716c0c01f60dcc145b25d0603666991d25ce4052d828a06370` | Present |
| `src/datamodelmatch/semantic_survey.py` | v1 | `f7aa6ac534b34007c7666a7cac68748d32a354815bed0ea506ab8fadb2060e18` | WP2 input |
| `src/datamodelmatch/semantic_inspection.py` | v1 | `77eb267f99ed79496e43597d66c3576de1f3b08f8d1c529713eb7ee88425a17` | WP2 input |
| `docs/semantic-contracts/semantic-contract-rfc.md` | v1 | `037b0093ead76511ac2b12f2067f445e13041418f5917056121cc490b3298e98` | Input fingerprint |
| `docs/semantic-contracts/common.schema.json` | v1 | `38d3da804426a9ec49db08b0b939b5e580d5debd7f0389773f8ec167056131fe` | Input fingerprint |

## Interface Delivered

`StructuralAnalysisInput` accepts a fixed snapshot revision, one WP2
`DatasetSketch`, deterministic WP2 facts, bounded documentation excerpts,
initial fact IDs, and a caller-provided allowlisted inspection executor.

`StructuralAnalysisResult` returns closed structural fields, claims, evidence,
unresolved fields, accepted inspection requests, warnings, model metadata, and
call count. Positive claims require evidence. Insufficient or contradictory
evidence becomes explicit `UNKNOWN`; failed analysis returns no publishable
candidate or claims.

The JSON protocol permits only `final` or an allowlisted `inspect_file`
request. The default extra-inspection budget is two and the absolute maximum
is four. Raw prompts, raw model responses, API keys, and authorization headers
are not retained or emitted.

## Verification Evidence

| command | exit code | observed result | time | environment |
| --- | ---: | --- | --- | --- |
| `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src uv run --no-project --with pytest --with pyarrow pytest -q tests/test_semantic_structural.py` | 0 | `6 passed, 1 skipped, 3 subtests passed` | `2026-09-09; exact time PENDING` | `uv 0.12.10`, Python `3.9.6`, pyarrow via uv |
| `RUN_REAL_LLM_TESTS=1 ... pytest -q tests/test_semantic_structural.py -k real_llm` | 0 | `1 passed, 6 deselected`; controlled timeout exercised | `2026-09-09; exact time PENDING` | root ignored config; logical model `glm-5.3-flash`; deployment `GLM_bv2il8` as previously recorded |
| `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src uv run --no-project --with pytest --with pyarrow pytest -q tests/test_semantic_survey.py tests/test_semantic_inspection.py tests/test_semantic_structural.py` | 0 | `15 passed, 1 skipped, 3 subtests passed` | `2026-09-09; exact time PENDING` | same environment |
| `python3 -m py_compile src/datamodelmatch/semantic_structural.py` | 0 | passed | `2026-09-09; exact time PENDING` | Python `3.9.6` |
| `git check-ignore -q config.llm.json` | 0 | passed | `2026-09-09; exact time PENDING` | repository worktree |
| `git diff --check` | 0 | passed | `2026-09-09; exact time PENDING` | repository worktree |

The configuration fingerprint, full request fingerprint, and exact real-run
artifact hash were not recorded in the existing evidence and remain `PENDING`.
No credential or full prompt/response is reproduced here.

## Acceptance Matrix

| requirement/evidence | current state | authoritative evidence or gap |
| --- | --- | --- |
| Closed structural result and evidence validation | SATISFIED AT SUBMODULE LEVEL | Focused tests recorded; independent rerun/signature PENDING |
| Bounded allowlisted inspection loop | SATISFIED AT SUBMODULE LEVEL | Focused tests recorded; integration with current WP2 output PENDING |
| Real LLM success and controlled failure | PARTIAL | One opt-in success and timeout recorded; request/config fingerprints and independent rerun PENDING |
| WP2 snapshot/evidence binding | PENDING | No main Agent job integration |
| Evidence-preserving fusion/profile publication | BLOCKED | WP5 and shared profile builder not delivered |
| HTTP/SSE/UI user-visible states | BLOCKED | Shared paths and WP7 browser evidence absent |
| Independent acceptance and signature | PENDING | Acceptor, approval time, and signed evidence bundle absent |

## Handoff and Main-Agent Actions

1. Pass only snapshot-bound WP2 facts and bounded redacted documentation
   excerpts into the component.
2. Preserve claims, evidence, unresolved fields, model metadata, and failures
   through WP5 fusion and profile publication.
3. Add production runtime error/retry behavior using the frozen P0.1 policy;
   isolated model tests do not replace this.
4. Independently rerun real-model success/failure tests with a sanitized
   non-secret request fingerprint and record all required hashes.
5. Complete Phase 3 execution documentation before treating WP3 as accepted.

## Failure and Rollback

Malformed model output, invalid inspection requests, conflicts, timeout, and
transport failure must produce controlled failure or explicit unknown results.
If redaction, path allowlisting, or evidence-reference validation fails, stop
the analysis and do not publish a candidate. Rollback means excluding WP3 from
the profile builder; no raw model data or credentials are deleted or exposed.
