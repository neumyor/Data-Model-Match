# Governance Baseline Plan

## Goal

Create a dependency-free, machine-verifiable governance baseline for the
dataset-management UI programme. It must prevent new work packages from being
treated as accepted inputs until their baseline revision, controlled artifacts,
ownership boundaries, evidence records, prohibited paths, and change-control
location have been checked.

## Non-goals

- This work does not amend product contracts, phase records, benchmark
  manifests, UI specifications, application source, or tests outside
  `tests/governance/`.
- It does not manufacture missing benchmark, phase, work-package, approval, or
  independent-review evidence.
- It does not read `config.llm.json`, make model requests, inspect raw media,
  or invoke tools from imported resources.

## Inputs

- The audit candidate at
  `docs/dataset-management-ui-phased-acceptance.md`.
- The requirements ledger and the existing semantic-contract, benchmark, and
  UI control artifacts.
- The repository's Git `HEAD`, used only as a public revision identifier.
- A caller-provided changed-path list when checking one work package before
  integration.

## Outputs and Interface

- `governance-baseline.schema.json` and `governance-baseline.json` define the
  frozen-input inventory, status, approval data, evidence templates, and
  freeze prerequisites.
- `frozen-contract-surface.schema.json` and
  `frozen-contract-surface.json` close the complete frozen contract surface:
  every contract document, JSON Schema, static Python/frontend type, fixture,
  RFC/policy artifact, and contract test has an individual SHA-256. The
  verifier also checks that the two frozen contract directories contain no
  unlisted file.
- `requirement-status-ledger.schema.json` and
  `requirement-status-ledger.json` are the signable, machine-readable
  requirement register. Every `SRC-*` and `DER-*` requirement has an explicit
  lifecycle status, artifact-path and SHA-256 state for inputs, outputs, and
  evidence, a responsible owner, and an independent acceptor. The existing
  Markdown ledger remains a human-readable source index only.
- `ownership-manifest.schema.json` and `ownership-manifest.json` define
  work-package status, exact write/generate/read-only/forbidden path sets, and
  the shared-path boundary.
- `change-record.schema.json` and `change-records/` reserve the only approved
  location and filename convention for contract-change records.
- `governance_verify.py` is the stable CLI:

  ```sh
  python3 docs/governance/governance_verify.py \
    --repo-root . \
    --baseline docs/governance/governance-baseline.json \
    --ownership docs/governance/ownership-manifest.json
  ```

  Add `--work-package <id> --changed-path <repository-relative-path>` for
  per-work-package diff validation. `--json` emits a stable report object.

## Failure Semantics

The verifier has two deliberate modes, derived from `baseline.status`.

- `CANDIDATE` validates the candidate's own shape, revision availability,
  committed controlled artifacts, SHA-256 values, real freeze prerequisites,
  requirement-status register, ownership, prohibited paths, and
  change-control directory. It does not report missing evidence records for
  future phases or planned work packages. Its expected dispatch-blocking
  codes are `BASELINE_NOT_FROZEN`, `BASELINE_NOT_COMMITTED`,
  `CONTROLLED_ARTIFACT_NOT_COMMITTED`, and real prerequisite codes such as
  `FREEZE_PREREQUISITE_MISSING`.
- `FROZEN` runs every `CANDIDATE` check and additionally enforces every
  declared phase/work-package evidence record and field. It emits
  `EVIDENCE_RECORD_MISSING` and `EVIDENCE_FIELD_MISSING` for incomplete
  signable evidence. Any non-zero result blocks dispatch or integration.

Both modes emit stable error codes for unavailable revisions, missing or
uncommitted controlled artifacts, hash drift, invalid requirement-register
records, active ownership overlap, prohibited or undeclared changed paths,
and invalid change-record directory content.

No error is silently downgraded. A successful process means every selected
governance gate was satisfied for the supplied repository state and changed
paths.

## Compatibility and Safety

The manifests are version `1`. Future incompatible formats must use a new
version and verifier support rather than changing version-1 semantics. The
verifier accepts only repository-relative POSIX paths, rejects traversal and
absolute paths, uses SHA-256 for content fingerprints, never prints file
contents, and does not inspect sensitive configuration.

## Verification

`tests/governance/test_governance_verify.py` creates isolated temporary Git
repositories and covers a valid frozen baseline plus each mandatory failure
class: revision/hash drift, ownership overlap, absent evidence field,
prohibited changed path, undeclared changed path, and malformed change-record
placement. It also covers frozen-contract-surface hash drift and an unlisted
contract file. The real candidate is tested to ensure it remains honestly
blocked until the audit prerequisites are resolved.

## Handoff

At the current candidate snapshot, `governance_verify.py --json` is expected
to fail only with these code families:

- `BASELINE_NOT_FROZEN`: the manifest deliberately remains `CANDIDATE`.
- `BASELINE_NOT_COMMITTED` and `CONTROLLED_ARTIFACT_NOT_COMMITTED`: the
  baseline and controlled audit artifacts have not yet been committed at the
  branch head.
- `FREEZE_PREREQUISITE_MISSING`: the actual
  `docs/semantic-benchmark/benchmark-manifest.json` is not present.

It must not emit `CONTROLLED_ARTIFACT_HASH_MISMATCH`,
`REQUIREMENT_LEDGER_HASH_MISMATCH`, `REQUIREMENT_ARTIFACT_HASH_MISMATCH`,
`EVIDENCE_RECORD_MISSING`, or `EVIDENCE_FIELD_MISSING` while the manifest is
`CANDIDATE`. Once the status changes to `FROZEN`, all declared evidence
records become mandatory and those last two evidence codes are expected for
any incomplete signable record.
