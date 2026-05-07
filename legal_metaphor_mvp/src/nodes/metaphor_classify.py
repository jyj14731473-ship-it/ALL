"""Conceptual metaphor classification node."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from graph.prompt_utils import call_structured_chain, load_common_system_prompt, load_prompt_text
from schemas.annotation import AnnotationState, MetaphorClassificationOutput


def _safe_float(value: Any) -> float:
    return max(0.0, min(1.0, float(value))) if isinstance(value, (int, float)) else 0.0


def _eligible(judgment: dict[str, Any]) -> bool:
    return str(judgment.get("mipvu_label", "")).strip() in {"MRW", "MRW_candidate", "borderline_candidate"}


def metaphor_classify_node(state: AnnotationState) -> dict[str, Any]:
    errors = list(state.get("errors", []))
    judgments = state.get("mipvu_annotations", [])
    candidates = state.get("candidates", [])
    if not isinstance(judgments, list) or not judgments:
        errors.append("[metaphor_classify] 판정 결과가 없어 분류를 생략합니다.")
        return {"metaphor_annotations": [], "final_annotations": [], "errors": errors}

    filtered = [j for j in judgments if isinstance(j, dict) and _eligible(j)]
    if not filtered:
        errors.append("[metaphor_classify] MRW 계열 판정이 없어 분류를 생략합니다.")
        return {"metaphor_annotations": [], "final_annotations": [], "errors": errors}

    prompt_dir = Path(__file__).resolve().parents[1] / "prompts"
    system_prompt = load_common_system_prompt(prompt_dir)
    user_prompt = load_prompt_text(prompt_dir, "metaphor_classify.md")
    if not user_prompt:
        user_prompt = "MIPVU 판정 결과를 개념 은유 주석 JSON으로 분류하세요.\n\n{{JUDGMENTS_JSON}}"
    payload = {"raw_text": state.get("raw_text", ""), "candidates": candidates, "judgments": filtered}
    user_prompt = user_prompt.replace("{{JUDGMENTS_JSON}}", json.dumps(payload, ensure_ascii=False))

    parsed = call_structured_chain(system_prompt, user_prompt, MetaphorClassificationOutput, errors, "metaphor_classify")
    metaphors = parsed.get("metaphors", []) if isinstance(parsed, dict) else []
    candidate_lookup = {str(c.get("candidate_id", "")): c for c in candidates if isinstance(c, dict)}

    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(metaphors if isinstance(metaphors, list) else [], start=1):
        if not isinstance(item, dict):
            continue
        entry = dict(item)
        entry.setdefault("metaphor_id", f"M{idx:03d}")
        entry["candidate_id"] = entry.get("candidate_id") or entry.get("source_candidate_id", "")
        entry.setdefault("sentence_id", "")
        source = candidate_lookup.get(str(entry.get("candidate_id", "")), {})
        entry.setdefault("surface_expression", source.get("surface_expression", ""))
        entry.setdefault("context_sentence", source.get("sentence", source.get("context_sentence", "")))
        if not entry["sentence_id"]:
            entry["sentence_id"] = source.get("sentence_id", f"S{idx:03d}")
        entry.setdefault("conceptual_metaphor", "")
        entry.setdefault("metaphor_type", "uncertain")
        entry.setdefault("source_domain", "")
        entry.setdefault("target_domain", "")
        entry.setdefault("legal_concept", source.get("candidate_legal_concept", ""))
        entry.setdefault("opinion_type", "unknown")
        entry.setdefault("is_legal_domain_specific", False)
        entry.setdefault("classification_reason", entry.get("rationale_brief", ""))
        entry["confidence"] = _safe_float(entry.get("confidence", 0.0))
        entry["needs_human_review"] = bool(entry.get("needs_human_review", False) or entry["confidence"] < 0.35)
        entry["source_candidate_id"] = entry["candidate_id"]
        entry["rationale_brief"] = entry.get("classification_reason", "")
        normalized.append(entry)

    return {"metaphor_annotations": normalized, "final_annotations": normalized, "errors": errors}
