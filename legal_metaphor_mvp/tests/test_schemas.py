"""Schema validation tests for the lemma MIPVU/KG pipeline."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from schemas.annotation import (  # noqa: E402
    ALLOWED_PREDICATES,
    RdfTriple,
    create_empty_state,
)


class SchemaValidationTests(unittest.TestCase):
    def test_empty_state_creation(self) -> None:
        state = create_empty_state(document_id="doc-1", case_id="case-1", raw_text="본문")
        self.assertEqual(state["document_id"], "doc-1")
        self.assertNotIn("candidates", state)
        self.assertEqual(state["errors"], [])
        self.assertNotIn("metaphor_annotations", state)

    def test_allowed_predicates_are_generated(self) -> None:
        self.assertIn("ex:hasSourceDomain", ALLOWED_PREDICATES)
        self.assertIn("ex:isConceptualizedAs", ALLOWED_PREDICATES)

    def test_valid_rdf_triple_creation(self) -> None:
        triple = RdfTriple(
            subject_label="법체계",
            subject_type="LegalConcept",
            subject_id="LegalSystem",
            predicate="ex:hasSourceDomain",
            object_label="질서",
            object_type="SourceDomain",
            object_id="Order",
        )
        self.assertEqual(triple.predicate, "ex:hasSourceDomain")

    def test_invalid_rdf_predicate_is_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            RdfTriple(
                subject_label="법체계",
                subject_type="LegalConcept",
                subject_id="LegalSystem",
                predicate="잘못된값",
                object_label="질서",
                object_type="SourceDomain",
                object_id="Order",
            )


if __name__ == "__main__":
    unittest.main()
