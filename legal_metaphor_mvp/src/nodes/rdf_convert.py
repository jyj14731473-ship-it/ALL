"""Deterministic RDF conversion node. This file never calls an LLM."""

from __future__ import annotations

from rdf.convert import mappings_to_turtle
from schemas.annotation import AnnotationState


def rdf_convert_node(state: AnnotationState) -> dict[str, Any]:
    errors = list(state.get("errors", []))
    mappings = state.get("rdf_mappings", [])
    if not isinstance(mappings, list):
        mappings = []
    validation_results = state.get("validation_results", [])
    metadata = dict(state.get("metadata", {}))
    metadata["validation_status"] = "needs_repair" if state.get("status") == "needs_repair" else metadata.get(
        "validation_status",
        "ok",
    )
    return {
        "rdf_output": mappings_to_turtle([m for m in mappings if isinstance(m, dict)], validation_results=validation_results),
        "errors": errors,
        "metadata": metadata,
    }
