/* Closed TypeScript public contracts for semantic API v1. */

export type SchemaVersion = 1;
export type ClaimStatus = "VERIFIED" | "SUPPORTED" | "OBSERVED" | "UNKNOWN";
export type UnknownReason = "NO_EVIDENCE" | "INSUFFICIENT_SAMPLE_COVERAGE" | "UNSUPPORTED_MEDIA" | "MODEL_FAILURE" | "CONFLICTING_EVIDENCE" | "INSPECTION_LIMIT" | "ACCESS_DENIED" | "CANCELLED";
export type TaskFamily = "image_classification" | "object_detection" | "multi_object_tracking" | "semantic_segmentation" | "instance_segmentation" | "pose_keypoints" | "action_video_understanding" | "video_anomaly_detection" | "reid_retrieval";
export type EvidenceKind = "README" | "inspection" | "sample" | "LLM" | "VLM" | "aggregation";
export type Stage = "survey" | "inspection" | "structural" | "sampling" | "vision" | "aggregation" | "fusion" | "matching";
export type JobStatus = "queued" | "running" | "partially_completed" | "completed" | "failed" | "cancelled" | "superseded";
export type ErrorCode = "SCHEMA_VALIDATION_FAILED" | "UNSUPPORTED_SCHEMA_VERSION" | "RESOURCE_NOT_FOUND" | "SNAPSHOT_NOT_FOUND" | "REVISION_CONFLICT" | "PROFILE_NOT_FOUND" | "TASK_PROFILE_NOT_FOUND" | "JOB_NOT_FOUND" | "JOB_NOT_CANCELLABLE" | "IDEMPOTENCY_KEY_CONFLICT" | "STALE_JOB_SUPERSEDED" | "VLM_CONFIG_INVALID" | "VLM_UNAVAILABLE" | "VLM_TIMEOUT" | "VLM_EMPTY_RESPONSE" | "VLM_INVALID_RESPONSE" | "UNSUPPORTED_MEDIA" | "MEDIA_READ_FAILED" | "INSUFFICIENT_EVIDENCE" | "ACCESS_DENIED" | "RATE_LIMITED" | "INTERNAL_ERROR";

export type EvidenceLocator =
  | { kind: "text"; path: string; lineStart: number; lineEnd: number }
  | { kind: "inspection"; inspectionRef: string }
  | { kind: "sample"; sampleRef: string }
  | { kind: "aggregation"; aggregationRef: string };
export interface Evidence { id: string; kind: EvidenceKind; sourceRef: string; locator: EvidenceLocator; stage: Stage; summary: string; snapshotRevision: string; }
export type SampleRef =
  | { id: string; kind: "image"; path: string; contentHash: string }
  | { id: string; kind: "frame" | "clip"; path: string; contentHash: string; videoPath: string; startMs: number; endMs: number; frameStart: number; frameEnd: number; samplingFps: number; };
export interface ValueDistribution { value: string; observationCount: number; eligibleObservationCount: number; proportion: number; isDominant: boolean; evidenceRefs: string[]; }
export type VisualObservation =
  | { id: string; sampleRef: string; objectCategories: string[]; environments: string[]; viewpoints: string[]; targetScale: "UNKNOWN" | "tiny" | "small" | "medium" | "large" | "mixed"; objectDensity: "UNKNOWN" | "low" | "medium" | "high" | "mixed"; occlusion: "UNKNOWN" | "rare" | "moderate" | "frequent"; illumination: string[]; cameraMotion: "UNKNOWN" | "static" | "moving"; targetMotion: "UNKNOWN" | "slow" | "moderate" | "fast" | "mixed"; vlmModel: string; configurationFingerprint: string; status: "COMPLETED"; evidenceRefs: string[] }
  | { id: string; sampleRef: string; objectCategories: string[]; environments: string[]; viewpoints: string[]; targetScale: "UNKNOWN" | "tiny" | "small" | "medium" | "large" | "mixed"; objectDensity: "UNKNOWN" | "low" | "medium" | "high" | "mixed"; occlusion: "UNKNOWN" | "rare" | "moderate" | "frequent"; illumination: string[]; cameraMotion: "UNKNOWN" | "static" | "moving"; targetMotion: "UNKNOWN" | "slow" | "moderate" | "fast" | "mixed"; vlmModel: string; configurationFingerprint: string; status: "FAILED" | "UNSUPPORTED" | "CANCELLED"; failureCode: "VLM_TIMEOUT" | "VLM_EMPTY_RESPONSE" | "VLM_INVALID_RESPONSE" | "UNSUPPORTED_MEDIA" | "MEDIA_READ_FAILED" | "CANCELLED"; evidenceRefs: string[] };
export interface SamplingSummary { id: string; strategy: "stratified" | "temporal_uniform" | "coverage_clustered" | "deterministic_fallback"; strata: string[]; candidateCount: number; selectedCount: number; successfulObservationCount: number; failedObservationCount: number; coverage: number; selectionSeed: number; selectionEvidenceRefs: string[]; }
export type SemanticClaimBase = { id: string; field: string; scope: "structural" | "content" | "task-specific"; evidenceRefs: string[]; conflictRefs?: string[]; };
export type SemanticClaim =
  | (SemanticClaimBase & { status: "VERIFIED" | "OBSERVED"; value: string; valueDistribution?: ValueDistribution; })
  | (SemanticClaimBase & { status: "VERIFIED" | "OBSERVED"; value?: string; valueDistribution: ValueDistribution; })
  | (SemanticClaimBase & { status: "SUPPORTED"; value: string; valueDistribution?: ValueDistribution; aggregationRef: string; })
  | (SemanticClaimBase & { status: "SUPPORTED"; value?: string; valueDistribution: ValueDistribution; aggregationRef: string; })
  | (SemanticClaimBase & { status: "UNKNOWN"; unknownReason: UnknownReason; });
export interface UnresolvedField { field: string; reason: UnknownReason; attemptedEvidenceRefs: string[]; nextAction: "inspect_metadata" | "inspect_annotation" | "sample_media" | "request_access" | "unsupported"; }
export type TaskSpecificSemantic =
  | { task: "image_classification"; longTail: "UNKNOWN" | "low" | "moderate" | "high"; domainFeatures: string[] }
  | { task: "object_detection"; scaleDistribution: "UNKNOWN" | "small_target_heavy" | "balanced" | "large_target_heavy"; occlusion: "UNKNOWN" | "rare" | "moderate" | "frequent" }
  | { task: "multi_object_tracking"; temporalContinuity: "UNKNOWN" | "sparse" | "continuous"; motionChallenge: "UNKNOWN" | "low" | "moderate" | "high" }
  | { task: "semantic_segmentation" | "instance_segmentation"; boundaryComplexity: "UNKNOWN" | "low" | "moderate" | "high"; smallObjectRatio: "UNKNOWN" | "low" | "moderate" | "high" }
  | { task: "pose_keypoints"; keypointVisibility: "UNKNOWN" | "low" | "moderate" | "high"; viewpointChallenge: "UNKNOWN" | "low" | "moderate" | "high" }
  | { task: "action_video_understanding"; actionTypes: string[]; temporalDynamics: "UNKNOWN" | "low" | "moderate" | "high" }
  | { task: "video_anomaly_detection"; anomalyTypes: string[]; temporalSparsity: "UNKNOWN" | "low" | "moderate" | "high" }
  | { task: "reid_retrieval"; identityDiversity: "UNKNOWN" | "low" | "moderate" | "high"; crossCameraVariation: "UNKNOWN" | "low" | "moderate" | "high"; crossDomainVariation: "UNKNOWN" | "low" | "moderate" | "high" };

export interface DatasetSemanticProfile { version: SchemaVersion; resourceId: string; snapshotRevision: string; generator: { profileBuilderVersion: string; samplingPolicyVersion: string; aggregationRuleVersion: string; configurationFingerprint: string; }; structuralSemantics: { tasks: TaskFamily[]; modalities: ("RGB" | "infrared" | "depth" | "thermal" | "multimodal" | "event")[]; sampleOrganization: "independent_image" | "image_sequence" | "video" | "mixed" | "UNKNOWN"; temporalStructure: "none" | "sequence" | "video" | "mixed" | "UNKNOWN"; supervision: ("class_label" | "bbox" | "track" | "semantic_mask" | "instance_mask" | "keypoints" | "action_label" | "temporal_segment" | "anomaly_label" | "identity" | "pair_ranking")[]; annotationSemantics: string[]; resourceRoles: ("media" | "annotation" | "metadata" | "documentation" | "split_definition")[]; resourceRelations: ("image_to_annotation" | "frame_to_track" | "video_to_clip_label" | "identity_to_camera" | "UNKNOWN")[]; }; contentSemantics: { objectCategories: string[]; environments: string[]; viewpoints: string[]; targetScale: string; objectDensity: string; occlusion: string; illumination: string[]; cameraMotion: string; targetMotion: string; taskSpecificSemantics: TaskSpecificSemantic[]; }; sampleRefs: SampleRef[]; observations: VisualObservation[]; samplingSummary: SamplingSummary; claims: SemanticClaim[]; evidence: Evidence[]; unresolved: UnresolvedField[]; generatedAt: string; }

export type TaskSpecificPreference =
  | { task: "image_classification"; longTail: ("low" | "moderate" | "high")[]; domainFeatures: string[] }
  | { task: "object_detection"; scaleDistribution: ("small_target_heavy" | "balanced" | "large_target_heavy")[]; occlusion: ("rare" | "moderate" | "frequent")[] }
  | { task: "multi_object_tracking"; temporalContinuity: ("sparse" | "continuous")[]; motionChallenge: ("low" | "moderate" | "high")[] }
  | { task: "semantic_segmentation" | "instance_segmentation"; boundaryComplexity: ("low" | "moderate" | "high")[]; smallObjectRatio: ("low" | "moderate" | "high")[] }
  | { task: "pose_keypoints"; keypointVisibility: ("low" | "moderate" | "high")[]; viewpointChallenge: ("low" | "moderate" | "high")[] }
  | { task: "action_video_understanding"; actionTypes: string[]; temporalDynamics: ("low" | "moderate" | "high")[] }
  | { task: "video_anomaly_detection"; anomalyTypes: string[]; temporalSparsity: ("low" | "moderate" | "high")[] }
  | { task: "reid_retrieval"; identityDiversity: ("low" | "moderate" | "high")[]; crossCameraVariation: ("low" | "moderate" | "high")[]; crossDomainVariation: ("low" | "moderate" | "high")[] };
export interface TaskSemanticProfile { version: SchemaVersion; id: string; revision: string; task: { value: TaskFamily; importance: "required"; }; required: { modalities: ("vision" | "RGB" | "infrared" | "depth" | "thermal" | "multimodal" | "event")[]; temporalStructure: "none" | "sequence" | "video" | "mixed"; supervision: ("classification_ground_truth" | "detection_ground_truth" | "tracking_ground_truth" | "semantic_segmentation_ground_truth" | "instance_segmentation_ground_truth" | "keypoints_ground_truth" | "action_ground_truth" | "anomaly_ground_truth" | "identity_ground_truth" | "ranking_ground_truth")[]; }; preferred: { objectCategories: string[]; environments: string[]; viewpoints: string[]; targetScale: ("tiny" | "small" | "medium" | "large" | "mixed")[]; objectDensity: ("low" | "medium" | "high" | "mixed")[]; occlusion: ("rare" | "moderate" | "frequent")[]; illumination: string[]; cameraMotion: ("static" | "moving")[]; targetMotion: ("slow" | "moderate" | "fast" | "mixed")[]; taskSpecificPreferences: TaskSpecificPreference[]; }; createdAt: string; }
export interface MatchFinding { field: string; outcome: "SATISFIED" | "MATCHED" | "CONFLICT" | "UNKNOWN" | "MISSING"; message: string; evidenceRefs: string[]; }
export interface DatasetTaskMatchResult { version: SchemaVersion; id: string; datasetResourceId: string; datasetProfileRevision: string; taskProfileId: string; taskProfileRevision: string; matchingRuleVersion: string; weightConfigurationFingerprint: string; compatibility: "COMPATIBLE" | "PARTIALLY_COMPATIBLE" | "INCOMPATIBLE" | "UNKNOWN"; suitabilityScore: number | null; defaultRankingEligible: boolean; satisfiedRequirements: MatchFinding[]; matchedPreferences: MatchFinding[]; conflicts: MatchFinding[]; unknowns: MatchFinding[]; explanation: string; evidenceRefs: string[]; generatedAt: string; }
export interface ErrorEnvelope { version: SchemaVersion; error: { code: ErrorCode; message: string; retryable: boolean; requestId?: string; jobId?: string; details?: { field: string; reason: string }[]; }; }
export interface Job { jobId: string; jobType: "profile" | "match"; status: JobStatus; createdAt: string; updatedAt: string; attempt: number; maxAttempts: number; idempotencyKey?: string; resultRef?: string; error?: ErrorEnvelope; }
export type ProfileJob = Job & { jobType: "profile"; };
export type MatchJob = Job & { jobType: "match"; };
export interface ProfileJobRequest { version: SchemaVersion; resourceId: string; snapshotRevision: string; profileSchemaVersion: SchemaVersion; configurationFingerprint: string; idempotencyKey?: string; }
export interface ProfileJobResponse { version: SchemaVersion; job: ProfileJob; }
export interface ProfileJobGetResponse { version: SchemaVersion; job: ProfileJob; profile: DatasetSemanticProfile | null; }
export interface ProfileJobCancelResponse { version: SchemaVersion; job: ProfileJob; }
export interface MatchJobRequest { version: SchemaVersion; taskProfileId: string; taskProfileRevision: string; datasetResourceIds: string[]; matchingRuleVersion: string; weightConfigurationFingerprint: string; idempotencyKey?: string; }
export interface MatchJobResponse { version: SchemaVersion; job: MatchJob; }
export interface MatchJobGetResponse { version: SchemaVersion; job: MatchJob; results: DatasetTaskMatchResult[]; }
export type TaskProfileCreateRequest = TaskSemanticProfile;
export interface TaskProfileCreateResponse { version: SchemaVersion; taskProfile: TaskSemanticProfile; }

export type SseEvent =
  | { version: SchemaVersion; jobId: string; eventId: number; timestamp: string; eventType: "stage"; data: { stage: Stage; status: "started" | "completed" | "skipped"; } }
  | { version: SchemaVersion; jobId: string; eventId: number; timestamp: string; eventType: "progress"; data: { stage: Stage; completed: number; total: number; } }
  | { version: SchemaVersion; jobId: string; eventId: number; timestamp: string; eventType: "evidence"; data: { evidence: Evidence; } }
  | { version: SchemaVersion; jobId: string; eventId: number; timestamp: string; eventType: "warning"; data: { code: "SAMPLE_FAILURE" | "INSUFFICIENT_COVERAGE" | "UNSUPPORTED_MEDIA" | "STALE_REVISION"; message: string; } }
  | { version: SchemaVersion; jobId: string; eventId: number; timestamp: string; eventType: "result"; data: { resultType: "dataset_semantic_profile" | "dataset_task_match_result"; resultId: string; } }
  | { version: SchemaVersion; jobId: string; eventId: number; timestamp: string; eventType: "error"; data: ErrorEnvelope; }
  | { version: SchemaVersion; jobId: string; eventId: number; timestamp: string; eventType: "end"; data: { status: "completed" | "failed" | "cancelled" | "superseded" | "partially_completed"; resultAvailable?: boolean; } };

export interface VlmConfiguration { version: SchemaVersion; provider: string; endpoint: string; apiKey: string; model: string; imageInput: { formats: ("jpeg" | "png" | "webp")[]; maxBytes: number; }; videoInput: { mode: "frames_only"; formats: ("mp4" | "webm" | "mov")[]; maxBytes: number; maxDurationMs: number; }; limits: { timeoutMs: number; maxCallsPerStage: number; maxCostUsdPerJob: number; }; retry: { maxAttempts: number; baseDelayMs: number; }; }
