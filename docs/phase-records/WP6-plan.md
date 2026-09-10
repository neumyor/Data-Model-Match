# WP6 Plan Task Parsing and Semantic Matching

## Governance Fields

```text
workPackageId: WP6
phase: Phase 6
status: PLANNED
goal: Parse reviewable TaskSemanticProfile objects and compute evidence-backed Compatibility and formal Suitability without score leakage.
nonGoals: Legacy API replacement, new public schema changes, shared-path wiring, and ranking non-compatible datasets.
sourceRequirementIds: [SRC-01, SRC-14, SRC-15, SRC-16, SRC-19, SRC-21]
inputArtifacts: WP0 contract SHA-256; WP5 accepted profile/evidence artifact; matching-rule and weight fingerprints
outputArtifacts: src/datamodelmatch/semantic_task.py; src/datamodelmatch/semantic_matching.py; focused tests; WP6 report
dependencies: WP0; WP5
ownedPaths: src/datamodelmatch/semantic_task.py; src/datamodelmatch/semantic_matching.py; tests/test_semantic_task.py; tests/test_semantic_matching.py
readOnlyPaths: docs/semantic-contracts/**; src/datamodelmatch/semantic_fusion.py
generatedPaths: .datamodelmatch/phase-6-evidence/**
forbiddenPaths: src/datamodelmatch/resource_types.py; src/datamodelmatch/resource_store.py; src/datamodelmatch/resource_cli.py; web/**; pyproject.toml; config.llm.json; _reference_only/**; docs/governance/**
baseRevision: PENDING_FROZEN_BASELINE
responsibleAgent: WP6_OWNER
modelTier: Terra Medium
verificationCommands: pytest tests/test_semantic_task.py tests/test_semantic_matching.py; real task LLM test entrypoint
acceptanceDeliverables: task parser behavior; compatibility decision table; suitability explanation/evidence; isolated failure tests; WP6 report
failureAndRollback: reject results with required-condition leakage, non-null invalid score, missing evidence or unversioned rules; retain legacy workflow
handoffConsumer: Main Agent; WP7; WP8
```
