"""RDF-ready mapping node.

The LLM chooses RDF-ready subject, predicate, and object labels as JSON.
It does not generate Turtle.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from graph.prompt_utils import call_structured_chain, load_common_system_prompt, load_prompt_text
from rdf.convert import fallback_mapping_from_annotation
from schemas.annotation import AnnotationState, RdfMappingOutput


def _safe_float(value: Any) -> float:
    return max(0.0, min(1.0, float(value))) if isinstance(value, (int, float)) else 0.0


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
        mappings = [fallback_mapping_from_annotation(item) for item in metaphors if isinstance(item, dict)]

    normalized: list[dict[str, Any]] = []
    for mapping in mappings:
        mapping.setdefault("supporting_triples", [])
        mapping.setdefault("mapping_reason", "")
        mapping["confidence"] = _safe_float(mapping.get("confidence", 0.0))
        mapping["needs_human_review"] = bool(mapping.get("needs_human_review", False) or mapping["confidence"] < 0.5)
        normalized.append(mapping)
    return {"rdf_mappings": normalized, "errors": errors}
