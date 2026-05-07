"""RDF-ready mapping node.

The LLM chooses RDF-ready subject, predicate, and object labels as JSON.
It does not generate Turtle.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from graph.prompt_utils import call_structured_chain, load_common_system_prompt, load_prompt_text
from schemas.annotation import AnnotationState, RdfMappingOutput


def _safe_float(value: Any) -> float:
    return max(0.0, min(1.0, float(value))) if isinstance(value, (int, float)) else 0.0


def _fallback_mapping(annotation: dict[str, Any]) -> dict[str, Any]:
    metaphor_id = str(annotation.get("metaphor_id", "M000"))
    legal = str(annotation.get("legal_concept") or annotation.get("target_domain") or "UnknownLegalConcept")
    source = str(annotation.get("source_domain") or "UnknownSourceDomain")
    target = str(annotation.get("target_domain") or "UnknownTargetDomain")
    surface = str(annotation.get("surface_expression") or "")
    sentence = str(annotation.get("context_sentence") or "")
    label = str(annotation.get("mipvu_label") or "MRW_candidate")
    metaphor_type = str(annotation.get("metaphor_type") or "uncertain")
    confidence = _safe_float(annotation.get("confidence", 0.0))
    return {
        "primary_triple": {
            "subject_label": legal,
            "subject_type": "LegalConcept",
            "subject_id": f"LegalConcept_{metaphor_id}",
            "predicate": "ex:isConceptualizedAs",
            "object_label": source,
            "object_type": "SourceDomain",
            "object_id": f"SourceDomain_{metaphor_id}",
        },
        "supporting_triples": [
            {
                "subject_label": metaphor_id,
                "subject_type": "MetaphorAnnotation",
                "subject_id": metaphor_id,
                "predicate": "ex:hasSurfaceExpression",
                "object_label": surface,
                "object_type": "Literal",
                "object_id": f"Literal_{metaphor_id}_surface",
            },
            {
                "subject_label": metaphor_id,
                "subject_type": "MetaphorAnnotation",
                "subject_id": metaphor_id,
                "predicate": "ex:appearsInSentence",
                "object_label": sentence,
                "object_type": "Literal",
                "object_id": f"Literal_{metaphor_id}_sentence",
            },
            {
                "subject_label": metaphor_id,
                "subject_type": "MetaphorAnnotation",
                "subject_id": metaphor_id,
                "predicate": "ex:hasSourceDomain",
                "object_label": source,
                "object_type": "SourceDomain",
                "object_id": f"SourceDomain_{metaphor_id}",
            },
            {
                "subject_label": metaphor_id,
                "subject_type": "MetaphorAnnotation",
                "subject_id": metaphor_id,
                "predicate": "ex:hasTargetDomain",
                "object_label": target,
                "object_type": "TargetDomain",
                "object_id": f"TargetDomain_{metaphor_id}",
            },
            {
                "subject_label": metaphor_id,
                "subject_type": "MetaphorAnnotation",
                "subject_id": metaphor_id,
                "predicate": "ex:hasMetaphorType",
                "object_label": metaphor_type,
                "object_type": "Literal",
                "object_id": f"Literal_{metaphor_id}_type",
            },
            {
                "subject_label": metaphor_id,
                "subject_type": "MetaphorAnnotation",
                "subject_id": metaphor_id,
                "predicate": "ex:hasMIPVULabel",
                "object_label": label,
                "object_type": "Literal",
                "object_id": f"Literal_{metaphor_id}_mipvu",
            },
        ],
        "mapping_reason": "LLM mapping unavailable; generated deterministic fallback from canonical annotation JSON.",
        "confidence": confidence,
        "needs_human_review": confidence < 0.5,
    }


def _mapping_items(parsed: dict[str, Any]) -> list[dict[str, Any]]:
    if isinstance(parsed.get("rdf_mappings"), list):
        return [item for item in parsed["rdf_mappings"] if isinstance(item, dict)]
    if isinstance(parsed.get("rdf_mapping"), dict):
        return [parsed["rdf_mapping"]]
    return []


def rdf_mapping_node(state: AnnotationState) -> dict[str, Any]:
    errors = list(state.get("errors", []))
    metaphors = state.get("metaphor_annotations", [])
    if not isinstance(metaphors, list) or not metaphors:
        errors.append("[rdf_mapping] 분류 결과가 없어 매핑을 건너뜁니다.")
        return {"rdf_mappings": [], "errors": errors}

    prompt_dir = Path(__file__).resolve().parents[1] / "prompts"
    system_prompt = load_common_system_prompt(prompt_dir)
    user_prompt = load_prompt_text(prompt_dir, "rdf_mapping.md")
    if not user_prompt:
        user_prompt = "은유 주석을 RDF-ready JSON mapping으로 변환하세요.\n\n{{METAPHORS_JSON}}"
    user_prompt = user_prompt.replace("{{METAPHORS_JSON}}", json.dumps({"metaphors": metaphors}, ensure_ascii=False))

    parsed = call_structured_chain(system_prompt, user_prompt, RdfMappingOutput, errors, "rdf_mapping")
    mappings = _mapping_items(parsed) if isinstance(parsed, dict) else []
    if not mappings:
        mappings = [_fallback_mapping(item) for item in metaphors if isinstance(item, dict)]

    normalized: list[dict[str, Any]] = []
    for mapping in mappings:
        mapping.setdefault("supporting_triples", [])
        mapping.setdefault("mapping_reason", "")
        mapping["confidence"] = _safe_float(mapping.get("confidence", 0.0))
        mapping["needs_human_review"] = bool(mapping.get("needs_human_review", False) or mapping["confidence"] < 0.5)
        normalized.append(mapping)
    return {"rdf_mappings": normalized, "errors": errors}
