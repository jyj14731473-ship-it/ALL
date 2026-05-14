"""RDF-ready mapping node.

The node creates RDF-ready subject/predicate/object triples deterministically
from MIPVU-based metaphor annotations and does not call an LLM.
"""

from __future__ import annotations

from typing import Any

from rdf.convert import mapping_from_mipvu_annotation
from schemas.annotation import AnnotationState


def rdf_mapping_node(state: AnnotationState) -> dict[str, Any]:
    errors = list(state.get("errors", []))
    mipvu_annotations = state.get("mipvu_annotations", [])

    if isinstance(mipvu_annotations, list) and mipvu_annotations:
        normalized: list[dict[str, Any]] = []
        for idx, item in enumerate([m for m in mipvu_annotations if isinstance(m, dict)], start=1):
            if str(item.get("mipvu_label", "")).strip() != "MRW":
                continue
            if not all(str(item.get(key, "")).strip() for key in ("source_domain", "target_domain", "conceptual_metaphor")):
                continue
            mapping = mapping_from_mipvu_annotation(item)
            mapping.setdefault("primary_triple", {})
            mapping.setdefault("supporting_triples", [])
            mapping.setdefault("mapping_reason", f"Deterministic KG mapping from MIPVU annotation {idx:03d}.")
            normalized.append(mapping)
        if normalized:
            return {"rdf_mappings": normalized, "errors": errors}
        errors.append("[rdf_mapping] KG로 변환 가능한 lemma 단위 MIPVU 판정이 없습니다.")

    return {"rdf_mappings": [], "errors": errors}
