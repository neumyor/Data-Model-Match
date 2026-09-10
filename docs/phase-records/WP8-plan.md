# WP8 Plan Benchmark Robustness Ablation and Final Acceptance

## Governance Fields

```text
workPackageId: WP8
phase: Phase 7
status: PLANNED
goal: Execute the frozen real benchmark, perturbations, ablations, research baselines, RQ analysis and final product acceptance evidence.
nonGoals: Dataset-name adapters, post-result threshold changes, raw media publication, product feature changes outside accepted change control.
sourceRequirementIds: [SRC-01, SRC-02, SRC-04, SRC-07, SRC-10, SRC-11, SRC-12, SRC-15, SRC-17, SRC-20, SRC-22, SRC-23]
inputArtifacts: final approved benchmark manifest; Ground Truth; perturbations; final threshold manifest; integrated WP2 through WP7 artifacts
outputArtifacts: benchmark reports; RQ1-RQ4 reports; robustness evidence; UI regression archive; WP8 report
dependencies: WP2; WP3; WP4; WP5; WP6; WP7 integrated
ownedPaths: docs/semantic-benchmark/benchmark-manifest.json; docs/semantic-benchmark/ground-truth/**; docs/semantic-benchmark/benchmark-reports/**; tests/semantic_benchmark/**
readOnlyPaths: docs/semantic-benchmark/benchmark-manifest.schema.json; docs/semantic-benchmark/ground-truth.schema.json; docs/semantic-contracts/**; docs/semantic-ui-acceptance/**
generatedPaths: .datamodelmatch/semantic-benchmark/**; .datamodelmatch/ui-acceptance/**
forbiddenPaths: src/**; web/**; pyproject.toml; config.llm.json; _reference_only/**; docs/governance/**
baseRevision: PENDING_FROZEN_BASELINE
responsibleAgent: WP8_OWNER
modelTier: Terra Medium
verificationCommands: benchmark validator; all benchmark tests; full regression; browser screenshot suite; real LLM/VLM acceptance entrypoints
acceptanceDeliverables: immutable run tuple; metrics; two resource scale bands; five ablations; two baselines; RQ1-RQ4 conclusions; license/provenance audit; WP8 report
failureAndRollback: mark failed thresholds, incomplete provenance, missing repeat evidence, named-adapter behavior, or hidden UNKNOWN as failed gates; do not revise thresholds after final results
handoffConsumer: Main Agent final acceptance
```
