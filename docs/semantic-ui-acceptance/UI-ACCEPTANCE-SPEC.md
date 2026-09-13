# Semantic UI Acceptance Specification

## Status and Authority

This is the WP0-C Phase 0 UI acceptance contract for the visual dataset semantic
understanding and task-matching work. It operationalizes section 12 of
`docs/dataset-management-ui-phased-acceptance.md`. The machine-readable companion,
`dom-fixture-manifest.json`, is authoritative for fixed values, IDs, selectors,
fixtures, and completeness checks. A change to either document follows the Phase 0
change-control process.

This specification covers the future semantic-profile detail surface and task-driven
dataset discovery workspace. It does not redefine the current dataset-to-model
compatibility workflow.

## Automation Gate

The current repository uses a native Bun-served HTML/CSS/JavaScript application.
The current host has Bun 1.4.2 but no installed browser automation runner. Phase 0
therefore provides a dependency-free Bun manifest validator only. It does not claim
that visual or live-DOM tests have run.

Before Phase 7 may pass, the main Agent must add an approved and version-pinned
Playwright-compatible browser harness that Bun can invoke against `web`'s local
server. It must implement every capability in `automation.phase7BrowserHarness` in
the manifest. The absence of that harness, its browser binary, or its screenshot
baselines is a blocking failure for UI acceptance, never a skipped pass.

Browser runs must use deterministic test-only fixtures, block external network
traffic, and make no LLM/VLM/API calls. Fixture activation is a test seam before
application bootstrap; it is not a user-visible production feature.

## Fixed Viewports and Screenshots

Every declared fixture is tested at both:

| ID | CSS viewport | Device scale | Purpose |
| --- | --- | --- | --- |
| `desktop-1440x1100` | 1440 x 1100 | 1 | Desktop workspace, drawer/detail density, and result comparison |
| `mobile-390x844` | 390 x 844 | 2 | Narrow layout, touch-target, evidence/path wrapping, and reachability |

Capture both a full-page screenshot and an element screenshot of the workflow root.
Baselines are stored at:

```text
tests/semantic_ui_acceptance/baselines/<fixture-id>/<viewport-id>/{full-page.png,root.png}
```

On mismatch, archive the actual image, expected image, diff image, sanitized DOM
capture, and report under:

```text
.datamodelmatch/ui-acceptance/<run-id>/<fixture-id>/<viewport-id>/
```

Use a pixelmatch-compatible RGBA comparison with anti-alias edge handling only,
per-pixel color-distance threshold `0.1`, at most `800` mismatched pixels, and at
most `0.002` mismatched-pixel ratio. Application content cannot be masked. Disable
or normalize only browser-owned caret blinking and the test-run timestamp before
capture. Any baseline update requires recorded approval.

## Stable DOM Contract

All future semantic UI selectors use the exact `data-testid` values in the manifest.
The selector grammar is:

```text
data-testid="semantic-<area>-<noun-or-action>"
data-testid="task-discovery-<noun-or-action>"
```

IDs are lowercase ASCII kebab case. They are stable test contracts, must be unique
when rendered, and must not be generated from dataset names, user data, index
positions, locale text, or changing revisions. Test IDs serve automation only; they
do not replace visible labels or accessible names.

## Dataset Details Review

The completed semantic-profile details surface always has three fixed, ordered review regions:

1. `semantic-details-structure-region` / `结构语义`
2. `semantic-details-content-region` / `内容语义`
3. `semantic-details-evidence-region` / `证据与未解决问题`

Each region's required content appears in `reviewRegions` in the manifest. The UI
must show snapshot and profile revision before a reviewer interprets a claim.

During analysis, `semantic-details-job-progress` instead shows a two-stage progress
surface: safe Agent-authored local inspection summaries during image sampling, followed
by a fixed evidence-aggregation message and elapsed time. It never exposes prompts,
generated code, raw model responses, stdout, image contents, or internal reasoning.
Dataset-level claims retain their evidence references and `UNKNOWN` reason where
applicable. A failed or partially completed job cannot overwrite or visually impersonate
the last complete profile.

The required details fixtures cover not started, queued, running, partial completion
with unknowns, conflict, retryable failure, cancellation, superseded old revision,
forbidden access, unsupported media, no samples, and reconnect.

## Task Discovery Workspace

The task discovery surface is a separate workspace, not a relabeling of the existing
dataset-to-model compatibility view. It includes:

- natural-language request input and parse action;
- reviewable required versus preferred TaskSemanticProfile conditions;
- dataset resource-scope selection;
- match start action, Compatibility filter, and job progress/error;
- default-ranked compatible result group and separately rendered non-ranked groups;
- selected-result explanation with satisfied requirements, preferences, conflicts,
  UNKNOWNs, evidence references, revision identifiers, matching-rule version, and
  generated timestamp.

Only `COMPATIBLE` results with a non-null formal suitability score may appear in the
default ranking. `PARTIALLY_COMPATIBLE`, `INCOMPATIBLE`, and `UNKNOWN` must remain
outside it, with their gap, blocking evidence, or missing-evidence explanation.
Filtering controls visibility only. They must not silently alter compatibility,
ranking eligibility, or formal score semantics.

## Keyboard, Focus, and Semantics

For every fixture and viewport:

- Sequential Tab reaches all enabled controls in visible order; no positive
  `tabindex` is allowed.
- Keyboard focus has a visible 2 CSS-pixel-or-greater indicator at at least 3:1
  contrast and cannot be clipped.
- Fixed review regions and major task-discovery regions use semantic landmarks or
  sections with accessible headings.
- Buttons, icon controls, inputs, selects, and expandable evidence have non-empty
  accessible names that describe their action.
- Job state, sanitized errors, and reconnect transition have appropriate live
  announcements, without duplicate announcements from replayed SSE events.
- Expandable evidence, unresolved items, and result explanations are discoverable
  and operable with Tab, Enter, and Space, and expose expanded state.

## Long Content and Narrow Layout

Fixtures must include a deliberately long relative path, source reference, revision,
evidence summary, unknown reason, and task explanation. At both fixed viewports:

- long paths wrap at natural break points and do not produce page-level horizontal
  overflow; full content remains available through an accessible title or explicit
  copy action;
- long evidence wraps or has bounded local scrolling without overlapping controls,
  claims, or drawer edges;
- at `mobile-390x844`, rows reflow into readable labeled stacks, or an explicitly
  scrollable table preserves row/column labels;
- icon-only targets are at least 44 x 44 CSS pixels; all named actions remain
  reachable by ordinary scrolling;
- no required content, focus indicator, live status, error, or action is clipped or
  hidden without a reachable scroll path.

## SSE Reconnect Acceptance

The browser harness simulates exact sequence/replay cases named in
`manifest.sseReconnectChecks`. The UI stores and displays only the effect of
contiguous increasing event IDs. On reconnect it sends/uses `lastEventId`, applies
replayed events idempotently, and reaches the same terminal state as the equivalent
no-disconnect fixture.

For details, events 1-3 are rendered, then disconnect/reconnect replays 3 and
delivers 4-6. Timeline entries must be exactly 1-6 once each. For task discovery,
the reconnect replays 7 and delivers 8 through terminal end; result membership,
selected explanation, evidence, and final state must equal the no-disconnect case.
Duplicate cards, evidence, errors, and premature completed states fail acceptance.

## Required Execution

Phase 0 validation:

```sh
bun test tests/semantic_ui_acceptance/test_manifest.test.mjs
```

Phase 7 validation must run the manifest scenario matrix at both fixed viewports,
capture screenshots, produce a comparison report, archive failures, and fail the
release on any failed scenario or missing baseline/harness.
