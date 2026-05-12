"""Validation node with rule checks."""

from __future__ import annotations

from typing import Any

from schemas.annotation import ALLOWED_PREDICATES, AnnotationState


def _issue(severity: str, location: str, message: str, suggested_fix: str) -> dict[str, str]:
    return {
        "severity": severity,
        "location": location,
        "message": message,
        "suggested_fix": suggested_fix,
    }


def _add_review_item(
    human_review_items: list[dict[str, Any]],
    *,
    reason: str,
    severity: str,
    lemma_group_id: str = "",
    lemma: str = "",
) -> None:
    item = {
        "reason": reason,
        "severity": severity,
        "lemma_group_id": lemma_group_id,
        "lemma": lemma,
    }
    if item not in human_review_items:
        human_review_items.append(item)


def validation_check_node(state: AnnotationState) -> dict[str, Any]:
    errors = list(state.get("errors", []))
    mipvu = state.get("mipvu_annotations", [])
    mappings = state.get("rdf_mappings", [])
    issues: list[dict[str, str]] = []
    human_review_items: list[dict[str, Any]] = list(state.get("human_review_items", []))

    for judgment in mipvu if isinstance(mipvu, list) else []:
        if not isinstance(judgment, dict):
            continue
        lemma_group_id = str(judgment.get("lemma_group_id", ""))
        lemma = str(judgment.get("lemma", ""))
        location = f"lemma_group_id={lemma_group_id or lemma}"
        confidence = judgment.get("confidence", 0.0)
        confidence = confidence if isinstance(confidence, (int, float)) else 0.0
        if confidence < 0.5:
            _add_review_item(
                human_review_items,
                reason="MIPVU confidence < 0.5",
                severity="warning",
                lemma_group_id=lemma_group_id,
                lemma=lemma,
            )
        if str(judgment.get("mipvu_label", "")) == "borderline_candidate":
            _add_review_item(
                human_review_items,
                reason="mipvu_label == borderline_candidate",
                severity="warning",
                lemma_group_id=lemma_group_id,
                lemma=lemma,
            )
        if bool(judgment.get("similarity")) and not bool(judgment.get("comparison_possible")):
            _add_review_item(
                human_review_items,
                reason="comparison_possible/similarity 판단 모순",
                severity="error",
                lemma_group_id=lemma_group_id,
                lemma=lemma,
            )
        if str(judgment.get("mipvu_label", "")) in {"MRW", "MRW_candidate", "borderline_candidate"}:
            if not judgment.get("distinctness", False):
                issues.append(_issue("error", location, "distinctness=false인데 MRW 계열입니다.", "MIPVU distinctness 단계를 재판정하세요."))
                _add_review_item(
                    human_review_items,
                    reason="distinctness 판단 모순",
                    severity="error",
                    lemma_group_id=lemma_group_id,
                    lemma=lemma,
                )
            if not bool(judgment.get("similarity", False)):
                issues.append(_issue("error", location, "similarity=false인데 MRW 계열입니다.", "basic/contextual meaning 유사성 단계를 재판정하세요."))
                _add_review_item(
                    human_review_items,
                    reason="similarity 판단 모순",
                    severity="error",
                    lemma_group_id=lemma_group_id,
                    lemma=lemma,
                )
            if not all(str(judgment.get(key, "")).strip() for key in ("source_domain", "target_domain", "conceptual_metaphor")):
                issues.append(_issue("error", location, "MRW 계열인데 KG domain/conceptual metaphor 필드가 비어 있습니다.", "lemma_mipvu_judge 결과를 재검토하세요."))
                _add_review_item(
                    human_review_items,
                    reason="KG domain/conceptual metaphor 누락",
                    severity="error",
                    lemma_group_id=lemma_group_id,
                    lemma=lemma,
                )

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

    repair_needed = any(issue.get("severity") == "error" for issue in issues)
    human_review_needed = any(issue.get("severity") == "warning" for issue in issues)
    status = "needs_repair" if repair_needed else "completed"
    metadata = dict(state.get("metadata", {}))
    metadata["validation_status"] = status if repair_needed else "ok"
    result = {
        "is_valid": not repair_needed,
        "repair_needed": repair_needed,
        "human_review_needed": human_review_needed,
        "issues": issues,
    }
    return {
        "validation_results": [result],
        "human_review_items": human_review_items,
        "errors": errors,
        "status": status,
        "metadata": metadata,
    }
