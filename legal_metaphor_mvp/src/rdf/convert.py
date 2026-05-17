"""Shared deterministic RDF mapping and Turtle conversion logic."""

from __future__ import annotations

from typing import Any

from schemas.annotation import ALLOWED_PREDICATES
from utils import escape_turtle_literal, slugify

LITERAL_PREDICATES = {
    "ex:hasSurfaceExpression",
    "ex:hasContextSentence",
    "ex:hasMetaphorType",
    "ex:appearsInOpinionType",
    "ex:hasConfidence",
    "ex:appearsInSentence",
    "ex:hasMIPVULabel",
    "ex:mappingReason",
    "ex:needsHumanReview",
}


def _slugged_id(prefix: str, value: str, fallback: str) -> str:
    return f"{prefix}_{slugify(value or fallback)}"


def fallback_mapping_from_annotation(annotation: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic RDF-ready mapping from canonical annotation JSON."""
    metaphor_id = str(annotation.get("metaphor_id") or "M000")
    candidate_id = str(annotation.get("candidate_id") or annotation.get("source_candidate_id") or "C000")
    legal = str(annotation.get("legal_concept") or annotation.get("target_domain") or "UnknownLegalConcept")
    source = str(annotation.get("source_domain") or "UnknownSourceDomain")
    target = str(annotation.get("target_domain") or "UnknownTargetDomain")
    conceptual = str(annotation.get("conceptual_metaphor") or f"{target}_AS_{source}")
    surface = str(annotation.get("surface_expression") or "")
    sentence = str(annotation.get("context_sentence") or "")
    opinion = str(annotation.get("opinion_type") or "unknown")
    metaphor_type = str(annotation.get("metaphor_type") or "uncertain")
    confidence = annotation.get("confidence", 0.0)
    confidence_value = float(confidence) if isinstance(confidence, (int, float)) else 0.0

    metaphor_instance_id = _slugged_id("Metaphor", metaphor_id, "unknown_metaphor")
    candidate_node_id = _slugged_id("Candidate", candidate_id, "unknown_candidate")
    legal_id = _slugged_id("LegalConcept", legal, "unknown_legal_concept")
    source_id = _slugged_id("SourceDomain", source, "unknown_source_domain")
    target_id = _slugged_id("TargetDomain", target, "unknown_target_domain")
    conceptual_id = _slugged_id("ConceptualMetaphor", conceptual, "unknown_conceptual_metaphor")

    return {
        "primary_triple": {
            "subject_label": legal,
            "subject_type": "LegalConcept",
            "subject_id": legal_id,
            "predicate": "ex:isConceptualizedAs",
            "object_label": source,
            "object_type": "SourceDomain",
            "object_id": source_id,
        },
        "supporting_triples": [
            {
                "subject_label": surface or metaphor_id,
                "subject_type": "MetaphorInstance",
                "subject_id": metaphor_instance_id,
                "predicate": "ex:hasLegalConcept",
                "object_label": legal,
                "object_type": "LegalConcept",
                "object_id": legal_id,
            },
            {
                "subject_label": surface or metaphor_id,
                "subject_type": "MetaphorInstance",
                "subject_id": metaphor_instance_id,
                "predicate": "ex:hasSourceDomain",
                "object_label": source,
                "object_type": "SourceDomain",
                "object_id": source_id,
            },
            {
                "subject_label": surface or metaphor_id,
                "subject_type": "MetaphorInstance",
                "subject_id": metaphor_instance_id,
                "predicate": "ex:hasTargetDomain",
                "object_label": target,
                "object_type": "TargetDomain",
                "object_id": target_id,
            },
            {
                "subject_label": surface or metaphor_id,
                "subject_type": "MetaphorInstance",
                "subject_id": metaphor_instance_id,
                "predicate": "ex:realizesConceptualMetaphor",
                "object_label": conceptual,
                "object_type": "ConceptualMetaphor",
                "object_id": conceptual_id,
            },
            {
                "subject_label": surface or metaphor_id,
                "subject_type": "MetaphorInstance",
                "subject_id": metaphor_instance_id,
                "predicate": "ex:hasSurfaceExpression",
                "object_label": surface,
                "object_type": "Literal",
                "object_id": _slugged_id("LiteralSurface", surface or metaphor_id, "surface"),
            },
            {
                "subject_label": surface or metaphor_id,
                "subject_type": "MetaphorInstance",
                "subject_id": metaphor_instance_id,
                "predicate": "ex:hasContextSentence",
                "object_label": sentence,
                "object_type": "Literal",
                "object_id": _slugged_id("LiteralSentence", sentence or metaphor_id, "sentence"),
            },
            {
                "subject_label": surface or metaphor_id,
                "subject_type": "MetaphorInstance",
                "subject_id": metaphor_instance_id,
                "predicate": "ex:appearsInOpinionType",
                "object_label": opinion,
                "object_type": "Literal",
                "object_id": _slugged_id("LiteralOpinion", opinion, "opinion"),
            },
            {
                "subject_label": surface or metaphor_id,
                "subject_type": "MetaphorInstance",
                "subject_id": metaphor_instance_id,
                "predicate": "ex:hasMetaphorType",
                "object_label": metaphor_type,
                "object_type": "Literal",
                "object_id": _slugged_id("LiteralType", metaphor_type, "type"),
            },
            {
                "subject_label": surface or metaphor_id,
                "subject_type": "MetaphorInstance",
                "subject_id": metaphor_instance_id,
                "predicate": "ex:hasConfidence",
                "object_label": f"{confidence_value:.4f}",
                "object_type": "Literal",
                "object_id": _slugged_id("LiteralConfidence", metaphor_id, "confidence"),
            },
            {
                "subject_label": surface or metaphor_id,
                "subject_type": "MetaphorInstance",
                "subject_id": metaphor_instance_id,
                "predicate": "ex:derivedFromCandidate",
                "object_label": candidate_id,
                "object_type": "Candidate",
                "object_id": candidate_node_id,
            },
        ],
        "mapping_reason": "Deterministic fallback mapping from canonical metaphor annotation.",
        "confidence": confidence_value,
        "needs_human_review": confidence_value < 0.5,
    }


def normalize_rdf_mappings(payload: Any) -> list[dict[str, Any]]:
    """Extract RDF mappings from graph output or build deterministic fallback mappings."""
    if isinstance(payload, dict):
        rdf_mappings = payload.get("rdf_mappings")
        if isinstance(rdf_mappings, list):
            return [item for item in rdf_mappings if isinstance(item, dict)]
        rdf_mapping = payload.get("rdf_mapping")
        if isinstance(rdf_mapping, dict):
            return [rdf_mapping]
        records = payload.get("metaphor_annotations")
        if not isinstance(records, list):
            records = payload.get("metaphors")
        if isinstance(records, list):
            return [fallback_mapping_from_annotation(item) for item in records if isinstance(item, dict)]
    if isinstance(payload, list):
        return [fallback_mapping_from_annotation(item) for item in payload if isinstance(item, dict)]
    return []


def _uri(value: str, fallback: str = "unknown") -> str:
    return f"ex:{slugify(value or fallback)}"


def _object_term(triple: dict[str, Any]) -> str:
    predicate = str(triple.get("predicate", ""))
    object_label = str(triple.get("object_label", ""))
    object_id = str(triple.get("object_id", ""))
    object_type = str(triple.get("object_type", ""))
    if predicate in LITERAL_PREDICATES or object_type == "Literal":
        return f'"{escape_turtle_literal(object_label)}"'
    return _uri(object_id or object_label, "unknown_object")


def _validation_has_errors(validation_results: Any) -> bool:
    if not isinstance(validation_results, list):
        return False
    for item in validation_results:
        if not isinstance(item, dict):
            continue
        if item.get("repair_needed"):
            return True
        issues = item.get("issues", [])
        if isinstance(issues, list) and any(isinstance(issue, dict) and issue.get("severity") == "error" for issue in issues):
            return True
    return False


def mappings_to_turtle(rdf_mappings: list[dict[str, Any]], validation_results: Any | None = None) -> str:
    """Render deterministic Turtle from RDF-ready mapping JSON."""
    lines: list[str] = []
    if _validation_has_errors(validation_results):
        lines.extend(
            [
                "# WARNING: validation reported errors. Review the annotation before using this RDF downstream.",
                "# validation_status: needs_repair",
                "",
            ]
        )

    lines.extend(
        [
            "@prefix ex: <http://example.org/legal-metaphor#> .",
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
            "",
        ]
    )
    if not rdf_mappings:
        lines.append("# No RDF mapping.")
        return "\n".join(lines) + "\n"

    emitted: set[str] = set()
    type_lines: set[str] = set()
    for idx, mapping in enumerate(rdf_mappings, start=1):
        if not isinstance(mapping, dict):
            continue
        triples: list[dict[str, Any]] = []
        primary = mapping.get("primary_triple")
        if isinstance(primary, dict):
            triples.append(primary)
        supporting = mapping.get("supporting_triples", [])
        if isinstance(supporting, list):
            triples.extend([item for item in supporting if isinstance(item, dict)])

        for triple in triples:
            predicate = str(triple.get("predicate", ""))
            if predicate not in ALLOWED_PREDICATES:
                continue
            subject_id = str(triple.get("subject_id") or triple.get("subject_label") or "UnknownSubject")
            subject = _uri(subject_id, "unknown_subject")
            object_term = _object_term(triple)
            line = f"{subject} {predicate} {object_term} ."
            if line not in emitted:
                lines.append(line)
                emitted.add(line)

            subject_type = str(triple.get("subject_type", "")).strip()
            if subject_type and subject_type != "Literal":
                type_lines.add(f"{subject} a ex:{subject_type} .")

            object_type = str(triple.get("object_type", "")).strip()
            object_id = str(triple.get("object_id") or triple.get("object_label") or "UnknownObject")
            if object_type and object_type != "Literal":
                type_lines.add(f"{_uri(object_id, 'unknown_object')} a ex:{object_type} .")

        mapping_node = f"_:mapping_{idx:03d}"
        confidence = mapping.get("confidence", 0.0)
        if isinstance(confidence, (int, float)):
            lines.append(f'{mapping_node} ex:hasConfidence "{float(confidence):.4f}"^^xsd:decimal .')
        reason = str(mapping.get("mapping_reason", "")).strip()
        if reason:
            lines.append(f'{mapping_node} ex:mappingReason "{escape_turtle_literal(reason)}" .')
        if mapping.get("needs_human_review"):
            lines.append(f'{mapping_node} ex:needsHumanReview "true" .')
        lines.append("")

    lines.extend(sorted(type_lines))
    return "\n".join(lines) + "\n"


def convert_payload_to_turtle(payload: Any, validation_results: Any | None = None) -> str:
    mappings = normalize_rdf_mappings(payload)
    if validation_results is None and isinstance(payload, dict):
        validation_results = payload.get("validation_results", [])
    return mappings_to_turtle(mappings, validation_results=validation_results)
