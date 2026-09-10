#!/usr/bin/env python3
"""Dependency-free verifier for the dataset-management governance baseline."""

from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable


ACTIVE_WORK_PACKAGE_STATUSES = {"ASSIGNED", "IMPLEMENTED", "REPORT_SUBMITTED"}
WORK_PACKAGE_STATUSES = ACTIVE_WORK_PACKAGE_STATUSES | {
    "PLANNED",
    "ACCEPTED",
    "INTEGRATED",
    "BLOCKED",
    "REJECTED",
}
BASELINE_STATUSES = {"CANDIDATE", "FROZEN", "SUPERSEDED"}
REQUIREMENT_STATUSES = {"PLANNED", "IN_PROGRESS", "BLOCKED", "PASSED", "SUPERSEDED"}
ARTIFACT_STATES = {"VERIFIED", "PENDING", "BLOCKED"}
EXPECTED_REQUIREMENTS = {
    *(f"SRC-{number:02d}" for number in range(1, 24)),
    *(f"DER-{number:02d}" for number in range(1, 8)),
}
REQUIRED_TYPE_BY_ID = {
    requirement_id: (
        "SOURCE_REQUIREMENT" if requirement_id.startswith("SRC-") else "DERIVED_PRODUCT_REQUIREMENT"
    )
    for requirement_id in EXPECTED_REQUIREMENTS
}
SHA256_RE = re.compile(r"^[a-f0-9]{64}$")
REVISION_RE = re.compile(r"^[a-f0-9]{40}$")
SAFE_PATH_RE = re.compile(r"^[A-Za-z0-9._/-]+$")
SAFE_PATTERN_RE = re.compile(r"^[A-Za-z0-9._/*?\[\]-]+$")


@dataclass(frozen=True)
class Finding:
    code: str
    location: str
    message: str


class GovernanceVerifier:
    def __init__(self, repo_root: Path) -> None:
        self.repo_root = repo_root.resolve()
        self.findings: list[Finding] = []

    def verify(
        self,
        baseline_path: str,
        ownership_path: str,
        requirement_ledger_path: str | None = None,
        work_package_id: str | None = None,
        changed_paths: Iterable[str] = (),
    ) -> list[Finding]:
        baseline = self._load_json(baseline_path, "BASELINE_JSON_INVALID")
        ownership = self._load_json(ownership_path, "OWNERSHIP_JSON_INVALID")
        if not isinstance(baseline, dict) or not isinstance(ownership, dict):
            return self.findings

        self._verify_baseline_shape(baseline, baseline_path)
        self._verify_revision_and_artifacts(baseline, baseline_path)
        self._verify_contract_surface(baseline, baseline_path)
        self._verify_evidence_requirements(
            baseline,
            baseline_path,
            enforce_records=baseline.get("status") == "FROZEN",
        )
        self._verify_change_control(baseline, baseline_path)

        ledger_config = baseline.get("requirementStatusLedger")
        if not isinstance(ledger_config, dict):
            self._error("REQUIREMENT_LEDGER_CONFIG_INVALID", baseline_path, "requirementStatusLedger must be an object")
        else:
            selected_path = requirement_ledger_path or ledger_config.get("path")
            if isinstance(selected_path, str):
                self._verify_requirement_ledger(selected_path, ledger_config, baseline)
            else:
                self._error(
                    "REQUIREMENT_LEDGER_CONFIG_INVALID",
                    baseline_path,
                    "requirementStatusLedger.path must be a repository-relative path",
                )

        self._verify_ownership(ownership, ownership_path, baseline)
        if work_package_id is not None:
            self._verify_changed_paths(ownership, ownership_path, work_package_id, changed_paths)
        elif list(changed_paths):
            self._error(
                "WORK_PACKAGE_REQUIRED_FOR_CHANGED_PATHS",
                ownership_path,
                "changed paths require --work-package",
            )
        return self.findings

    def _load_json(self, relative_path: str, error_code: str) -> Any:
        path = self._safe_file(relative_path, error_code)
        if path is None:
            return None
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            self._error(error_code, relative_path, str(exc))
            return None

    def _verify_baseline_shape(self, baseline: dict[str, Any], location: str) -> None:
        required = {
            "schemaVersion",
            "baselineId",
            "status",
            "codeRevision",
            "controlledArtifacts",
            "contractSurface",
            "requirementStatusLedger",
            "freezePrerequisites",
            "evidenceRequirements",
            "changeControl",
        }
        self._require_keys(baseline, required, location, "BASELINE_FIELD_MISSING")
        if baseline.get("schemaVersion") != 1:
            self._error("BASELINE_SCHEMA_VERSION_INVALID", location, "schemaVersion must equal 1")
        if baseline.get("status") not in BASELINE_STATUSES:
            self._error("BASELINE_STATUS_INVALID", location, "status is not a supported baseline state")
        if not isinstance(baseline.get("baselineId"), str) or not re.fullmatch(
            r"governance_baseline_[a-z0-9_]+", baseline.get("baselineId", "")
        ):
            self._error("BASELINE_ID_INVALID", location, "baselineId is invalid")
        if not self._is_revision(baseline.get("codeRevision")):
            self._error("BASELINE_REVISION_INVALID", location, "codeRevision must be a full SHA-1 revision")
        for collection_name in ("controlledArtifacts", "freezePrerequisites"):
            if not isinstance(baseline.get(collection_name), list) or not baseline[collection_name]:
                self._error("BASELINE_COLLECTION_INVALID", location, f"{collection_name} must be a non-empty array")
        if baseline.get("status") == "FROZEN":
            approval = baseline.get("approval")
            if not isinstance(approval, dict):
                self._error("BASELINE_APPROVAL_MISSING", location, "FROZEN baseline requires approval")
            else:
                self._require_keys(
                    approval,
                    {"approvedAt", "approvedBy", "independentReviewer"},
                    f"{location}:approval",
                    "BASELINE_APPROVAL_MISSING",
                )
                if approval.get("approvedBy") == approval.get("independentReviewer"):
                    self._error(
                        "BASELINE_INDEPENDENT_REVIEW_INVALID",
                        f"{location}:approval",
                        "approvedBy and independentReviewer must differ",
                    )
        else:
            self._error(
                "BASELINE_NOT_FROZEN",
                location,
                f"baseline status is {baseline.get('status')!r}; FROZEN is required for dispatch",
            )

    def _verify_revision_and_artifacts(self, baseline: dict[str, Any], location: str) -> None:
        expected_revision = baseline.get("codeRevision")
        actual_revision = self._git_revision()
        if isinstance(expected_revision, str) and not self._revision_exists(expected_revision):
            self._error(
                "BASELINE_REVISION_UNAVAILABLE",
                location,
                f"codeRevision {expected_revision} is not available in this repository",
            )
        if actual_revision and not self._is_tracked_at_revision(actual_revision, location):
            self._error(
                "BASELINE_NOT_COMMITTED",
                location,
                "baseline file is not committed at current HEAD",
            )

        artifacts = baseline.get("controlledArtifacts")
        if not isinstance(artifacts, list):
            return
        seen_ids: set[str] = set()
        seen_paths: set[str] = set()
        for index, artifact in enumerate(artifacts):
            artifact_location = f"{location}:controlledArtifacts[{index}]"
            if not isinstance(artifact, dict):
                self._error("CONTROLLED_ARTIFACT_INVALID", artifact_location, "artifact must be an object")
                continue
            self._require_keys(
                artifact,
                {"id", "path", "sha256", "requiredForFreeze"},
                artifact_location,
                "CONTROLLED_ARTIFACT_FIELD_MISSING",
            )
            artifact_id = artifact.get("id")
            path_value = artifact.get("path")
            expected_hash = artifact.get("sha256")
            if not isinstance(artifact_id, str) or artifact_id in seen_ids:
                self._error("CONTROLLED_ARTIFACT_ID_INVALID", artifact_location, "id must be unique")
            else:
                seen_ids.add(artifact_id)
            if not isinstance(path_value, str) or path_value in seen_paths or not self._is_safe_path(path_value):
                self._error("CONTROLLED_ARTIFACT_PATH_INVALID", artifact_location, "path must be unique and safe")
                continue
            seen_paths.add(path_value)
            if not self._is_sha256(expected_hash):
                self._error("CONTROLLED_ARTIFACT_HASH_INVALID", artifact_location, "sha256 must be lowercase SHA-256")
                continue
            path = self._safe_file(path_value, "CONTROLLED_ARTIFACT_PATH_INVALID")
            if path is None:
                continue
            actual_hash = self._sha256(path)
            if actual_hash != expected_hash:
                self._error(
                    "CONTROLLED_ARTIFACT_HASH_MISMATCH",
                    path_value,
                    f"expected {expected_hash}, got {actual_hash}",
                )
            if actual_revision and not self._is_tracked_at_revision(actual_revision, path_value):
                self._error(
                    "CONTROLLED_ARTIFACT_NOT_COMMITTED",
                    path_value,
                    "artifact is not committed at current HEAD",
                )

        prerequisites = baseline.get("freezePrerequisites", [])
        if isinstance(prerequisites, list):
            for index, prerequisite in enumerate(prerequisites):
                prerequisite_location = f"{location}:freezePrerequisites[{index}]"
                if not isinstance(prerequisite, dict):
                    self._error("FREEZE_PREREQUISITE_INVALID", prerequisite_location, "prerequisite must be an object")
                    continue
                self._require_keys(
                    prerequisite,
                    {"id", "path", "reason"},
                    prerequisite_location,
                    "FREEZE_PREREQUISITE_INVALID",
                )
                required_path = prerequisite.get("path")
                if not isinstance(required_path, str):
                    self._error(
                        "FREEZE_PREREQUISITE_MISSING",
                        prerequisite_location,
                        "required freeze prerequisite path is invalid",
                    )
                else:
                    self._safe_file(required_path, "FREEZE_PREREQUISITE_MISSING")

    def _verify_evidence_requirements(
        self,
        baseline: dict[str, Any],
        location: str,
        enforce_records: bool,
    ) -> None:
        requirements = baseline.get("evidenceRequirements")
        if not isinstance(requirements, dict):
            self._error("EVIDENCE_REQUIREMENTS_INVALID", location, "evidenceRequirements must be an object")
            return
        for kind in ("phaseExecutionRecords", "workPackagePlans", "workPackageReports"):
            evidence_set = requirements.get(kind)
            evidence_location = f"{location}:evidenceRequirements.{kind}"
            if not isinstance(evidence_set, dict):
                self._error("EVIDENCE_REQUIREMENTS_INVALID", evidence_location, "evidence set must be an object")
                continue
            fields = evidence_set.get("requiredFields")
            records = evidence_set.get("records")
            if not isinstance(fields, list) or not all(isinstance(field, str) and field for field in fields):
                self._error("EVIDENCE_FIELDS_INVALID", evidence_location, "requiredFields must be a non-empty string array")
                continue
            if not isinstance(records, list):
                self._error("EVIDENCE_RECORDS_INVALID", evidence_location, "records must be an array")
                continue
            if not enforce_records:
                continue
            for record in records:
                if not isinstance(record, dict) or not isinstance(record.get("id"), str) or not isinstance(record.get("path"), str):
                    self._error("EVIDENCE_RECORDS_INVALID", evidence_location, "each record needs id and path")
                    continue
                record_path = record["path"]
                path = self._safe_file(record_path, "EVIDENCE_RECORD_MISSING")
                if path is None:
                    continue
                contents = path.read_text(encoding="utf-8")
                for field in fields:
                    if not re.search(rf"(?m)^\s*(?:[-*]\s+)?{re.escape(field)}\s*:\s*\S", contents):
                        self._error(
                            "EVIDENCE_FIELD_MISSING",
                            record_path,
                            f"{record['id']} is missing required field {field}",
                        )

    def _verify_contract_surface(self, baseline: dict[str, Any], location: str) -> None:
        config = baseline.get("contractSurface")
        if not isinstance(config, dict):
            self._error("CONTRACT_SURFACE_CONFIG_INVALID", location, "contractSurface must be an object")
            return
        self._require_keys(
            config,
            {"path", "schemaPath", "sha256", "schemaSha256"},
            f"{location}:contractSurface",
            "CONTRACT_SURFACE_CONFIG_INVALID",
        )
        surface_path = config.get("path")
        schema_path = config.get("schemaPath")
        if not isinstance(surface_path, str) or not isinstance(schema_path, str):
            self._error("CONTRACT_SURFACE_CONFIG_INVALID", location, "surface paths must be strings")
            return
        surface_file = self._safe_file(surface_path, "CONTRACT_SURFACE_MISSING")
        schema_file = self._safe_file(schema_path, "CONTRACT_SURFACE_SCHEMA_MISSING")
        if surface_file is None or schema_file is None:
            return
        if not self._is_sha256(config.get("sha256")) or self._sha256(surface_file) != config["sha256"]:
            self._error("CONTRACT_SURFACE_HASH_MISMATCH", surface_path, "surface manifest hash does not match baseline")
        if not self._is_sha256(config.get("schemaSha256")) or self._sha256(schema_file) != config["schemaSha256"]:
            self._error(
                "CONTRACT_SURFACE_SCHEMA_HASH_MISMATCH",
                schema_path,
                "surface schema hash does not match baseline",
            )
        surface = self._load_json(surface_path, "CONTRACT_SURFACE_JSON_INVALID")
        if not isinstance(surface, dict):
            return
        self._require_keys(
            surface,
            {"schemaVersion", "surfaceId", "coverageRoots", "artifacts"},
            surface_path,
            "CONTRACT_SURFACE_FIELD_MISSING",
        )
        if surface.get("schemaVersion") != 1:
            self._error("CONTRACT_SURFACE_SCHEMA_VERSION_INVALID", surface_path, "schemaVersion must equal 1")
        roots = surface.get("coverageRoots")
        artifacts = surface.get("artifacts")
        expected_roots = {"docs/semantic-contracts", "tests/semantic_contracts"}
        if not isinstance(roots, list) or set(roots) != expected_roots:
            self._error(
                "CONTRACT_SURFACE_ROOTS_INVALID",
                surface_path,
                "coverageRoots must exactly cover frozen contract docs and tests",
            )
            return
        if not isinstance(artifacts, list):
            self._error("CONTRACT_SURFACE_ARTIFACTS_INVALID", surface_path, "artifacts must be an array")
            return
        declared: set[str] = set()
        for index, artifact in enumerate(artifacts):
            artifact_location = f"{surface_path}:artifacts[{index}]"
            if not isinstance(artifact, dict):
                self._error("CONTRACT_SURFACE_ARTIFACT_INVALID", artifact_location, "artifact must be an object")
                continue
            path_value = artifact.get("path")
            hash_value = artifact.get("sha256")
            if not isinstance(path_value, str) or not self._is_safe_path(path_value) or path_value in declared:
                self._error("CONTRACT_SURFACE_ARTIFACT_PATH_INVALID", artifact_location, "path must be safe and unique")
                continue
            declared.add(path_value)
            if not self._is_sha256(hash_value):
                self._error("CONTRACT_SURFACE_ARTIFACT_HASH_INVALID", artifact_location, "sha256 is invalid")
                continue
            artifact_file = self._safe_file(path_value, "CONTRACT_SURFACE_ARTIFACT_MISSING")
            if artifact_file is not None and self._sha256(artifact_file) != hash_value:
                self._error(
                    "CONTRACT_SURFACE_ARTIFACT_HASH_MISMATCH",
                    path_value,
                    "frozen contract artifact hash does not match",
                )
        actual: set[str] = set()
        for root_value in roots:
            root = self.repo_root / root_value
            if not root.is_dir():
                self._error("CONTRACT_SURFACE_ROOT_MISSING", root_value, "coverage root is missing")
                continue
            actual.update(
                item.relative_to(self.repo_root).as_posix()
                for item in root.rglob("*")
                if item.is_file()
            )
        for path_value in sorted(actual - declared):
            self._error(
                "CONTROLLED_ARTIFACT_COVERAGE_MISSING",
                path_value,
                "frozen contract artifact is not declared in contract surface",
            )
        for path_value in sorted(declared - actual):
            self._error(
                "CONTRACT_SURFACE_ARTIFACT_EXTRA",
                path_value,
                "contract surface declares an artifact outside its coverage roots",
            )

    def _verify_requirement_ledger(
        self,
        ledger_path: str,
        ledger_config: dict[str, Any],
        baseline: dict[str, Any],
    ) -> None:
        path = self._safe_file(ledger_path, "REQUIREMENT_LEDGER_MISSING")
        if path is None:
            return
        configured_hash = ledger_config.get("sha256")
        if not self._is_sha256(configured_hash):
            self._error("REQUIREMENT_LEDGER_HASH_INVALID", ledger_path, "configured sha256 is invalid")
        elif self._sha256(path) != configured_hash:
            self._error("REQUIREMENT_LEDGER_HASH_MISMATCH", ledger_path, "ledger hash does not match baseline")
        schema_path = ledger_config.get("schemaPath")
        schema_hash = ledger_config.get("schemaSha256")
        schema_file = self._safe_file(schema_path, "REQUIREMENT_LEDGER_SCHEMA_MISSING") if isinstance(schema_path, str) else None
        if schema_file is not None:
            if not self._is_sha256(schema_hash):
                self._error("REQUIREMENT_LEDGER_SCHEMA_HASH_INVALID", ledger_path, "configured schema SHA-256 is invalid")
            elif self._sha256(schema_file) != schema_hash:
                self._error(
                    "REQUIREMENT_LEDGER_SCHEMA_HASH_MISMATCH",
                    str(schema_path),
                    "requirement ledger schema hash does not match baseline",
                )

        ledger = self._load_json(ledger_path, "REQUIREMENT_LEDGER_JSON_INVALID")
        if not isinstance(ledger, dict):
            return
        required_top_level = {"schemaVersion", "ledgerId", "baselineId", "requirements"}
        self._require_keys(ledger, required_top_level, ledger_path, "REQUIREMENT_LEDGER_FIELD_MISSING")
        if ledger.get("schemaVersion") != 1:
            self._error("REQUIREMENT_LEDGER_SCHEMA_VERSION_INVALID", ledger_path, "schemaVersion must equal 1")
        if ledger.get("baselineId") != baseline.get("baselineId"):
            self._error("REQUIREMENT_LEDGER_BASELINE_MISMATCH", ledger_path, "ledger baselineId must equal baselineId")
        requirements = ledger.get("requirements")
        if not isinstance(requirements, list):
            self._error("REQUIREMENT_LEDGER_REQUIREMENTS_INVALID", ledger_path, "requirements must be an array")
            return

        seen: set[str] = set()
        for index, requirement in enumerate(requirements):
            requirement_location = f"{ledger_path}:requirements[{index}]"
            if not isinstance(requirement, dict):
                self._error("REQUIREMENT_RECORD_INVALID", requirement_location, "requirement must be an object")
                continue
            self._require_keys(
                requirement,
                {
                    "requirementId",
                    "requirementType",
                    "status",
                    "owner",
                    "independentAcceptor",
                    "inputArtifacts",
                    "outputArtifacts",
                    "acceptanceEvidence",
                },
                requirement_location,
                "REQUIREMENT_RECORD_FIELD_MISSING",
            )
            requirement_id = requirement.get("requirementId")
            if not isinstance(requirement_id, str) or requirement_id not in EXPECTED_REQUIREMENTS:
                self._error("REQUIREMENT_ID_INVALID", requirement_location, "requirementId is unknown")
                continue
            if requirement_id in seen:
                self._error("REQUIREMENT_ID_DUPLICATE", requirement_location, f"{requirement_id} is duplicated")
            seen.add(requirement_id)
            if requirement.get("requirementType") != REQUIRED_TYPE_BY_ID[requirement_id]:
                self._error(
                    "REQUIREMENT_TYPE_MISMATCH",
                    requirement_location,
                    f"{requirement_id} has an invalid requirementType",
                )
            status = requirement.get("status")
            if status not in REQUIREMENT_STATUSES:
                self._error("REQUIREMENT_STATUS_INVALID", requirement_location, "status is invalid")
            owner = requirement.get("owner")
            acceptor = requirement.get("independentAcceptor")
            if not isinstance(owner, str) or not owner:
                self._error("REQUIREMENT_OWNER_INVALID", requirement_location, "owner is required")
            if not isinstance(acceptor, str) or not acceptor:
                self._error("REQUIREMENT_ACCEPTOR_INVALID", requirement_location, "independentAcceptor is required")
            if status == "PASSED" and owner == acceptor:
                self._error(
                    "REQUIREMENT_INDEPENDENT_ACCEPTOR_INVALID",
                    requirement_location,
                    "PASSED requirement requires an independent acceptor",
                )
            all_artifacts_verified = True
            for artifact_group in ("inputArtifacts", "outputArtifacts", "acceptanceEvidence"):
                artifacts = requirement.get(artifact_group)
                if not isinstance(artifacts, list) or not artifacts:
                    self._error(
                        "REQUIREMENT_ARTIFACT_GROUP_INVALID",
                        requirement_location,
                        f"{artifact_group} must be a non-empty array",
                    )
                    all_artifacts_verified = False
                    continue
                for artifact_index, artifact in enumerate(artifacts):
                    if not self._verify_requirement_artifact(
                        artifact,
                        f"{requirement_location}:{artifact_group}[{artifact_index}]",
                    ):
                        all_artifacts_verified = False
            if status == "PASSED" and not all_artifacts_verified:
                self._error(
                    "REQUIREMENT_PASSED_WITH_UNVERIFIED_ARTIFACTS",
                    requirement_location,
                    "PASSED requirement needs verified input, output, and evidence artifacts",
                )
        missing = sorted(EXPECTED_REQUIREMENTS - seen)
        unexpected = sorted(seen - EXPECTED_REQUIREMENTS)
        if missing:
            self._error("REQUIREMENT_RECORD_MISSING", ledger_path, f"missing records: {', '.join(missing)}")
        if unexpected:
            self._error("REQUIREMENT_ID_INVALID", ledger_path, f"unexpected records: {', '.join(unexpected)}")

    def _verify_requirement_artifact(self, artifact: Any, location: str) -> bool:
        if not isinstance(artifact, dict):
            self._error("REQUIREMENT_ARTIFACT_INVALID", location, "artifact must be an object")
            return False
        self._require_keys(artifact, {"path", "sha256", "state"}, location, "REQUIREMENT_ARTIFACT_FIELD_MISSING")
        path_value = artifact.get("path")
        state = artifact.get("state")
        value = artifact.get("sha256")
        if not isinstance(path_value, str) or not self._is_safe_path(path_value):
            self._error("REQUIREMENT_ARTIFACT_PATH_INVALID", location, "artifact path is invalid")
            return False
        if state not in ARTIFACT_STATES:
            self._error("REQUIREMENT_ARTIFACT_STATE_INVALID", location, "artifact state is invalid")
            return False
        if state == "VERIFIED":
            if not self._is_sha256(value):
                self._error("REQUIREMENT_ARTIFACT_HASH_INVALID", location, "VERIFIED artifact needs SHA-256")
                return False
            file_path = self._safe_file(path_value, "REQUIREMENT_ARTIFACT_MISSING")
            if file_path is None:
                return False
            if self._sha256(file_path) != value:
                self._error("REQUIREMENT_ARTIFACT_HASH_MISMATCH", path_value, "artifact hash does not match")
                return False
            return True
        if value is not None:
            self._error(
                "REQUIREMENT_ARTIFACT_PENDING_HASH_INVALID",
                location,
                "PENDING or BLOCKED artifact must use sha256: null",
            )
        return False

    def _verify_change_control(self, baseline: dict[str, Any], location: str) -> None:
        change_control = baseline.get("changeControl")
        if not isinstance(change_control, dict):
            self._error("CHANGE_CONTROL_INVALID", location, "changeControl must be an object")
            return
        self._require_keys(
            change_control,
            {"recordDirectory", "recordFilenamePattern", "schemaPath"},
            f"{location}:changeControl",
            "CHANGE_CONTROL_INVALID",
        )
        directory_value = change_control.get("recordDirectory")
        pattern = change_control.get("recordFilenamePattern")
        schema_value = change_control.get("schemaPath")
        if not isinstance(directory_value, str) or not self._is_safe_path(directory_value):
            self._error("CHANGE_RECORD_DIRECTORY_INVALID", location, "recordDirectory must be safe")
            return
        directory = self.repo_root / directory_value
        if not directory.is_dir():
            self._error("CHANGE_RECORD_DIRECTORY_MISSING", directory_value, "change-record directory is missing")
            return
        if not isinstance(pattern, str):
            self._error("CHANGE_RECORD_PATTERN_INVALID", location, "recordFilenamePattern must be a string")
            return
        try:
            filename_re = re.compile(pattern)
        except re.error as exc:
            self._error("CHANGE_RECORD_PATTERN_INVALID", location, str(exc))
            return
        if not isinstance(schema_value, str) or self._safe_file(schema_value, "CHANGE_RECORD_SCHEMA_MISSING") is None:
            self._error("CHANGE_RECORD_SCHEMA_MISSING", location, "change-record schema is missing")
        for item in sorted(directory.rglob("*")):
            if item.is_dir():
                continue
            relative = item.relative_to(directory).as_posix()
            if "/" in relative or item.name not in {"README.md", ".gitkeep"} and not filename_re.fullmatch(item.name):
                self._error(
                    "CHANGE_RECORD_LOCATION_INVALID",
                    item.relative_to(self.repo_root).as_posix(),
                    "only README.md, .gitkeep, or CR-*.json files may appear directly in the change-record directory",
                )
                continue
            if filename_re.fullmatch(item.name):
                record = self._load_json(item.relative_to(self.repo_root).as_posix(), "CHANGE_RECORD_JSON_INVALID")
                if isinstance(record, dict):
                    self._require_keys(
                        record,
                        {
                            "schemaVersion",
                            "changeId",
                            "status",
                            "compatibility",
                            "proposer",
                            "independentReviewer",
                            "mainAgentApprover",
                            "affectedRequirementIds",
                            "affectedArtifacts",
                            "migration",
                            "rollback",
                            "testPlan",
                            "reacceptanceScope",
                        },
                        item.relative_to(self.repo_root).as_posix(),
                        "CHANGE_RECORD_FIELD_MISSING",
                    )
                    if record.get("changeId") != item.stem:
                        self._error(
                            "CHANGE_RECORD_ID_FILENAME_MISMATCH",
                            item.relative_to(self.repo_root).as_posix(),
                            "changeId must equal the CR filename stem",
                        )

    def _verify_ownership(
        self,
        ownership: dict[str, Any],
        location: str,
        baseline: dict[str, Any],
    ) -> None:
        required = {
            "schemaVersion",
            "baselineId",
            "baseRevision",
            "sharedPaths",
            "globalForbiddenPaths",
            "workPackages",
        }
        self._require_keys(ownership, required, location, "OWNERSHIP_FIELD_MISSING")
        if ownership.get("schemaVersion") != 1:
            self._error("OWNERSHIP_SCHEMA_VERSION_INVALID", location, "schemaVersion must equal 1")
        if ownership.get("baselineId") != baseline.get("baselineId"):
            self._error("OWNERSHIP_BASELINE_MISMATCH", location, "baselineId must match governance baseline")
        if ownership.get("baseRevision") != baseline.get("codeRevision"):
            self._error("OWNERSHIP_REVISION_MISMATCH", location, "baseRevision must match codeRevision")
        shared = ownership.get("sharedPaths")
        forbidden = ownership.get("globalForbiddenPaths")
        work_packages = ownership.get("workPackages")
        if not self._valid_pattern_array(shared):
            self._error("SHARED_PATHS_INVALID", location, "sharedPaths must be safe unique patterns")
            shared = []
        if not self._valid_pattern_array(forbidden):
            self._error("GLOBAL_FORBIDDEN_PATHS_INVALID", location, "globalForbiddenPaths must be safe unique patterns")
            forbidden = []
        if not isinstance(work_packages, list):
            self._error("WORK_PACKAGES_INVALID", location, "workPackages must be an array")
            return

        active_write_sets: list[tuple[str, str]] = []
        seen_ids: set[str] = set()
        for index, work_package in enumerate(work_packages):
            package_location = f"{location}:workPackages[{index}]"
            if not isinstance(work_package, dict):
                self._error("WORK_PACKAGE_INVALID", package_location, "work package must be an object")
                continue
            required_package_fields = {
                "workPackageId",
                "phase",
                "status",
                "ownedPaths",
                "readOnlyPaths",
                "generatedPaths",
                "forbiddenPaths",
                "baseRevision",
                "responsibleAgent",
                "modelTier",
                "evidencePaths",
            }
            self._require_keys(work_package, required_package_fields, package_location, "WORK_PACKAGE_FIELD_MISSING")
            package_id = work_package.get("workPackageId")
            if not isinstance(package_id, str) or package_id in seen_ids:
                self._error("WORK_PACKAGE_ID_INVALID", package_location, "workPackageId must be unique")
                continue
            seen_ids.add(package_id)
            if work_package.get("status") not in WORK_PACKAGE_STATUSES:
                self._error("WORK_PACKAGE_STATUS_INVALID", package_location, "status is invalid")
            if work_package.get("baseRevision") != baseline.get("codeRevision"):
                self._error("WORK_PACKAGE_REVISION_MISMATCH", package_location, "baseRevision must match baseline")
            if work_package.get("modelTier") not in {"Luna Medium", "Terra Medium"}:
                self._error("WORK_PACKAGE_MODEL_TIER_INVALID", package_location, "modelTier must be Luna Medium or Terra Medium")
            for field_name in ("ownedPaths", "readOnlyPaths", "generatedPaths", "forbiddenPaths", "evidencePaths"):
                if not self._valid_pattern_array(work_package.get(field_name)):
                    self._error(
                        "WORK_PACKAGE_PATH_SET_INVALID",
                        package_location,
                        f"{field_name} must be a safe unique pattern array",
                    )
            if work_package.get("status") in ACTIVE_WORK_PACKAGE_STATUSES:
                for evidence_path in work_package.get("evidencePaths", []):
                    self._safe_file(evidence_path, "WORK_PACKAGE_EVIDENCE_MISSING")
                for write_pattern in [
                    *work_package.get("ownedPaths", []),
                    *work_package.get("generatedPaths", []),
                ]:
                    for prohibited_pattern in [*shared, *forbidden, *work_package.get("forbiddenPaths", [])]:
                        if self._patterns_may_overlap(write_pattern, prohibited_pattern):
                            self._error(
                                "WORK_PACKAGE_PROHIBITED_PATH_DECLARATION",
                                package_location,
                                f"{write_pattern} intersects prohibited {prohibited_pattern}",
                            )
                    for existing_id, existing_pattern in active_write_sets:
                        if self._patterns_may_overlap(write_pattern, existing_pattern):
                            self._error(
                                "ACTIVE_WORK_PACKAGE_PATH_OVERLAP",
                                package_location,
                                f"{package_id}:{write_pattern} intersects {existing_id}:{existing_pattern}",
                            )
                    active_write_sets.append((package_id, write_pattern))

    def _verify_changed_paths(
        self,
        ownership: dict[str, Any],
        location: str,
        work_package_id: str,
        changed_paths: Iterable[str],
    ) -> None:
        packages = ownership.get("workPackages")
        if not isinstance(packages, list):
            return
        package = next(
            (
                value
                for value in packages
                if isinstance(value, dict) and value.get("workPackageId") == work_package_id
            ),
            None,
        )
        if package is None:
            self._error("WORK_PACKAGE_NOT_FOUND", location, f"{work_package_id} is not declared")
            return
        if package.get("status") not in ACTIVE_WORK_PACKAGE_STATUSES:
            self._error(
                "WORK_PACKAGE_NOT_ACTIVE",
                location,
                f"{work_package_id} status {package.get('status')!r} is not active",
            )
        writable = [*package.get("ownedPaths", []), *package.get("generatedPaths", [])]
        prohibited = [
            *ownership.get("sharedPaths", []),
            *ownership.get("globalForbiddenPaths", []),
            *package.get("forbiddenPaths", []),
        ]
        for changed_path in changed_paths:
            if not self._is_safe_path(changed_path):
                self._error("CHANGED_PATH_INVALID", changed_path, "changed path must be safe and repository-relative")
                continue
            if any(self._matches(pattern, changed_path) for pattern in prohibited):
                self._error(
                    "CHANGED_PATH_PROHIBITED",
                    changed_path,
                    f"{work_package_id} must not modify this path",
                )
                continue
            if not any(self._matches(pattern, changed_path) for pattern in writable):
                self._error(
                    "CHANGED_PATH_UNDECLARED",
                    changed_path,
                    f"{work_package_id} does not own or generate this path",
                )

    def _safe_file(self, relative_path: str, missing_code: str) -> Path | None:
        if not self._is_safe_path(relative_path):
            self._error(missing_code, relative_path, "path is not a safe repository-relative path")
            return None
        candidate = self.repo_root / relative_path
        if not candidate.is_file():
            self._error(missing_code, relative_path, "file does not exist")
            return None
        return candidate

    def _git_revision(self) -> str | None:
        try:
            result = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=self.repo_root,
                capture_output=True,
                check=True,
                text=True,
            )
        except (OSError, subprocess.CalledProcessError) as exc:
            self._error("GIT_REVISION_UNAVAILABLE", str(self.repo_root), str(exc))
            return None
        revision = result.stdout.strip()
        if not self._is_revision(revision):
            self._error("GIT_REVISION_UNAVAILABLE", str(self.repo_root), "git returned an invalid revision")
            return None
        return revision

    def _is_tracked_at_revision(self, revision: str, relative_path: str) -> bool:
        if not self._is_safe_path(relative_path) or not self._is_revision(revision):
            return False
        result = subprocess.run(
            ["git", "cat-file", "-e", f"{revision}:{relative_path}"],
            cwd=self.repo_root,
            capture_output=True,
            check=False,
            text=True,
        )
        return result.returncode == 0

    def _revision_exists(self, revision: str) -> bool:
        if not self._is_revision(revision):
            return False
        result = subprocess.run(
            ["git", "cat-file", "-e", f"{revision}^{{commit}}"],
            cwd=self.repo_root,
            capture_output=True,
            check=False,
            text=True,
        )
        return result.returncode == 0

    @staticmethod
    def _sha256(path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for block in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(block)
        return digest.hexdigest()

    @staticmethod
    def _is_sha256(value: Any) -> bool:
        return isinstance(value, str) and SHA256_RE.fullmatch(value) is not None

    @staticmethod
    def _is_revision(value: Any) -> bool:
        return isinstance(value, str) and REVISION_RE.fullmatch(value) is not None

    @staticmethod
    def _is_safe_path(value: Any) -> bool:
        if not isinstance(value, str) or not value or not SAFE_PATH_RE.fullmatch(value):
            return False
        path = PurePosixPath(value)
        return not path.is_absolute() and ".." not in path.parts

    @staticmethod
    def _is_safe_pattern(value: Any) -> bool:
        if not isinstance(value, str) or not value or not SAFE_PATTERN_RE.fullmatch(value):
            return False
        return not value.startswith("/") and ".." not in PurePosixPath(value).parts

    def _valid_pattern_array(self, value: Any) -> bool:
        return isinstance(value, list) and len(value) == len(set(value)) and all(
            self._is_safe_pattern(item) for item in value
        )

    @staticmethod
    def _matches(pattern: str, path: str) -> bool:
        return fnmatch.fnmatchcase(path, pattern)

    def _patterns_may_overlap(self, left: str, right: str) -> bool:
        if left == right:
            return True
        left_prefix = self._static_prefix(left)
        right_prefix = self._static_prefix(right)
        if not left_prefix or not right_prefix:
            return True
        return (
            left_prefix == right_prefix
            or left_prefix.startswith(right_prefix + "/")
            or right_prefix.startswith(left_prefix + "/")
        )

    @staticmethod
    def _static_prefix(pattern: str) -> str:
        parts: list[str] = []
        for part in PurePosixPath(pattern).parts:
            if any(character in part for character in "*?["):
                break
            parts.append(part)
        return "/".join(parts)

    def _require_keys(
        self,
        value: dict[str, Any],
        required: set[str],
        location: str,
        code: str,
    ) -> None:
        for field in sorted(required - set(value)):
            self._error(code, location, f"missing {field}")

    def _error(self, code: str, location: str, message: str) -> None:
        self.findings.append(Finding(code=code, location=location, message=message))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Verify the dataset-management governance baseline.")
    parser.add_argument("--repo-root", default=".", help="repository root")
    parser.add_argument(
        "--baseline",
        default="docs/governance/governance-baseline.json",
        help="repository-relative baseline manifest",
    )
    parser.add_argument(
        "--ownership",
        default="docs/governance/ownership-manifest.json",
        help="repository-relative ownership manifest",
    )
    parser.add_argument(
        "--requirement-ledger",
        default=None,
        help="optional repository-relative requirement status ledger override",
    )
    parser.add_argument("--work-package", default=None, help="work package used for changed paths")
    parser.add_argument(
        "--changed-path",
        action="append",
        default=[],
        help="repository-relative changed path; repeat for every changed path",
    )
    parser.add_argument("--json", action="store_true", help="emit a JSON report")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    verifier = GovernanceVerifier(Path(args.repo_root))
    findings = verifier.verify(
        baseline_path=args.baseline,
        ownership_path=args.ownership,
        requirement_ledger_path=args.requirement_ledger,
        work_package_id=args.work_package,
        changed_paths=args.changed_path,
    )
    if args.json:
        print(
            json.dumps(
                {
                    "ok": not findings,
                    "errorCount": len(findings),
                    "errors": [asdict(finding) for finding in findings],
                },
                ensure_ascii=True,
                sort_keys=True,
            )
        )
    elif findings:
        for finding in findings:
            print(f"{finding.code}: {finding.location}: {finding.message}")
        print(f"governance verification failed with {len(findings)} finding(s)")
    else:
        print("governance verification passed")
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
