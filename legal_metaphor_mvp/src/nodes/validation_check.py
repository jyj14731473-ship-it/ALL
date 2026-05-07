"""Validation node with rule checks and optional LLM review."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from graph.prompt_utils import call_structured_chain, load_common_system_prompt, load_prompt_text
from schemas.annotation import ALLOWED_PREDICATES, AnnotationState, ValidationOutput


def _issue(severity: str, location: str, message: str, suggested_fix: str) -> dict[str, str]:
    return {
        "severity": severity,
        "location": location,
        "message": message,
        "suggested_fix": suggested_fix,
    }


def validation_check_node(state: AnnotationState) -> dict[str, Any]:
    errors = list(state.get("errors", []))
    mipvu = state.get("mipvu_annotations", [])
    metaphors = state.get("metaphor_annotations", [])
    mappings = state.get("rdf_mappings", [])
    issues: list[dict[str, str]] = []
    human_review_items: list[dict[str, Any]] = list(state.get("human_review_items", []))

    mipvu_lookup = {str(item.get("candidate_id", "")): item for item in mipvu if isinstance(item, dict)}
    for annotation in metaphors if isinstance(metaphors, list) else []:
        if not isinstance(annotation, dict):
            continue
        mid = str(annotation.get("metaphor_id", ""))
        cid = str(annotation.get("candidate_id") or annotation.get("source_candidate_id") or "")
        confidence = annotation.get("confidence", 0.0)
        confidence = confidence if isinstance(confidence, (int, float)) else 0.0
        if confidence < 0.35:
            issues.append(_issue("warning", f"metaphor_id={mid}", "confidence가 낮습니다.", "human review에서 근거를 확인하세요."))
            human_review_items.append({"metaphor_id": mid, "candidate_id": cid, "issue_type": "low_confidence"})
        if not str(annotation.get("source_domain", "")).strip() or not str(annotation.get("target_domain", "")).strip():
            issues.append(_issue("error", f"metaphor_id={mid}", "source_domain 또는 target_domain이 비어 있습니다.", "분류 노드 출력을 재검토하세요."))

        judgment = mipvu_lookup.get(cid, {})
        if isinstance(judgment, dict) and str(judgment.get("mipvu_label", "")) in {"MRW", "MRW_candidate", "borderline_candidate"}:
            if not judgment.get("distinctness", False):
                issues.append(_issue("error", f"candidate_id={cid}", "distinctness=false인데 MRW 계열입니다.", "MIPVU distinctness 단계를 재판정하세요."))
            if not (judgment.get("similarity", False) or judgment.get("comparison_possible", False)):
                issues.append(_issue("error", f"candidate_id={cid}", "similarity=false인데 MRW 계열입니다.", "비교 가능성 단계를 재판정하세요."))

    for mapping in mappings if isinstance(mappings, list) else []:
        if not isinstance(mapping, dict):
            continue
        triples = []
        primary = mapping.get("primary_triple")
        if isinstance(primary, dict):
            triples.append(primary)
        supporting = mapping.get("supporting_triples", [])
        if isinstance(supporting, list):
            triples.extend([item for item in supporting if isinstance(item, dict)])
        for triple in triples:
            predicate = str(triple.get("predicate", ""))
            if predicate and predicate not in ALLOWED_PREDICATES:
                issues.append(_issue("error", str(triple.get("subject_id", "")), f"허용되지 않은 predicate: {predicate}", "ALLOWED_PREDICATES 중 하나로 바꾸세요."))
                errors.append(f"[validation_check] 허용되지 않은 predicate 사용: {predicate}")

    prompt_dir = Path(__file__).resolve().parents[1] / "prompts"
    system_prompt = load_common_system_prompt(prompt_dir)
    user_prompt = load_prompt_text(prompt_dir, "validation_check.md")
    payload = {"mipvu_annotations": mipvu, "metaphor_annotations": metaphors, "rdf_mappings": mappings}
    if user_prompt:
        llm_output = call_structured_chain(
            system_prompt,
            f"{user_prompt}\n\n입력:\n{json.dumps(payload, ensure_ascii=False)}",
            ValidationOutput,
            errors,
            "validation_check",
        )
        if isinstance(llm_output, dict):
            for item in llm_output.get("issues", []):
                if isinstance(item, dict):
                    issues.append(item)

    repair_needed = any(issue.get("severity") == "error" for issue in issues)
    human_review_needed = any(issue.get("severity") == "warning" for issue in issues)
    result = {
        "is_valid": not repair_needed,
        "repair_needed": repair_needed,
        "human_review_needed": human_review_needed,
        "issues": issues,
    }
    return {"validation_results": [result], "human_review_items": human_review_items, "errors": errors}
