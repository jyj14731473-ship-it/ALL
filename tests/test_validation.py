from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from datetime import UTC, datetime

import pytest

from all_metaphor.config import RuntimeSettings
from all_metaphor.observability import RunObserver
from all_metaphor.schemas import (
    DictionaryMeaning,
    DocumentMetadata,
    ErrorCode,
    IntermediateAnalysis,
    LexicalUnit,
    MetaphorCandidate,
    MetaphorType,
    MipvuDecision,
    RunMetadata,
    RunStatus,
)
from all_metaphor.validation import (
    VALIDATE_INTERMEDIATE_STAGE,
    is_rdf_mappable,
    validate_intermediate,
)


def make_lexical_unit(
    unit_id: str = "unit-001",
    *,
    local_context: str = "계약의 성립 여부를 판단한다.",
) -> LexicalUnit:
    return LexicalUnit(
        unit_id=unit_id,
        surface="성립",
        lemma="성립",
        pos="Noun",
        start_char=0,
        end_char=2,
        sentence_id="sentence-001",
        local_context=local_context,
        local_context_char_count=len(local_context),
        is_candidate=True,
        filter_reason=None,
    )


def meaning() -> DictionaryMeaning:
    return DictionaryMeaning(
        sense_id="sense-001",
        definition="어떤 일이 이루어짐.",
    )


def make_candidate(
    candidate_id: str = "candidate-001",
    *,
    unit_id: str = "unit-001",
    decision: MipvuDecision = MipvuDecision.METAPHORICAL,
    dictionary_meanings: list[DictionaryMeaning] | None = None,
    metaphor_type: MetaphorType | None = MetaphorType.INDIRECT,
    contextual_meaning: str | None = "법률 요건이 갖추어짐.",
    basic_meaning: str | None = "어떤 일이 이루어짐.",
    meaning_contrast: str | None = "법률 요건의 성취를 일의 성립과 비교함.",
    source_domain: str | None = "일의 성립",
    target_domain: str | None = "법률관계",
    confidence: float = 0.8,
) -> MetaphorCandidate:
    if dictionary_meanings is None:
        dictionary_meanings = [meaning()]
    return MetaphorCandidate(
        candidate_id=candidate_id,
        unit_id=unit_id,
        dictionary_query="성립",
        dictionary_meanings=dictionary_meanings,
        contextual_meaning=contextual_meaning,
        basic_meaning=basic_meaning,
        meaning_contrast=meaning_contrast,
        mipvu_decision=decision,
        metaphor_type=metaphor_type,
        source_domain=source_domain,
        target_domain=target_domain,
        confidence=confidence,
        llm_rationale="MIPVU comparison rationale.",
        errors=[],
    )


def make_analysis(
    candidates: Sequence[MetaphorCandidate],
    *,
    lexical_units: Sequence[LexicalUnit] | None = None,
) -> IntermediateAnalysis:
    timestamp = datetime(2026, 5, 17, 12, 0, tzinfo=UTC)
    return IntermediateAnalysis(
        status=RunStatus.COMPLETED,
        run=RunMetadata(
            run_id="run-001",
            started_at=timestamp,
            input_path="data/input/example.txt",
            openai_model="test-model",
        ),
        document=DocumentMetadata(
            document_id="doc-001",
            source_file="example.txt",
            character_count=42,
        ),
        lexical_units=list(lexical_units if lexical_units is not None else [make_lexical_unit()]),
        candidates=list(candidates),
    )


def test_validate_intermediate_keeps_valid_payload_unchanged() -> None:
    metaphorical = make_candidate("candidate-001")
    non_metaphorical = make_candidate(
        "candidate-002",
        decision=MipvuDecision.NON_METAPHORICAL,
        metaphor_type=None,
        source_domain=None,
        target_domain=None,
        confidence=0.1,
    )
    analysis = make_analysis(
        [metaphorical, non_metaphorical],
        lexical_units=[make_lexical_unit("unit-001"), make_lexical_unit("unit-002")],
    )
    analysis = analysis.model_copy(
        update={
            "candidates": [
                metaphorical,
                non_metaphorical.model_copy(update={"unit_id": "unit-002"}),
            ]
        },
        deep=True,
    )

    validated = validate_intermediate(analysis)

    assert validated.model_dump() == analysis.model_dump()
    assert is_rdf_mappable(validated.candidates[0]) is True
    assert validated.candidates[1].mipvu_decision is MipvuDecision.NON_METAPHORICAL


def test_validate_intermediate_marks_later_duplicate_candidate_unresolved() -> None:
    first = make_candidate("candidate-001")
    duplicate = make_candidate("candidate-001", confidence=0.9)
    analysis = make_analysis([first, duplicate])

    validated = validate_intermediate(analysis)

    assert validated.candidates[0].mipvu_decision is MipvuDecision.METAPHORICAL
    assert validated.candidates[1].mipvu_decision is MipvuDecision.UNRESOLVED
    assert validated.candidates[1].confidence == 0.0
    assert validated.candidates[1].errors[-1].error_code is ErrorCode.VALIDATION_ERROR
    assert "duplicate candidate_id" in validated.candidates[1].errors[-1].message


def test_validate_intermediate_marks_missing_unit_id_unresolved() -> None:
    candidate = make_candidate(unit_id="unit-missing")
    analysis = make_analysis([candidate])

    validated = validate_intermediate(analysis)

    assert validated.candidates[0].mipvu_decision is MipvuDecision.UNRESOLVED
    assert validated.candidates[0].errors[-1].error_code is ErrorCode.VALIDATION_ERROR
    assert "unit_id not found" in validated.candidates[0].errors[-1].message


def test_validate_intermediate_requires_dictionary_meanings_for_metaphorical() -> None:
    candidate = make_candidate(dictionary_meanings=[])
    analysis = make_analysis([candidate])

    validated = validate_intermediate(analysis)

    assert validated.candidates[0].mipvu_decision is MipvuDecision.UNRESOLVED
    assert validated.candidates[0].metaphor_type is None
    assert validated.candidates[0].source_domain is None
    assert validated.candidates[0].target_domain is None
    assert validated.candidates[0].confidence == 0.0
    assert "dictionary meanings required for MIPVU comparison" in (
        validated.candidates[0].errors[-1].message
    )


def test_validate_intermediate_normalizes_non_metaphorical_domains() -> None:
    candidate = make_candidate(
        decision=MipvuDecision.NON_METAPHORICAL,
        metaphor_type=None,
        source_domain="source should be removed",
        target_domain="target should be removed",
        confidence=0.2,
    )
    analysis = make_analysis([candidate])

    validated = validate_intermediate(analysis)

    assert validated.candidates[0].mipvu_decision is MipvuDecision.NON_METAPHORICAL
    assert validated.candidates[0].metaphor_type is None
    assert validated.candidates[0].source_domain is None
    assert validated.candidates[0].target_domain is None
    assert validated.candidates[0].confidence == 0.2
    assert validated.candidates[0].errors[-1].error_code is ErrorCode.VALIDATION_ERROR


def test_validate_intermediate_normalizes_unresolved_metaphor_fields() -> None:
    candidate = make_candidate()
    invalid_unresolved = MetaphorCandidate.model_construct(
        **{
            **candidate.model_dump(mode="python"),
            "mipvu_decision": MipvuDecision.UNRESOLVED,
            "metaphor_type": MetaphorType.INDIRECT,
            "source_domain": "source should be removed",
            "target_domain": "target should be removed",
            "confidence": 0.4,
        }
    )
    analysis = make_analysis([]).model_copy(
        update={"candidates": [invalid_unresolved]},
        deep=True,
    )

    validated = validate_intermediate(analysis)

    assert validated.candidates[0].mipvu_decision is MipvuDecision.UNRESOLVED
    assert validated.candidates[0].metaphor_type is None
    assert validated.candidates[0].source_domain is None
    assert validated.candidates[0].target_domain is None
    assert validated.candidates[0].confidence == 0.4
    assert validated.candidates[0].errors[-1].error_code is ErrorCode.VALIDATION_ERROR


def test_validate_intermediate_marks_metaphorical_missing_required_fields_unresolved() -> None:
    candidate = make_candidate(source_domain=None, meaning_contrast=None)
    analysis = make_analysis([candidate])

    validated = validate_intermediate(analysis)

    assert validated.candidates[0].mipvu_decision is MipvuDecision.UNRESOLVED
    assert validated.candidates[0].metaphor_type is None
    assert validated.candidates[0].source_domain is None
    assert validated.candidates[0].target_domain is None
    assert validated.candidates[0].confidence == 0.0
    assert "meaning_contrast" in validated.candidates[0].errors[-1].message
    assert "source_domain" in validated.candidates[0].errors[-1].message


def test_is_rdf_mappable_checks_required_fields() -> None:
    complete = make_candidate()
    unresolved = make_candidate(
        decision=MipvuDecision.UNRESOLVED,
        metaphor_type=None,
        source_domain=None,
        target_domain=None,
    )
    non_metaphorical = make_candidate(
        decision=MipvuDecision.NON_METAPHORICAL,
        metaphor_type=None,
        source_domain=None,
        target_domain=None,
    )
    missing_field = make_candidate(target_domain=None)

    assert is_rdf_mappable(complete) is True
    assert is_rdf_mappable(unresolved) is False
    assert is_rdf_mappable(non_metaphorical) is False
    assert is_rdf_mappable(missing_field) is False


def test_validate_intermediate_logs_safe_summary(caplog: pytest.LogCaptureFixture) -> None:
    sensitive_context = "이 판결문 원문은 로그에 나오면 안 된다."
    secret = "super-secret-api-key"
    settings = RuntimeSettings(
        openai_api_key=secret,
        openai_model="test-model",
        krdict_api_key="test-krdict-key",
    )
    observer = RunObserver(settings, run_id="run-validation")
    caplog.set_level(logging.INFO, logger="all_metaphor.observability")
    candidate = make_candidate(unit_id="unit-missing")
    analysis = make_analysis(
        [candidate],
        lexical_units=[make_lexical_unit("unit-001", local_context=sensitive_context)],
    )

    validated = validate_intermediate(analysis, observer=observer)

    log_text = "\n".join(record.message for record in caplog.records)
    error_text = "\n".join(error.message for error in validated.candidates[0].errors)
    assert sensitive_context not in log_text
    assert sensitive_context not in error_text
    assert secret not in log_text
    records = [json.loads(record.message) for record in caplog.records]
    summary = next(
        record for record in records if record["event"] == "intermediate_validation_summary"
    )
    assert summary["stage"] == VALIDATE_INTERMEDIATE_STAGE
    assert summary["metadata"] == {
        "duplicate_candidate_count": 0,
        "invalid_count": 1,
        "missing_unit_count": 1,
        "normalized_count": 1,
        "total_candidates": 1,
    }
