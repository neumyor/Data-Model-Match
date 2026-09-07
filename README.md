# DataModelMatch

DataModelMatch uses a real OpenAI-compatible LLM endpoint to identify likely field mappings between two JSON data models.

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
  "matches": [
    {
      "source_field": "user_id",
      "target_field": "id",
      "confidence": 0.9,
      "reason": "Both identify the user"
    }
  ],
  "unmatched_source_fields": [],
  "unmatched_target_fields": []
}
```

Model files can be ordinary JSON object samples or JSON Schema-style objects with a `properties` object. The LLM result is rejected if it invents fields, duplicates a mapping, uses an invalid confidence, or fails to account for every input field.

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
