# WP7 Plan API SSE and Dataset Management UI

## Governance Fields

```text
workPackageId: WP7
phase: Phase 7
status: PLANNED
goal: Integrate accepted semantic artifacts into HTTP/SSE and the dataset-management semantic detail and task-discovery user workflows.
nonGoals: Redefining business semantics, changing frozen schemas, direct modification of main-Agent shared paths, or replacing legacy dataset-to-model compatibility.
sourceRequirementIds: [SRC-01, SRC-06, SRC-13, SRC-14, SRC-15, SRC-16, SRC-18, SRC-19]
inputArtifacts: WP0 contracts and UI specification; WP1 store; WP5 profiles; WP6 match artifacts, all ACCEPTED
outputArtifacts: web/semantic-profile.js; web/task-discovery.js; API/E2E tests; browser screenshots; WP7 report
dependencies: WP0; WP1; WP5; WP6; main-Agent shared-path wiring
ownedPaths: web/semantic-profile.js; web/task-discovery.js; tests/semantic_ui_acceptance/e2e/**; tests/semantic_api/**
readOnlyPaths: docs/semantic-contracts/**; docs/semantic-ui-acceptance/**; web/server.ts; web/app.js; web/index.html; web/styles.css
generatedPaths: .datamodelmatch/ui-acceptance/**
forbiddenPaths: src/datamodelmatch/resource_types.py; src/datamodelmatch/resource_store.py; src/datamodelmatch/resource_cli.py; web/server.ts; web/app.js; web/index.html; web/styles.css; pyproject.toml; config.llm.json; _reference_only/**; docs/governance/**
baseRevision: PENDING_FROZEN_BASELINE
responsibleAgent: WP7_OWNER
modelTier: Terra Medium
verificationCommands: API contract suite; Playwright-compatible browser suite at both frozen viewports; web build
acceptanceDeliverables: four review regions; separate task-discovery workspace; SSE reconnect evidence; screenshot diff reports; WP7 report
failureAndRollback: reject duplicate replay states, inaccessible controls, score/ranking misrepresentation, unsupported-media masking, or old-profile overwrite; preserve legacy UI
handoffConsumer: Main Agent; WP8
```

The main Agent alone wires `web/server.ts`, `web/app.js`, `web/index.html`, `web/styles.css`, resource storage and CLI paths after independently accepting WP7 output.
