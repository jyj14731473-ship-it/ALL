"""Conceptual metaphor classification node."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from graph.prompt_utils import call_structured_chain, load_common_system_prompt, load_prompt_text
from schemas.annotation import AnnotationState, MetaphorClassificationOutput


def _safe_float(value: Any) -> float:
    return max(0.0, min(1.0, float(value))) if isinstance(value, (int, float)) else 0.0


def _eligible(judgment: dict[str, Any]) -> bool:
    return str(judgment.get("mipvu_label", "")).strip() in {"MRW", "MRW_candidate", "borderline_candidate"}


def _batch_items(items: list[dict[str, Any]], batch_size: int) -> list[list[dict[str, Any]]]:
    if batch_size <= 0:
        return [items]
    return [items[idx : idx + batch_size] for idx in range(0, len(items), batch_size)]


def _compact_judgment_for_llm(judgment: dict[str, Any]) -> dict[str, Any]:
    return {
        "candidate_id": str(judgment.get("candidate_id", "")),
        "surface_expression": str(judgment.get("surface_expression") or judgment.get("token") or ""),
        "lemma": str(judgment.get("lemma", "")),
        "pos": str(judgment.get("pos", "")),
        "context_sentence": str(judgment.get("context_sentence", "")),
        "contextual_meaning": str(judgment.get("contextual_meaning", "")),
        "basic_meaning": str(judgment.get("basic_meaning", "")),
        "mipvu_label": str(judgment.get("mipvu_label", "")),
        "judgment_reason": str(judgment.get("judgment_reason", "")),
        "mipvu_confidence": judgment.get("confidence", 0.0),
    }


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

    batch_size = int(os.getenv("METAPHOR_BATCH_SIZE", "30").strip() or 30)
    if batch_size < 1:
        batch_size = 30

    all_metaphors: list[dict[str, Any]] = []
    chunks = _batch_items(filtered, batch_size)
    for chunk_idx, chunk in enumerate(chunks, start=1):
        if not chunk:
            continue
        payload = {"judgments": [_compact_judgment_for_llm(item) for item in chunk]}
        chunk_prompt = user_prompt.replace("{{JUDGMENTS_JSON}}", json.dumps(payload, ensure_ascii=False))
        parsed = call_structured_chain(
            system_prompt,
            chunk_prompt,
            MetaphorClassificationOutput,
            errors,
            f"metaphor_classify_batch{chunk_idx}",
        )
        all_metaphors.extend(parsed.get("metaphors", []) if isinstance(parsed, dict) else [])
    metaphors = all_metaphors
    candidate_lookup = {str(c.get("candidate_id", "")): c for c in candidates if isinstance(c, dict)}

    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(metaphors if isinstance(metaphors, list) else [], start=1):
        if not isinstance(item, dict):
            continue
        entry = dict(item)
        if not entry.get("metaphor_id"):
            entry["metaphor_id"] = f"M{idx:03d}"
        entry["candidate_id"] = entry.get("candidate_id") or entry.get("source_candidate_id", "")
        source = candidate_lookup.get(str(entry.get("candidate_id", "")), {})
        if not entry.get("surface_expression"):
            entry["surface_expression"] = source.get("surface_expression", "")
        if not entry.get("context_sentence"):
            entry["context_sentence"] = source.get("sentence", source.get("context_sentence", ""))
        if not entry.get("sentence_id"):
            entry["sentence_id"] = source.get("sentence_id", f"S{idx:03d}")
        if not entry.get("conceptual_metaphor"):
            entry["conceptual_metaphor"] = ""
        if not entry.get("metaphor_type"):
            entry["metaphor_type"] = "uncertain"
        if not entry.get("source_domain"):
            entry["source_domain"] = ""
        if not entry.get("target_domain"):
            entry["target_domain"] = ""
        if not entry.get("legal_concept"):
            entry["legal_concept"] = source.get("candidate_legal_concept", "")
        if not entry.get("opinion_type"):
            entry["opinion_type"] = "unknown"
        entry.setdefault("is_legal_domain_specific", False)
        if not entry.get("classification_reason"):
            entry["classification_reason"] = entry.get("rationale_brief", "")
        entry["confidence"] = _safe_float(entry.get("confidence", 0.0))
        entry["needs_human_review"] = bool(entry.get("needs_human_review", False) or entry["confidence"] < 0.35)
        entry["source_candidate_id"] = entry["candidate_id"]
        entry["rationale_brief"] = entry.get("classification_reason", "")
        normalized.append(entry)

    return {"metaphor_annotations": normalized, "final_annotations": normalized, "errors": errors}
