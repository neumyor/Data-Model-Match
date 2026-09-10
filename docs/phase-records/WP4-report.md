# WP4 Report: Representative Sampling, VLM, Observation Validation, and Aggregation

## Governance Fields

```text
workPackageId: WP4
phase: Phase 4
status: BLOCKED_PENDING_RUNTIME_WIRING_AND_VIDEO_DECODER
planPath: docs/phase-records/WP4-plan.md
verificationResults: see Verification
modelRunSummary: see Verification; sanitized real image VLM success, video VLM BLOCKED
artifactHashes: see Delivered Files and Verification
mainAgentReview: PENDING
requirementSourceSha256: a2c4f4d2d53e7d1156f171b15f00def54f44b6ac89c761a9fae8eb0ee12dffa5
workPackageStatus: BLOCKED_PENDING_RUNTIME_WIRING_AND_VIDEO_DECODER
verificationCommands: see Verification
workDirectory: /Users/yimingniu/Code/DataModelMatch
startedAt: 2026-09-09; exact time PENDING
finishedAt: PENDING
exitCode: 0_RECORDED_ISOLATED_TESTS; PRODUCTION_RUNTIME_PENDING
environmentVersion: uv 0.12.10; Python 3.9.6; exact environment fingerprint PENDING
realModelSummary: MiniCPM-V-4.5 real image success recorded; real video VLM BLOCKED; P0.1 runtime evidence PENDING
sanitizedEvidence: see Verification and P0.1 Retry Alignment and Blocking Gap; no secrets/raw media
riskItems: P0.1 runtime wiring, real video decoder/toolchain, fusion, API/SSE/UI, independent acceptance incomplete
rollbackOrReopen: REOPEN_WP4_ON_RUNTIME_POLICY_OR_MEDIA_BOUNDARY_FAILURE; no rollback executed
approvedAt: PENDING
sourceRequirementIds: [SRC-04, SRC-05, SRC-07, SRC-10, SRC-11, SRC-12, SRC-16, SRC-17, SRC-19]
inputArtifacts: see Delivered Files and P0.1 Retry Alignment and Blocking Gap
outputArtifacts: see Delivered Files and Verification
actualModifiedPaths: see Delivered Files
verificationCommands: see Verification
evidencePaths: see Verification and P0.1 Retry Alignment and Blocking Gap
realModelSummary: see Verification; sanitized real image VLM only
uncoveredItems: see Known Limitations and Main-Agent Follow-up
approvalStatus: BLOCKED
approvalTime: PENDING
plannedBaseRevision: 3ab448b5c3449f4d14287076cc187591f2f8aa92
actualRevision: 3ab448b5c3449f4d14287076cc187591f2f8aa92
responsibleAgent: WP4 implementation agent
modelTier: Terra Medium
independentAcceptor: BLOCKED; not assigned
mainAgentDecision: BLOCKED; isolated implementation is not production runtime acceptance
```

## Status

WP4 isolated implementation completed on 2026-09-09. This is a subtask
handoff, not a Phase 4 product sign-off; main-agent wiring, profile fusion,
HTTP/SSE integration, and final dataset acceptance remain outside this work
package.

WP2 facts are required for WP4 startup. A WP3 structural result is an optional
optimization input only: WP4 can start and produce deterministic fallback
behavior without WP3. This matches the source DOCX Survey fan-out and does not
make WP3 a scheduling dependency.

## Delivered Files

- `src/datamodelmatch/semantic_sampling.py`
  - Deterministic image stratification with stable SHA-256 ranking.
  - Representative-video selection followed by temporal-uniform frame/clip
    references with video path, time range, frame range, and sampling FPS.
  - Explicit seed, strata, metadata/embedding availability, fallback reason,
    coverage, and coverage-loss reporting.
  - Safe relative paths, regular-file checks, symlink rejection, and exact
    SHA-256 content fingerprint validation.
- `src/datamodelmatch/semantic_vision.py`
  - Explicit nested `config.llm.json.vlm` parser with closed fields,
    HTTPS-only endpoint enforcement, `frames_only` video enforcement, bounded
    limits, retry settings, and redacted configuration fingerprinting.
  - Closed `CostEstimate`/`CostEstimator`/`VlmBudgetTracker` interfaces.
    Every outbound attempt requires an explicit bounded estimate; missing or
    unbounded cost and exhausted per-job budget fail closed with controlled
    `VLM_UNAVAILABLE` reasons and never assume zero cost.
  - Safe image data-URL preparation and rejection of unsupported, corrupt,
    over-limit, missing, symlinked, or out-of-root media.
  - Pluggable approved `FrameDecoder` interface. Validated frame/clip
    `SampleRef` bounds are decoded into bounded derived images under a
    caller-specified safe temporary root with fixed provenance. Missing
    decoder, invalid temporal bounds, unsafe derived root, decoder failure,
    and invalid output are controlled outcomes.
  - OpenAI Chat Completions-compatible image request with bounded timeout,
    retry, call budget, and response size.
  - Strict observation JSON validation and one controlled observation outcome
    per sample ID, including failure codes and evidence references.
- `src/datamodelmatch/semantic_aggregation.py`
  - Per-field distributions, evidence references, coverage, completed/failed
    counts, and explicit `UNKNOWN` reasons.
  - Frozen conservative status rules: one observation is `OBSERVED`, at least
    three completed observations at proportion >= 0.60 and coverage >= 0.60
    can be `SUPPORTED`, and conflicts become `UNKNOWN`.
- `tests/test_semantic_sampling.py`
- `tests/test_semantic_vision.py`
- `tests/test_semantic_aggregation.py`
- `docs/phase-records/WP4-plan.md`

No shared resource/store/CLI/server/web path, configuration file, dependency
manifest, or `_reference_only` file was modified.

## P0.1 Retry Alignment and Blocking Gap

The authoritative retry policy is
`docs/semantic-contracts/job-runtime-semantics-v1.json` version `1.0.0`.
`VLM_UNAVAILABLE`, `VLM_TIMEOUT`, `VLM_EMPTY_RESPONSE`,
`VLM_INVALID_RESPONSE`, and `RATE_LIMITED` are retryable when the job is not
cancelled and the `1 + maxAttempts` total-attempt limit has not been reached.
`VLM_EMPTY_RESPONSE` and `VLM_INVALID_RESPONSE` are explicitly retryable; any
earlier wording that malformed model output was not retried is superseded and
must not be used for implementation or acceptance.

Retry delay must use the frozen deterministic bounded exponential jitter
derived from `sha256(jobId + ':' + retryOrdinal)`, with the policy's `0.8..1.2`
multiplier and 60,000 ms cap. `attempt` increments on durable worker lease
acquisition. Unsupported media, media read failures, invalid configuration,
unknown or exhausted budget, cancellation, and other non-retryable errors do
not retry.

The current WP4 evidence does **not** claim that these semantics are fully
implemented. The isolated VLM client is not the durable worker lease, retry
scheduler, recovery, cancellation/publication race, or SSE runtime required by
P0.1. Those pieces remain a main-Agent integration blocker, and the P0.1 gate
remains `BLOCKED_PENDING_MAIN_AGENT_WIRING` until independently verified with
runtime tests. No runtime strategy file was modified by this report update.

## Verification

Focused WP4 tests:

```text
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src uv run --no-project --with pytest --with pyarrow pytest -q tests/test_semantic_sampling.py tests/test_semantic_vision.py tests/test_semantic_aggregation.py
15 passed, 1 skipped
```

The skipped test is the opt-in real-provider test when the environment
variable is absent. It was executed explicitly:

```text
RUN_REAL_VLM_TESTS=1 ... pytest -q tests/test_semantic_vision.py -k real_vlm_generated_image_success
1 passed
```

The real request used the ignored root `config.llm.json`, logical model
`MiniCPM-V-4.5`, a generated non-sensitive complete 16x16 PNG, and a bounded
JSON-only prompt with an explicit bounded test cost estimate. Sanitized
evidence was `COMPLETED`; no API key, raw media, full prompt, or model
response was printed. `config.llm.json` remained Git-ignored.

No real video VLM test is claimed. The environment has no approved
ffmpeg/ffprobe decoder toolchain; the injected decoder tests are deterministic
contract tests only. Phase 4 remains blocked for video acceptance until an
approved decoder/toolchain is provisioned, version-locked, and used for a real
video/sequence VLM success plus controlled failure test.

WP1/WP2 regression:

```text
19 passed
```

`py_compile` and `git diff --check` passed.

## Known Limitations and Main-Agent Follow-up

- This package does not ship a video decoder. It requires an approved
  implementation injected through `FrameDecoder`; native video input remains
  intentionally rejected.
- The sampler records deterministic fallback when clustering metadata or
  embeddings are absent. It does not implement an embedding provider.
- Aggregation results are isolated artifacts and still require the main agent
  to map their references into a schema-validated `DatasetSemanticProfile`
  with referential-integrity checks.
- Main-agent integration must preserve the distinction between sample-level
  observations and dataset-level claims, retain failed observation records,
  and wire VLM errors to the frozen HTTP/SSE error envelope.
- Main-agent integration must add and independently verify P0.1 runtime
  behavior for retryable empty/invalid responses, deterministic jitter,
  durable attempt/lease accounting, recovery, cancellation/publication races,
  and terminal SSE ordering before changing this report's status.
