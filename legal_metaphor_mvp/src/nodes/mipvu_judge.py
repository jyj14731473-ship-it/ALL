"""Lemma-level MIPVU-informed original meaning judgment node."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from prompt_utils import call_structured_chain, load_prompt_text
from schemas.annotation import AnnotationState
from utils import read_json

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CONTEXTUAL_JSON_PATH = PROJECT_ROOT / "data" / "output" / "pos_nodes_contextualized.json"
DEFAULT_DICTIONARY_LOOKUP_PATH = PROJECT_ROOT / "data" / "output" / "lemma_dictionary_lookup.json"
LEMMA_MIPVU_BATCH_SIZE = 25
ALLOWED_LABELS = {"MRW", "MRW_candidate", "borderline_candidate", "non_MRW", "uncertain"}
ALLOWED_LAKOFF_JOHNSON_TYPES = {"structural", "orientational", "ontological", "not_applicable", "uncertain"}
OUTPUT_KEYS = [
    "lemma_group_id",
    "lemma",
    "contextual_meaning",
    "selected_sup_no",
    "original_meaning",
    "original_meaning_selection_reason",
    "meaning_contrast",
    "distinctness",
    "comparison_possible",
    "similarity",
    "target_domain",
    "source_domain",
    "conceptual_metaphor",
    "concept_mapping_reason",
    "lakoff_johnson_type",
    "lakoff_johnson_type_reason",
    "mipvu_label",
    "judgment_reason",
    "confidence",
    "needs_human_review",
    "occurrence_count",
    "sample_sentences",
]


class LemmaMipvuJudgment(BaseModel):
    """Lenient LLM output schema; final normalization enforces our contract."""

    lemma_group_id: str = ""
    lemma: str = ""
    contextual_meaning: str = ""
    selected_sup_no: str = ""
    original_meaning: str = ""
    original_meaning_selection_reason: str = ""
    meaning_contrast: str = ""
    distinctness: bool = False
    comparison_possible: bool = False
    similarity: bool = False
    target_domain: str = ""
    source_domain: str = ""
    conceptual_metaphor: str = ""
    concept_mapping_reason: str = ""
    lakoff_johnson_type: str = "uncertain"
    lakoff_johnson_type_reason: str = ""
    mipvu_label: str = "uncertain"
    judgment_reason: str = ""
    confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    needs_human_review: bool = False
    occurrence_count: int = 0
    sample_sentences: list[str] = Field(default_factory=list)


class LemmaMipvuJudgmentOutput(BaseModel):
    judgments: list[LemmaMipvuJudgment] = Field(default_factory=list)


def _load_lemma_system_prompt(prompt_dir: Path) -> str:
    parts = [
        load_prompt_text(prompt_dir, "system_role.md"),
        load_prompt_text(prompt_dir, "korean_legal_mipvu_guideline.md"),
    ]
    return "\n\n".join(part for part in parts if part.strip())


def _normalize_label(value: Any) -> str:
    raw = str(value or "uncertain").strip()
    lookup = {
        "MRW": "MRW",
        "mrw": "MRW",
        "MRW_candidate": "MRW_candidate",
        "mrw_candidate": "MRW_candidate",
        "borderline_candidate": "borderline_candidate",
        "borderline": "borderline_candidate",
        "non-MRW": "non_MRW",
        "non_MRW": "non_MRW",
        "non_mrw": "non_MRW",
        "not_mrw": "non_MRW",
        "not-MRW": "non_MRW",
        "not_MRW": "non_MRW",
        "uncertain": "uncertain",
        "": "uncertain",
    }
    return lookup.get(raw, "uncertain")


def _normalize_lakoff_johnson_type(value: Any) -> str:
    raw = str(value or "uncertain").strip()
    key = raw.lower().replace("-", "_").replace(" ", "_")
    lookup = {
        "structural": "structural",
        "structural_metaphor": "structural",
        "orientational": "orientational",
        "orientation": "orientational",
        "orientational_metaphor": "orientational",
        "ontological": "ontological",
        "ontological_metaphor": "ontological",
        "container": "ontological",
        "container_metaphor": "ontological",
        "entity": "ontological",
        "entity_metaphor": "ontological",
        "entity_substance": "ontological",
        "entity_substance_metaphor": "ontological",
        "personification": "ontological",
        "personification_metaphor": "ontological",
        "not_applicable": "not_applicable",
        "non_metaphorical": "not_applicable",
        "non_mrw": "not_applicable",
        "not_mrw": "not_applicable",
        "n/a": "not_applicable",
        "none": "not_applicable",
        "uncertain": "uncertain",
        "unknown": "uncertain",
        "": "uncertain",
    }
    return lookup.get(key, "uncertain")


def _safe_float(value: Any) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return 0.0


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _unique_nonempty_strings(values: list[Any]) -> list[str]:
    seen: set[str] = set()
    output: list[str] = []
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        output.append(text)
        seen.add(text)
    return output


def _normalize_definitions(value: Any) -> list[dict[str, str]]:
    definitions: list[dict[str, str]] = []
    if not isinstance(value, list):
        return definitions
    for item in value:
        if not isinstance(item, dict):
            continue
        definition = str(item.get("definition", "")).strip()
        if not definition:
            continue
        definitions.append(
            {
                "sup_no": str(item.get("sup_no", "")).strip(),
                "definition": definition,
            }
        )
    return definitions


def _definitions_by_sup_no(definitions: list[dict[str, str]]) -> dict[str, str]:
    return {str(item.get("sup_no", "")): str(item.get("definition", "")) for item in definitions}


def _contextual_groups(payload: dict[str, Any]) -> list[dict[str, Any]]:
    groups = payload.get("lemma_groups", [])
    if not isinstance(groups, list):
        return []
    return [group for group in groups if isinstance(group, dict)]


def _dictionary_lookup_by_group_id(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    results = payload.get("lemma_dictionary_results", [])
    if not isinstance(results, list):
        return {}
    return {
        str(item.get("lemma_group_id", "")).strip(): item
        for item in results
        if isinstance(item, dict) and str(item.get("lemma_group_id", "")).strip()
    }


def build_lemma_mipvu_inputs(
    contextual_payload: dict[str, Any],
    dictionary_payload: dict[str, Any],
) -> list[dict[str, Any]]:
    """Build lemma-level LLM inputs from contextual and dictionary outputs.

    POS is intentionally ignored throughout this function.
    """
    dictionary_by_id = _dictionary_lookup_by_group_id(dictionary_payload)
    records: list[dict[str, Any]] = []

    for group in _contextual_groups(contextual_payload):
        group_id = str(group.get("lemma_group_id", "")).strip()
        lemma = str(group.get("lemma", "")).strip()
        if not group_id or not lemma:
            continue

        occurrences = group.get("occurrences", [])
        occurrence_items = [item for item in occurrences if isinstance(item, dict)] if isinstance(occurrences, list) else []
        sample_sentences = _unique_nonempty_strings([item.get("sentence", "") for item in occurrence_items])
        lookup = dictionary_by_id.get(group_id, {})
        definitions = _normalize_definitions(lookup.get("definitions", []))
        records.append(
            {
                "lemma_group_id": group_id,
                "lemma": lemma,
                "contextual_meaning": str(group.get("contextual_meaning", "")).strip(),
                "sample_sentences": sample_sentences,
                "occurrence_count": len(occurrence_items),
                "definitions": definitions,
                "dictionary_status": str(lookup.get("status", "missing_lookup")),
                "exists_in_dictionary": bool(lookup.get("exists_in_dictionary", False)),
            }
        )
    return records


def batch_lemma_inputs(items: list[dict[str, Any]], batch_size: int = LEMMA_MIPVU_BATCH_SIZE) -> list[list[dict[str, Any]]]:
    if batch_size <= 0:
        return [items]
    return [items[idx : idx + batch_size] for idx in range(0, len(items), batch_size)]


def _fallback_judgment(source: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        "lemma_group_id": str(source.get("lemma_group_id", "")),
        "lemma": str(source.get("lemma", "")),
        "contextual_meaning": str(source.get("contextual_meaning", "")),
        "selected_sup_no": "",
        "original_meaning": "",
        "original_meaning_selection_reason": reason,
        "meaning_contrast": "original meaning을 안정적으로 선택할 수 없어 문맥 의미와 비교하지 않았습니다.",
        "distinctness": False,
        "comparison_possible": False,
        "similarity": False,
        "target_domain": "",
        "source_domain": "",
        "conceptual_metaphor": "",
        "concept_mapping_reason": "",
        "lakoff_johnson_type": "uncertain",
        "lakoff_johnson_type_reason": "",
        "mipvu_label": "uncertain",
        "judgment_reason": reason,
        "confidence": 0.0,
        "needs_human_review": True,
        "occurrence_count": int(source.get("occurrence_count", 0) or 0),
        "sample_sentences": list(source.get("sample_sentences", [])),
    }


def normalize_lemma_judgment(raw: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
    """Normalize one raw LLM judgment to the lemma-level output contract."""
    definitions = list(source.get("definitions", []))
    definition_by_sup_no = _definitions_by_sup_no(definitions)
    selected_sup_no = str(raw.get("selected_sup_no", "")).strip()
    original_meaning = str(raw.get("original_meaning", "")).strip()
    if selected_sup_no in definition_by_sup_no:
        original_meaning = definition_by_sup_no[selected_sup_no]

    label = _normalize_label(raw.get("mipvu_label"))
    lakoff_johnson_type = _normalize_lakoff_johnson_type(raw.get("lakoff_johnson_type"))
    confidence = _safe_float(raw.get("confidence", 0.0))
    comparison_possible = _safe_bool(raw.get("comparison_possible", False)) and bool(original_meaning)

    normalized = {
        "lemma_group_id": str(source.get("lemma_group_id", raw.get("lemma_group_id", ""))),
        "lemma": str(source.get("lemma", raw.get("lemma", ""))),
        "contextual_meaning": str(source.get("contextual_meaning", raw.get("contextual_meaning", ""))),
        "selected_sup_no": selected_sup_no,
        "original_meaning": original_meaning,
        "original_meaning_selection_reason": str(raw.get("original_meaning_selection_reason", "")).strip(),
        "meaning_contrast": str(raw.get("meaning_contrast", "")).strip(),
        "distinctness": _safe_bool(raw.get("distinctness", False)),
        "comparison_possible": comparison_possible,
        "similarity": _safe_bool(raw.get("similarity", False)) if comparison_possible else False,
        "target_domain": str(raw.get("target_domain", "")).strip(),
        "source_domain": str(raw.get("source_domain", "")).strip(),
        "conceptual_metaphor": str(raw.get("conceptual_metaphor", "")).strip(),
        "concept_mapping_reason": str(raw.get("concept_mapping_reason", "")).strip(),
        "lakoff_johnson_type": lakoff_johnson_type,
        "lakoff_johnson_type_reason": str(raw.get("lakoff_johnson_type_reason", "")).strip(),
        "mipvu_label": label,
        "judgment_reason": str(raw.get("judgment_reason", "")).strip(),
        "confidence": confidence,
        "needs_human_review": _safe_bool(raw.get("needs_human_review", False)),
        "occurrence_count": int(source.get("occurrence_count", raw.get("occurrence_count", 0)) or 0),
        "sample_sentences": list(source.get("sample_sentences", raw.get("sample_sentences", []))),
    }
    if not normalized["original_meaning"] or label == "uncertain" or confidence < 0.5:
        normalized["needs_human_review"] = True
    if label not in ALLOWED_LABELS:
        normalized["mipvu_label"] = "uncertain"
        normalized["needs_human_review"] = True
    if normalized["lakoff_johnson_type"] not in ALLOWED_LAKOFF_JOHNSON_TYPES:
        normalized["lakoff_johnson_type"] = "uncertain"
        normalized["needs_human_review"] = True
    if normalized["mipvu_label"] in {"non_MRW", "uncertain"}:
        normalized["target_domain"] = ""
        normalized["source_domain"] = ""
        normalized["conceptual_metaphor"] = ""
        normalized["concept_mapping_reason"] = ""
        normalized["lakoff_johnson_type"] = "not_applicable" if normalized["mipvu_label"] == "non_MRW" else "uncertain"
        normalized["lakoff_johnson_type_reason"] = ""
    elif not normalized["target_domain"] or not normalized["source_domain"] or not normalized["conceptual_metaphor"]:
        normalized["needs_human_review"] = True
    if normalized["mipvu_label"] in {"MRW", "MRW_candidate", "borderline_candidate"}:
        if normalized["lakoff_johnson_type"] in {"not_applicable", "uncertain"}:
            normalized["lakoff_johnson_type"] = "uncertain"
            normalized["needs_human_review"] = True
        elif not normalized["lakoff_johnson_type_reason"]:
            normalized["needs_human_review"] = True
    return {key: normalized[key] for key in OUTPUT_KEYS}


def _call_lemma_mipvu_batch(
    batch: list[dict[str, Any]],
    *,
    prompt_dir: Path,
    errors: list[str],
    stage: str,
) -> list[dict[str, Any]]:
    prompt_template = load_prompt_text(prompt_dir, "lemma_mipvu_judge.md")
    if not prompt_template:
        errors.append(f"[{stage}] lemma_mipvu_judge.md 프롬프트를 찾을 수 없습니다.")
        return []

    payload = {
        "lemma_count": len(batch),
        "lemma_items": [
            {
                "lemma_group_id": item["lemma_group_id"],
                "lemma": item["lemma"],
                "contextual_meaning": item["contextual_meaning"],
                "sample_sentences": item["sample_sentences"],
                "definitions": item["definitions"],
            }
            for item in batch
        ],
    }
    user_prompt = prompt_template.replace("{{LEMMA_BATCH_JSON}}", json.dumps(payload, ensure_ascii=False, indent=2))
    parsed = call_structured_chain(
        _load_lemma_system_prompt(prompt_dir),
        user_prompt,
        LemmaMipvuJudgmentOutput,
        errors,
        stage,
    )
    judgments = parsed.get("judgments", []) if isinstance(parsed, dict) else []
    return [item for item in judgments if isinstance(item, dict)]


def _load_node_inputs(errors: list[str]) -> list[dict[str, Any]]:
    contextual_payload = read_json(DEFAULT_CONTEXTUAL_JSON_PATH, default={})
    dictionary_payload = read_json(DEFAULT_DICTIONARY_LOOKUP_PATH, default={})
    if not isinstance(contextual_payload, dict):
        errors.append(f"[mipvu_judge] contextual JSON을 읽을 수 없습니다: {DEFAULT_CONTEXTUAL_JSON_PATH}")
        contextual_payload = {}
    if not isinstance(dictionary_payload, dict):
        errors.append(f"[mipvu_judge] dictionary lookup JSON을 읽을 수 없습니다: {DEFAULT_DICTIONARY_LOOKUP_PATH}")
        dictionary_payload = {}
    return build_lemma_mipvu_inputs(contextual_payload, dictionary_payload)


def mipvu_judge_node(state: AnnotationState) -> dict[str, Any]:
    errors = list(state.get("errors", []))
    lemma_inputs = _load_node_inputs(errors)
    if not lemma_inputs:
        errors.append("[mipvu_judge] 판정할 lemma group이 없습니다.")
        return {"mipvu_annotations": [], "errors": errors}

    prompt_dir = Path(__file__).resolve().parents[1] / "prompts"
    llm_inputs = [item for item in lemma_inputs if item.get("definitions")]
    raw_by_group_id: dict[str, dict[str, Any]] = {}

    for batch_idx, batch in enumerate(batch_lemma_inputs(llm_inputs), start=1):
        raw_judgments = _call_lemma_mipvu_batch(
            batch,
            prompt_dir=prompt_dir,
            errors=errors,
            stage=f"lemma_mipvu_judge_batch{batch_idx}",
        )
        for raw in raw_judgments:
            group_id = str(raw.get("lemma_group_id", "")).strip()
            if group_id:
                raw_by_group_id[group_id] = raw

    annotations: list[dict[str, Any]] = []
    for item in lemma_inputs:
        group_id = str(item.get("lemma_group_id", ""))
        if not item.get("definitions"):
            annotations.append(_fallback_judgment(item, "사전 뜻 후보가 없어 original meaning을 선택할 수 없습니다."))
            continue
        raw = raw_by_group_id.get(group_id)
        if raw is None:
            annotations.append(_fallback_judgment(item, "LLM 판정 결과가 누락되어 MIPVU 판단을 보류합니다."))
            continue
        annotations.append(normalize_lemma_judgment(raw, item))

    metadata = dict(state.get("metadata", {}))
    metadata.update(
        {
            "mipvu_unit": "lemma_group",
            "mipvu_batch_size": LEMMA_MIPVU_BATCH_SIZE,
            "dictionary_lookup_path": str(DEFAULT_DICTIONARY_LOOKUP_PATH),
            "contextual_json_path": str(DEFAULT_CONTEXTUAL_JSON_PATH),
            "lemma_group_count": len(lemma_inputs),
            "lemma_groups_with_dictionary_definitions": len(llm_inputs),
        }
    )
    return {"mipvu_annotations": annotations, "errors": errors, "metadata": metadata}
