# WP0-C Plan: Semantic UI Acceptance Governance

## Goal

Freeze a concrete, implementation-facing UI acceptance specification for the native
HTML/CSS/JavaScript application. The specification defines the Phase 7 visual
regression contract for dataset semantic-profile details and task-driven dataset
discovery, including fixtures, stable DOM selectors, keyboard and semantic behavior,
SSE reconnect checks, screenshot comparison, and artifact retention.

## Non-goals

- Do not implement semantic-profile UI, task discovery UI, API routes, SSE routes, or
  any server behavior.
- Do not change the existing resource, dataset-to-model compatibility, import, or
  drawer workflows.
- Do not add browser-test dependencies or modify package/build configuration.
- Do not make real LLM, VLM, HTTP API, or browser automation calls.

## Inputs

- `AGENTS.md`
- `docs/dataset-management-ui-phased-acceptance.md`, especially sections 4.4, 5,
  7, and 12.
- Current native application structure in `web/index.html`, `web/app.js`, and
  `web/styles.css`, read only to keep the future selector and automation contract
  compatible with the project.
- Installed local tools: Bun 1.4.2 is available; no browser automation runner is
  currently installed.

## Outputs

- `docs/semantic-ui-acceptance/UI-ACCEPTANCE-SPEC.md`: normative acceptance rules.
- `docs/semantic-ui-acceptance/dom-fixture-manifest.json`: machine-readable selector,
  fixture, viewport, visual-diff, accessibility, and SSE acceptance manifest.
- `tests/semantic_ui_acceptance/test_manifest.test.mjs`: a dependency-free Bun test that
  validates manifest shape, selector naming, required coverage, and rule
  completeness.

## Dependencies

- Phase 7 must add an approved, pinned browser automation runner compatible with Bun
  before screenshot or live-DOM acceptance can pass. This work package specifies
  that future runner boundary but does not install it.
- WP7 must implement every required `data-testid`, fixture seam, semantic role, and
  observable SSE state defined by the frozen manifest.
- The main Agent must approve any change to a selector, fixture state, viewport,
  screenshot threshold, or acceptance rule under the Phase 0 change-control
  procedure.

## Allowed Paths

- `docs/semantic-ui-acceptance/**`
- `tests/semantic_ui_acceptance/**`

## Prohibited Paths

- `src/**`
- `web/**`
- `pyproject.toml`
- `config.llm.json`
- Existing files below `tests/`
- `_reference_only/**`
- Shared files listed in section 7.2 of the phase acceptance document.

## Interfaces

- Manifest interface: JSON document at
  `docs/semantic-ui-acceptance/dom-fixture-manifest.json`, schema version `1`.
- DOM interface: future UI elements expose the exact `data-testid` values listed in
  the manifest; selectors are contracts, not implementation suggestions.
- Fixture interface: the future browser harness selects a named fixture and renders
  it through a test-only, non-production fixture seam. Fixtures must not require a
  real LLM/VLM or expose sensitive media.
- SSE interface: the live UI must retain the highest contiguous `eventId` and use
  idempotent event application after reconnect; the specification defines the
  observable behavior, while the API/SSE protocol remains owned by the relevant
  WP0 contract work package.

## Failure Cases

- Missing browser runner, screenshot baselines, or artifact directories blocks visual
  acceptance; it must be reported as blocked rather than skipped as passed.
- A missing selector, duplicate selector ID, nonconforming selector name, or fixture
  state causes manifest validation to fail.
- A visual diff above tolerance, unreadable focus target, inaccessible control,
  overflowed long evidence/path, or inconsistent SSE reconnect result fails the
  corresponding Phase 7 scenario.
- Sensitive values such as API keys, Authorization headers, full prompts/responses,
  or raw sensitive media in a fixture, screenshot, report, or archive fail
  acceptance.

## Validation

- Run `bun test tests/semantic_ui_acceptance/test_manifest.test.mjs`.
- Run `git diff --check`.
- Inspect changed paths to confirm that this work package only writes within its
  allowed paths.
- No real API calls are part of this work package.
