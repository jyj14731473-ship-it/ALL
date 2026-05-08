"""MIPVU-informed judgment node."""

from __future__ import annotations

import json
from pathlib import Path
import re
from difflib import SequenceMatcher
import os
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
LEXICAL_OVERLAP_MIN = 0.45
LEXICAL_OVERLAP_LOW = 0.20
LEXICAL_SIMILARITY_MIN = 0.78


def _safe_float(value: Any) -> float:
    return max(0.0, min(1.0, float(value))) if isinstance(value, (int, float)) else 0.0


def _canonical(text: str) -> str:
    """Normalize text for lightweight lexical comparison."""
    normalized = (text or "").strip().lower()
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def _extract_terms(text: str) -> set[str]:
    """Tokenize a string using simple Korean/word boundary heuristics."""
    cleaned = re.sub(r"[^0-9가-힣A-Za-z]+", " ", text.lower())
    return {token for token in cleaned.split() if token}


def _token_char_ngrams(text: str, size: int = 2) -> set[str]:
    if not text:
        return set()
    normalized = re.sub(r"\s+", "", text.lower())
    if len(normalized) <= size:
        return {normalized} if normalized else set()
    return {normalized[i : i + size] for i in range(len(normalized) - size + 1)}


def _compare_meanings(
    basic_meaning: str,
    contextual_meaning: str,
    context_sentence: str,
) -> dict[str, Any]:
    """Compare meanings before LLM judgment, without any LLM involvement."""
    basic = _canonical(basic_meaning)
    other = _canonical(contextual_meaning or context_sentence)

    if not basic or not other:
        return {
            "comparison_possible": False,
            "similarity": False,
            "distinctness": False,
            "meaning_contrast": "기본 의미 또는 비교 대상이 비어 있어 의미 비교를 수행할 수 없습니다.",
            "pre_judgment": "uncertain",
            "pre_confidence": 0.15,
        }

    basic_terms = _extract_terms(basic)
    other_terms = _extract_terms(other)
    comparison_possible = bool(basic_terms) and bool(other_terms)
    if not comparison_possible:
        return {
            "comparison_possible": False,
            "similarity": False,
            "distinctness": False,
            "meaning_contrast": "의미 비교 토큰이 충분하지 않습니다.",
            "pre_judgment": "uncertain",
            "pre_confidence": 0.20,
        }

    overlap = len(basic_terms & other_terms) / max(1, len(basic_terms | other_terms))
    char_ratio = SequenceMatcher(None, basic, other).ratio()
    char_ngrams = _token_char_ngrams(basic) | _token_char_ngrams(other)
    ngram_overlap = (
        len(_token_char_ngrams(basic) & _token_char_ngrams(other)) / max(1, len(char_ngrams))
        if char_ngrams
        else 0.0
    )
    similarity = (
        overlap >= LEXICAL_OVERLAP_MIN
        or char_ratio >= LEXICAL_SIMILARITY_MIN
        or ngram_overlap >= LEXICAL_OVERLAP_MIN
    )
    distinctness = comparison_possible and not similarity
    if distinctness and overlap < LEXICAL_OVERLAP_LOW:
        pre = "MRW_candidate"
        pre_confidence = 0.72 + min(0.2, (1.0 - overlap) * 0.25)
    elif similarity and overlap >= LEXICAL_OVERLAP_MIN:
        pre = "non_MRW"
        pre_confidence = 0.75
    else:
        pre = "uncertain"
        pre_confidence = 0.55 if char_ratio >= 0.55 else 0.3

    if similarity:
        contrast = "기본 의미와 비교 문맥 의미의 중첩이 높아 동일 의미 사용 가능성이 큽니다."
    else:
        contrast = "기본 의미와 문맥 의미 간 차이가 커 은유 가능성이 증가합니다."

    return {
        "comparison_possible": True,
        "similarity": bool(similarity),
        "distinctness": bool(distinctness),
        "meaning_contrast": contrast,
        "pre_judgment": pre,
        "pre_confidence": pre_confidence,
    }


def _attach_dictionary_hint(
    candidates: list[dict[str, Any]],
    contextual_lookup: dict[str, str] | None = None,
) -> list[dict[str, Any]]:
    dictionary = DictionaryTool()
    lookup_requests: list[tuple[str, str | None]] = []
    for item in candidates:
        term = str(item.get("lemma") or item.get("surface_expression") or "").strip()
        lookup_requests.append((term, item.get("pos")))
    dictionary_lookups = dictionary.lookup_batch(lookup_requests)
    enriched: list[dict[str, Any]] = []
    lookup_map = contextual_lookup or {}
    for idx, item in enumerate(candidates):
        updated = dict(item)
        term = str(updated.get("lemma") or updated.get("surface_expression") or "").strip()
        lookup = dictionary_lookups[idx] if idx < len(dictionary_lookups) else dictionary.lookup(term, updated.get("pos"))
        updated["dictionary_lookup"] = lookup
        updated["basic_meaning"] = str(updated.get("basic_meaning") or lookup.get("definition") or "")
        updated["basic_meaning_source"] = str(updated.get("basic_meaning_source") or lookup.get("basic_meaning_source", "unavailable"))
        contextual_meaning = str(
            lookup_map.get(term)
            or updated.get("contextual_meaning")
            or updated.get("contextual_meaning_hint", "")
        ).strip()
        updated["contextual_meaning"] = contextual_meaning
        comparison = _compare_meanings(
            basic_meaning=updated["basic_meaning"],
            contextual_meaning=contextual_meaning,
            context_sentence=str(updated.get("context_sentence", updated.get("sentence", ""))),
        )
        updated.update(comparison)
        updated["pre_mipvu_judgment"] = comparison["pre_judgment"]
        updated["pre_mipvu_confidence"] = comparison["pre_confidence"]
        enriched.append(updated)
    return enriched


def _normalize_label(value: Any) -> str:
    raw = str(value or "uncertain").strip()
    lookup = {
        "MRW": "MRW",
        "mrw": "MRW",
        "MRW_candidate": "MRW_candidate",
        "mrw_candidate": "MRW_candidate",
        "non-MRW": "non_MRW",
        "borderline_candidate": "borderline_candidate",
        "non_MRW": "non_MRW",
        "non_mrw": "non_MRW",
        "not_mrw": "non_MRW",
        "not-mrw": "non_MRW",
        "not_MRW": "non_MRW",
        "uncertain": "uncertain",
        "": "uncertain",
    }
    return lookup.get(raw, "uncertain")


def _batch_items(items: list[dict[str, Any]], batch_size: int) -> list[list[dict[str, Any]]]:
    if batch_size <= 0:
        return [items]
    return [items[idx : idx + batch_size] for idx in range(0, len(items), batch_size)]


def mipvu_judge_node(state: AnnotationState) -> dict[str, Any]:
    errors = list(state.get("errors", []))
    candidates = state.get("candidates", [])
    if not isinstance(candidates, list) or not candidates:
        errors.append("[mipvu_judge] 판정할 후보가 없습니다.")
        return {"mipvu_annotations": [], "errors": errors}

    contextual_lookup = {
        str(key): str(value).strip()
        for key, value in state.get("contextual_meaning_by_lemma", {}).items()
        if isinstance(key, str)
    }
    enriched = _attach_dictionary_hint(
        [c for c in candidates if isinstance(c, dict)],
        contextual_lookup=contextual_lookup,
    )
    prompt_dir = Path(__file__).resolve().parents[1] / "prompts"
    system_prompt = load_common_system_prompt(prompt_dir)
    user_prompt = load_prompt_text(prompt_dir, "mipvu_judge.md")
    if not user_prompt:
        user_prompt = "후보별 MIPVU 판정을 JSON으로 반환하세요.\n\n{{CANDIDATES_JSON}}"
    user_prompt = user_prompt.replace("{{CANDIDATES_JSON}}", json.dumps({"candidates": enriched}, ensure_ascii=False))

    batch_size = int(os.getenv("MIPVU_BATCH_SIZE", "30").strip() or 30)
    if batch_size < 1:
        batch_size = 30

    all_judgments: list[dict[str, Any]] = []
    chunks = _batch_items(enriched, batch_size)
    for chunk_idx, chunk in enumerate(chunks, start=1):
        if not chunk:
            continue
        chunk_user_prompt = load_prompt_text(prompt_dir, "mipvu_judge.md")
        if not chunk_user_prompt:
            chunk_user_prompt = "후보별 MIPVU 판정을 JSON으로 반환하세요.\n\n{{CANDIDATES_JSON}}"
        chunk_user_prompt = chunk_user_prompt.replace(
            "{{CANDIDATES_JSON}}",
            json.dumps({"candidates": chunk}, ensure_ascii=False),
        )
        parsed = call_structured_chain(
            system_prompt,
            chunk_user_prompt,
            MipvuJudgmentOutput,
            errors,
            f"mipvu_judge_batch{chunk_idx}",
        )
        chunk_judgments = parsed.get("judgments", []) if isinstance(parsed, dict) else []
        all_judgments.extend(chunk_judgments)

    judgments = all_judgments
    candidate_lookup = {str(c.get("candidate_id", "")): c for c in enriched}

    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(judgments if isinstance(judgments, list) else [], start=1):
        if not isinstance(item, dict):
            continue
        judgment = dict(item)
        source = candidate_lookup.get(str(judgment.get("candidate_id", "")))
        if source is None:
            source = enriched[min(idx - 1, len(enriched) - 1)] if enriched else {}
            judgment.setdefault("candidate_id", str(source.get("candidate_id", f"C{idx:03d}")))
        else:
            judgment.setdefault("candidate_id", str(source.get("candidate_id", f"C{idx:03d}")))
        judgment.setdefault("sentence_id", source.get("sentence_id", f"S{idx:03d}"))
        judgment.setdefault("token", judgment.get("surface_expression", source.get("surface_expression", "")))
        judgment.setdefault("lemma", source.get("lemma", ""))
        judgment.setdefault("pos", source.get("pos", ""))
        judgment.setdefault("context_sentence", source.get("sentence", source.get("context_sentence", "")))
        judgment.setdefault("contextual_meaning", source.get("contextual_meaning", ""))
        judgment.setdefault("basic_meaning", source.get("basic_meaning", ""))
        judgment.setdefault("basic_meaning_source", source.get("basic_meaning_source", "unavailable"))
        judgment.setdefault("meaning_contrast", source.get("meaning_contrast", ""))
        judgment.setdefault("distinctness", source.get("distinctness", False))
        judgment.setdefault("comparison_possible", source.get("comparison_possible", False))
        judgment.setdefault("similarity", source.get("similarity", False))
        judgment.setdefault("pre_mipvu_judgment", source.get("pre_mipvu_judgment", "uncertain"))
        judgment.setdefault("pre_mipvu_confidence", source.get("pre_mipvu_confidence", 0.0))
        judgment["mipvu_label"] = _normalize_label(judgment.get("mipvu_label"))
        if judgment["mipvu_label"] == "uncertain" and judgment.get("pre_mipvu_judgment") in {
            "MRW",
            "MRW_candidate",
            "non_MRW",
            "borderline_candidate",
        }:
            judgment["mipvu_label"] = str(judgment["pre_mipvu_judgment"])
            if judgment["mipvu_label"] != "uncertain":
                judgment["confidence"] = float(judgment.get("pre_mipvu_confidence", 0.0))
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
