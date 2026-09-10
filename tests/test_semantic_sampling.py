import tempfile
import unittest
from pathlib import Path

from datamodelmatch.semantic_sampling import (
    ImageCandidate,
    VideoCandidate,
    sample_images,
    sample_videos,
)


class SemanticSamplingTests(unittest.TestCase):
    def test_image_strata_are_deterministic_and_report_fallback(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            candidates = []
            for name in ("a.jpg", "b.jpg", "c.png", "d.png"):
                (root / name).write_bytes(b"media")
                candidates.append(ImageCandidate(name, "sha256:" + (name.encode().hex() * 64)[:64], "camera-a" if name < "c" else "camera-b"))
            first = sample_images(root, candidates, 2, 42)
            second = sample_images(root, list(reversed(candidates)), 2, 42)
        self.assertEqual([item.to_dict() for item in first[0]], [item.to_dict() for item in second[0]])
        self.assertEqual(first[1].strategy, "deterministic_fallback")
        self.assertIn("clustering_metadata_or_embedding_unavailable", first[1].fallback_reason)
        self.assertEqual(first[1].coverage, 0.5)

    def test_video_representative_and_temporal_refs(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for name in ("one.mp4", "two.mp4"):
                (root / name).write_bytes(b"video")
            candidates = [
                VideoCandidate("one.mp4", "sha256:" + "1" * 64, 10_000, 100, 10.0, "scene-a", True, True),
                VideoCandidate("two.mp4", "sha256:" + "2" * 64, 8_000, 80, 10.0, "scene-b", True, True),
            ]
            refs, summary = sample_videos(root, candidates, 1, 3, 7, clip_duration_ms=500)
        self.assertEqual(summary.strategy, "temporal_uniform")
        self.assertEqual(len(refs), 3)
        for ref in refs:
            self.assertEqual(ref.kind, "clip")
            self.assertEqual(ref.video_path, ref.path)
            self.assertGreaterEqual(ref.end_ms, ref.start_ms + 1)
            self.assertGreaterEqual(ref.frame_end, ref.frame_start)

    def test_empty_and_unsafe_candidates_are_explicit(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            refs, summary = sample_images(root, [], 1, 0)
            self.assertEqual(refs, ())
            self.assertEqual(summary.fallback_reason, "empty_candidates")
            (root / "a.jpg").write_bytes(b"x")
            with self.assertRaises(ValueError):
                sample_images(root, [ImageCandidate("../a.jpg", "sha256:" + "a" * 64)], 1, 0)
