"""Deterministic RDF conversion node. This file never calls an LLM."""

from __future__ import annotations

from typing import Any

from schemas.annotation import ALLOWED_PREDICATES, AnnotationState
from utils import escape_turtle_literal, slugify

LITERAL_PREDICATES = {
    "ex:hasSurfaceExpression",
    "ex:hasMetaphorType",
    "ex:appearsInSentence",
    "ex:hasMIPVULabel",
}


def _uri(value: str, fallback: str = "Unknown") -> str:
    return f"ex:{slugify(value or fallback)}"


def _object_term(triple: dict[str, Any]) -> str:
    predicate = str(triple.get("predicate", ""))
    label = str(triple.get("object_label", ""))
    object_id = str(triple.get("object_id", ""))
    if predicate in LITERAL_PREDICATES or str(triple.get("object_type", "")) == "Literal":
        return f'"{escape_turtle_literal(label)}"'
    return _uri(object_id or label)


def convert_mapping_to_turtle(rdf_mappings: list[dict[str, Any]]) -> str:
    lines = [
        "@prefix ex: <http://example.org/legal-metaphor#> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
    ]
    if not rdf_mappings:
        lines.append("# No RDF mapping.")
        return "\n".join(lines) + "\n"

    emitted: set[str] = set()
    for mapping in rdf_mappings:
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
            subject = _uri(str(triple.get("subject_id") or triple.get("subject_label") or "UnknownSubject"))
            obj = _object_term(triple)
            line = f"{subject} {predicate} {obj} ."
            if line not in emitted:
                lines.append(line)
                emitted.add(line)

        confidence = mapping.get("confidence", 0.0)
        if isinstance(confidence, (int, float)):
            lines.append(f'_:mapping ex:hasConfidence "{float(confidence):.4f}"^^xsd:decimal .')
        reason = str(mapping.get("mapping_reason", ""))
        if reason:
            lines.append(f'_:mapping ex:mappingReason "{escape_turtle_literal(reason)}" .')
        lines.append("")

    return "\n".join(lines)


def rdf_convert_node(state: AnnotationState) -> dict[str, Any]:
    errors = list(state.get("errors", []))
    mappings = state.get("rdf_mappings", [])
    if not isinstance(mappings, list):
        mappings = []
    return {"rdf_output": convert_mapping_to_turtle([m for m in mappings if isinstance(m, dict)]), "errors": errors}
