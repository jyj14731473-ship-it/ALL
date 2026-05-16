"""Prompt loading and LangChain helpers for the optional LangGraph workflow."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import os
import re
import time
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional at runtime
    def load_dotenv(*_args: object, **_kwargs: object) -> bool:
        return False
from pydantic import BaseModel

from langchain_core.messages import HumanMessage, SystemMessage

load_dotenv()


def load_prompt_text(prompt_dir: Path, filename: str) -> str:
    path = prompt_dir / filename
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def load_common_system_prompt(prompt_dir: Path) -> str:
    parts = [
        load_prompt_text(prompt_dir, "system_role.md"),
        load_prompt_text(prompt_dir, "korean_legal_mipvu_guideline.md"),
        load_prompt_text(prompt_dir, "annotation_schema.md"),
    ]
    return "\n\n".join(part for part in parts if part.strip())


def _extract_first_json(text: str) -> dict[str, Any] | list[Any] | None:
    try:
        return json.loads(text)
    except Exception:
        pass
    match = re.search(r"\{[\s\S]*\}", text or "")
    if not match:
        return None
    try:
        return json.loads(match.group(0))
    except Exception:
        return None


def _safe_empty_for_model(output_model: type[BaseModel]) -> dict[str, Any]:
    name = output_model.__name__
    if name == "CandidateExtractionOutput":
        return {"candidates": []}
    if name == "MipvuJudgmentOutput":
        return {"judgments": []}
    if name == "MetaphorClassificationOutput":
        return {"metaphors": []}
    if name == "ValidationOutput":
        return {"is_valid": True, "issues": []}
    return {}


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return max(0.0, min(1.0, float(value)))
    except (TypeError, ValueError):
        return default


def _safe_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"true", "1", "yes", "y"}
    return bool(value)


def _normalize_mipvu_label(value: Any) -> str:
    raw = str(value or "uncertain").strip()
    lookup = {
        "MRW": "MRW",
        "mrw": "MRW",
        "MRW_candidate": "MRW_candidate",
        "mrw_candidate": "MRW_candidate",
        "borderline": "borderline_candidate",
        "borderline_candidate": "borderline_candidate",
        "non-MRW": "non_MRW",
        "non_mrw": "non_MRW",
        "non_MRW": "non_MRW",
        "not_mrw": "non_MRW",
        "not-MRW": "non_MRW",
        "not_MRW": "non_MRW",
        "literal": "non_MRW",
        "uncertain": "uncertain",
        "": "uncertain",
    }
    return lookup.get(raw, "uncertain")


def _normalize_basic_meaning_source(value: Any) -> str:
    raw = str(value or "unavailable").strip().lower()
    if raw in {"stdict", "standard_korean_dictionary", "표준국어대사전"}:
        return "stdict"
    if raw in {"inferred", "llm", "model", "general_lexical_knowledge", "general knowledge", "추론"}:
        return "inferred"
    return "unavailable"


def _normalize_metaphor_type(value: Any) -> str:
    raw = str(value or "uncertain").strip().lower()
    if raw in {"structural", "ontological", "orientational"}:
        return raw
    return "uncertain"


def _normalize_opinion_type(value: Any) -> str:
    raw = str(value or "unknown").strip().lower()
    if raw in {"majority", "dissenting", "concurring", "unknown"}:
        return raw
    return "unknown"


def _normalize_structured_output(
    parsed: dict[str, Any] | list[Any] | None,
    output_model: type[BaseModel],
) -> dict[str, Any] | list[Any] | None:
    if not isinstance(parsed, dict):
        return parsed
    name = output_model.__name__
    normalized = dict(parsed)
    if name == "MipvuJudgmentOutput":
        judgments = normalized.get("judgments", [])
        if isinstance(judgments, list):
            cleaned = []
            for item in judgments:
                if not isinstance(item, dict):
                    continue
                judgment = dict(item)
                judgment["mipvu_label"] = _normalize_mipvu_label(judgment.get("mipvu_label"))
                judgment["basic_meaning_source"] = _normalize_basic_meaning_source(
                    judgment.get("basic_meaning_source")
                )
                judgment["confidence"] = _safe_float(judgment.get("confidence", 0.0))
                judgment["needs_human_review"] = _safe_bool(judgment.get("needs_human_review", False))
                cleaned.append(judgment)
            normalized["judgments"] = cleaned
    elif name == "MetaphorClassificationOutput":
        metaphors = normalized.get("metaphors", [])
        if isinstance(metaphors, list):
            cleaned = []
            for item in metaphors:
                if not isinstance(item, dict):
                    continue
                metaphor = dict(item)
                metaphor["metaphor_type"] = _normalize_metaphor_type(metaphor.get("metaphor_type"))
                metaphor["opinion_type"] = _normalize_opinion_type(metaphor.get("opinion_type"))
                metaphor["confidence"] = _safe_float(metaphor.get("confidence", 0.0))
                metaphor["needs_human_review"] = _safe_bool(metaphor.get("needs_human_review", False))
                cleaned.append(metaphor)
            normalized["metaphors"] = cleaned
    return normalized


def _validate_output_model(
    parsed: dict[str, Any] | list[Any] | None,
    output_model: type[BaseModel],
    errors: list[str],
    stage: str,
) -> dict[str, Any] | None:
    normalized = _normalize_structured_output(parsed, output_model)
    if not isinstance(normalized, dict):
        return None
    try:
        return output_model.model_validate(normalized).model_dump()
    except Exception as exc:  # noqa: BLE001
        errors.append(f"[{stage}] Pydantic 파싱 실패: {exc}")
        return None


def _read_retry_count() -> int:
    raw = os.getenv("OPENAI_MAX_RETRIES", "2").strip()
    try:
        return max(1, int(raw))
    except ValueError:
        return 2


def _call_openai_json(
    api_key: str,
    model_name: str,
    messages: list[dict[str, str]],
    temperature: float,
) -> dict[str, Any] | list[Any] | None:
    """Call OpenAI chat completions endpoint with explicit UTF-8 JSON serialization."""
    payload = {
        "model": model_name,
        "messages": messages,
        "temperature": temperature,
        "response_format": {"type": "json_object"},
    }
    request_payload = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(
        "https://api.openai.com/v1/chat/completions",
        data=request_payload,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Authorization": f"Bearer {api_key}",
        },
    )
    with urllib.request.urlopen(request, timeout=120) as response:
        raw = response.read().decode("utf-8")
    body = json.loads(raw)
    choice = body.get("choices", [{}])[0]
    message = choice.get("message", {})
    content = message.get("content", "")
    return _extract_first_json(str(content))


def call_structured_chain(
    system_prompt: str,
    user_prompt: str,
    output_model: type[BaseModel],
    errors: list[str],
    stage: str,
) -> dict[str, Any]:
    """Call an LLM through LangChain and return a Pydantic-validated dict."""
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        errors.append(f"[{stage}] OPENAI_API_KEY가 없어 LLM 호출을 생략했습니다.")
        return _safe_empty_for_model(output_model)

    model_name = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    temperature = float(os.getenv("OPENAI_TEMPERATURE", "0") or 0)
    messages: list[dict[str, str]] = [
        {"role": "system", "content": str(system_prompt)},
        {"role": "user", "content": str(user_prompt)},
    ]
    parsed = None
    retry_count = _read_retry_count()
    for attempt in range(1, retry_count + 1):
        try:
            parsed = _call_openai_json(api_key=api_key, model_name=model_name, messages=messages, temperature=temperature)
            validated = _validate_output_model(parsed, output_model, errors, stage)
            if validated is not None:
                return validated
        except Exception as exc:  # noqa: BLE001
            errors.append(f"[{stage}] OPENAI SDK 호출 실패 attempt={attempt}/{retry_count}: {exc}")
        if attempt < retry_count:
            time.sleep(2 ** (attempt - 1))

    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(model=model_name, temperature=temperature, api_key=api_key)
        response = llm.invoke([SystemMessage(content=str(system_prompt)), HumanMessage(content=str(user_prompt))])
        content = response.content if hasattr(response, "content") else str(response)
        parsed = _extract_first_json(str(content))
        validated = _validate_output_model(parsed, output_model, errors, stage)
        if validated is not None:
            return validated
        errors.append(f"[{stage}] JSON 파싱 실패 원문: {str(content)[:500]}")
    except Exception as exc:  # noqa: BLE001
        if parsed is None:
            errors.append(f"[{stage}] LLM 호출 실패: {exc}")

    return _safe_empty_for_model(output_model)
