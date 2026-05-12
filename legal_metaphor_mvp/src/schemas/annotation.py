"""Pydantic schemas and shared types for the lemma MIPVU/KG pipeline."""

from __future__ import annotations

from typing import Literal, TypedDict, get_args

from pydantic import BaseModel, Field

RdfPredicate = Literal[
    "ex:isConceptualizedAs",
    "ex:hasSourceDomain",
    "ex:hasSourceDomainLabel",
    "ex:hasTargetDomain",
    "ex:hasTargetDomainLabel",
    "ex:hasMetaphorType",
    "ex:hasConceptualMetaphorLabel",
    "ex:hasSurfaceExpression",
    "ex:hasContextSentence",
    "ex:realizesConceptualMetaphor",
    "ex:hasConfidence",
    "ex:hasMIPVULabel",
    "ex:mappingReason",
    "ex:needsHumanReview",
]

ALLOWED_PREDICATES: set[str] = set(get_args(RdfPredicate))


class AnnotationState(TypedDict):
    """Dict-friendly state for node handoff."""

    document_id: str
    case_id: str
    raw_text: str
    sentences: list[str]
    mipvu_annotations: list[dict]
    rdf_mappings: list[dict]
    validation_results: list[dict]
    contextual_meaning_by_lemma: dict[str, str]
    rdf_output: str
    errors: list[str]
    human_review_items: list[dict]
    metadata: dict[str, object]
    status: str


def create_empty_state(document_id: str = "", case_id: str = "", raw_text: str = "") -> AnnotationState:
    """Create an empty annotation state."""
    return {
        "document_id": document_id,
        "case_id": case_id,
        "raw_text": raw_text,
        "sentences": [],
        "mipvu_annotations": [],
        "rdf_mappings": [],
        "validation_results": [],
        "contextual_meaning_by_lemma": {},
        "rdf_output": "",
        "errors": [],
        "human_review_items": [],
        "metadata": {},
        "status": "initialized",
    }

class RdfTriple(BaseModel):
    subject_label: str
    subject_type: str
    subject_id: str
    predicate: RdfPredicate
    object_label: str
    object_type: str
    object_id: str


class RdfMapping(BaseModel):
    primary_triple: RdfTriple
    supporting_triples: list[RdfTriple] = Field(default_factory=list)
    mapping_reason: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    needs_human_review: bool = False


class RdfMappingOutput(BaseModel):
    rdf_mapping: RdfMapping | None = None
    rdf_mappings: list[RdfMapping] = Field(default_factory=list)
