"""Dependency-free verification for the frozen semantic JSON Schema package."""

from __future__ import annotations

import copy
import datetime as dt
import json
import re
import unittest
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parents[2] / "docs" / "semantic-contracts"


class ValidationError(AssertionError):
    pass


class Draft202012SubsetValidator:
    """Validates every JSON Schema keyword used by the frozen local schemas."""

    def __init__(self, root: Path) -> None:
        self.root = root
        self._documents: Dict[Path, Dict[str, Any]] = {}

    def validate_target(self, target: str, instance: Any) -> None:
        filename, _, fragment = target.partition("#")
        document_path = (self.root / filename).resolve()
        schema = self._resolve_pointer(self._load(document_path), fragment)
        self._validate(instance, schema, document_path, "$")

    def _load(self, path: Path) -> Dict[str, Any]:
        if path not in self._documents:
            self._documents[path] = json.loads(path.read_text(encoding="utf-8"))
        return self._documents[path]

    def _resolve_pointer(self, document: Any, fragment: str) -> Any:
        if not fragment:
            return document
        if not fragment.startswith("/"):
            raise ValidationError(f"unsupported JSON pointer fragment #{fragment}")
        value = document
        for token in fragment[1:].split("/"):
            value = value[token.replace("~1", "/").replace("~0", "~")]
        return value

    def _resolve_ref(self, ref: str, current_path: Path) -> Tuple[Any, Path]:
        filename, _, fragment = ref.partition("#")
        target_path = current_path if not filename else (current_path.parent / filename).resolve()
        return self._resolve_pointer(self._load(target_path), fragment), target_path

    def _validate(self, value: Any, schema: Any, current_path: Path, path: str) -> None:
        if isinstance(schema, bool):
            if not schema:
                raise ValidationError(f"{path}: false schema")
            return
        if "$ref" in schema:
            resolved, resolved_path = self._resolve_ref(schema["$ref"], current_path)
            self._validate(value, resolved, resolved_path, path)
            return
        if "const" in schema and value != schema["const"]:
            raise ValidationError(f"{path}: expected const {schema['const']!r}")
        if "enum" in schema and value not in schema["enum"]:
            raise ValidationError(f"{path}: value {value!r} is outside enum")
        if "allOf" in schema:
            for branch in schema["allOf"]:
                self._validate(value, branch, current_path, path)
        if "anyOf" in schema:
            self._require_one(value, schema["anyOf"], current_path, path, minimum=1)
        if "oneOf" in schema:
            self._require_one(value, schema["oneOf"], current_path, path, minimum=1, maximum=1)
        if "not" in schema:
            try:
                self._validate(value, schema["not"], current_path, path)
            except ValidationError:
                pass
            else:
                raise ValidationError(f"{path}: disallowed by not")
        if "if" in schema:
            try:
                self._validate(value, schema["if"], current_path, path)
            except ValidationError:
                branch = schema.get("else")
            else:
                branch = schema.get("then")
            if branch is not None:
                self._validate(value, branch, current_path, path)
        expected = schema.get("type")
        if expected is not None:
            types = expected if isinstance(expected, list) else [expected]
            if not any(self._is_type(value, item) for item in types):
                raise ValidationError(f"{path}: expected {types}, got {type(value).__name__}")
        if isinstance(value, dict):
            self._validate_object(value, schema, current_path, path)
        elif isinstance(value, list):
            self._validate_array(value, schema, current_path, path)
        elif isinstance(value, str):
            self._validate_string(value, schema, path)
        elif isinstance(value, (int, float)) and not isinstance(value, bool):
            self._validate_number(value, schema, path)

    def _require_one(
        self,
        value: Any,
        branches: List[Any],
        current_path: Path,
        path: str,
        minimum: int,
        maximum: int | None = None,
    ) -> None:
        matches = 0
        for branch in branches:
            try:
                self._validate(value, branch, current_path, path)
            except ValidationError:
                continue
            matches += 1
        if matches < minimum or (maximum is not None and matches > maximum):
            raise ValidationError(f"{path}: expected {minimum}{'..' + str(maximum) if maximum is not None else '+'} matching branches, got {matches}")

    @staticmethod
    def _is_type(value: Any, expected: str) -> bool:
        return {
            "object": isinstance(value, dict),
            "array": isinstance(value, list),
            "string": isinstance(value, str),
            "integer": isinstance(value, int) and not isinstance(value, bool),
            "number": isinstance(value, (int, float)) and not isinstance(value, bool),
            "boolean": isinstance(value, bool),
            "null": value is None,
        }.get(expected, False)

    def _validate_object(self, value: Dict[str, Any], schema: Dict[str, Any], current_path: Path, path: str) -> None:
        required = schema.get("required", [])
        missing = [key for key in required if key not in value]
        if missing:
            raise ValidationError(f"{path}: missing required {missing}")
        properties = schema.get("properties", {})
        if schema.get("additionalProperties") is False:
            extras = set(value) - set(properties)
            if extras:
                raise ValidationError(f"{path}: unexpected properties {sorted(extras)}")
        for key, child_schema in properties.items():
            if key in value:
                self._validate(value[key], child_schema, current_path, f"{path}.{key}")

    def _validate_array(self, value: List[Any], schema: Dict[str, Any], current_path: Path, path: str) -> None:
        if len(value) < schema.get("minItems", 0):
            raise ValidationError(f"{path}: fewer than minItems")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise ValidationError(f"{path}: more than maxItems")
        if schema.get("uniqueItems") and len({json.dumps(item, sort_keys=True) for item in value}) != len(value):
            raise ValidationError(f"{path}: duplicate items")
        if "items" in schema:
            for index, item in enumerate(value):
                self._validate(item, schema["items"], current_path, f"{path}[{index}]")

    @staticmethod
    def _validate_string(value: str, schema: Dict[str, Any], path: str) -> None:
        if len(value) < schema.get("minLength", 0):
            raise ValidationError(f"{path}: shorter than minLength")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise ValidationError(f"{path}: longer than maxLength")
        if "pattern" in schema and re.search(schema["pattern"], value) is None:
            raise ValidationError(f"{path}: does not match pattern")
        if schema.get("format") == "date-time":
            try:
                dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
            except ValueError as exc:
                raise ValidationError(f"{path}: invalid date-time") from exc
        if schema.get("format") == "uri":
            parsed = urlparse(value)
            if not parsed.scheme or not parsed.netloc:
                raise ValidationError(f"{path}: invalid URI")

    @staticmethod
    def _validate_number(value: float, schema: Dict[str, Any], path: str) -> None:
        if "minimum" in schema and value < schema["minimum"]:
            raise ValidationError(f"{path}: below minimum")
        if "maximum" in schema and value > schema["maximum"]:
            raise ValidationError(f"{path}: above maximum")
        if "exclusiveMinimum" in schema and value <= schema["exclusiveMinimum"]:
            raise ValidationError(f"{path}: below exclusiveMinimum")


class SemanticContractSchemaTests(unittest.TestCase):
    def setUp(self) -> None:
        self.validator = Draft202012SubsetValidator(ROOT)

    def test_schemas_are_json_and_draft_2020_12(self) -> None:
        schemas = sorted(ROOT.glob("*.schema.json"))
        self.assertGreaterEqual(len(schemas), 9)
        for path in schemas:
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(document["$schema"], "https://json-schema.org/draft/2020-12/schema", path.name)
            self.assertIn("$id", document, path.name)

    def test_declared_object_schemas_are_closed(self) -> None:
        for schema_path in ROOT.glob("*.schema.json"):
            document = json.loads(schema_path.read_text(encoding="utf-8"))
            for location, node in self._walk(document):
                declared_type = node.get("type") if isinstance(node, dict) else None
                types = declared_type if isinstance(declared_type, list) else [declared_type]
                if "object" in types:
                    self.assertIs(
                        node.get("additionalProperties"),
                        False,
                        f"{schema_path.name}{location} must close its object",
                    )

    def test_valid_and_invalid_contract_fixtures(self) -> None:
        fixtures = json.loads((ROOT / "fixtures" / "contracts.json").read_text(encoding="utf-8"))
        self.assertGreaterEqual(len(fixtures), 16)
        for fixture in fixtures:
            with self.subTest(fixture=fixture["name"]):
                if fixture["valid"]:
                    self.validator.validate_target(fixture["target"], fixture["instance"])
                else:
                    with self.assertRaises(ValidationError):
                        self.validator.validate_target(fixture["target"], fixture["instance"])

    def test_manifest_is_valid_and_all_public_schema_files_exist(self) -> None:
        manifest_path = ROOT / "contract-manifest.json"
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        self.validator.validate_target("schema-catalog.json", manifest)
        for entry in manifest["schemas"]:
            self.assertTrue((ROOT / entry["schemaRef"]).is_file(), entry["name"])

    def test_closed_objects_reject_unbounded_top_level_fields(self) -> None:
        fixtures = json.loads((ROOT / "fixtures" / "contracts.json").read_text(encoding="utf-8"))
        valid_profile = next(item for item in fixtures if item["name"] == "valid-dataset-semantic-profile")
        invalid = copy.deepcopy(valid_profile["instance"])
        invalid["unbounded"] = {"not": "allowed"}
        with self.assertRaises(ValidationError):
            self.validator.validate_target(valid_profile["target"], invalid)

    def test_each_task_specific_preference_union_branch_is_valid(self) -> None:
        fixtures = json.loads((ROOT / "fixtures" / "contracts.json").read_text(encoding="utf-8"))
        base = copy.deepcopy(next(item for item in fixtures if item["name"] == "valid-task-profile")["instance"])
        variants = [
            {"task": "image_classification", "longTail": ["high"], "domainFeatures": ["cross_domain"]},
            {"task": "object_detection", "scaleDistribution": ["small_target_heavy"], "occlusion": ["frequent"]},
            {"task": "multi_object_tracking", "temporalContinuity": ["continuous"], "motionChallenge": ["high"]},
            {"task": "semantic_segmentation", "boundaryComplexity": ["high"], "smallObjectRatio": ["high"]},
            {"task": "instance_segmentation", "boundaryComplexity": ["high"], "smallObjectRatio": ["high"]},
            {"task": "pose_keypoints", "keypointVisibility": ["moderate"], "viewpointChallenge": ["high"]},
            {"task": "action_video_understanding", "actionTypes": ["turning"], "temporalDynamics": ["high"]},
            {"task": "video_anomaly_detection", "anomalyTypes": ["intrusion"], "temporalSparsity": ["high"]},
            {"task": "reid_retrieval", "identityDiversity": ["high"], "crossCameraVariation": ["high"], "crossDomainVariation": ["moderate"]},
        ]
        for variant in variants:
            with self.subTest(task=variant["task"]):
                instance = copy.deepcopy(base)
                instance["preferred"]["taskSpecificPreferences"] = [variant]
                self.validator.validate_target("task-semantic-profile.schema.json", instance)

    @staticmethod
    def _walk(value: Any, location: str = ""):
        if isinstance(value, dict):
            yield location, value
            for key, child in value.items():
                yield from SemanticContractSchemaTests._walk(child, f"{location}/{key}")
        elif isinstance(value, list):
            for index, child in enumerate(value):
                yield from SemanticContractSchemaTests._walk(child, f"{location}/{index}")


if __name__ == "__main__":
    unittest.main()
