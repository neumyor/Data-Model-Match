"""P0 contract checks for dataset modality and VLM video transport.

Callers: profile producers and frontend consumers read these closed contracts.
Boundary: event is a dataset modality definition; V1 VLM video transport is
frames-only and never exposes a native-video configuration mode.
Inputs/outputs: contract JSON and static type artifacts are checked directly.
Failure paths: unsupported modalities and native_video configuration are
rejected by schema fixtures; drift in either type artifact fails this suite.
"""

from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2] / "docs" / "semantic-contracts"


class VlmAndModalityContractTests(unittest.TestCase):
    def test_dataset_modality_definition_includes_event(self) -> None:
        common = json.loads((ROOT / "common.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(
            common["$defs"]["datasetModality"]["enum"],
            ["RGB", "infrared", "depth", "thermal", "multimodal", "event"],
        )
        profile = json.loads((ROOT / "dataset-semantic-profile.schema.json").read_text(encoding="utf-8"))
        task = json.loads((ROOT / "task-semantic-profile.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(
            profile["properties"]["structuralSemantics"]["properties"]["modalities"]["items"],
            {"$ref": "common.schema.json#/$defs/datasetModality"},
        )
        self.assertIn(
            "event",
            task["properties"]["required"]["properties"]["modalities"]["items"]["enum"],
        )

    def test_v1_vlm_video_input_is_frames_only(self) -> None:
        schema = json.loads((ROOT / "vlm-configuration.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(schema["properties"]["videoInput"]["properties"]["mode"], {"const": "frames_only"})

    def test_static_type_artifacts_match_p0_contract(self) -> None:
        python_types = (ROOT / "python_types.py").read_text(encoding="utf-8")
        frontend_types = (ROOT / "frontend-types.d.ts").read_text(encoding="utf-8")
        for artifact in (python_types, frontend_types):
            self.assertIn('"event"', artifact)
            self.assertNotIn("native_video", artifact)


if __name__ == "__main__":
    unittest.main()
