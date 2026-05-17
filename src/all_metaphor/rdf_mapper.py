"""RDF mapping for validated ALL_Metaphor intermediate analysis."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from urllib.parse import quote

from rdflib import Graph, Literal, Namespace, URIRef
from rdflib.namespace import RDF, RDFS, XSD

from all_metaphor.observability import RunObserver
from all_metaphor.schemas import IntermediateAnalysis, LexicalUnit, MetaphorCandidate
from all_metaphor.validation import is_rdf_mappable

RDF_MAPPING_STAGE = "map_rdf"
EX = Namespace("http://example.org/legal-metaphor#")


@dataclass(frozen=True, slots=True)
class RdfMappingStats:
    """Summary of RDF mapping results."""

    total_candidates: int
    mapped_count: int
    skipped_count: int
    document_id: str

    def as_metadata(self) -> dict[str, int | str]:
        return {
            "total_candidates": self.total_candidates,
            "mapped_count": self.mapped_count,
            "skipped_count": self.skipped_count,
            "document_id": self.document_id,
        }


def map_rdf(
    payload: IntermediateAnalysis,
    *,
    observer: RunObserver | None = None,
) -> str:
    """Map RDF-ready metaphor candidates to a Turtle string."""
    graph = _new_graph()
    lexical_units_by_id = {unit.unit_id: unit for unit in payload.lexical_units}
    mapped_count = 0

    for candidate in payload.candidates:
        if not is_rdf_mappable(candidate):
            continue
        lexical_unit = lexical_units_by_id.get(candidate.unit_id)
        if lexical_unit is None:
            continue
        _add_candidate_triples(
            graph,
            payload=payload,
            candidate=candidate,
            lexical_unit=lexical_unit,
        )
        mapped_count += 1

    if observer is not None:
        observer.set_rdf_triple_count(len(graph))
        observer.log_event(
            "rdf_mapping_summary",
            stage=RDF_MAPPING_STAGE,
            metadata=RdfMappingStats(
                total_candidates=len(payload.candidates),
                mapped_count=mapped_count,
                skipped_count=len(payload.candidates) - mapped_count,
                document_id=payload.document.document_id,
            ).as_metadata(),
        )

    serialized = graph.serialize(format="turtle")
    return serialized if isinstance(serialized, str) else serialized.decode("utf-8")


def _new_graph() -> Graph:
    graph = Graph()
    graph.bind("ex", EX)
    graph.bind("xsd", XSD)
    graph.bind("rdfs", RDFS)
    return graph


def _add_candidate_triples(
    graph: Graph,
    *,
    payload: IntermediateAnalysis,
    candidate: MetaphorCandidate,
    lexical_unit: LexicalUnit,
) -> None:
    metaphor_uri = _resource_uri("metaphor", candidate.candidate_id)
    source_domain_uri = _resource_uri("sourceDomain", _required_text(candidate.source_domain))
    target_domain_uri = _resource_uri("targetDomain", _required_text(candidate.target_domain))
    lexical_unit_uri = _resource_uri("lexicalUnit", candidate.unit_id)

    graph.add((metaphor_uri, RDF.type, EX.MetaphorCandidate))
    graph.add((metaphor_uri, EX.hasMIPVUDecision, Literal(candidate.mipvu_decision.value)))
    graph.add((metaphor_uri, EX.hasMetaphorType, Literal(_required_text(candidate.metaphor_type))))
    graph.add((metaphor_uri, EX.hasSourceDomain, source_domain_uri))
    graph.add((metaphor_uri, EX.hasTargetDomain, target_domain_uri))
    graph.add((metaphor_uri, EX.hasLexicalUnit, lexical_unit_uri))
    graph.add((metaphor_uri, EX.hasSurfaceExpression, Literal(lexical_unit.surface)))
    graph.add((metaphor_uri, EX.hasContextualMeaning, Literal(candidate.contextual_meaning)))
    graph.add((metaphor_uri, EX.hasBasicMeaning, Literal(candidate.basic_meaning)))
    graph.add((metaphor_uri, EX.hasMeaningContrast, Literal(candidate.meaning_contrast)))
    graph.add(
        (
            metaphor_uri,
            EX.hasConfidence,
            Literal(Decimal(str(candidate.confidence)), datatype=XSD.decimal),
        )
    )

    graph.add((source_domain_uri, RDF.type, EX.SourceDomain))
    graph.add((source_domain_uri, RDFS.label, Literal(candidate.source_domain)))
    graph.add((target_domain_uri, RDF.type, EX.TargetDomain))
    graph.add((target_domain_uri, RDFS.label, Literal(candidate.target_domain)))
    graph.add((source_domain_uri, EX.isMappedTo, target_domain_uri))

    graph.add((lexical_unit_uri, RDF.type, EX.LexicalUnit))
    graph.add((lexical_unit_uri, RDFS.label, Literal(lexical_unit.surface)))
    graph.add((lexical_unit_uri, EX.hasUnitId, Literal(candidate.unit_id)))

    if lexical_unit.sentence_id is not None:
        sentence_uri = _resource_uri("sentence", lexical_unit.sentence_id)
        graph.add((metaphor_uri, EX.appearsInSentence, sentence_uri))
        graph.add((sentence_uri, RDF.type, EX.Sentence))
        graph.add((sentence_uri, EX.hasSentenceId, Literal(lexical_unit.sentence_id)))

    document_uri = _resource_uri("document", payload.document.document_id)
    graph.add((metaphor_uri, EX.appearsInDocument, document_uri))
    graph.add((document_uri, RDF.type, EX.Document))
    graph.add((document_uri, EX.hasDocumentId, Literal(payload.document.document_id)))

    for meaning in candidate.dictionary_meanings:
        graph.add((metaphor_uri, EX.hasDictionaryMeaning, Literal(meaning.definition)))


def _resource_uri(kind: str, identifier: str) -> URIRef:
    return URIRef(f"{EX}{kind}/{_safe_uri_segment(identifier)}")


def _safe_uri_segment(value: str) -> str:
    normalized = "_".join(value.strip().split())
    return quote(normalized, safe="-._~")


def _required_text(value: object) -> str:
    if isinstance(value, str):
        return value
    return str(value)


__all__ = [
    "EX",
    "RDF_MAPPING_STAGE",
    "RdfMappingStats",
    "map_rdf",
]
