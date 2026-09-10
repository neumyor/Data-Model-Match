# WP0 Plan Public Contracts Benchmark and UI Baseline

## Governance Fields

```text
workPackageId: WP0
phase: Phase 0
status: PLANNED
goal: Freeze closed public contracts, benchmark protocol, UI acceptance specification, and migration rules before product implementation.
nonGoals: Product module implementation, shared-path wiring, production endpoint changes, and acceptance of pre-baseline experiments.
sourceRequirementIds: [SRC-02, SRC-05, SRC-06, SRC-07, SRC-11, SRC-14, SRC-17, SRC-18, SRC-21, SRC-23]
inputArtifacts: source DOCX SHA-256 a2c4f4d2d53e7d1156f171b15f00def54f44b6ac89c761a9fae8eb0ee12dffa5; acceptance document; existing product baseline
outputArtifacts: semantic contracts; benchmark protocol and real de-identified manifest; UI acceptance specification; WP0 report
dependencies: none
ownedPaths: docs/semantic-contracts/**; tests/semantic_contracts/**; docs/semantic-benchmark/**; tests/semantic_benchmark/**; docs/semantic-ui-acceptance/**; tests/semantic_ui_acceptance/**
readOnlyPaths: docs/dataset-management-ui-phased-acceptance.md; docs/semantic-requirements-ledger.md; src/**; web/**
generatedPaths: .datamodelmatch/semantic-benchmark/**; .datamodelmatch/ui-acceptance/**
forbiddenPaths: src/**; web/**; pyproject.toml; config.llm.json; _reference_only/**; docs/governance/**
baseRevision: PENDING_FROZEN_BASELINE
responsibleAgent: WP0_OWNER
modelTier: Terra Medium
verificationCommands: contract tests; benchmark tests; UI manifest test; governance verification in candidate-remediation mode
acceptanceDeliverables: closed schema catalog; RFC; source-verified real benchmark manifest; threshold state; UI contract; signed WP0 report
failureAndRollback: mark BLOCKED on missing source verification, contract drift, placeholder benchmark data, or UI contract incompleteness; reopen affected artifacts by change record after freeze
handoffConsumer: Main Agent; WP1 through WP8
```

WP0 is the only pre-product work package. A benchmark manifest is acceptable only when anonymous dataset IDs resolve in ignored source registry records with verified first-party license, acquisition and immutable revision evidence; placeholders, unknown-pending-review licenses and zero revisions are not acceptable.
