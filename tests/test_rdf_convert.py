"""Tests for deterministic RDF fallback mapping behavior."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from rdf.convert import fallback_mapping_from_annotation, mappings_to_turtle  # noqa: E402


class RdfFallbackMappingTests(unittest.TestCase):
    def test_same_source_domain_uses_same_uri_id(self) -> None:
        first = fallback_mapping_from_annotation(
            {
                "metaphor_id": "M001",
                "candidate_id": "C001",
                "legal_concept": "법체계",
                "source_domain": "질서",
                "target_domain": "LegalSystem",
                "conceptual_metaphor": "LEGAL SYSTEM IS ORDER",
            }
        )
        second = fallback_mapping_from_annotation(
            {
                "metaphor_id": "M002",
                "candidate_id": "C002",
                "legal_concept": "헌법질서",
                "source_domain": "질서",
                "target_domain": "ConstitutionalSystem",
                "conceptual_metaphor": "CONSTITUTIONAL SYSTEM IS ORDER",
            }
        )

        first_source = next(item for item in first["supporting_triples"] if item["predicate"] == "ex:hasSourceDomain")
        second_source = next(item for item in second["supporting_triples"] if item["predicate"] == "ex:hasSourceDomain")
        self.assertEqual(first_source["object_id"], second_source["object_id"])

    def test_validation_warning_comment_is_added_to_turtle(self) -> None:
        mapping = fallback_mapping_from_annotation(
            {
                "metaphor_id": "M003",
                "candidate_id": "C003",
                "legal_concept": "법질서",
                "source_domain": "질서",
                "target_domain": "LegalOrder",
                "conceptual_metaphor": "LEGAL ORDER IS ORDER",
            }
        )
        turtle = mappings_to_turtle([mapping], validation_results=[{"repair_needed": True, "issues": []}])
        self.assertIn("# validation_status: needs_repair", turtle)


if __name__ == "__main__":
    unittest.main()
