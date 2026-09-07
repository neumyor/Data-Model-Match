# DataModelMatch

DataModelMatch uses a real OpenAI-compatible LLM endpoint to identify likely field mappings between two JSON data models.

The minimal version accepts versioned multi-entity model documents and returns structured source-to-target field references. See [docs/design.md](docs/design.md) for the input and output contract.

## Quick start

The CLI reads LLM settings from the root `config.llm.json` file. The file is intentionally ignored by Git because it contains a credential.

```sh
python3 -m unittest discover -s tests
PYTHONPATH=src python3 -m datamodelmatch.cli \
  examples/source_user.json \
  examples/target_customer.json
```

The command prints a validated JSON result:

```json
{
  "sourceModelId": "crm",
  "targetModelId": "billing",
  "matches": [
    {
      "source": {"entityId": "customer", "fieldId": "user_id"},
      "target": {"entityId": "account", "fieldId": "account_id"},
      "kind": "semantic",
      "confidence": 0.9,
      "reason": "Both identify the customer"
    }
  ],
  "unmatchedSourceFields": [],
  "unmatchedTargetFields": [
    {"entityId": "account", "fieldId": "status"}
  ],
  "meta": {
    "model": "glm-5.3-flash",
    "attemptCount": 1
  }
}
```

Model files use the versioned multi-entity format described in [docs/design.md](docs/design.md). Legacy JSON object samples and simple JSON Schema objects are still accepted and normalized into a single entity. The LLM result is rejected if it invents fields, duplicates a mapping, uses an invalid match kind or confidence, or returns a malformed field reference. Unmatched fields are calculated by the application.

## Real acceptance

The real acceptance path reads the ignored root `config.llm.json` and calls the configured remote LLM endpoint:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=src python3 -m datamodelmatch.cli \
  examples/source_user.json \
  examples/target_customer.json \
  --timeout 90
```

Acceptance requires a valid JSON result whose mappings reference only input fields, contain no duplicate source or target fields, and account for every field as matched or unmatched. The API key is never printed or committed.

## Development

The project uses only Python's standard library at runtime. Keep public interfaces typed and validate all network and model-response boundaries. Read [AGENTS.md](AGENTS.md) before changing the project.
