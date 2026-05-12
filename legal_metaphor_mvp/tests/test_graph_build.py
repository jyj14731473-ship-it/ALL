"""Tests for local RDFLib knowledge graph construction."""

from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from graph_build import graph_from_annotation_payload, graph_stats, serialize_graph  # noqa: E402


class GraphBuildTests(unittest.TestCase):
    def test_build_graph_from_mipvu_annotation_payload(self) -> None:
        payload = {
            "mipvu_annotations": [
                {
                    "lemma_group_id": "lg-collapse",
                    "lemma": "무너지다",
                    "mipvu_label": "MRW",
                    "judgment_reason": "indirect 확장이다.",
                    "source_domain": "BUILDING / PHYSICAL STRUCTURE",
                    "target_domain": "ARGUMENT / LEGAL REASONING",
                    "conceptual_metaphor": "ARGUMENT IS A STRUCTURE",
                    "lakoff_johnson_type": "structural",
                    "confidence": 0.91,
                    "sample_sentences": ["그 주장은 무너졌다."],
                }
            ]
        }

        graph = graph_from_annotation_payload(payload)
        stats = graph_stats(graph)

        self.assertGreater(stats["triple_count"], 0)

    def test_serialize_graph_to_turtle(self) -> None:
        payload = {
            "mipvu_annotations": [
                {
                    "lemma_group_id": "lg001",
                    "lemma": "무너지다",
                    "mipvu_label": "MRW",
                    "judgment_reason": "indirect",
                    "source_domain": "BUILDING",
                    "target_domain": "ARGUMENT",
                    "conceptual_metaphor": "ARGUMENT IS A BUILDING",
                    "lakoff_johnson_type": "structural",
                    "confidence": 0.8,
                }
            ]
        }
        graph = graph_from_annotation_payload(payload)

        with tempfile.TemporaryDirectory() as tmpdir:
            output = Path(tmpdir) / "kg.ttl"
            serialize_graph(graph, output)

            text = output.read_text(encoding="utf-8")

        self.assertIn("hasMIPVULabel", text)
        self.assertIn("ARGUMENT IS A BUILDING", text)


if __name__ == "__main__":
    unittest.main()
