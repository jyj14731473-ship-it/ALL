"""RDF-ready mapping node.

The node creates RDF-ready subject/predicate/object triples deterministically
from MIPVU-based metaphor annotations and does not call an LLM.
"""

from __future__ import annotations

from typing import Any

from rdf.convert import fallback_mapping_from_annotation, fallback_mapping_from_mipvu_annotation
from schemas.annotation import AnnotationState


def rdf_mapping_node(state: AnnotationState) -> dict[str, Any]:
    errors = list(state.get("errors", []))
    mipvu_annotations = state.get("mipvu_annotations", [])
    metaphors = state.get("metaphor_annotations", [])

    if isinstance(mipvu_annotations, list) and mipvu_annotations:
        normalized: list[dict[str, Any]] = []
        for idx, item in enumerate([m for m in mipvu_annotations if isinstance(m, dict)], start=1):
            if str(item.get("mipvu_label", "")).strip() not in {"MRW", "MRW_candidate", "borderline_candidate"}:
                continue
            if not all(str(item.get(key, "")).strip() for key in ("source_domain", "target_domain", "conceptual_metaphor")):
                continue
            mapping = fallback_mapping_from_mipvu_annotation(item)
            mapping.setdefault("primary_triple", {})
            mapping.setdefault("supporting_triples", [])
            mapping.setdefault("mapping_reason", f"Deterministic KG mapping from MIPVU annotation {idx:03d}.")
            normalized.append(mapping)
        if normalized:
            return {"rdf_mappings": normalized, "errors": errors}
        errors.append("[rdf_mapping] KG로 변환 가능한 lemma 단위 MIPVU 판정이 없습니다.")

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
