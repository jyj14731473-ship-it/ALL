from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import ValidationError

from all_metaphor.schemas import (
    AGENT_NAME,
    PROJECT_NAME,
    SCHEMA_VERSION,
    AnalysisError,
    ContextWindow,
    DictionaryMeaning,
    DocumentMetadata,
    ErrorCode,
    IntermediateAnalysis,
    LexicalUnit,
    MetaphorCandidate,
    MetaphorType,
    MipvuDecision,
    RdfMetadata,
    RunMetadata,
    RunStatus,
    TokenUsage,
)


@pytest.fixture
def timestamp() -> datetime:
    return datetime(2026, 5, 17, 12, 0, tzinfo=UTC)


@pytest.fixture
def minimal_run(timestamp: datetime) -> RunMetadata:
    return RunMetadata(
        run_id="run-001",
        started_at=timestamp,
        input_path="data/input/example.txt",
        openai_model="test-model",
    )


@pytest.fixture
def minimal_document() -> DocumentMetadata:
    return DocumentMetadata(
        document_id="doc-001",
        source_file="example.txt",
        character_count=42,
    )


@pytest.fixture
def minimal_analysis(
    minimal_run: RunMetadata,
    minimal_document: DocumentMetadata,
) -> IntermediateAnalysis:
    return IntermediateAnalysis(
        status=RunStatus.COMPLETED,
        run=minimal_run,
        document=minimal_document,
    )


@pytest.fixture
def candidate_factory() -> Callable[..., MetaphorCandidate]:
    def build_candidate(**overrides: Any) -> MetaphorCandidate:
        data: dict[str, Any] = {
            "candidate_id": "candidate-001",
            "unit_id": "unit-001",
            "dictionary_query": "성립",
            "dictionary_meanings": [
                DictionaryMeaning(
                    sense_id="sense-001",
                    definition="어떤 일이 이루어짐.",
                )
            ],
            "contextual_meaning": "법률 요건이 갖추어짐.",
            "basic_meaning": "어떤 일이 이루어짐.",
            "meaning_contrast": "법률 맥락의 관습적 의미와 일반 의미를 비교함.",
            "mipvu_decision": MipvuDecision.NON_METAPHORICAL,
            "metaphor_type": None,
            "source_domain": None,
            "target_domain": None,
            "confidence": 0.0,
            "llm_rationale": "법률 전문용어의 관습적 의미로 사용됨.",
            "errors": [],
        }
        data.update(overrides)
        return MetaphorCandidate(**data)

    return build_candidate


@pytest.fixture
def full_analysis(
    timestamp: datetime,
    candidate_factory: Callable[..., MetaphorCandidate],
) -> IntermediateAnalysis:
    lexical_unit = LexicalUnit(
        unit_id="unit-001",
        surface="성립",
        lemma="성립",
        pos="Noun",
        start_char=0,
        end_char=2,
        sentence_id="sentence-001",
        local_context="권리의 성립 여부를 판단한다.",
        local_context_char_count=17,
        is_candidate=True,
        filter_reason=None,
    )
    candidate_error = AnalysisError(
        error_code=ErrorCode.LLM_VALIDATION_ERROR,
        stage="judge_metaphor",
        candidate_id="candidate-001",
        message="LLM response required repair.",
        retryable=True,
        timestamp=timestamp,
    )
    candidate = candidate_factory(errors=[candidate_error])
    run_error = AnalysisError(
        error_code=ErrorCode.DICT_API_FAILURE,
        stage="lookup_dictionary_meanings",
        candidate_id=None,
        message="Dictionary API timeout.",
        retryable=True,
        timestamp=timestamp,
    )
    return IntermediateAnalysis(
        schema_version=SCHEMA_VERSION,
        project=PROJECT_NAME,
        agent=AGENT_NAME,
        status=RunStatus.PARTIAL,
        run=RunMetadata(
            run_id="run-001",
            started_at=timestamp,
            completed_at=timestamp,
            input_path="data/input/example.txt",
            openai_model="test-model",
            openai_temperature=0.0,
            openai_seed=123,
            context_window=ContextWindow(
                tokens_before=10,
                tokens_after=10,
                max_tokens_each_side=30,
                max_characters=100,
            ),
            token_usage=TokenUsage(
                prompt_tokens=10,
                completion_tokens=5,
                total_tokens=15,
            ),
        ),
        document=DocumentMetadata(
            document_id="doc-001",
            source_file="example.txt",
            character_count=42,
        ),
        lexical_units=[lexical_unit],
        candidates=[candidate],
        rdf=RdfMetadata(
            output_path="outputs/rdf/example.ttl",
            triple_count=3,
            confidence_threshold=0.5,
        ),
        errors=[run_error],
    )


def test_run_status_accepts_all_values(
    minimal_run: RunMetadata,
    minimal_document: DocumentMetadata,
) -> None:
    for status in RunStatus:
        analysis = IntermediateAnalysis(status=status, run=minimal_run, document=minimal_document)
        assert analysis.status is status


def test_mipvu_decision_accepts_all_values(
    candidate_factory: Callable[..., MetaphorCandidate],
) -> None:
    for decision in MipvuDecision:
        metaphor_type = MetaphorType.INDIRECT if decision is MipvuDecision.METAPHORICAL else None
        candidate = candidate_factory(mipvu_decision=decision, metaphor_type=metaphor_type)
        assert candidate.mipvu_decision is decision


def test_metaphor_type_accepts_all_values(
    candidate_factory: Callable[..., MetaphorCandidate],
) -> None:
    for metaphor_type in MetaphorType:
        candidate = candidate_factory(
            mipvu_decision=MipvuDecision.METAPHORICAL,
            metaphor_type=metaphor_type,
            confidence=0.8,
        )
        assert candidate.metaphor_type is metaphor_type


def test_error_code_accepts_all_values(timestamp: datetime) -> None:
    for error_code in ErrorCode:
        error = AnalysisError(
            error_code=error_code,
            stage="test_stage",
            candidate_id=None,
            message="message",
            retryable=False,
            timestamp=timestamp,
        )
        assert error.error_code is error_code


def test_intermediate_analysis_accepts_minimal_fields(
    minimal_analysis: IntermediateAnalysis,
) -> None:
    assert minimal_analysis.schema_version == SCHEMA_VERSION
    assert minimal_analysis.project == PROJECT_NAME
    assert minimal_analysis.agent == AGENT_NAME
    assert minimal_analysis.lexical_units == []
    assert minimal_analysis.candidates == []


def test_intermediate_analysis_accepts_all_fields(
    full_analysis: IntermediateAnalysis,
) -> None:
    assert full_analysis.status is RunStatus.PARTIAL
    assert len(full_analysis.lexical_units) == 1
    assert len(full_analysis.candidates) == 1
    assert len(full_analysis.errors) == 1


def test_confidence_below_zero_is_rejected(
    candidate_factory: Callable[..., MetaphorCandidate],
) -> None:
    with pytest.raises(ValidationError):
        candidate_factory(confidence=-0.1)


def test_confidence_above_one_is_rejected(
    candidate_factory: Callable[..., MetaphorCandidate],
) -> None:
    with pytest.raises(ValidationError):
        candidate_factory(confidence=1.1)


def test_local_context_char_count_above_limit_is_rejected() -> None:
    with pytest.raises(ValidationError):
        LexicalUnit(
            unit_id="unit-001",
            surface="성립",
            lemma=None,
            pos=None,
            start_char=0,
            end_char=2,
            sentence_id=None,
            local_context="x" * 101,
            local_context_char_count=101,
            is_candidate=True,
            filter_reason=None,
        )


def test_unknown_status_is_rejected(
    minimal_run: RunMetadata,
    minimal_document: DocumentMetadata,
) -> None:
    with pytest.raises(ValidationError):
        IntermediateAnalysis(status="unknown", run=minimal_run, document=minimal_document)


def test_unknown_mipvu_decision_is_rejected(
    candidate_factory: Callable[..., MetaphorCandidate],
) -> None:
    with pytest.raises(ValidationError):
        candidate_factory(mipvu_decision="unknown")


def test_unknown_schema_version_is_rejected(
    minimal_run: RunMetadata,
    minimal_document: DocumentMetadata,
) -> None:
    with pytest.raises(ValidationError):
        IntermediateAnalysis(
            schema_version="0.2",
            status=RunStatus.COMPLETED,
            run=minimal_run,
            document=minimal_document,
        )


def test_extra_field_is_rejected(
    minimal_run: RunMetadata,
    minimal_document: DocumentMetadata,
) -> None:
    with pytest.raises(ValidationError):
        IntermediateAnalysis(
            status=RunStatus.COMPLETED,
            run=minimal_run,
            document=minimal_document,
            unexpected="value",
        )


def test_nullable_fields_accept_none(
    timestamp: datetime,
    candidate_factory: Callable[..., MetaphorCandidate],
) -> None:
    lexical_unit = LexicalUnit(
        unit_id="unit-001",
        surface="성립",
        lemma=None,
        pos=None,
        start_char=0,
        end_char=2,
        sentence_id=None,
        local_context="성립 여부",
        local_context_char_count=5,
        is_candidate=True,
        filter_reason=None,
    )
    candidate = candidate_factory(
        contextual_meaning=None,
        basic_meaning=None,
        meaning_contrast=None,
        metaphor_type=None,
        source_domain=None,
        target_domain=None,
        llm_rationale=None,
    )
    error = AnalysisError(
        error_code=ErrorCode.MISSING_INPUT_FILE,
        stage="load_input",
        candidate_id=None,
        message="Missing input file.",
        retryable=False,
        timestamp=timestamp,
    )
    rdf = RdfMetadata(output_path=None)

    assert lexical_unit.lemma is None
    assert candidate.contextual_meaning is None
    assert error.candidate_id is None
    assert rdf.output_path is None


def test_empty_lexical_units_and_candidates_are_accepted(
    minimal_analysis: IntermediateAnalysis,
) -> None:
    assert minimal_analysis.lexical_units == []
    assert minimal_analysis.candidates == []


def test_non_metaphorical_candidate_with_metaphor_type_is_rejected(
    candidate_factory: Callable[..., MetaphorCandidate],
) -> None:
    with pytest.raises(ValidationError):
        candidate_factory(
            mipvu_decision=MipvuDecision.NON_METAPHORICAL,
            metaphor_type=MetaphorType.INDIRECT,
        )
