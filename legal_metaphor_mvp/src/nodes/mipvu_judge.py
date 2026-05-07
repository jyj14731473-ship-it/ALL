"""MIPVU-informed judgment node."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from graph.prompt_utils import call_structured_chain, load_common_system_prompt, load_prompt_text
from schemas.annotation import AnnotationState, MipvuJudgmentOutput
from tools.dictionary import DictionaryTool

CONVENTIONAL_TERMS = {
    "부담하다",
    "성립하다",
    "소멸하다",
    "귀속되다",
    "관철하다",
    "배척하다",
    "흠결",
    "효력",
    "요건",
    "기초",
    "전제",
    "범위",
    "한계",
}


def _safe_float(value: Any) -> float:
    return max(0.0, min(1.0, float(value))) if isinstance(value, (int, float)) else 0.0


def _attach_dictionary_hint(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    dictionary = DictionaryTool()
    enriched: list[dict[str, Any]] = []
    for item in candidates:
        updated = dict(item)
        term = str(updated.get("lemma") or updated.get("surface_expression") or "").strip()
        lookup = dictionary.lookup(term, updated.get("pos"))
        updated["dictionary_lookup"] = lookup
        if not updated.get("basic_meaning") and lookup.get("definition"):
            updated["basic_meaning"] = lookup["definition"]
            updated["basic_meaning_source"] = "stdict"
        enriched.append(updated)
    return enriched


def _normalize_label(value: Any) -> str:
    raw = str(value or "uncertain").strip()
    lookup = {
        "MRW": "MRW",
        "mrw": "MRW",
        "MRW_candidate": "MRW_candidate",
        "mrw_candidate": "MRW_candidate",
        "borderline_candidate": "borderline_candidate",
        "non_MRW": "non_MRW",
        "non_mrw": "non_MRW",
        "uncertain": "uncertain",
    }
    return lookup.get(raw, "uncertain")


def mipvu_judge_node(state: AnnotationState) -> dict[str, Any]:
    errors = list(state.get("errors", []))
    candidates = state.get("candidates", [])
    if not isinstance(candidates, list) or not candidates:
        errors.append("[mipvu_judge] 판정할 후보가 없습니다.")
        return {"mipvu_annotations": [], "errors": errors}

    enriched = _attach_dictionary_hint([c for c in candidates if isinstance(c, dict)])
    prompt_dir = Path(__file__).resolve().parents[1] / "prompts"
    system_prompt = load_common_system_prompt(prompt_dir)
    user_prompt = load_prompt_text(prompt_dir, "mipvu_judge.md")
    if not user_prompt:
        user_prompt = "후보별 MIPVU 판정을 JSON으로 반환하세요.\n\n{{CANDIDATES_JSON}}"
    user_prompt = user_prompt.replace("{{CANDIDATES_JSON}}", json.dumps({"candidates": enriched}, ensure_ascii=False))

    parsed = call_structured_chain(system_prompt, user_prompt, MipvuJudgmentOutput, errors, "mipvu_judge")
    judgments = parsed.get("judgments", []) if isinstance(parsed, dict) else []
    candidate_lookup = {str(c.get("candidate_id", "")): c for c in enriched}

    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(judgments if isinstance(judgments, list) else [], start=1):
        if not isinstance(item, dict):
            continue
        judgment = dict(item)
        judgment.setdefault("candidate_id", f"C{idx:03d}")
        source = candidate_lookup.get(str(judgment["candidate_id"]), {})
        judgment.setdefault("sentence_id", source.get("sentence_id", f"S{idx:03d}"))
        judgment.setdefault("token", judgment.get("surface_expression", source.get("surface_expression", "")))
        judgment.setdefault("lemma", source.get("lemma", ""))
        judgment.setdefault("pos", source.get("pos", ""))
        judgment.setdefault("context_sentence", source.get("sentence", source.get("context_sentence", "")))
        judgment.setdefault("contextual_meaning", "")
        judgment.setdefault("basic_meaning", source.get("basic_meaning", ""))
        judgment.setdefault("basic_meaning_source", source.get("basic_meaning_source", "unavailable"))
        judgment.setdefault("meaning_contrast", "")
        judgment.setdefault("distinctness", False)
        judgment.setdefault("comparison_possible", judgment.get("similarity", False))
        judgment.setdefault("similarity", judgment.get("comparison_possible", False))
        judgment["mipvu_label"] = _normalize_label(judgment.get("mipvu_label"))
        judgment.setdefault("judgment_reason", "")
        judgment["confidence"] = _safe_float(judgment.get("confidence", 0.0))
        if judgment["confidence"] < 0.35 and judgment["mipvu_label"] == "MRW":
            judgment["mipvu_label"] = "MRW_candidate"
        surface = str(judgment.get("token", ""))
        judgment["needs_human_review"] = bool(
            judgment.get("needs_human_review", False)
            or judgment["confidence"] < 0.35
            or any(term in surface for term in CONVENTIONAL_TERMS)
        )
        judgment["surface_expression"] = judgment["token"]
        normalized.append(judgment)

    return {"mipvu_annotations": normalized, "errors": errors}
