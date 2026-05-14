"""Tests for deterministic RDF mapping behavior."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rdf.convert import (  # noqa: E402
    mapping_from_mipvu_annotation,
    mappings_to_turtle,
    normalize_rdf_mappings,
)


class RdfMappingTests(unittest.TestCase):
    def test_same_source_domain_uses_same_uri_id(self) -> None:
        first = mapping_from_mipvu_annotation(
            {
                "lemma_group_id": "lg001",
                "lemma": "서다",
                "mipvu_label": "MRW",
                "source_domain": "질서",
                "target_domain": "LegalSystem",
                "conceptual_metaphor": "LEGAL SYSTEM IS ORDER",
            }
        )
        second = mapping_from_mipvu_annotation(
            {
                "lemma_group_id": "lg002",
                "lemma": "세우다",
                "mipvu_label": "MRW",
                "source_domain": "질서",
                "target_domain": "ConstitutionalSystem",
                "conceptual_metaphor": "CONSTITUTIONAL SYSTEM IS ORDER",
            }
        )

        first_source = next(item for item in first["supporting_triples"] if item["predicate"] == "ex:hasSourceDomain")
        second_source = next(item for item in second["supporting_triples"] if item["predicate"] == "ex:hasSourceDomain")
        self.assertEqual(first_source["object_id"], second_source["object_id"])

    def test_validation_warning_comment_is_added_to_turtle(self) -> None:
        mapping = mapping_from_mipvu_annotation(
            {
                "lemma_group_id": "lg003",
                "lemma": "질서",
                "mipvu_label": "MRW",
                "source_domain": "질서",
                "target_domain": "LegalOrder",
                "conceptual_metaphor": "LEGAL ORDER IS ORDER",
            }
        )
        turtle = mappings_to_turtle([mapping], validation_results=[{"repair_needed": True, "issues": []}])
        self.assertIn("# validation_status: needs_repair", turtle)

    def test_mipvu_annotation_maps_kg_layers_to_turtle(self) -> None:
        mapping = mapping_from_mipvu_annotation(
            {
                "lemma_group_id": "lg-collapse",
                "lemma": "무너지다",
                "mipvu_label": "MRW",
                "judgment_reason": "basic meaning에서 indirect 확장이므로 MRW로 판단한다.",
                "source_domain": "BUILDING / PHYSICAL STRUCTURE",
                "target_domain": "ARGUMENT / LEGAL REASONING",
                "conceptual_metaphor": "ARGUMENT IS A STRUCTURE",
                "lakoff_johnson_type": "structural",
                "confidence": 0.91,
                "sample_sentences": ["그 주장은 무너졌다."],
            }
        )

        turtle = mappings_to_turtle([mapping])

        self.assertIn("ex:isConceptualizedAs", turtle)
        self.assertIn("BUILDING / PHYSICAL STRUCTURE", turtle)
        self.assertIn("ARGUMENT / LEGAL REASONING", turtle)
        self.assertIn("ARGUMENT IS A STRUCTURE", turtle)
        self.assertIn('ex:hasMIPVULabel "MRW_INDIRECT"', turtle)
        self.assertIn('ex:hasMetaphorType "STRUCTURAL"', turtle)

    def test_normalize_payload_prefers_mipvu_annotations(self) -> None:
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
                },
                {
                    "lemma_group_id": "lg002",
                    "lemma": "이유",
                    "mipvu_label": "non_MRW",
                    "source_domain": "",
                    "target_domain": "",
                    "conceptual_metaphor": "",
                },
                {
                    "lemma_group_id": "lg003",
                    "lemma": "맡기다",
                    "mipvu_label": "MRW_candidate",
                    "source_domain": "DELEGATED RESPONSIBILITY",
                    "target_domain": "LEGAL DISCRETION",
                    "conceptual_metaphor": "LEGAL DISCRETION IS DELEGATED RESPONSIBILITY",
                },
                {
                    "lemma_group_id": "lg004",
                    "lemma": "흔들리다",
                    "mipvu_label": "borderline_candidate",
                    "source_domain": "PHYSICAL INSTABILITY",
                    "target_domain": "TESTIMONY CREDIBILITY",
                    "conceptual_metaphor": "CREDIBILITY IS PHYSICAL STABILITY",
                },
            ],
        }

        mappings = normalize_rdf_mappings(payload)

        self.assertEqual(len(mappings), 1)
        primary = mappings[0]["primary_triple"]
        self.assertEqual(primary["subject_label"], "ARGUMENT")
        self.assertEqual(primary["object_label"], "BUILDING")

    def test_normalize_payload_accepts_batch_judgments(self) -> None:
        payload = {
            "judgments": [
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

        mappings = normalize_rdf_mappings(payload)

        self.assertEqual(len(mappings), 1)
        mipvu_label = next(
            item
            for item in mappings[0]["supporting_triples"]
            if item["predicate"] == "ex:hasMIPVULabel"
        )
        self.assertEqual(mipvu_label["object_label"], "MRW_INDIRECT")


if __name__ == "__main__":
    unittest.main()
