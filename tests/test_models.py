import json
import tempfile
import unittest
from pathlib import Path

from datamodelmatch.models import Entity, Field, ModelError, load_model, load_model_document


class ModelDocumentTests(unittest.TestCase):
    def test_loads_versioned_multi_entity_document(self) -> None:
        document = {
            "version": 1,
            "id": "crm",
            "name": "CRM",
            "entities": [
                {
                    "id": "customer",
                    "name": "Customer",
                    "description": "A customer record",
                    "fields": [
                        {
                            "id": "customer-id",
                            "name": "id",
                            "dataType": "uuid",
                            "nullable": False,
                            "description": "Customer identifier",
                        },
                        {
                            "id": "customer-email",
                            "name": "email",
                            "dataType": "string",
                            "nullable": True,
                            "description": "Customer email address",
                        },
                    ],
                },
                {
                    "id": "order",
                    "name": "Order",
                    "description": "An order record",
                    "fields": [
                        {
                            "id": "order-id",
                            "name": "id",
                            "dataType": "uuid",
                            "nullable": False,
                            "description": "Order identifier",
                        },
                    ],
                },
            ],
        }

        model = _load_document(document)

        self.assertEqual(model.version, "1")
        self.assertEqual(model.entities[0].fields[0].data_type, "uuid")
        self.assertEqual(model.entities[0].fields[0].dataType, "uuid")
        self.assertEqual(model.entities[0].fields[0].type, "uuid")
        self.assertFalse(model.entities[0].fields[0].nullable)
        self.assertEqual(model.entities[1].fields[0].id, "order-id")

    def test_rejects_missing_or_blank_required_values(self) -> None:
        document = _valid_document()
        del document["entities"][0]["fields"][0]["dataType"]

        with self.assertRaisesRegex(ModelError, "dataType"):
            _load_document(document)

        document = _valid_document()
        document["entities"][0]["description"] = "  "

        with self.assertRaisesRegex(ModelError, "description.*non-empty"):
            _load_document(document)

        document = _valid_document()
        document["version"] = 2

        with self.assertRaisesRegex(ModelError, "version must be 1"):
            _load_document(document)

    def test_rejects_empty_collections_and_non_boolean_nullable(self) -> None:
        document = _valid_document()
        document["entities"] = []

        with self.assertRaisesRegex(ModelError, "entities.*non-empty"):
            _load_document(document)

        document = _valid_document()
        document["entities"][0]["fields"] = []

        with self.assertRaisesRegex(ModelError, "fields.*non-empty"):
            _load_document(document)

        document = _valid_document()
        document["entities"][0]["fields"][0]["nullable"] = "false"

        with self.assertRaisesRegex(ModelError, "nullable.*boolean"):
            _load_document(document)

    def test_rejects_duplicate_ids_within_their_scopes(self) -> None:
        document = _valid_document()
        duplicate_entity = _valid_document()["entities"][0]
        duplicate_entity["name"] = "Another customer"
        document["entities"].append(duplicate_entity)

        with self.assertRaisesRegex(ModelError, "Entity ids.*unique"):
            _load_document(document)

        document = _valid_document()
        duplicate_field = document["entities"][0]["fields"][0].copy()
        duplicate_field["name"] = "external_id"
        document["entities"][0]["fields"].append(duplicate_field)

        with self.assertRaisesRegex(ModelError, "Field ids.*unique"):
            _load_document(document)

    def test_allows_matching_field_ids_in_different_entities(self) -> None:
        document = _valid_document()
        second_entity = _valid_document()["entities"][0]
        second_entity["id"] = "order"
        second_entity["name"] = "Order"
        second_entity["fields"][0]["name"] = "order_id"
        document["entities"].append(second_entity)

        model = _load_document(document)

        self.assertEqual(model.entities[0].fields[0].id, model.entities[1].fields[0].id)

    def test_normalizes_legacy_sample_and_preserves_legacy_loader(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "account.json"
            path.write_text(json.dumps({"id": 7, "email": "ada@example.com"}), encoding="utf-8")

            legacy = load_model(path)
            document = load_model_document(path)

        self.assertEqual(legacy.name, "account")
        self.assertEqual([(field.name, field.type) for field in legacy.fields], [
            ("id", "integer"),
            ("email", "string"),
        ])
        self.assertEqual(document.version, "legacy")
        self.assertEqual(document.entities[0].id, "account")
        self.assertEqual(document.entities[0].fields[0].id, "id")
        self.assertEqual(document.entities[0].fields[0].description, "Legacy field 'id'")

    def test_supports_camel_case_field_type_and_validates_direct_entities(self) -> None:
        field = Field(
            name="id",
            id="customer-id",
            dataType="uuid",
            nullable=False,
            description="Customer identifier",
        )
        self.assertEqual(field.data_type, "uuid")

        with self.assertRaisesRegex(ModelError, "Field description.*non-empty"):
            Entity("customer", "Customer", "A customer record", (
                Field(name="id", id="customer-id", data_type="uuid"),
            ))


def _load_document(document: dict) -> object:
    with tempfile.TemporaryDirectory() as directory:
        path = Path(directory) / "document.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        return load_model_document(path)


def _valid_document() -> dict:
    return {
        "version": 1,
        "id": "crm",
        "name": "CRM",
        "entities": [
            {
                "id": "customer",
                "name": "Customer",
                "description": "A customer record",
                "fields": [
                    {
                        "id": "customer-id",
                        "name": "id",
                        "dataType": "uuid",
                        "nullable": False,
                        "description": "Customer identifier",
                    },
                ],
            },
        ],
    }


if __name__ == "__main__":
    unittest.main()
