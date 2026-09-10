"""Closed static Python type contracts for semantic public API v1.

This is a documentation/type artifact. Runtime JSON validation remains defined
by the sibling Draft 2020-12 schemas.
"""

from __future__ import annotations

from typing import List, Literal, Optional, TypedDict, Union


SchemaVersion = Literal[1]
ClaimStatus = Literal["VERIFIED", "SUPPORTED", "OBSERVED", "UNKNOWN"]
UnknownReason = Literal[
    "NO_EVIDENCE", "INSUFFICIENT_SAMPLE_COVERAGE", "UNSUPPORTED_MEDIA",
    "MODEL_FAILURE", "CONFLICTING_EVIDENCE", "INSPECTION_LIMIT",
    "ACCESS_DENIED", "CANCELLED",
]
TaskFamily = Literal[
    "image_classification", "object_detection", "multi_object_tracking",
    "semantic_segmentation", "instance_segmentation", "pose_keypoints",
    "action_video_understanding", "video_anomaly_detection", "reid_retrieval",
]
EvidenceKind = Literal["README", "inspection", "sample", "LLM", "VLM", "aggregation"]
Stage = Literal["survey", "inspection", "structural", "sampling", "vision", "aggregation", "fusion", "matching"]
JobStatus = Literal["queued", "running", "partially_completed", "completed", "failed", "cancelled", "superseded"]
ErrorCode = Literal[
    "SCHEMA_VALIDATION_FAILED", "UNSUPPORTED_SCHEMA_VERSION", "RESOURCE_NOT_FOUND",
    "SNAPSHOT_NOT_FOUND", "REVISION_CONFLICT", "PROFILE_NOT_FOUND",
    "TASK_PROFILE_NOT_FOUND", "JOB_NOT_FOUND", "JOB_NOT_CANCELLABLE",
    "IDEMPOTENCY_KEY_CONFLICT", "STALE_JOB_SUPERSEDED", "VLM_CONFIG_INVALID",
    "VLM_UNAVAILABLE", "VLM_TIMEOUT", "VLM_EMPTY_RESPONSE",
    "VLM_INVALID_RESPONSE", "UNSUPPORTED_MEDIA", "MEDIA_READ_FAILED",
    "INSUFFICIENT_EVIDENCE", "ACCESS_DENIED", "RATE_LIMITED", "INTERNAL_ERROR",
]


class TextLocator(TypedDict):
    kind: Literal["text"]
    path: str
    lineStart: int
    lineEnd: int


class InspectionLocator(TypedDict):
    kind: Literal["inspection"]
    inspectionRef: str


class SampleLocator(TypedDict):
    kind: Literal["sample"]
    sampleRef: str


class AggregationLocator(TypedDict):
    kind: Literal["aggregation"]
    aggregationRef: str


EvidenceLocator = Union[TextLocator, InspectionLocator, SampleLocator, AggregationLocator]


class Evidence(TypedDict):
    id: str
    kind: EvidenceKind
    sourceRef: str
    locator: EvidenceLocator
    stage: Stage
    summary: str
    snapshotRevision: str


class ImageSampleRef(TypedDict):
    id: str
    kind: Literal["image"]
    path: str
    contentHash: str


class TemporalSampleRef(TypedDict):
    id: str
    kind: Literal["frame", "clip"]
    path: str
    contentHash: str
    videoPath: str
    startMs: int
    endMs: int
    frameStart: int
    frameEnd: int
    samplingFps: float


SampleRef = Union[ImageSampleRef, TemporalSampleRef]


class ValueDistribution(TypedDict):
    value: str
    observationCount: int
    eligibleObservationCount: int
    proportion: float
    isDominant: bool
    evidenceRefs: List[str]


class CompletedVisualObservation(TypedDict):
    id: str
    sampleRef: str
    objectCategories: List[str]
    environments: List[str]
    viewpoints: List[str]
    targetScale: Literal["UNKNOWN", "tiny", "small", "medium", "large", "mixed"]
    objectDensity: Literal["UNKNOWN", "low", "medium", "high", "mixed"]
    occlusion: Literal["UNKNOWN", "rare", "moderate", "frequent"]
    illumination: List[str]
    cameraMotion: Literal["UNKNOWN", "static", "moving"]
    targetMotion: Literal["UNKNOWN", "slow", "moderate", "fast", "mixed"]
    vlmModel: str
    configurationFingerprint: str
    status: Literal["COMPLETED"]
    evidenceRefs: List[str]


class FailedVisualObservation(CompletedVisualObservation):
    status: Literal["FAILED", "UNSUPPORTED", "CANCELLED"]
    failureCode: Literal["VLM_TIMEOUT", "VLM_EMPTY_RESPONSE", "VLM_INVALID_RESPONSE", "UNSUPPORTED_MEDIA", "MEDIA_READ_FAILED", "CANCELLED"]


VisualObservation = Union[CompletedVisualObservation, FailedVisualObservation]


class SamplingSummary(TypedDict):
    id: str
    strategy: Literal["stratified", "temporal_uniform", "coverage_clustered", "deterministic_fallback"]
    strata: List[str]
    candidateCount: int
    selectedCount: int
    successfulObservationCount: int
    failedObservationCount: int
    coverage: float
    selectionSeed: int
    selectionEvidenceRefs: List[str]


class SemanticClaimBase(TypedDict):
    id: str
    field: str
    scope: Literal["structural", "content", "task-specific"]
    evidenceRefs: List[str]


class VerifiedObservedClaimBase(SemanticClaimBase):
    status: Literal["VERIFIED", "OBSERVED"]


class VerifiedObservedValueClaim(VerifiedObservedClaimBase, total=False):
    value: str
    valueDistribution: ValueDistribution
    conflictRefs: List[str]


class VerifiedObservedDistributionClaim(VerifiedObservedClaimBase, total=False):
    value: str
    valueDistribution: ValueDistribution
    conflictRefs: List[str]


class SupportedClaimBase(SemanticClaimBase):
    status: Literal["SUPPORTED"]


class SupportedValueClaim(SupportedClaimBase, total=False):
    value: str
    valueDistribution: ValueDistribution
    aggregationRef: str
    conflictRefs: List[str]


class SupportedDistributionClaim(SupportedClaimBase, total=False):
    value: str
    valueDistribution: ValueDistribution
    aggregationRef: str
    conflictRefs: List[str]


class UnknownClaimBase(SemanticClaimBase):
    status: Literal["UNKNOWN"]
    unknownReason: UnknownReason


class UnknownSemanticClaim(UnknownClaimBase, total=False):
    conflictRefs: List[str]


SemanticClaim = Union[
    VerifiedObservedValueClaim, VerifiedObservedDistributionClaim,
    SupportedValueClaim, SupportedDistributionClaim, UnknownSemanticClaim,
]


class UnresolvedField(TypedDict):
    field: str
    reason: UnknownReason
    attemptedEvidenceRefs: List[str]
    nextAction: Literal["inspect_metadata", "inspect_annotation", "sample_media", "request_access", "unsupported"]


class ClassificationTaskSpecificSemantic(TypedDict):
    task: Literal["image_classification"]
    longTail: Literal["UNKNOWN", "low", "moderate", "high"]
    domainFeatures: List[str]


class DetectionTaskSpecificSemantic(TypedDict):
    task: Literal["object_detection"]
    scaleDistribution: Literal["UNKNOWN", "small_target_heavy", "balanced", "large_target_heavy"]
    occlusion: Literal["UNKNOWN", "rare", "moderate", "frequent"]


class TrackingTaskSpecificSemantic(TypedDict):
    task: Literal["multi_object_tracking"]
    temporalContinuity: Literal["UNKNOWN", "sparse", "continuous"]
    motionChallenge: Literal["UNKNOWN", "low", "moderate", "high"]


class SegmentationTaskSpecificSemantic(TypedDict):
    task: Literal["semantic_segmentation", "instance_segmentation"]
    boundaryComplexity: Literal["UNKNOWN", "low", "moderate", "high"]
    smallObjectRatio: Literal["UNKNOWN", "low", "moderate", "high"]


class PoseTaskSpecificSemantic(TypedDict):
    task: Literal["pose_keypoints"]
    keypointVisibility: Literal["UNKNOWN", "low", "moderate", "high"]
    viewpointChallenge: Literal["UNKNOWN", "low", "moderate", "high"]


class ActionTaskSpecificSemantic(TypedDict):
    task: Literal["action_video_understanding"]
    actionTypes: List[str]
    temporalDynamics: Literal["UNKNOWN", "low", "moderate", "high"]


class AnomalyTaskSpecificSemantic(TypedDict):
    task: Literal["video_anomaly_detection"]
    anomalyTypes: List[str]
    temporalSparsity: Literal["UNKNOWN", "low", "moderate", "high"]


class ReIdTaskSpecificSemantic(TypedDict):
    task: Literal["reid_retrieval"]
    identityDiversity: Literal["UNKNOWN", "low", "moderate", "high"]
    crossCameraVariation: Literal["UNKNOWN", "low", "moderate", "high"]
    crossDomainVariation: Literal["UNKNOWN", "low", "moderate", "high"]


TaskSpecificSemantic = Union[
    ClassificationTaskSpecificSemantic, DetectionTaskSpecificSemantic,
    TrackingTaskSpecificSemantic, SegmentationTaskSpecificSemantic,
    PoseTaskSpecificSemantic, ActionTaskSpecificSemantic,
    AnomalyTaskSpecificSemantic, ReIdTaskSpecificSemantic,
]


class Generator(TypedDict):
    profileBuilderVersion: str
    samplingPolicyVersion: str
    aggregationRuleVersion: str
    configurationFingerprint: str


class StructuralSemantics(TypedDict):
    tasks: List[TaskFamily]
    modalities: List[Literal["RGB", "infrared", "depth", "thermal", "multimodal", "event"]]
    sampleOrganization: Literal["independent_image", "image_sequence", "video", "mixed", "UNKNOWN"]
    temporalStructure: Literal["none", "sequence", "video", "mixed", "UNKNOWN"]
    supervision: List[Literal["class_label", "bbox", "track", "semantic_mask", "instance_mask", "keypoints", "action_label", "temporal_segment", "anomaly_label", "identity", "pair_ranking"]]
    annotationSemantics: List[str]
    resourceRoles: List[Literal["media", "annotation", "metadata", "documentation", "split_definition"]]
    resourceRelations: List[Literal["image_to_annotation", "frame_to_track", "video_to_clip_label", "identity_to_camera", "UNKNOWN"]]


class ContentSemantics(TypedDict):
    objectCategories: List[str]
    environments: List[str]
    viewpoints: List[str]
    targetScale: str
    objectDensity: str
    occlusion: str
    illumination: List[str]
    cameraMotion: str
    targetMotion: str
    taskSpecificSemantics: List[TaskSpecificSemantic]


class DatasetSemanticProfile(TypedDict):
    version: SchemaVersion
    resourceId: str
    snapshotRevision: str
    generator: Generator
    structuralSemantics: StructuralSemantics
    contentSemantics: ContentSemantics
    sampleRefs: List[SampleRef]
    observations: List[VisualObservation]
    samplingSummary: SamplingSummary
    claims: List[SemanticClaim]
    evidence: List[Evidence]
    unresolved: List[UnresolvedField]
    generatedAt: str


class TaskDescriptor(TypedDict):
    value: TaskFamily
    importance: Literal["required"]


class RequiredTaskConditions(TypedDict):
    modalities: List[Literal["vision", "RGB", "infrared", "depth", "thermal", "multimodal", "event"]]
    temporalStructure: Literal["none", "sequence", "video", "mixed"]
    supervision: List[Literal["classification_ground_truth", "detection_ground_truth", "tracking_ground_truth", "semantic_segmentation_ground_truth", "instance_segmentation_ground_truth", "keypoints_ground_truth", "action_ground_truth", "anomaly_ground_truth", "identity_ground_truth", "ranking_ground_truth"]]


class ClassificationTaskSpecificPreference(TypedDict):
    task: Literal["image_classification"]
    longTail: List[Literal["low", "moderate", "high"]]
    domainFeatures: List[str]


class DetectionTaskSpecificPreference(TypedDict):
    task: Literal["object_detection"]
    scaleDistribution: List[Literal["small_target_heavy", "balanced", "large_target_heavy"]]
    occlusion: List[Literal["rare", "moderate", "frequent"]]


class TrackingTaskSpecificPreference(TypedDict):
    task: Literal["multi_object_tracking"]
    temporalContinuity: List[Literal["sparse", "continuous"]]
    motionChallenge: List[Literal["low", "moderate", "high"]]


class SegmentationTaskSpecificPreference(TypedDict):
    task: Literal["semantic_segmentation", "instance_segmentation"]
    boundaryComplexity: List[Literal["low", "moderate", "high"]]
    smallObjectRatio: List[Literal["low", "moderate", "high"]]


class PoseTaskSpecificPreference(TypedDict):
    task: Literal["pose_keypoints"]
    keypointVisibility: List[Literal["low", "moderate", "high"]]
    viewpointChallenge: List[Literal["low", "moderate", "high"]]


class ActionTaskSpecificPreference(TypedDict):
    task: Literal["action_video_understanding"]
    actionTypes: List[str]
    temporalDynamics: List[Literal["low", "moderate", "high"]]


class AnomalyTaskSpecificPreference(TypedDict):
    task: Literal["video_anomaly_detection"]
    anomalyTypes: List[str]
    temporalSparsity: List[Literal["low", "moderate", "high"]]


class ReIdTaskSpecificPreference(TypedDict):
    task: Literal["reid_retrieval"]
    identityDiversity: List[Literal["low", "moderate", "high"]]
    crossCameraVariation: List[Literal["low", "moderate", "high"]]
    crossDomainVariation: List[Literal["low", "moderate", "high"]]


TaskSpecificPreference = Union[
    ClassificationTaskSpecificPreference, DetectionTaskSpecificPreference,
    TrackingTaskSpecificPreference, SegmentationTaskSpecificPreference,
    PoseTaskSpecificPreference, ActionTaskSpecificPreference,
    AnomalyTaskSpecificPreference, ReIdTaskSpecificPreference,
]


class PreferredTaskConditions(TypedDict):
    objectCategories: List[str]
    environments: List[str]
    viewpoints: List[str]
    targetScale: List[Literal["tiny", "small", "medium", "large", "mixed"]]
    objectDensity: List[Literal["low", "medium", "high", "mixed"]]
    occlusion: List[Literal["rare", "moderate", "frequent"]]
    illumination: List[str]
    cameraMotion: List[Literal["static", "moving"]]
    targetMotion: List[Literal["slow", "moderate", "fast", "mixed"]]
    taskSpecificPreferences: List[TaskSpecificPreference]


class TaskSemanticProfile(TypedDict):
    version: SchemaVersion
    id: str
    revision: str
    task: TaskDescriptor
    required: RequiredTaskConditions
    preferred: PreferredTaskConditions
    createdAt: str


class MatchFinding(TypedDict):
    field: str
    outcome: Literal["SATISFIED", "MATCHED", "CONFLICT", "UNKNOWN", "MISSING"]
    message: str
    evidenceRefs: List[str]


class DatasetTaskMatchResult(TypedDict):
    version: SchemaVersion
    id: str
    datasetResourceId: str
    datasetProfileRevision: str
    taskProfileId: str
    taskProfileRevision: str
    matchingRuleVersion: str
    weightConfigurationFingerprint: str
    compatibility: Literal["COMPATIBLE", "PARTIALLY_COMPATIBLE", "INCOMPATIBLE", "UNKNOWN"]
    suitabilityScore: Optional[float]
    defaultRankingEligible: bool
    satisfiedRequirements: List[MatchFinding]
    matchedPreferences: List[MatchFinding]
    conflicts: List[MatchFinding]
    unknowns: List[MatchFinding]
    explanation: str
    evidenceRefs: List[str]
    generatedAt: str


class ErrorDetail(TypedDict):
    field: str
    reason: str


class ErrorBodyRequired(TypedDict):
    code: ErrorCode
    message: str
    retryable: bool


class ErrorBody(ErrorBodyRequired, total=False):
    requestId: str
    jobId: str
    details: List[ErrorDetail]


class ErrorEnvelope(TypedDict):
    version: SchemaVersion
    error: ErrorBody


class JobRequired(TypedDict):
    jobId: str
    jobType: Literal["profile", "match"]
    status: JobStatus
    createdAt: str
    updatedAt: str
    attempt: int
    maxAttempts: int


class Job(JobRequired, total=False):
    idempotencyKey: str
    resultRef: str
    error: ErrorEnvelope


class ProfileJobRequired(TypedDict):
    jobId: str
    jobType: Literal["profile"]
    status: JobStatus
    createdAt: str
    updatedAt: str
    attempt: int
    maxAttempts: int


class ProfileJob(ProfileJobRequired, total=False):
    idempotencyKey: str
    resultRef: str
    error: ErrorEnvelope


class MatchJobRequired(TypedDict):
    jobId: str
    jobType: Literal["match"]
    status: JobStatus
    createdAt: str
    updatedAt: str
    attempt: int
    maxAttempts: int


class MatchJob(MatchJobRequired, total=False):
    idempotencyKey: str
    resultRef: str
    error: ErrorEnvelope


class ProfileJobRequestRequired(TypedDict):
    version: SchemaVersion
    resourceId: str
    snapshotRevision: str
    profileSchemaVersion: SchemaVersion
    configurationFingerprint: str


class ProfileJobRequest(ProfileJobRequestRequired, total=False):
    idempotencyKey: str


class ProfileJobResponse(TypedDict):
    version: SchemaVersion
    job: ProfileJob


class ProfileJobGetResponse(TypedDict):
    version: SchemaVersion
    job: ProfileJob
    profile: Optional[DatasetSemanticProfile]


class ProfileJobCancelResponse(TypedDict):
    version: SchemaVersion
    job: ProfileJob


class MatchJobRequestRequired(TypedDict):
    version: SchemaVersion
    taskProfileId: str
    taskProfileRevision: str
    datasetResourceIds: List[str]
    matchingRuleVersion: str
    weightConfigurationFingerprint: str


class MatchJobRequest(MatchJobRequestRequired, total=False):
    idempotencyKey: str


class MatchJobResponse(TypedDict):
    version: SchemaVersion
    job: MatchJob


class MatchJobGetResponse(TypedDict):
    version: SchemaVersion
    job: MatchJob
    results: List[DatasetTaskMatchResult]


TaskProfileCreateRequest = TaskSemanticProfile


class TaskProfileCreateResponse(TypedDict):
    version: SchemaVersion
    taskProfile: TaskSemanticProfile


class StageEventData(TypedDict):
    stage: Stage
    status: Literal["started", "completed", "skipped"]


class ProgressEventData(TypedDict):
    stage: Stage
    completed: int
    total: int


class EvidenceEventData(TypedDict):
    evidence: Evidence


class WarningEventData(TypedDict):
    code: Literal["SAMPLE_FAILURE", "INSUFFICIENT_COVERAGE", "UNSUPPORTED_MEDIA", "STALE_REVISION"]
    message: str


class ResultEventData(TypedDict):
    resultType: Literal["dataset_semantic_profile", "dataset_task_match_result"]
    resultId: str


class EndEventDataRequired(TypedDict):
    status: Literal["completed", "failed", "cancelled", "superseded", "partially_completed"]


class EndEventData(EndEventDataRequired, total=False):
    resultAvailable: bool


class SseEventBase(TypedDict):
    version: SchemaVersion
    jobId: str
    eventId: int
    timestamp: str


class StageSseEvent(SseEventBase):
    eventType: Literal["stage"]
    data: StageEventData


class ProgressSseEvent(SseEventBase):
    eventType: Literal["progress"]
    data: ProgressEventData


class EvidenceSseEvent(SseEventBase):
    eventType: Literal["evidence"]
    data: EvidenceEventData


class WarningSseEvent(SseEventBase):
    eventType: Literal["warning"]
    data: WarningEventData


class ResultSseEvent(SseEventBase):
    eventType: Literal["result"]
    data: ResultEventData


class ErrorSseEvent(SseEventBase):
    eventType: Literal["error"]
    data: ErrorEnvelope


class EndSseEvent(SseEventBase):
    eventType: Literal["end"]
    data: EndEventData


SseEvent = Union[StageSseEvent, ProgressSseEvent, EvidenceSseEvent, WarningSseEvent, ResultSseEvent, ErrorSseEvent, EndSseEvent]


class ImageInput(TypedDict):
    formats: List[Literal["jpeg", "png", "webp"]]
    maxBytes: int


class VideoInput(TypedDict):
    mode: Literal["frames_only"]
    formats: List[Literal["mp4", "webm", "mov"]]
    maxBytes: int
    maxDurationMs: int


class VlmLimits(TypedDict):
    timeoutMs: int
    maxCallsPerStage: int
    maxCostUsdPerJob: float


class VlmRetry(TypedDict):
    maxAttempts: int
    baseDelayMs: int


class VlmConfiguration(TypedDict):
    version: SchemaVersion
    provider: str
    endpoint: str
    apiKey: str
    model: str
    imageInput: ImageInput
    videoInput: VideoInput
    limits: VlmLimits
    retry: VlmRetry
