# WP5 Plan Semantic Fusion and Evidence

## Governance Fields

```text
workPackageId: WP5
phase: Phase 5
status: PLANNED
goal: Build evidence-preserving semantic fusion that publishes conservative DatasetSemanticProfile artifacts from accepted structural and visual inputs.
nonGoals: New public contracts, VLM execution, task matching, shared-path wiring, and conflict suppression.
sourceRequirementIds: [SRC-01, SRC-05, SRC-06, SRC-07, SRC-13, SRC-16, SRC-19]
inputArtifacts: WP0 contract SHA-256; WP1 store artifact; WP3 structural artifact; WP4 aggregation artifact, all ACCEPTED
outputArtifacts: src/datamodelmatch/semantic_evidence.py; src/datamodelmatch/semantic_fusion.py; focused tests; WP5 report
dependencies: WP0; WP1; WP3; WP4
ownedPaths: src/datamodelmatch/semantic_evidence.py; src/datamodelmatch/semantic_fusion.py; tests/test_semantic_evidence.py; tests/test_semantic_fusion.py
readOnlyPaths: docs/semantic-contracts/**; src/datamodelmatch/semantic_aggregation.py; src/datamodelmatch/semantic_store.py
generatedPaths: .datamodelmatch/phase-5-evidence/**
forbiddenPaths: src/datamodelmatch/resource_types.py; src/datamodelmatch/resource_store.py; src/datamodelmatch/resource_cli.py; web/**; pyproject.toml; config.llm.json; _reference_only/**; docs/governance/**
baseRevision: PENDING_FROZEN_BASELINE
responsibleAgent: WP5_OWNER
modelTier: Terra Medium
verificationCommands: pytest tests/test_semantic_evidence.py tests/test_semantic_fusion.py
acceptanceDeliverables: reference-closed claims/evidence/unresolved artifacts; conflict and UNKNOWN tests; WP5 report
failureAndRollback: reject publication on unresolved references, invalid status evidence, conflict suppression, or snapshot mismatch; retain last complete profile
handoffConsumer: Main Agent; WP6; WP7
```
