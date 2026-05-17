"""Prompt loading and LangChain helpers for the optional LangGraph workflow."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
import os
import re
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
    try:
        parsed = _call_openai_json(api_key=api_key, model_name=model_name, messages=messages, temperature=temperature)
    except Exception as exc:  # noqa: BLE001
        errors.append(f"[{stage}] OPENAI SDK 호출 실패: {exc}")

    if isinstance(parsed, dict):
        try:
            return output_model.model_validate(parsed).model_dump()
        except Exception as exc:  # noqa: BLE001
            errors.append(f"[{stage}] Pydantic 파싱 실패: {exc}")

    try:
        from langchain_openai import ChatOpenAI

        llm = ChatOpenAI(model=model_name, temperature=temperature, api_key=api_key)
        response = llm.invoke([SystemMessage(content=str(system_prompt)), HumanMessage(content=str(user_prompt))])
        content = response.content if hasattr(response, "content") else str(response)
        parsed = _extract_first_json(str(content))
        if isinstance(parsed, dict):
            return output_model.model_validate(parsed).model_dump()
        errors.append(f"[{stage}] JSON 파싱 실패 원문: {str(content)[:500]}")
    except Exception as exc:  # noqa: BLE001
        if parsed is None:
            errors.append(f"[{stage}] LLM 호출 실패: {exc}")

    return _safe_empty_for_model(output_model)
