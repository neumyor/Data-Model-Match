# WP4 Plan: Representative Sampling, VLM, Observation Validation, and Aggregation

## Governance Fields

```text
workPackageId: WP4
phase: Phase 4
status: BLOCKED_PENDING_RUNTIME_WIRING_AND_VIDEO_DECODER
requirementSourceSha256: a2c4f4d2d53e7d1156f171b15f00def54f44b6ac89c761a9fae8eb0ee12dffa5
workPackageStatus: BLOCKED_PENDING_RUNTIME_WIRING_AND_VIDEO_DECODER
verificationCommands: see Verification
workDirectory: /Users/yimingniu/Code/DataModelMatch
startedAt: PENDING_NOT_RECORDED
finishedAt: PENDING
exitCode: PENDING
environmentVersion: uv 0.12.10; Python 3.9.6; exact environment fingerprint PENDING
realModelSummary: real image VLM evidence exists; real video VLM and production runtime evidence BLOCKED
sanitizedEvidence: PENDING; sanitized image evidence is recorded in WP4-report.md
riskItems: P0.1 runtime wiring, real video decoder/toolchain, budget/retry integration, fusion, and independent acceptance incomplete
rollbackOrReopen: REOPEN_WP4_ON_RUNTIME_POLICY_OR_MEDIA_BOUNDARY_FAILURE; no rollback executed
approvedAt: PENDING
goal: Produce deterministic representative samples, validated VLM observations, and conservative dataset-level aggregation artifacts.
nonGoals: Profile publication, semantic fusion, task matching, HTTP/SSE/UI wiring, and native-video VLM requests.
sourceRequirementIds: [SRC-04, SRC-05, SRC-07, SRC-10, SRC-11, SRC-12, SRC-16, SRC-17, SRC-19]
inputArtifacts: see Input Artifacts
outputArtifacts: see Output Artifacts
dependencies: WP2 facts required; WP3 structural result optional optimization input; see Dependencies
ownedPaths: see Ownership and Isolation
readOnlyPaths: see Ownership and Isolation
generatedPaths: []
forbiddenPaths: see Ownership and Isolation
baseRevision: 3ab448b5c3449f4d14287076cc187591f2f8aa92
responsibleAgent: WP4 implementation agent; main Agent owns integration and acceptance
modelTier: Terra Medium
independentAcceptor: PENDING_UNASSIGNED
approvalStatus: BLOCKED
verificationCommands: see Verification
acceptanceDeliverables: see Acceptance Deliverables
failureAndRollback: see Failure and Rollback
handoffConsumer: Main Agent / WP5 fusion and profile-builder integration
```

## Scope

WP4 consumes the fact-only outputs of WP2 and produces isolated, auditable
sample references, VLM observations, and dataset-level aggregation artifacts.
It does not publish profiles, fuse documentary/structural evidence, perform
task matching, or change any shared path.

WP2 `DatasetSketch` and deterministic `InspectionFact` values are required
inputs and the startup dependency for WP4. A WP3 structural result may be
passed as an optional optimization input for strata/quota prioritization or
coverage diagnostics, but WP3 is not a launch dependency and WP4 must retain a
deterministic behavior when no WP3 result is available. This preserves the
source DOCX processing graph in which Survey feeds the sampling and structural
branches can proceed in parallel.

Allowed implementation paths are limited to:

- `src/datamodelmatch/semantic_sampling*.py`
- `src/datamodelmatch/semantic_vision*.py`
- `src/datamodelmatch/semantic_aggregation*.py`
- `tests/test_semantic_sampling*.py`
- `tests/test_semantic_vision*.py`
- `tests/test_semantic_aggregation*.py`
- this plan and `WP4-report.md`

## Input Artifacts

| path | version | sha256 | role |
| --- | --- | --- | --- |
| `docs/semantic-contracts/vlm-configuration.schema.json` | v1 | `e0208934fdfaa6a715aace10114c4c72c3031cc0380ccb69f96beec6cbd5e261` | Explicit VLM configuration boundary |
| `docs/semantic-contracts/job-runtime-semantics-v1.json` | 1.0.0 | `9c16628857b0e2c402da5fba31ab0146487315615b2881421ecd0090dbab5adc` | Retry, attempt, cancellation, and SSE runtime policy |
| `src/datamodelmatch/semantic_survey.py` | v1 | `f7aa6ac534b34007c7666a7cac68748d32a354815bed0ea506ab8fadb2060e18` | Required WP2 sketch/fact producer |
| `src/datamodelmatch/semantic_inspection.py` | v1 | `77eb267f99ed79496e43597d66c3576de1f3b08f8d1c529713eb7ee88425a17` | Required WP2 inspection facts |
| `src/datamodelmatch/semantic_structural.py` | v1 | `4738f1635443bb8046efcb8cae3580c801efe57077a43f1b578e93798c7a7ea2` | Optional WP3 structural optimization input |

## Output Artifacts

| path | version | sha256WhenAccepted | current evidence |
| --- | --- | --- | --- |
| `src/datamodelmatch/semantic_sampling.py` | v1 | `34b2ad8ee321996d27bdcf2d6afe7103785db0cf9919d5f125fee3f5210ebe21` | Isolated implementation present |
| `src/datamodelmatch/semantic_vision.py` | v1 | `9422dca52c974b6ced72be91bbb3e2af6e183ad04bb5af0627847416235a3ecd` | Isolated implementation present |
| `src/datamodelmatch/semantic_aggregation.py` | v1 | `6223d5da309ec62c47ee3e30237f37f14bd99a86dd4f1ec3d0e22d49801bf7a8` | Isolated implementation present |
| `tests/test_semantic_sampling.py` | current | `daa6aac39c956caf62562e23cf05a3bb17cf4439f0aaede1a2da212a2d11a1a1` | Focused tests present |
| `tests/test_semantic_vision.py` | current | `025d21ed2e5dcf1157cdf3bb5a7411b13b1e74ab82adaf0cc91c5b0a62f0dd47` | Focused tests present |
| `tests/test_semantic_aggregation.py` | current | `57f93f08889a6e98ea08073e40db69e3f94e46ea587bac2fa43fea4e178a3cc2` | Focused tests present |

## Dependencies

- WP2 facts are required for startup and must be bound to a managed snapshot.
- WP3 structural output is optional optimization input and is not a scheduling
  dependency.
- An approved, version-locked video decoder/toolchain is required for Phase 4
  real-video acceptance; its absence is a blocker, not a skipped pass.
- Main Agent wiring is required for durable P0.1 runtime behavior, profile
  publication, HTTP/SSE, and UI acceptance.

## Ownership and Isolation

```text
ownedPaths:
  - src/datamodelmatch/semantic_sampling.py
  - src/datamodelmatch/semantic_vision.py
  - src/datamodelmatch/semantic_aggregation.py
  - tests/test_semantic_sampling.py
  - tests/test_semantic_vision.py
  - tests/test_semantic_aggregation.py
  - docs/phase-records/WP4-plan.md
  - docs/phase-records/WP4-report.md
readOnlyPaths:
  - src/datamodelmatch/semantic_survey.py
  - src/datamodelmatch/semantic_inspection.py
  - src/datamodelmatch/semantic_structural.py
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

## Interfaces and Ownership

- The caller supplies WP2 facts, a snapshot root, generic image/video
  candidates, bounded media metadata when available, a fixed seed, and a
  sample budget. The caller may additionally supply a WP3 structural result;
  that result is advisory and optional, not required for startup.
- `semantic_sampling` returns immutable sample records and a sampling summary.
  It never infers dataset claims and never uses dataset names.
- `semantic_vision` parses only the explicit `config.llm.json.vlm` object,
  prepares bounded media without logging raw bytes, sends an OpenAI
  Chat-Completions-compatible image request, validates the closed observation
  shape, and returns one controlled observation per sample ID. Every outbound
  attempt requires an explicit bounded cost estimate and reserves against a
  per-job budget; unknown cost and exhausted budget fail closed.
- `semantic_aggregation` accepts validated observations and sample coverage,
  returns field distributions and a claim status, and never upgrades one
  observation to `SUPPORTED`.

All cross-boundary data is closed and validated at runtime. Public v1 field
names, enums, failure codes, and thresholds remain those in the Phase 0
schemas; no new public contract is introduced.

## Sampling Rules

Image candidates are sorted by safe relative path and deterministically
partitioned by an explicit stratum (caller-provided metadata, otherwise
`format:<suffix>`). Per-stratum quota allocation uses largest remainder, and
selection uses a stable SHA-256 ranking of `(seed, stratum, path, hash)`.
Video candidates are first selected as representative videos using the same
stable ranking, then each selected video receives temporal-uniform frame or
clip references from supplied duration/frame metadata. Missing clustering or
embedding metadata produces a visible `deterministic_fallback` strategy and a
coverage-loss record; it never triggers uncontrolled randomness.

Every summary records candidate/selected counts, strata, seed, coverage,
metadata availability, fallback reason, and coverage losses. Unsafe paths,
symlinks, unreadable/corrupt media, empty candidates, and unavailable video
metadata are explicit outcomes.

## VLM and Media Rules

`config.llm.json` is mandatory and Git-ignored. The root text fields are not
fallbacks for VLM fields. The nested `vlm` object must satisfy the frozen
configuration constraints, including explicit endpoint, API key, model,
formats, `frames_only` video mode, timeout, call budget, cost budget, and
retry values. The API key is used only in memory and never appears in output.

Images are sent as `data:` URLs in `image_url` content blocks. Videos are not
sent natively; only prepared frame/clip images are accepted. An approved
decoder may be injected to derive a bounded image under a caller-owned safe
temporary root; without one the result is explicitly unsupported. Media paths
must remain below the snapshot root, be regular files, fit configured byte
limits, and have an allowed extension. Responses are bounded, parsed as JSON, checked
against the exact observation fields, and mapped to controlled
`VLM_TIMEOUT`, `VLM_EMPTY_RESPONSE`, `VLM_INVALID_RESPONSE`,
`VLM_UNAVAILABLE`, `RATE_LIMITED`, `UNSUPPORTED_MEDIA`, or
`MEDIA_READ_FAILED` outcomes.

## P0.1 Runtime Retry Semantics

The authoritative runtime policy is
`docs/semantic-contracts/job-runtime-semantics-v1.json` version `1.0.0`.
WP4 must not define a second retry policy. The retryable set is exactly:

- `VLM_UNAVAILABLE`
- `VLM_TIMEOUT`
- `VLM_EMPTY_RESPONSE`
- `VLM_INVALID_RESPONSE`
- `RATE_LIMITED`

`VLM_EMPTY_RESPONSE` and `VLM_INVALID_RESPONSE` are therefore explicitly
retryable when the job is not cancelled and the attempt limit permits another
try. `UNSUPPORTED_MEDIA`, `MEDIA_READ_FAILED`, `VLM_CONFIG_INVALID`, budget
exhaustion or unknown cost, cancellation, and other non-retryable outcomes must
not be retried.

`maxAttempts` means the maximum number of retries after the initial execution,
so total attempts are `1 + maxAttempts`. `attempt` increments durably when a
worker lease is acquired. Retry delay uses the policy's deterministic bounded
exponential jitter derived from `sha256(jobId + ':' + retryOrdinal)`, with the
frozen `0.8..1.2` multiplier and 60,000 ms cap. A retry emits the existing
retryable error envelope without an `end` event.

The isolated WP4 code and tests are not the production worker/lease/runtime
implementation. Until the main Agent wires these semantics through durable
job execution, budget handling, error mapping, cancellation race, recovery,
and SSE lifecycle, the P0.1 runtime gate remains
`BLOCKED_PENDING_MAIN_AGENT_WIRING`; WP4 cannot be marked as Phase 4
`BACKEND_READY` or `PASSED` on the basis of isolated tests alone.

## Aggregation Rules

For each requested observation field, completed observations contribute
frequency distributions. Failed, unsupported, and cancelled observations
remain in the audit counts and are never silently dropped. A value is
`SUPPORTED` only when at least three completed eligible observations support
it at proportion >= 0.60, sampling coverage is >= 0.60, an aggregation
reference exists, and all counted evidence references resolve. One completed
observation can only yield `OBSERVED`; no completed evidence yields explicit
`UNKNOWN`. Conflicting tied dominant values yield
`CONFLICTING_EVIDENCE` rather than an arbitrary winner.

## Verification

Focused tests cover deterministic image strata, video representative and
temporal sampling, mixed/empty/corrupt candidates, safe media preparation,
configuration rejection, strict observation validation, mocked controlled
failure paths, aggregation thresholds, failures, conflicts, coverage, and the
optional absence of WP3 structural input. Contract verification must also
confirm that eligible empty and invalid responses retry, while unsupported
media, invalid configuration, and budget failures do not; retry counts,
deterministic delays, and terminal event behavior must match P0.1.
When the ignored configuration is valid and the provider is available, a
separate real VLM test uses a generated non-sensitive PNG and records only
status, logical model, elapsed time, and response-shape validation. It never
prints credentials, raw media, prompts, or model response text.

## Acceptance Deliverables

- Focused sampling, vision, and aggregation test output with command, exit
  code, revision, environment, and artifact hashes.
- Real image VLM success and controlled failure evidence using the ignored
  configuration, without secrets or raw sensitive media.
- Real video/sequence VLM evidence using an approved version-locked decoder,
  or an explicit `BLOCKED` record if unavailable.
- Main Agent runtime wiring evidence for P0.1 retry/lease/recovery,
  publication, API/SSE, and downstream profile integration.
- Independent acceptance and a Phase 4 execution record; none is claimed by
  this plan.

## Failure and Rollback

Unsupported media, unreadable files, unknown/exhausted cost, invalid
configuration, and non-retryable errors fail closed. Retryable outcomes must
follow P0.1 exactly. If an output hash, contract, or ownership boundary
changes, stop integration and exclude WP4 artifacts from composition; do not
delete source media, credentials, or previously accepted profiles.
