# WP0-A Plan: Frozen Semantic Contracts

## Goal

Create a self-contained, executable Draft 2020-12 contract package for the
version 1 public visual-semantic APIs: `DatasetSemanticProfile`,
`TaskSemanticProfile`, `DatasetTaskMatchResult`, asynchronous profile and
match jobs, structured errors, and SSE payloads.

## Non-goals

- Do not implement or wire production application modules, HTTP routes,
  persistence, UI, LLM/VLM clients, sampling, aggregation, or matching logic.
- Do not change the legacy `DatasetProfile`, `/api/compatibility`, or existing
  resource contracts.
- Do not choose a VLM provider or perform a real LLM/VLM API call.

## Inputs

- `AGENTS.md`
- `docs/dataset-management-ui-phased-acceptance.md`, especially sections 2--5,
  7--9, 11--13
- Existing `DatasetProfile` only as the migration source contract; it is not a
  compatible replacement for a semantic profile.

## Outputs

- Closed Draft 2020-12 JSON Schemas and valid/invalid JSON fixtures under
  `docs/semantic-contracts/`.
- Closed Python `TypedDict`/`Literal` definitions and strict TypeScript
  declarations, both mapped one-to-one to the public schema catalog.
- A concise RFC defining field semantics, enums, defaults, ranges, references,
  VLM configuration precedence, SSE lifecycle, idempotency/concurrency, and
  legacy migration.
- A standard-library contract test runner under `tests/semantic_contracts/`.

## Dependencies

- Python 3.9+ standard library only for the test runner.
- The frozen version-1 public boundary described in the acceptance document.
- Production implementers must use an independently conforming JSON Schema
  Draft 2020-12 validator at API/persistence boundaries; the local runner
  verifies the exercised subset and fixtures without adding a dependency.

## Allowed Paths

- `docs/semantic-contracts/` (new files only)
- `tests/semantic_contracts/` (new files only)

## Prohibited Paths

- `pyproject.toml`
- `src/datamodelmatch/resource_types.py`
- `src/datamodelmatch/resource_store.py`
- `src/datamodelmatch/resource_cli.py`
- `web/server.ts`, `web/app.js`, `web/index.html`, `web/styles.css`
- Existing tests, `config.llm.json`, and `_reference_only/`

## Public Interfaces

- Schemas are identified by stable `$id` URLs under
  `https://datamodelmatch.local/schemas/semantic/v1/`.
- API payload schemas preserve the endpoints frozen in the acceptance document.
- All public objects use `additionalProperties: false`; extensions require a
  future schema version and approved change record.

## Failure Cases

- Unsupported schema version, unknown enums, malformed identifiers, missing
  evidence, invalid event sequencing, result/job type mismatch, bad
  suitability score, VLM configuration ambiguity, stale concurrent publication,
  and attempts to represent unknown as omission or `null`.
- The schemas intentionally reject unbounded payload objects and raw media,
  prompts, model responses, credentials, or authorization headers.

## Validation

1. Run `python -m unittest discover -s tests/semantic_contracts -v`.
2. Verify every schema parses as JSON, has Draft 2020-12 metadata, and is
   recursively closed where it defines an object.
3. Validate every valid fixture and reject every invalid fixture.
4. Deterministically verify public-schema catalog coverage, fixture coverage,
   Python symbols, frontend symbols, schema property names, and enum/const
   discriminators without installing dependencies.
5. Run `git diff --check` and inspect the changed-path list.

## Completion Criteria

- The contract package covers all named WP0-A payloads, fixtures exercise normal
  and material failure paths, and the RFC resolves the lifecycle/configuration
  rules required before downstream work packages can start.
