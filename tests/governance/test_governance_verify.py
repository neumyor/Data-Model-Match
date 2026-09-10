"""Tests for the dependency-free governance baseline verifier."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[2]
VERIFIER_PATH = PROJECT_ROOT / "docs" / "governance" / "governance_verify.py"
SPEC = importlib.util.spec_from_file_location("governance_verify", VERIFIER_PATH)
assert SPEC is not None and SPEC.loader is not None
MODULE = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = MODULE
SPEC.loader.exec_module(MODULE)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_git(root: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


class GovernanceVerifierTests(unittest.TestCase):
    def setUp(self) -> None:
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        run_git(self.root, "init", "-q")
        run_git(self.root, "config", "user.name", "Governance Test")
        run_git(self.root, "config", "user.email", "governance@example.invalid")
        (self.root / "README.md").write_text("fixture\n", encoding="utf-8")
        run_git(self.root, "add", "README.md")
        run_git(self.root, "commit", "-qm", "fixture base")
        self.base_revision = run_git(self.root, "rev-parse", "HEAD")
        self._write_frozen_fixture()
        run_git(self.root, "add", ".")
        run_git(self.root, "commit", "-qm", "frozen governance fixture")

    def tearDown(self) -> None:
        self.directory.cleanup()

    def _write_frozen_fixture(self) -> None:
        source = self.root / "docs" / "source.md"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_text("controlled source\n", encoding="utf-8")
        change_dir = self.root / "docs" / "governance" / "change-records"
        change_dir.mkdir(parents=True)
        (change_dir / "README.md").write_text("change records\n", encoding="utf-8")
        (self.root / "docs" / "benchmark.json").write_text("{}\n", encoding="utf-8")
        write_json(self.root / "docs" / "governance" / "change-record.schema.json", {"schemaVersion": 1})
        write_json(
            self.root / "docs" / "governance" / "requirement-status-ledger.schema.json",
            {"schemaVersion": 1},
        )
        contract_document = self.root / "docs" / "semantic-contracts" / "fixture.json"
        contract_document.parent.mkdir(parents=True)
        contract_document.write_text("{}\n", encoding="utf-8")
        contract_test = self.root / "tests" / "semantic_contracts" / "test_fixture.py"
        contract_test.parent.mkdir(parents=True)
        contract_test.write_text("pass\n", encoding="utf-8")
        write_json(
            self.root / "docs" / "governance" / "frozen-contract-surface.schema.json",
            {"schemaVersion": 1},
        )
        contract_surface = {
            "schemaVersion": 1,
            "surfaceId": "frozen_contract_surface_fixture",
            "coverageRoots": ["docs/semantic-contracts", "tests/semantic_contracts"],
            "artifacts": [
                {"path": "docs/semantic-contracts/fixture.json", "sha256": sha256(contract_document)},
                {"path": "tests/semantic_contracts/test_fixture.py", "sha256": sha256(contract_test)},
            ],
        }
        write_json(
            self.root / "docs" / "governance" / "frozen-contract-surface.json",
            contract_surface,
        )

        requirement_ledger = {
            "schemaVersion": 1,
            "ledgerId": "requirement_status_ledger_fixture",
            "baselineId": "governance_baseline_fixture",
            "requirements": [
                {
                    "requirementId": requirement_id,
                    "requirementType": (
                        "SOURCE_REQUIREMENT"
                        if requirement_id.startswith("SRC-")
                        else "DERIVED_PRODUCT_REQUIREMENT"
                    ),
                    "status": "PLANNED",
                    "owner": "OWNER",
                    "independentAcceptor": "ACCEPTOR",
                    "inputArtifacts": [self._verified_artifact("docs/source.md")],
                    "outputArtifacts": [self._verified_artifact("docs/source.md")],
                    "acceptanceEvidence": [self._verified_artifact("docs/source.md")],
                }
                for requirement_id in sorted(MODULE.EXPECTED_REQUIREMENTS)
            ],
        }
        write_json(self.root / "docs" / "governance" / "requirement-status-ledger.json", requirement_ledger)

        ownership = {
            "schemaVersion": 1,
            "baselineId": "governance_baseline_fixture",
            "baseRevision": self.base_revision,
            "sharedPaths": ["src/shared.py"],
            "globalForbiddenPaths": ["config.llm.json", "_reference_only/**"],
            "workPackages": [
                {
                    "workPackageId": "GOV-BASELINE",
                    "phase": "Governance",
                    "status": "ASSIGNED",
                    "ownedPaths": ["docs/sandbox/**"],
                    "readOnlyPaths": ["docs/source.md"],
                    "generatedPaths": [],
                    "forbiddenPaths": ["src/**"],
                    "baseRevision": self.base_revision,
                    "responsibleAgent": "OWNER",
                    "modelTier": "Terra Medium",
                    "evidencePaths": ["docs/source.md"],
                }
            ],
        }
        write_json(self.root / "docs" / "governance" / "ownership.json", ownership)

        ledger_path = self.root / "docs" / "governance" / "requirement-status-ledger.json"
        ledger_schema_path = self.root / "docs" / "governance" / "requirement-status-ledger.schema.json"
        ownership_path = self.root / "docs" / "governance" / "ownership.json"
        contract_surface_path = self.root / "docs" / "governance" / "frozen-contract-surface.json"
        contract_surface_schema_path = (
            self.root / "docs" / "governance" / "frozen-contract-surface.schema.json"
        )
        baseline = {
            "schemaVersion": 1,
            "baselineId": "governance_baseline_fixture",
            "status": "FROZEN",
            "codeRevision": self.base_revision,
            "controlledArtifacts": [
                {
                    "id": "source",
                    "path": "docs/source.md",
                    "sha256": sha256(source),
                    "requiredForFreeze": True,
                },
                {
                    "id": "ledger",
                    "path": "docs/governance/requirement-status-ledger.json",
                    "sha256": sha256(ledger_path),
                    "requiredForFreeze": True,
                },
                {
                    "id": "ownership",
                    "path": "docs/governance/ownership.json",
                    "sha256": sha256(ownership_path),
                    "requiredForFreeze": True,
                },
                {
                    "id": "contract_surface",
                    "path": "docs/governance/frozen-contract-surface.json",
                    "sha256": sha256(contract_surface_path),
                    "requiredForFreeze": True,
                },
            ],
            "contractSurface": {
                "path": "docs/governance/frozen-contract-surface.json",
                "schemaPath": "docs/governance/frozen-contract-surface.schema.json",
                "sha256": sha256(contract_surface_path),
                "schemaSha256": sha256(contract_surface_schema_path),
            },
            "requirementStatusLedger": {
                "path": "docs/governance/requirement-status-ledger.json",
                "schemaPath": "docs/governance/requirement-status-ledger.schema.json",
                "sha256": sha256(ledger_path),
                "schemaSha256": sha256(ledger_schema_path),
            },
            "freezePrerequisites": [
                {
                    "id": "benchmark",
                    "path": "docs/benchmark.json",
                    "reason": "fixture prerequisite",
                }
            ],
            "evidenceRequirements": {
                "phaseExecutionRecords": {"requiredFields": ["phaseId"], "records": []},
                "workPackagePlans": {"requiredFields": ["workPackageId"], "records": []},
                "workPackageReports": {"requiredFields": ["workPackageId"], "records": []},
            },
            "approval": {
                "approvedAt": "2026-09-09T00:00:00Z",
                "approvedBy": "MAIN_AGENT",
                "independentReviewer": "INDEPENDENT_ACCEPTOR",
            },
            "changeControl": {
                "recordDirectory": "docs/governance/change-records",
                "recordFilenamePattern": "CR-[A-Z0-9-]+\\.json",
                "schemaPath": "docs/governance/change-record.schema.json",
            },
        }
        write_json(self.root / "docs" / "governance" / "baseline.json", baseline)

    def _verified_artifact(self, relative_path: str) -> dict[str, str]:
        return {
            "path": relative_path,
            "sha256": sha256(self.root / relative_path),
            "state": "VERIFIED",
        }

    def _verify(self, **kwargs):
        return MODULE.GovernanceVerifier(self.root).verify(
            baseline_path="docs/governance/baseline.json",
            ownership_path="docs/governance/ownership.json",
            **kwargs,
        )

    @staticmethod
    def _codes(findings):
        return {finding.code for finding in findings}

    def _read_baseline(self):
        return json.loads((self.root / "docs" / "governance" / "baseline.json").read_text(encoding="utf-8"))

    def _write_baseline(self, baseline):
        write_json(self.root / "docs" / "governance" / "baseline.json", baseline)

    def test_valid_frozen_fixture_passes(self):
        self.assertEqual(self._verify(), [])

    def test_detects_controlled_hash_drift(self):
        (self.root / "docs" / "source.md").write_text("drift\n", encoding="utf-8")
        self.assertIn("CONTROLLED_ARTIFACT_HASH_MISMATCH", self._codes(self._verify()))

    def test_detects_frozen_contract_surface_hash_drift(self):
        (self.root / "docs" / "semantic-contracts" / "fixture.json").write_text(
            '{"drift":true}\n',
            encoding="utf-8",
        )
        self.assertIn("CONTRACT_SURFACE_ARTIFACT_HASH_MISMATCH", self._codes(self._verify()))

    def test_detects_unlisted_frozen_contract_surface_artifact(self):
        (self.root / "docs" / "semantic-contracts" / "new.schema.json").write_text(
            "{}\n",
            encoding="utf-8",
        )
        self.assertIn("CONTROLLED_ARTIFACT_COVERAGE_MISSING", self._codes(self._verify()))

    def test_detects_active_ownership_overlap(self):
        ownership_path = self.root / "docs" / "governance" / "ownership.json"
        ownership = json.loads(ownership_path.read_text(encoding="utf-8"))
        duplicate = dict(ownership["workPackages"][0])
        duplicate["workPackageId"] = "WP1"
        duplicate["phase"] = "Phase 1"
        duplicate["ownedPaths"] = ["docs/sandbox/**"]
        ownership["workPackages"].append(duplicate)
        write_json(ownership_path, ownership)
        self.assertIn("ACTIVE_WORK_PACKAGE_PATH_OVERLAP", self._codes(self._verify()))

    def test_detects_frozen_evidence_field_absence(self):
        baseline = self._read_baseline()
        baseline["evidenceRequirements"]["phaseExecutionRecords"]["records"] = [
            {"id": "phase-0", "path": "docs/source.md"}
        ]
        self._write_baseline(baseline)
        self.assertIn("EVIDENCE_FIELD_MISSING", self._codes(self._verify()))

    def test_detects_prohibited_and_undeclared_changed_paths(self):
        findings = self._verify(
            work_package_id="GOV-BASELINE",
            changed_paths=["config.llm.json", "docs/other.md"],
        )
        codes = self._codes(findings)
        self.assertIn("CHANGED_PATH_PROHIBITED", codes)
        self.assertIn("CHANGED_PATH_UNDECLARED", codes)

    def test_detects_invalid_change_record_location(self):
        (self.root / "docs" / "governance" / "change-records" / "invalid.txt").write_text(
            "invalid\n",
            encoding="utf-8",
        )
        self.assertIn("CHANGE_RECORD_LOCATION_INVALID", self._codes(self._verify()))

    def test_detects_missing_requirement_record_fields(self):
        ledger_path = self.root / "docs" / "governance" / "requirement-status-ledger.json"
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        del ledger["requirements"][0]["owner"]
        write_json(ledger_path, ledger)
        self.assertIn("REQUIREMENT_RECORD_FIELD_MISSING", self._codes(self._verify()))

    def test_candidate_defers_future_evidence_but_keeps_real_freeze_blockers(self):
        baseline = self._read_baseline()
        baseline["status"] = "CANDIDATE"
        baseline.pop("approval")
        baseline["freezePrerequisites"][0]["path"] = "docs/missing-benchmark.json"
        baseline["evidenceRequirements"]["phaseExecutionRecords"]["records"] = [
            {"id": "phase-7", "path": "docs/missing-phase.md"}
        ]
        self._write_baseline(baseline)
        codes = self._codes(self._verify())
        self.assertIn("BASELINE_NOT_FROZEN", codes)
        self.assertIn("FREEZE_PREREQUISITE_MISSING", codes)
        self.assertNotIn("EVIDENCE_RECORD_MISSING", codes)
        self.assertNotIn("EVIDENCE_FIELD_MISSING", codes)

    def test_real_candidate_has_no_stale_governance_hash_error(self):
        findings = MODULE.GovernanceVerifier(PROJECT_ROOT).verify(
            baseline_path="docs/governance/governance-baseline.json",
            ownership_path="docs/governance/ownership-manifest.json",
        )
        codes = self._codes(findings)
        self.assertIn("BASELINE_NOT_FROZEN", codes)
        self.assertIn("FREEZE_PREREQUISITE_MISSING", codes)
        self.assertNotIn("CONTROLLED_ARTIFACT_HASH_MISMATCH", codes)
        self.assertNotIn("CONTROLLED_ARTIFACT_COVERAGE_MISSING", codes)
        self.assertNotIn("REQUIREMENT_LEDGER_HASH_MISMATCH", codes)


if __name__ == "__main__":
    unittest.main()
