"""Parity checks between frozen schemas, fixtures, Python, and frontend types."""

from __future__ import annotations

import ast
import importlib.util
import json
import re
import unittest
from pathlib import Path
from typing import Any, Iterator, Set


ROOT = Path(__file__).resolve().parents[2] / "docs" / "semantic-contracts"


class SemanticTypeParityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.contract_manifest = self._load("contract-manifest.json")
        self.type_manifest = self._load("type-parity-manifest.json")
        self.python_text = (ROOT / self.type_manifest["pythonArtifact"]).read_text(encoding="utf-8")
        self.frontend_text = (ROOT / self.type_manifest["frontendArtifact"]).read_text(encoding="utf-8")

    def test_catalog_has_exactly_one_python_and_frontend_symbol_per_interface(self) -> None:
        catalog_names = {item["name"] for item in self.contract_manifest["schemas"]}
        typed_names = [item["name"] for item in self.type_manifest["interfaces"]]
        self.assertEqual(catalog_names, set(typed_names))
        self.assertEqual(len(typed_names), len(set(typed_names)))

        module = self._load_python_types()
        for item in self.type_manifest["interfaces"]:
            with self.subTest(interface=item["name"]):
                self.assertTrue(hasattr(module, item["pythonSymbol"]))
                self.assertRegex(
                    self.frontend_text,
                    rf"\b(?:interface|type)\s+{re.escape(item['frontendSymbol'])}\b",
                )

    def test_schema_properties_and_discriminator_literals_are_present_in_both_type_artifacts(self) -> None:
        schema_paths = self._public_schema_dependency_paths()
        property_names: Set[str] = set()
        literals: Set[str] = set()
        for schema_path in schema_paths:
            document = json.loads(schema_path.read_text(encoding="utf-8"))
            for node in self._walk(document):
                if not isinstance(node, dict):
                    continue
                property_names.update(node.get("properties", {}).keys())
                if isinstance(node.get("const"), str):
                    literals.add(node["const"])
                literals.update(value for value in node.get("enum", []) if isinstance(value, str))

        for token in sorted(property_names | literals):
            with self.subTest(token=token):
                quoted = re.escape(f'"{token}"')
                self.assertTrue(
                    token in self.python_text,
                    f"Python type artifact is missing {token!r}",
                )
                self.assertTrue(
                    token in self.frontend_text or re.search(quoted, self.frontend_text),
                    f"frontend type artifact is missing {token!r}",
                )

    def test_python_top_level_typed_dict_fields_match_object_schema_fields(self) -> None:
        module = self._load_python_types()
        schema_refs = {item["name"]: item["schemaRef"] for item in self.contract_manifest["schemas"]}
        for item in self.type_manifest["interfaces"]:
            schema, _ = self._resolve_root_schema(ROOT / schema_refs[item["name"]])
            properties = set(schema.get("properties", {}))
            symbol = getattr(module, item["pythonSymbol"])
            annotations = set(getattr(symbol, "__annotations__", {}))
            if properties:
                with self.subTest(interface=item["name"]):
                    self.assertEqual(properties, annotations)

    def test_every_catalog_schema_has_a_valid_fixture(self) -> None:
        fixtures = self._load("fixtures/contracts.json")
        valid_targets = {item["target"] for item in fixtures if item["valid"]}
        expected_targets = {item["schemaRef"] for item in self.contract_manifest["schemas"]}
        self.assertTrue(expected_targets <= valid_targets, expected_targets - valid_targets)

    def test_type_artifacts_parse_without_runtime_dependencies(self) -> None:
        ast.parse(self.python_text)
        self.assertIn("export type", self.frontend_text)
        self.assertNotIn("Record<", self.frontend_text)
        self.assertNotIn("Dict[", self.python_text)

    def _public_schema_dependency_paths(self) -> Set[Path]:
        pending = [ROOT / item["schemaRef"] for item in self.contract_manifest["schemas"]]
        resolved: Set[Path] = set()
        while pending:
            path = pending.pop().resolve()
            if path in resolved:
                continue
            resolved.add(path)
            document = json.loads(path.read_text(encoding="utf-8"))
            for node in self._walk(document):
                if isinstance(node, dict) and isinstance(node.get("$ref"), str):
                    filename = node["$ref"].split("#", 1)[0]
                    if filename:
                        pending.append(path.parent / filename)
        return resolved

    def _resolve_root_schema(self, path: Path) -> tuple[Any, Path]:
        document = json.loads(path.read_text(encoding="utf-8"))
        while isinstance(document, dict) and "$ref" in document:
            filename, _, fragment = document["$ref"].partition("#")
            path = path if not filename else (path.parent / filename).resolve()
            document = json.loads(path.read_text(encoding="utf-8"))
            if fragment:
                for token in fragment.lstrip("/").split("/"):
                    document = document[token.replace("~1", "/").replace("~0", "~")]
        return document, path

    @staticmethod
    def _walk(value: Any) -> Iterator[Any]:
        yield value
        if isinstance(value, dict):
            for child in value.values():
                yield from SemanticTypeParityTests._walk(child)
        elif isinstance(value, list):
            for child in value:
                yield from SemanticTypeParityTests._walk(child)

    def _load_python_types(self) -> Any:
        spec = importlib.util.spec_from_file_location("semantic_contract_python_types", ROOT / self.type_manifest["pythonArtifact"])
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    @staticmethod
    def _load(relative_path: str) -> Any:
        return json.loads((ROOT / relative_path).read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
