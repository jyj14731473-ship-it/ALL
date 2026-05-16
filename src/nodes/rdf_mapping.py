"""RDF-ready mapping node.

The node creates RDF-ready subject/predicate/object triples deterministically
from MIPVU-based metaphor annotations and does not call an LLM.
"""

from __future__ import annotations

from typing import Any

from rdf.convert import fallback_mapping_from_annotation
from schemas.annotation import AnnotationState


def rdf_mapping_node(state: AnnotationState) -> dict[str, Any]:
    errors = list(state.get("errors", []))
    metaphors = state.get("metaphor_annotations", [])
    if not isinstance(metaphors, list) or not metaphors:
        errors.append("[rdf_mapping] 분류 결과가 없어 매핑을 건너뜁니다.")
        return {"rdf_mappings": [], "errors": errors}

    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate([m for m in metaphors if isinstance(m, dict)], start=1):
        mapping = fallback_mapping_from_annotation(item)
        mapping.setdefault("primary_triple", {})
        mapping.setdefault("supporting_triples", [])
        mapping.setdefault("mapping_reason", f"Deterministic fallback mapping from metaphor annotation {idx:03d}.")
        mapping_confidence = item.get("confidence", mapping.get("confidence", 0.0))
        if not isinstance(mapping_confidence, (int, float)):
            mapping["confidence"] = 0.0
        else:
            mapping["confidence"] = float(mapping_confidence)
        if mapping["confidence"] < 0.5:
            mapping["needs_human_review"] = True
        mapping.setdefault("needs_human_review", bool(mapping.get("needs_human_review", False)))
        normalized.append(mapping)

    return {"rdf_mappings": normalized, "errors": errors}
