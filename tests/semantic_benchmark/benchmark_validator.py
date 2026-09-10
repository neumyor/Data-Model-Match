"""Pure, deterministic validators for semantic benchmark governance assets.

The JSON Schemas describe local field shapes.  This module enforces the
cross-record invariants that JSON Schema cannot express without implementation
specific extensions, such as count equality, split closure, and reference
closure.
"""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from datetime import datetime


_ID_PATTERNS = {
    "dataset": re.compile(r"^ds_[a-z0-9_]+$"),
    "query": re.compile(r"^q_[a-z0-9_]+$"),
    "ground_truth": re.compile(r"^gt_[a-z0-9_.-]+$"),
    "perturbation": re.compile(r"^perturbation_[a-z0-9_.-]+$"),
}
_SPLITS = ("development", "calibration", "test")
_COUNT_RULES = (
    ("datasetCount", "datasets", 15, 30),
    ("taskFamilyCount", "taskFamilies", 4, 6),
    ("taskQueryCount", "taskQueries", 50, 100),
)


def validate_benchmark_manifest(
    manifest: Mapping[str, object],
    *,
    ground_truth_versions: Iterable[str],
    perturbation_rule_ids: Iterable[str],
) -> list[str]:
    """Return deterministic validation errors; an empty list means accepted.

    ``ground_truth_versions`` and ``perturbation_rule_ids`` are explicit
    catalogs supplied by the caller.  The validator does not infer that a
    version exists merely because its string has a valid shape.
    """

    errors: list[str] = []
    if not isinstance(manifest, Mapping):
        return ["$: manifest must be an object"]

    ground_truth_catalog = set(ground_truth_versions)
    perturbation_catalog = set(perturbation_rule_ids)
    datasets = manifest.get("datasets")
    task_families = manifest.get("taskFamilies")
    task_queries = manifest.get("taskQueries")
    split = manifest.get("split")

    for count_key, array_key, minimum, maximum in _COUNT_RULES:
        count = manifest.get(count_key)
        values = manifest.get(array_key)
        if not isinstance(count, int) or isinstance(count, bool):
            errors.append(f"$.{count_key}: must be an integer")
            continue
        if not isinstance(values, list):
            errors.append(f"$.{array_key}: must be an array")
            continue
        if not minimum <= count <= maximum:
            errors.append(f"$.{count_key}: must be between {minimum} and {maximum}")
        if count != len(values):
            errors.append(
                f"$.{count_key}: {count} does not equal $.{array_key} length {len(values)}"
            )

    if not isinstance(task_families, list):
        errors.append("$.taskFamilies: must be an array")
        task_families = []
    if len(set(task_families)) != len(task_families):
        errors.append("$.taskFamilies: values must be unique")
    task_family_set = set(task_families)

    dataset_ids: list[str] = []
    if isinstance(datasets, list):
        for index, dataset in enumerate(datasets):
            path = f"$.datasets[{index}]"
            if not isinstance(dataset, Mapping):
                errors.append(f"{path}: must be an object")
                continue
            dataset_id = dataset.get("datasetId")
            if not isinstance(dataset_id, str) or not _ID_PATTERNS["dataset"].fullmatch(dataset_id):
                errors.append(f"{path}.datasetId: invalid or missing dataset ID")
            else:
                dataset_ids.append(dataset_id)
            _validate_reference_fields(
                dataset,
                path,
                ground_truth_catalog,
                perturbation_catalog,
                errors,
            )
            families = dataset.get("taskFamilies")
            if isinstance(families, list):
                if not set(families) <= task_family_set:
                    errors.append(f"{path}.taskFamilies: contains family absent from taskFamilies")
                if len(set(families)) != len(families):
                    errors.append(f"{path}.taskFamilies: values must be unique")

    _append_duplicate_error(dataset_ids, "$.datasets[*].datasetId", errors)

    query_ids: list[str] = []
    if isinstance(task_queries, list):
        for index, query in enumerate(task_queries):
            path = f"$.taskQueries[{index}]"
            if not isinstance(query, Mapping):
                errors.append(f"{path}: must be an object")
                continue
            query_id = query.get("queryId")
            if not isinstance(query_id, str) or not _ID_PATTERNS["query"].fullmatch(query_id):
                errors.append(f"{path}.queryId: invalid or missing query ID")
            else:
                query_ids.append(query_id)
            _validate_reference_fields(
                query,
                path,
                ground_truth_catalog,
                perturbation_catalog,
                errors,
            )
            if query.get("taskFamily") not in task_family_set:
                errors.append(f"{path}.taskFamily: absent from taskFamilies")

    _append_duplicate_error(query_ids, "$.taskQueries[*].queryId", errors)
    _validate_split(split, set(dataset_ids), set(query_ids), errors)
    return sorted(set(errors))


def validate_threshold_manifest(manifest: Mapping[str, object]) -> list[str]:
    """Validate threshold state/evidence combinations not expressible locally."""

    errors: list[str] = []
    status = manifest.get("status")
    calibration = manifest.get("calibrationEvidence")
    approval = manifest.get("approval")
    protocol = manifest.get("calibrationProtocol")

    if status not in {
        "preliminary_pending_independent_calibration",
        "final_approved",
    }:
        errors.append("$.status: unsupported threshold state")
        return errors
    if not isinstance(calibration, Mapping):
        errors.append("$.calibrationEvidence: must be an object")
        calibration = {}
    if not isinstance(approval, Mapping):
        errors.append("$.approval: must be an object")
        approval = {}
    if not isinstance(protocol, Mapping):
        errors.append("$.calibrationProtocol: must be an object")
        protocol = {}

    if protocol.get("pilotManifestId") != manifest.get("benchmarkManifestId"):
        errors.append("$.calibrationProtocol.pilotManifestId: must equal benchmarkManifestId")

    if status == "preliminary_pending_independent_calibration":
        if calibration.get("status") != "pending":
            errors.append("$.calibrationEvidence.status: preliminary state requires pending")
        if approval.get("status") != "pending":
            errors.append("$.approval.status: preliminary state requires pending")
        for field in ("reportId", "reportSha256", "completedAt"):
            if calibration.get(field) is not None:
                errors.append(f"$.calibrationEvidence.{field}: must be null while pending")
        for field in ("approverId", "approvedAt", "changeRecordId"):
            if approval.get(field) is not None:
                errors.append(f"$.approval.{field}: must be null while pending")
    else:
        if protocol.get("independentCalibratorStatus") != "completed":
            errors.append(
                "$.calibrationProtocol.independentCalibratorStatus: "
                "final state requires completed"
            )
        _require_pattern(
            protocol.get("independentCalibrator"),
            re.compile(r"^calibrator_[a-z0-9_]+$"),
            "$.calibrationProtocol.independentCalibrator",
            errors,
        )
        if calibration.get("status") != "completed":
            errors.append("$.calibrationEvidence.status: final state requires completed")
        if approval.get("status") != "approved":
            errors.append("$.approval.status: final state requires approved")
        _require_pattern(
            calibration.get("reportId"),
            re.compile(r"^calibration_[a-z0-9_]+$"),
            "$.calibrationEvidence.reportId",
            errors,
        )
        _require_pattern(
            calibration.get("reportSha256"),
            re.compile(r"^[a-f0-9]{64}$"),
            "$.calibrationEvidence.reportSha256",
            errors,
        )
        _require_iso_datetime(calibration.get("completedAt"), "$.calibrationEvidence.completedAt", errors)
        _require_pattern(
            approval.get("approverId"),
            re.compile(r"^approver_[a-z0-9_]+$"),
            "$.approval.approverId",
            errors,
        )
        _require_iso_datetime(approval.get("approvedAt"), "$.approval.approvedAt", errors)
        _require_pattern(
            approval.get("changeRecordId"),
            re.compile(r"^CR-[0-9]{4,}$"),
            "$.approval.changeRecordId",
            errors,
        )
    return sorted(set(errors))


def _validate_reference_fields(
    item: Mapping[str, object],
    path: str,
    ground_truth_versions: set[str],
    perturbation_rule_ids: set[str],
    errors: list[str],
) -> None:
    ground_truth = item.get("groundTruthVersion")
    if not isinstance(ground_truth, str) or not _ID_PATTERNS["ground_truth"].fullmatch(ground_truth):
        errors.append(f"{path}.groundTruthVersion: invalid or missing reference")
    elif ground_truth not in ground_truth_versions:
        errors.append(f"{path}.groundTruthVersion: unresolved reference {ground_truth}")
    perturbations = item.get("perturbationVersions")
    if not isinstance(perturbations, list) or not perturbations:
        errors.append(f"{path}.perturbationVersions: must contain at least one reference")
        return
    if len(set(perturbations)) != len(perturbations):
        errors.append(f"{path}.perturbationVersions: values must be unique")
    for index, perturbation in enumerate(perturbations):
        if not isinstance(perturbation, str) or not _ID_PATTERNS["perturbation"].fullmatch(perturbation):
            errors.append(f"{path}.perturbationVersions[{index}]: invalid reference")
        elif perturbation not in perturbation_rule_ids:
            errors.append(f"{path}.perturbationVersions[{index}]: unresolved reference {perturbation}")


def _validate_split(
    split: object,
    dataset_ids: set[str],
    query_ids: set[str],
    errors: list[str],
) -> None:
    if not isinstance(split, Mapping):
        errors.append("$.split: must be an object")
        return
    for kind, expected_ids in (("datasetIds", dataset_ids), ("queryIds", query_ids)):
        groups = split.get(kind)
        if not isinstance(groups, Mapping):
            errors.append(f"$.split.{kind}: must be an object")
            continue
        seen: set[str] = set()
        for split_name in _SPLITS:
            values = groups.get(split_name)
            path = f"$.split.{kind}.{split_name}"
            if not isinstance(values, list) or not values:
                errors.append(f"{path}: must be a non-empty array")
                continue
            if len(set(values)) != len(values):
                errors.append(f"{path}: values must be unique")
            unknown = set(values) - expected_ids
            if unknown:
                errors.append(f"{path}: contains unknown IDs {sorted(unknown)}")
            overlap = seen & set(values)
            if overlap:
                errors.append(f"{path}: overlaps another split {sorted(overlap)}")
            seen.update(values)
        if seen != expected_ids:
            errors.append(
                f"$.split.{kind}: union must cover exactly all declared IDs "
                f"(missing={sorted(expected_ids - seen)}, extra={sorted(seen - expected_ids)})"
            )


def _append_duplicate_error(values: list[str], path: str, errors: list[str]) -> None:
    if len(values) != len(set(values)):
        errors.append(f"{path}: values must be unique")


def _require_pattern(value: object, pattern: re.Pattern[str], path: str, errors: list[str]) -> None:
    if not isinstance(value, str) or not pattern.fullmatch(value):
        errors.append(f"{path}: invalid or missing value")


def _require_iso_datetime(value: object, path: str, errors: list[str]) -> None:
    if not isinstance(value, str):
        errors.append(f"{path}: invalid or missing date-time")
        return
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.append(f"{path}: invalid date-time")
