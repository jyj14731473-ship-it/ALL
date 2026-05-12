"""Pydantic schemas and shared types for the LangGraph annotation workflow."""

from __future__ import annotations

from typing import Literal, TypedDict, get_args

from pydantic import BaseModel, Field

MetaphorType = Literal["structural", "ontological", "orientational", "uncertain"]
OpinionType = Literal["majority", "dissenting", "concurring", "unknown"]
BasicMeaningSource = Literal["stdict", "inferred", "unavailable"]
MIPVULabel = Literal[
    "MRW",
    "MRW_candidate",
    "borderline_candidate",
    "non_MRW",
    "non-MRW",
    "not_mrw",
    "not-MRW",
    "not_MRW",
    "uncertain",
]
RdfPredicate = Literal[
    "ex:isConceptualizedAs",
    "ex:hasSourceDomain",
    "ex:hasSourceDomainLabel",
    "ex:hasTargetDomain",
    "ex:hasTargetDomainLabel",
    "ex:evokesFrame",
    "ex:hasMetaphorType",
    "ex:hasConceptualMetaphorLabel",
    "ex:hasSurfaceExpression",
    "ex:hasContextSentence",
    "ex:hasLegalConcept",
    "ex:realizesConceptualMetaphor",
    "ex:appearsInOpinionType",
    "ex:hasConfidence",
    "ex:derivedFromCandidate",
    "ex:appearsInSentence",
    "ex:hasMIPVULabel",
    "ex:mappingReason",
    "ex:needsHumanReview",
]

ALLOWED_PREDICATES: set[str] = set(get_args(RdfPredicate))


class AnnotationState(TypedDict):
    """LangGraph state. Keep dict-friendly values for node handoff."""

    document_id: str
    case_id: str
    raw_text: str
    sentences: list[str]
    candidates: list[dict]
    mipvu_annotations: list[dict]
    metaphor_annotations: list[dict]
    rdf_mappings: list[dict]
    validation_results: list[dict]
    final_annotations: list[dict]
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
        "candidates": [],
        "mipvu_annotations": [],
        "metaphor_annotations": [],
        "rdf_mappings": [],
        "validation_results": [],
        "final_annotations": [],
        "contextual_meaning_by_lemma": {},
        "rdf_output": "",
        "errors": [],
        "human_review_items": [],
        "metadata": {},
        "status": "initialized",
    }


class CandidateMorphemeTag(BaseModel):
    token: str
    pos: str


class MetaphorCandidate(BaseModel):
    candidate_id: str
    sentence_id: str
    sentence: str
    surface_expression: str
    lemma: str = ""
    pos: str = ""
    morphemes: list[CandidateMorphemeTag] = Field(default_factory=list)
    context_window: str = ""
    opinion_type: OpinionType = "unknown"
    extraction_reason: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    needs_human_review: bool = False


class CandidateExtractionOutput(BaseModel):
    candidates: list[MetaphorCandidate] = Field(default_factory=list)


class MipvuJudgment(BaseModel):
    candidate_id: str
    sentence_id: str
    token: str
    lemma: str = ""
    pos: str = ""
    context_sentence: str
    contextual_meaning: str = ""
    basic_meaning: str = ""
    basic_meaning_source: BasicMeaningSource = "unavailable"
    meaning_contrast: str = ""
    distinctness: bool = False
    comparison_possible: bool = False
    similarity: bool = False
    mipvu_label: MIPVULabel
    judgment_reason: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    needs_human_review: bool = False


class MipvuJudgmentOutput(BaseModel):
    judgments: list[MipvuJudgment] = Field(default_factory=list)


class MetaphorAnnotation(BaseModel):
    metaphor_id: str
    candidate_id: str
    sentence_id: str
    surface_expression: str
    context_sentence: str
    conceptual_metaphor: str
    metaphor_type: MetaphorType = "uncertain"
    source_domain: str
    target_domain: str
    legal_concept: str = ""
    opinion_type: OpinionType = "unknown"
    is_legal_domain_specific: bool = False
    classification_reason: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    needs_human_review: bool = False


class MetaphorClassificationOutput(BaseModel):
    metaphors: list[MetaphorAnnotation] = Field(default_factory=list)


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


class ValidationIssue(BaseModel):
    severity: Literal["error", "warning"]
    location: str
    message: str
    suggested_fix: str


class ValidationOutput(BaseModel):
    is_valid: bool
    repair_needed: bool = False
    human_review_needed: bool = False
    issues: list[ValidationIssue] = Field(default_factory=list)


class NodeValidationWrapper(BaseModel):
    validation: ValidationOutput
