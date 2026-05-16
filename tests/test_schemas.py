"""Schema validation tests for the LangGraph annotation workflow."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from schemas.annotation import (  # noqa: E402
    ALLOWED_PREDICATES,
    MetaphorAnnotation,
    MipvuJudgment,
    RdfTriple,
    create_empty_state,
)


class SchemaValidationTests(unittest.TestCase):
    def test_empty_state_creation(self) -> None:
        state = create_empty_state(document_id="doc-1", case_id="case-1", raw_text="본문")
        self.assertEqual(state["document_id"], "doc-1")
        self.assertEqual(state["candidates"], [])
        self.assertEqual(state["errors"], [])

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

    def test_mipvu_judgment_creation(self) -> None:
        judgment = MipvuJudgment(
            candidate_id="C001",
            sentence_id="S001",
            token="관철하다",
            context_sentence="조례의 적법성을 관철한다.",
            contextual_meaning="법적 기준이 실제 판단에서 유지되도록 한다.",
            basic_meaning="꿰뚫다.",
            basic_meaning_source="stdict",
            meaning_contrast="물리적 관통 의미와 법적 실현 의미가 대비된다.",
            comparison_possible=True,
            similarity=True,
            mipvu_label="MRW_candidate",
            confidence=0.65,
        )
        self.assertEqual(judgment.basic_meaning_source, "stdict")
        self.assertEqual(judgment.mipvu_label, "MRW_candidate")

    def test_compact_mipvu_judgment_creation(self) -> None:
        judgment = MipvuJudgment(candidate_id="C001", mipvu_label="uncertain")
        self.assertEqual(judgment.sentence_id, "")
        self.assertEqual(judgment.context_sentence, "")
        self.assertEqual(judgment.basic_meaning_source, "unavailable")

    def test_metaphor_annotation_creation(self) -> None:
        annotation = MetaphorAnnotation(
            metaphor_id="M001",
            candidate_id="C001",
            sentence_id="S001",
            surface_expression="법질서의 통일성",
            context_sentence="전체 법질서의 통일성을 확보한다.",
            conceptual_metaphor="LEGAL SYSTEM IS ORDER",
            metaphor_type="structural",
            source_domain="Order",
            target_domain="LegalSystem",
            legal_concept="법체계",
            confidence=0.8,
        )
        self.assertEqual(annotation.metaphor_type, "structural")
        self.assertEqual(annotation.opinion_type, "unknown")

    def test_compact_metaphor_annotation_creation(self) -> None:
        annotation = MetaphorAnnotation(candidate_id="C001", source_domain="Body", target_domain="Law")
        self.assertEqual(annotation.metaphor_id, "")
        self.assertEqual(annotation.context_sentence, "")
        self.assertEqual(annotation.metaphor_type, "uncertain")


if __name__ == "__main__":
    unittest.main()
