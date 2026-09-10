# RFC: Visual Semantic Public Contracts v1

## Status and Scope

This RFC freezes the Phase 0 public boundary for visual semantic discovery.
The normative executable definitions are the Draft 2020-12 files in this
directory. Their `$id` values use
`https://datamodelmatch.local/schemas/semantic/v1/`; consumers resolve
relative references from the referenced schema file. A future incompatible
change requires a new `/vN/` schema namespace and the change-control record
required by acceptance-document section 13.

This RFC defines new semantic APIs only. It does not replace
`DatasetProfile`, `/api/compatibility`, or `/api/match`.

## Normative Schema Entry Points

| Interface | Schema |
| --- | --- |
| `DatasetSemanticProfile` | `dataset-semantic-profile.schema.json` |
| `TaskSemanticProfile` | `task-semantic-profile.schema.json` |
| `DatasetTaskMatchResult` | `dataset-task-match-result.schema.json` |
| Profile create/get/cancel payloads | `profile-job-{request,response,get-response,cancel-response}.schema.json` |
| Match create/get payloads | `match-job-{request,response,get-response}.schema.json` |
| Task Profile create request/response | `task-profile-create-{request,response}.schema.json` |
| Error envelope | `error-envelope.schema.json` |
| SSE events | `sse-event.schema.json` |
| VLM configuration object | `vlm-configuration.schema.json` |

Every declared object uses `additionalProperties: false`; no public payload
permits an unbounded map. `data` in the SSE base is a boolean schema only so
that each event branch supplies its own closed object. Raw media, prompts,
model responses, API keys, and authorization headers have no public field.

## Static Type Artifacts

`python_types.py` and `frontend-types.d.ts` are normative static projections of
the public schemas for downstream Python and frontend work. They use closed
named `TypedDict`/`Literal` and TypeScript object/discriminated-union shapes,
not unconstrained dictionaries or `Record` types. The profile and match job
responses narrow `jobType` respectively to `profile` and `match`; SSE event
types are likewise discriminated by `eventType`.

`type-parity-manifest.json` maps every `contract-manifest.json` public
interface to one Python symbol and one frontend symbol. The dependency-free
parity test checks catalog membership, valid-fixture coverage, symbol
existence, and inclusion of every public-schema property and string
enum/const discriminator in both artifacts. It complements, rather than
replaces, a production type checker and a standards-conformant JSON Schema
validator.

All public version fields are the required constant integer `1`. No field has
an implicit client-visible default. The only optional request field is
`idempotencyKey`; when omitted, the server derives the canonical idempotency
key defined below and returns it on the job. Optional result artifacts are
explicit `null`, never omitted: profile-job `profile` is `null` until a
complete profile is published; match-job `results` is an empty array until
results exist.

## Shared Values and Constraints

`id` is `[A-Za-z][A-Za-z0-9_-]{2,127}`. Revisions are nonempty strings up to
256 characters. A fingerprint is exactly `sha256:` followed by 64 lowercase
hexadecimal characters. Relative paths are nonempty, at most 4096 characters,
not absolute, and may not traverse `..`. Timestamps are RFC 3339 date-times.

The global enums are:

- Claim status: `VERIFIED`, `SUPPORTED`, `OBSERVED`, `UNKNOWN`.
- Unknown reason: `NO_EVIDENCE`, `INSUFFICIENT_SAMPLE_COVERAGE`,
  `UNSUPPORTED_MEDIA`, `MODEL_FAILURE`, `CONFLICTING_EVIDENCE`,
  `INSPECTION_LIMIT`, `ACCESS_DENIED`, `CANCELLED`.
- Task family: `image_classification`, `object_detection`,
  `multi_object_tracking`, `semantic_segmentation`,
  `instance_segmentation`, `pose_keypoints`,
  `action_video_understanding`, `video_anomaly_detection`,
  `reid_retrieval`.
- Job status: `queued`, `running`, `partially_completed`, `completed`,
  `failed`, `cancelled`, `superseded`.

`UNKNOWN` is an explicit status/value. It is never represented by missing
fields, empty arrays, `null`, a failed request, or a zero score. A claim with
status `UNKNOWN` requires `unknownReason` and may not carry `value` or
`valueDistribution`. A non-UNKNOWN claim requires one of those values.
`SUPPORTED` additionally requires `aggregationRef`; `VERIFIED` must be backed
by deterministic inspection or explicit documentation evidence in the
application-level referential-integrity check; `OBSERVED` may cite only sample
evidence.

Evidence kinds are `README`, `inspection`, `sample`, `LLM`, `VLM`, and
`aggregation`; stages are `survey`, `inspection`, `structural`, `sampling`,
`vision`, `aggregation`, `fusion`, and `matching`. Locator kinds are `text`,
`inspection`, `sample`, and `aggregation`, each requiring respectively
path+line range, `inspectionRef`, `sampleRef`, or `aggregationRef`.

`SampleRef.kind` is `image`, `frame`, or `clip`. Frame and clip samples require
`videoPath`, `startMs`, `endMs`, `frameStart`, `frameEnd`, and `samplingFps`;
durations and frame values are nonnegative, end time is at least one
millisecond, and FPS is `(0, 240]`. Sampling strategies are `stratified`,
`temporal_uniform`, `coverage_clustered`, and `deterministic_fallback`.
Coverage and all suitability scores are `[0, 1]`. Selection seeds are
`[0, 2147483647]`.

`VisualObservation.status` is `COMPLETED`, `FAILED`, `UNSUPPORTED`, or
`CANCELLED`. All non-completed observations require a controlled failure code:
`VLM_TIMEOUT`, `VLM_EMPTY_RESPONSE`, `VLM_INVALID_RESPONSE`,
`UNSUPPORTED_MEDIA`, `MEDIA_READ_FAILED`, or `CANCELLED`. A completed
observation forbids `failureCode`. Observation scale, density, occlusion,
camera motion, and target motion use the exact enums in
`common.schema.json`; their `UNKNOWN` values remain observation facts, not
dataset-level proof.

Dataset structural values are closed as follows: modalities are `RGB`,
`infrared`, `depth`, `thermal`, `multimodal`, or `event`; sample organization is
`independent_image`, `image_sequence`, `video`, `mixed`, or `UNKNOWN`;
temporal structure is `none`, `sequence`, `video`, `mixed`, or `UNKNOWN`;
supervision is `class_label`, `bbox`, `track`, `semantic_mask`,
`instance_mask`, `keypoints`, `action_label`, `temporal_segment`,
`anomaly_label`, `identity`, or `pair_ranking`; resource roles are `media`,
`annotation`, `metadata`, `documentation`, or `split_definition`; resource
relations are `image_to_annotation`, `frame_to_track`, `video_to_clip_label`,
`identity_to_camera`, or `UNKNOWN`. Arrays marked unique are set-like.

Task-specific semantics are a closed discriminated union. The classification
variant records long-tail and domain features; detection records scale
distribution and occlusion; tracking records temporal continuity and motion
challenge; semantic/instance segmentation records boundary complexity and
small-object ratio; pose records keypoint visibility and viewpoint challenge;
action/video understanding records action types and temporal dynamics; anomaly
detection records anomaly types and temporal sparsity; Re-ID/retrieval records
identity diversity plus cross-camera and cross-domain variation. Downstream
code must reject a task-specific variant whose discriminator and fields do not
match one of these alternatives.

`ValueDistribution.observationCount` is nonnegative,
`eligibleObservationCount` is at least one, and `proportion` is `[0,1]`.
At aggregation time it must equal
`observationCount / eligibleObservationCount` within floating-point tolerance.
The following status rules are frozen:

- `VERIFIED`: one or more `README` or `inspection` evidence records at the
  fixed revision prove the field. LLM/VLM evidence alone is insufficient.
- `SUPPORTED`: the value has at least three completed eligible observations,
  `proportion >= 0.60`, sampling coverage is at least `0.60`, an aggregation
  reference, and evidence for each counted observation. It cannot be
  `SUPPORTED` while an unresolved deterministic/documentary contradiction
  remains.
- `OBSERVED`: one or more completed sample observations support the value but
  the `SUPPORTED` thresholds or evidence quality are not met.
- `UNKNOWN`: the field has the explicit reason above. Conflicting positive
  evidence requires `CONFLICTING_EVIDENCE` rather than selecting a winner.

Schema validation establishes syntax, enum, range, and closed-object rules.
Implementations must additionally check references against the containing
artifact: every `sampleRef`, `evidenceRef`, `claim` reference,
`aggregationRef`, and job result reference must resolve within its fixed
resource snapshot. It is an error to repair a dangling reference by guessing.

## Profile and Match Semantics

`DatasetSemanticProfile` always binds `resourceId` to `snapshotRevision` and
stores generator, structural semantics, content claim IDs, samples,
observations, sampling summary, claims, evidence, unresolved fields, and
`generatedAt`. Tasks, modalities, organization, temporal structure,
supervision, roles, and relations are structural facts. Content fields contain
claim IDs only; they cannot directly contain VLM prose or unaggregated sample
labels.

`TaskSemanticProfile.task.importance` is always `required`. Its `required`
object is limited to modality, temporal structure, and supervision hard
constraints. Required modalities are `vision`, `RGB`, `infrared`, `depth`,
`thermal`, `multimodal`, or `event`; temporal values are `none`, `sequence`, `video`,
or `mixed`; and supervision values are `classification_ground_truth`,
`detection_ground_truth`, `tracking_ground_truth`,
`semantic_segmentation_ground_truth`, `instance_segmentation_ground_truth`,
`keypoints_ground_truth`, `action_ground_truth`, `anomaly_ground_truth`,
`identity_ground_truth`, or `ranking_ground_truth`. Preferred scale values are
`tiny`, `small`, `medium`, `large`, or `mixed`; density values are `low`,
`medium`, `high`, or `mixed`; occlusion values are `rare`, `moderate`, or
`frequent`; camera motion is `static` or `moving`; target motion is `slow`,
`moderate`, `fast`, or `mixed`. Other preferred strings are nonempty and at
most 128 characters. Preferred fields are closed named arrays. They are not a
free-form score model and do not include `UNKNOWN`.

`TaskSpecificPreference` is the same closed task-discriminated union as
`TaskSpecificSemantic`, but every preference dimension is an array of desired
values and excludes `UNKNOWN`. Classification requires `longTail` (`low`,
`moderate`, `high`) and `domainFeatures`; detection requires
`scaleDistribution` (`small_target_heavy`, `balanced`,
`large_target_heavy`) and `occlusion`; tracking requires
`temporalContinuity` (`sparse`, `continuous`) and `motionChallenge`; semantic
or instance segmentation requires `boundaryComplexity` and
`smallObjectRatio`; pose requires `keypointVisibility` and
`viewpointChallenge`; action understanding requires `actionTypes` and
`temporalDynamics`; anomaly detection requires `anomalyTypes` and
`temporalSparsity`; Re-ID/retrieval requires `identityDiversity`,
`crossCameraVariation`, and `crossDomainVariation`. Every listed
non-string-scale preference uses `low`, `moderate`, or `high`, except
detection occlusion (`rare`, `moderate`, `frequent`). A `{task, value}`
object is invalid and has no compatibility fallback.

Match compatibility is exactly `COMPATIBLE`, `PARTIALLY_COMPATIBLE`,
`INCOMPATIBLE`, or `UNKNOWN`:

| Compatibility | `suitabilityScore` | `defaultRankingEligible` |
| --- | --- | --- |
| `COMPATIBLE` | required number `[0,1]` | `true` |
| `PARTIALLY_COMPATIBLE` | required `null` | `false` |
| `INCOMPATIBLE` | required `null` | `false` |
| `UNKNOWN` | required `null` | `false` |

Only compatible results enter default suitability ranking. Diagnostic
comparisons for other statuses remain job artifacts and must not populate this
public result or ranking. A match finding has one of `SATISFIED`, `MATCHED`,
`CONFLICT`, `UNKNOWN`, or `MISSING`; all match explanation strings are
nonempty and at most 4096 characters. Rule, builder, sampling, and aggregation
versions use `1.<nonnegative integer>.<nonnegative integer>`.

## API and Error Rules

The endpoints are fixed:

- `POST /api/dataset-semantic-profiles/jobs`
- `GET /api/dataset-semantic-profiles/jobs/:jobId`
- `GET /api/dataset-semantic-profiles/jobs/:jobId/events`
- `POST /api/dataset-semantic-profiles/jobs/:jobId/cancel`
- `POST /api/task-profiles`
- `POST /api/dataset-task-matches/jobs`
- `GET /api/dataset-task-matches/jobs/:jobId`
- `GET /api/dataset-task-matches/jobs/:jobId/events`

Errors use `{"version":1,"error":{...}}`. The only error codes are
`SCHEMA_VALIDATION_FAILED`, `UNSUPPORTED_SCHEMA_VERSION`, `RESOURCE_NOT_FOUND`,
`SNAPSHOT_NOT_FOUND`, `REVISION_CONFLICT`, `PROFILE_NOT_FOUND`,
`TASK_PROFILE_NOT_FOUND`, `JOB_NOT_FOUND`, `JOB_NOT_CANCELLABLE`,
`IDEMPOTENCY_KEY_CONFLICT`, `STALE_JOB_SUPERSEDED`, `VLM_CONFIG_INVALID`,
`VLM_UNAVAILABLE`, `VLM_TIMEOUT`, `VLM_EMPTY_RESPONSE`,
`VLM_INVALID_RESPONSE`, `UNSUPPORTED_MEDIA`, `MEDIA_READ_FAILED`,
`INSUFFICIENT_EVIDENCE`, `ACCESS_DENIED`, `RATE_LIMITED`, and
`INTERNAL_ERROR`. Error `details` is at most 20 closed `{field, reason}`
objects. Messages must be diagnostic but must never contain secrets, raw media,
full prompts, authorization headers, or full model responses.

## SSE, Retry, Cancellation, and Concurrency

Each SSE event conforms to `sse-event.schema.json` and has `version`, `jobId`,
strictly increasing positive integer `eventId`, timestamp, event type, and
closed event data. Event types are `stage`, `progress`, `evidence`, `warning`,
`result`, `error`, and `end`.

The two `.../events` endpoints are the only public event-stream transports.
They return `text/event-stream`, accept standard `Last-Event-ID` on reconnect,
and stream only events for the path's job type. A `JOB_NOT_FOUND` response uses
the normal JSON error envelope, never an SSE `error` event.

For a job, event IDs are monotonic and never reused. Reconnect clients send
`Last-Event-ID`; the server replays events with an ID greater than that value.
If retention has expired, it sends a new `stage` snapshot followed by current
state and clients must read the GET job endpoint for final artifacts. `end` is
terminal and emitted exactly once after any final `result` or `error`. Its
status is one of `completed`, `failed`, `cancelled`, `superseded`, or
`partially_completed`; no later event is legal. `progress.completed` must not
exceed `total`, and `total=0` is legal only before countable work exists.

### P0.1 Runtime Semantics Supplement

`job-runtime-semantics-v1.json` is the versioned, machine-readable authority
for runtime behavior not expressible in the public request/response schemas.
It freezes the retryability of every `ErrorCode`, attempt counting, retry
delay, cancellation/publish winner, private worker lease recovery, SSE
retention/replay, and crash reconciliation. A job runner must consume this
file's version and must not invent a different retry or recovery policy.

`Job.attempt` is the count of execution attempts that have durably started.
It begins at zero and increments when a worker durably acquires an execution
lease.
For v1 compatibility, `maxAttempts` is the number of retries permitted after
the first attempt, so a job has at most `1 + maxAttempts` started attempts.
After a retryable error, retry is allowed only while
`attempt <= maxAttempts` and the durable job state is not cancelled or
terminal. Retry delay uses the policy's deterministic bounded exponential
jitter calculation. The runner records delay and retry ordinal only in its
private audit state; the public SSE stream may emit the existing retryable
error envelope, but must not emit `end` until a terminal outcome.

A worker lease is private execution state, not a new public Job field. An
expired lease is reclaimed under the job lock. A crash after durable lease
acquisition consumes that attempt; a crash before lease acquisition does not.
A stale worker cannot publish with an expired or replaced lease token.
Cancellation and publication are resolved by the first
durable terminal transition under the job lock. Publication must recheck both
the durable job state and `resolvedRevision` while it holds that lock.

Per-job events are retained for at least the policy's minimum period.
`Last-Event-ID` replays only greater IDs. When retention expires, the server
emits a current stage snapshot and the client must retrieve final artifacts
through GET. Reconciliation after a process crash recognizes a valid profile
artifact and published pointer for the same request as the one completed
publication; it may append missing terminal events but cannot publish a
different result.

Cancellation is accepted only for `queued`, `running`, or
`partially_completed` jobs. It is idempotent: repeated cancellation returns
the same terminal cancelled job. Cancellation prevents new work, preserves
auditable completed/failed observation artifacts, emits `end(cancelled)`, and
never publishes a partial profile as ready. Completed, failed, superseded, and
cancelled jobs reject a new cancellation with `JOB_NOT_CANCELLABLE`.

The profile idempotency key is the tuple
`(resourceId, snapshotRevision, profileSchemaVersion, configurationFingerprint)`.
The match idempotency key is the canonical ordered request consisting of task
profile ID/revision, sorted resource IDs, matching rule version, and weight
configuration fingerprint. An explicit idempotency key may replay only an
identical canonical request; otherwise return `IDEMPOTENCY_KEY_CONFLICT`.
Concurrent equal keys return the same job.

For different profile revisions of one resource, only a completed job whose
snapshot equals the resource's then-current `resolvedRevision` may atomically
publish. A successful stale job is marked `superseded`, emits `end(superseded)`,
and cannot overwrite a newer complete profile. Failed or partially completed
jobs may retain artifacts but never replace the last complete profile.

## VLM Configuration Extension and Precedence

Text LLM configuration remains root `config.llm.json` fields `endpoint`,
`apiKey`, `model`, and `stream`, with the existing file as the highest-priority
and required source. The VLM extension is an optional `vlm` object in that same
Git-ignored file and must validate against `vlm-configuration.schema.json`.
It has its own `endpoint`, `apiKey`, and `model`; these values are for VLM
requests only and can never override the root text LLM fields. There is no
fallback from VLM fields to text LLM values and no environment-variable
override. Missing or invalid `vlm` configuration returns `VLM_CONFIG_INVALID`.
This frozen contract intentionally separates interface definition from an
operational deployment decision: the contract supports an approved provider,
model, and endpoint without naming one here. Phase 4 remains blocked until
that deployment decision, credential provisioning, and a sanitized
availability check are independently approved.

VLM `apiKey` is write-only. Configuration is fingerprinted from a canonical
redacted configuration representation, excluding the API key. V1 video mode is
fixed to `frames_only`: native-video transport is not part of the public
contract. Image formats, video formats, size/duration limits, timeout, call
budget, cost budget, and retry counts are all required and bounded by the
schema. Configuration logs may record provider, model, limits, and fingerprint
only.

## Migration from Legacy DatasetProfile

`DatasetProfile` remains a legacy static resource profile. It may continue to
drive the existing dataset-to-model compatibility flow, but it is neither
serialized as nor coerced into `DatasetSemanticProfile`. A migration creates no
semantic claim automatically. It only identifies the legacy resource and
resolved snapshot as the input to a new profile job. Until that job completes,
the UI/API states are “structural profile available; visual semantic profile
not started/running/failed” and no inferred content is displayed.

Persist new semantic profiles separately as versioned artifacts keyed by
`resourceId`, `snapshotRevision`, profile schema version, and configuration
fingerprint. Legacy clients ignore the new artifact; new clients explicitly
read the semantic endpoints. This preserves current resource serialization and
the old compatibility API without ambiguous mixed fields.
