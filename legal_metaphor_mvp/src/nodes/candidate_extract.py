"""Candidate extraction node."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from graph.prompt_utils import call_structured_chain, load_common_system_prompt, load_prompt_text
from schemas.annotation import AnnotationState, CandidateExtractionOutput


def _split_sentences(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text.replace("\n", " ")).strip()
    if not normalized:
        return []
    return [part.strip() for part in re.split(r"(?<=[.!?。！？])\s*", normalized) if part.strip()]


def candidate_extract_node(state: AnnotationState) -> dict[str, Any]:
    raw_text = state.get("raw_text", "")
    errors = list(state.get("errors", []))
    sentences = _split_sentences(raw_text)
    if not raw_text.strip():
        errors.append("[candidate_extract] 입력 텍스트가 비어 있습니다.")
        return {"sentences": [], "candidates": [], "errors": errors}

    prompt_dir = Path(__file__).resolve().parents[1] / "prompts"
    system_prompt = load_common_system_prompt(prompt_dir)
    user_prompt = load_prompt_text(prompt_dir, "candidate_extract.md")
    if not user_prompt:
        user_prompt = "한국어 법률 텍스트에서 은유 후보를 JSON으로 추출하세요.\n\n{{INPUT_TEXT}}"
    user_prompt = user_prompt.replace("{{INPUT_TEXT}}", raw_text)

    parsed = call_structured_chain(
        system_prompt,
        user_prompt,
        CandidateExtractionOutput,
        errors,
        "candidate_extract",
    )
    candidates = parsed.get("candidates", []) if isinstance(parsed, dict) else []

    normalized: list[dict[str, Any]] = []
    for idx, item in enumerate(candidates if isinstance(candidates, list) else [], start=1):
        if not isinstance(item, dict):
            continue
        candidate = dict(item)
        candidate.setdefault("candidate_id", f"C{idx:03d}")
        candidate.setdefault("sentence_id", f"S{idx:03d}")
        candidate.setdefault("sentence", candidate.get("context_sentence", ""))
        candidate.setdefault("surface_expression", "")
        candidate.setdefault("lemma", "")
        candidate.setdefault("pos", candidate.get("primary_pos", ""))
        candidate.setdefault("morphemes", candidate.get("morpheme_or_pos_tags", []))
        candidate.setdefault("context_window", candidate.get("sentence", ""))
        candidate.setdefault("opinion_type", "unknown")
        candidate.setdefault("extraction_reason", candidate.get("reason_for_candidate", ""))
        confidence = candidate.get("confidence", 0.0)
        candidate["confidence"] = max(0.0, min(1.0, float(confidence if isinstance(confidence, (int, float)) else 0.0)))
        candidate["needs_human_review"] = bool(candidate.get("needs_human_review", False))
        candidate["context_sentence"] = candidate.get("sentence", "")
        candidate["reason_for_candidate"] = candidate.get("extraction_reason", "")
        normalized.append(candidate)

    return {"sentences": sentences, "candidates": normalized, "errors": errors}
