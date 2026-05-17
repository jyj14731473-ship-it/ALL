from __future__ import annotations

import json
import logging
from collections.abc import Sequence
from datetime import UTC, datetime
from decimal import Decimal
from urllib.parse import quote

import pytest
from rdflib import Graph, Literal, URIRef
from rdflib.namespace import RDF, RDFS, XSD

from all_metaphor.config import RuntimeSettings
from all_metaphor.observability import RunObserver
from all_metaphor.rdf_mapper import EX, RDF_MAPPING_STAGE, map_rdf
from all_metaphor.schemas import (
    DictionaryMeaning,
    DocumentMetadata,
    IntermediateAnalysis,
    LexicalUnit,
    MetaphorCandidate,
    MetaphorType,
    MipvuDecision,
    RunMetadata,
    RunStatus,
)


def safe_segment(value: str) -> str:
    return quote("_".join(value.strip().split()), safe="-._~")


def resource(kind: str, identifier: str) -> URIRef:
    return URIRef(f"{EX}{kind}/{safe_segment(identifier)}")


def make_lexical_unit(
    unit_id: str = "unit-001",
    *,
    surface: str = "성립",
    sentence_id: str | None = "sentence-001",
    local_context: str = "계약의 성립 여부를 판단한다.",
) -> LexicalUnit:
    return LexicalUnit(
        unit_id=unit_id,
        surface=surface,
        lemma=surface,
        pos="Noun",
        start_char=0,
        end_char=len(surface),
        sentence_id=sentence_id,
        local_context=local_context,
        local_context_char_count=len(local_context),
        is_candidate=True,
        filter_reason=None,
    )


def make_candidate(
    candidate_id: str = "candidate-001",
    *,
    unit_id: str = "unit-001",
    decision: MipvuDecision = MipvuDecision.METAPHORICAL,
    metaphor_type: MetaphorType | None = MetaphorType.INDIRECT,
    source_domain: str | None = "일의 성립",
    target_domain: str | None = "법률관계",
    contextual_meaning: str | None = "법률 요건이 갖추어짐.",
    basic_meaning: str | None = "어떤 일이 이루어짐.",
    meaning_contrast: str | None = "법률 요건의 성취를 일의 성립과 비교함.",
    dictionary_meanings: list[DictionaryMeaning] | None = None,
    confidence: float = 0.75,
) -> MetaphorCandidate:
    if dictionary_meanings is None:
        dictionary_meanings = [
            DictionaryMeaning(sense_id="sense-001", definition="어떤 일이 이루어짐.")
        ]
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


def make_payload(
    candidates: Sequence[MetaphorCandidate],
    *,
    lexical_units: Sequence[LexicalUnit] | None = None,
    document_id: str = "doc-001",
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
            document_id=document_id,
            source_file="example.txt",
            character_count=42,
        ),
        lexical_units=list(lexical_units if lexical_units is not None else [make_lexical_unit()]),
        candidates=list(candidates),
    )


def parse_turtle(turtle: str) -> Graph:
    graph = Graph()
    graph.parse(data=turtle, format="turtle")
    return graph


def test_map_rdf_creates_triples_for_rdf_mappable_candidate() -> None:
    payload = make_payload([make_candidate()])

    graph = parse_turtle(map_rdf(payload))

    metaphor_uri = resource("metaphor", "candidate-001")
    source_uri = resource("sourceDomain", "일의 성립")
    target_uri = resource("targetDomain", "법률관계")
    lexical_unit_uri = resource("lexicalUnit", "unit-001")
    assert (metaphor_uri, RDF.type, EX.MetaphorCandidate) in graph
    assert (metaphor_uri, EX.hasSourceDomain, source_uri) in graph
    assert (metaphor_uri, EX.hasTargetDomain, target_uri) in graph
    assert (metaphor_uri, EX.hasLexicalUnit, lexical_unit_uri) in graph
    assert (metaphor_uri, EX.hasMetaphorType, Literal("indirect")) in graph
    assert (metaphor_uri, EX.hasSurfaceExpression, Literal("성립")) in graph
    assert (
        metaphor_uri,
        EX.hasConfidence,
        Literal(Decimal("0.75"), datatype=XSD.decimal),
    ) in graph


def test_map_rdf_skips_non_metaphorical_candidate() -> None:
    payload = make_payload(
        [
            make_candidate(
                decision=MipvuDecision.NON_METAPHORICAL,
                metaphor_type=None,
                source_domain=None,
                target_domain=None,
            )
        ]
    )

    graph = parse_turtle(map_rdf(payload))

    assert list(graph.subjects(RDF.type, EX.MetaphorCandidate)) == []


def test_map_rdf_skips_unresolved_candidate() -> None:
    payload = make_payload(
        [
            make_candidate(
                decision=MipvuDecision.UNRESOLVED,
                metaphor_type=None,
                source_domain=None,
                target_domain=None,
            )
        ]
    )

    graph = parse_turtle(map_rdf(payload))

    assert list(graph.subjects(RDF.type, EX.MetaphorCandidate)) == []


def test_map_rdf_skips_incomplete_metaphorical_candidate_without_exception() -> None:
    payload = make_payload([make_candidate(source_domain=None)])

    graph = parse_turtle(map_rdf(payload))

    assert list(graph.subjects(RDF.type, EX.MetaphorCandidate)) == []


def test_map_rdf_creates_source_target_mapping_triple() -> None:
    payload = make_payload([make_candidate()])

    graph = parse_turtle(map_rdf(payload))

    assert (
        resource("sourceDomain", "일의 성립"),
        EX.isMappedTo,
        resource("targetDomain", "법률관계"),
    ) in graph


def test_map_rdf_adds_multiple_dictionary_meaning_literals() -> None:
    payload = make_payload(
        [
            make_candidate(
                dictionary_meanings=[
                    DictionaryMeaning(sense_id="sense-001", definition="첫 번째 뜻."),
                    DictionaryMeaning(sense_id="sense-002", definition="두 번째 뜻."),
                ]
            )
        ]
    )

    graph = parse_turtle(map_rdf(payload))

    metaphor_uri = resource("metaphor", "candidate-001")
    dictionary_meanings = set(graph.objects(metaphor_uri, EX.hasDictionaryMeaning))
    assert dictionary_meanings == {Literal("첫 번째 뜻."), Literal("두 번째 뜻.")}


def test_map_rdf_links_sentence_and_document() -> None:
    payload = make_payload([make_candidate()], document_id="doc-판결 1")

    graph = parse_turtle(map_rdf(payload))

    metaphor_uri = resource("metaphor", "candidate-001")
    sentence_uri = resource("sentence", "sentence-001")
    document_uri = resource("document", "doc-판결 1")
    assert (metaphor_uri, EX.appearsInSentence, sentence_uri) in graph
    assert (sentence_uri, RDF.type, EX.Sentence) in graph
    assert (sentence_uri, EX.hasSentenceId, Literal("sentence-001")) in graph
    assert (metaphor_uri, EX.appearsInDocument, document_uri) in graph
    assert (document_uri, RDF.type, EX.Document) in graph
    assert (document_uri, EX.hasDocumentId, Literal("doc-판결 1")) in graph


def test_map_rdf_builds_safe_deterministic_uris() -> None:
    candidate = make_candidate(
        candidate_id="후보 1/?#",
        unit_id="unit 1/#",
        source_domain="몸의 이동 / source",
        target_domain="법률 관계 # target",
    )
    lexical_unit = make_lexical_unit(unit_id="unit 1/#", surface="흘러갔다")
    payload = make_payload([candidate], lexical_units=[lexical_unit])

    graph = parse_turtle(map_rdf(payload))

    metaphor_uri = resource("metaphor", "후보 1/?#")
    source_uri = resource("sourceDomain", "몸의 이동 / source")
    target_uri = resource("targetDomain", "법률 관계 # target")
    lexical_unit_uri = resource("lexicalUnit", "unit 1/#")
    assert (metaphor_uri, RDF.type, EX.MetaphorCandidate) in graph
    assert (metaphor_uri, EX.hasSourceDomain, source_uri) in graph
    assert (metaphor_uri, EX.hasTargetDomain, target_uri) in graph
    assert (lexical_unit_uri, RDFS.label, Literal("흘러갔다")) in graph


def test_map_rdf_does_not_emit_local_context_or_api_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secret = "super-secret-api-key"
    sensitive_context = "이 판결문 문장은 RDF나 로그에 나오면 안 된다."
    settings = RuntimeSettings(
        openai_api_key=secret,
        openai_model="test-model",
        krdict_api_key="test-krdict-key",
    )
    observer = RunObserver(settings, run_id="run-rdf")
    caplog.set_level(logging.INFO, logger="all_metaphor.observability")
    candidate = make_candidate()
    lexical_unit = make_lexical_unit(local_context=sensitive_context)
    payload = make_payload([candidate], lexical_units=[lexical_unit])

    turtle = map_rdf(payload, observer=observer)

    log_text = "\n".join(record.message for record in caplog.records)
    assert sensitive_context not in turtle
    assert sensitive_context not in log_text
    assert secret not in turtle
    assert secret not in log_text
    records = [json.loads(record.message) for record in caplog.records]
    summary = next(record for record in records if record["event"] == "rdf_mapping_summary")
    assert summary["stage"] == RDF_MAPPING_STAGE
    assert summary["metadata"] == {
        "document_id": "doc-001",
        "mapped_count": 1,
        "skipped_count": 0,
        "total_candidates": 1,
    }
    assert observer.metrics.rdf_triple_count > 0
