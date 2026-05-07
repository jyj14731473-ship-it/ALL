"""Prompt loading and LangChain helpers for the optional LangGraph workflow."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from pydantic import BaseModel

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
    if name == "RdfMappingOutput":
        return {"rdf_mapping": None, "rdf_mappings": []}
    if name == "ValidationOutput":
        return {"is_valid": True, "issues": []}
    return {}


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

    try:
        from langchain_core.prompts import ChatPromptTemplate
        from langchain_openai import ChatOpenAI
    except Exception as exc:  # noqa: BLE001
        errors.append(f"[{stage}] LangChain 의존성을 불러오지 못했습니다: {exc}")
        return _safe_empty_for_model(output_model)

    model_name = os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
    temperature = float(os.getenv("OPENAI_TEMPERATURE", "0") or 0)
    llm = ChatOpenAI(model=model_name, temperature=temperature, api_key=api_key)
    prompt = ChatPromptTemplate.from_messages([("system", system_prompt), ("user", user_prompt)])

    try:
        chain = prompt | llm.with_structured_output(output_model)
        result = chain.invoke({})
        if isinstance(result, BaseModel):
            return result.model_dump()
        if isinstance(result, dict):
            return output_model.model_validate(result).model_dump()
    except Exception as exc:  # noqa: BLE001
        errors.append(f"[{stage}] structured output 실패: {exc}")

    try:
        chain = prompt | llm
        response = chain.invoke({})
        content = response.content if hasattr(response, "content") else str(response)
        parsed = _extract_first_json(str(content))
        if isinstance(parsed, dict):
            return output_model.model_validate(parsed).model_dump()
        errors.append(f"[{stage}] JSON 파싱 실패 원문: {str(content)[:500]}")
    except Exception as exc:  # noqa: BLE001
        errors.append(f"[{stage}] LLM 호출 실패: {exc}")

    return _safe_empty_for_model(output_model)
