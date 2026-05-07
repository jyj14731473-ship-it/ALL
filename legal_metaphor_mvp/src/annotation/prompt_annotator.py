"""Prompt-based annotation backend for the MVP."""

from __future__ import annotations

import json
import os
from json import JSONDecodeError
from pathlib import Path
from typing import Any

from annotation.base import BaseAnnotator
from annotation.dictionary_client import StandardKoreanDictionaryClient

try:
    from openai import OpenAI
except ImportError:  # pragma: no cover - handled at runtime with safe fallback.
    OpenAI = None  # type: ignore[assignment]


class PromptAnnotator(BaseAnnotator):
    """Prompt-based annotator with explicit MIPVU-informed stages.

    Pipelines:
    - simple: compact one-step annotation for quick MVP use
    - staged: candidate extraction -> dictionary lookup -> MIPVU judgment -> classification
    """

    def __init__(self, prompt_dir: Path | None = None, model: str | None = None) -> None:
        project_root = Path(__file__).resolve().parents[2]
        self.prompt_dir = prompt_dir or (project_root / "prompts")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4.1-mini")
        self.dictionary_client = StandardKoreanDictionaryClient()
        self._warned_no_llm = False
        self.client = self._build_openai_client()
        self.prompt_files = {
            "system_role": "00_system_role.txt",
            "candidate_extract": "01_candidate_extract.txt",
            "mipvu_judge": "02_mipvu_judge.txt",
            "metaphor_classify": "03_metaphor_classify.txt",
            "annotation_schema": "04_annotation_schema.txt",
            "mipvu_guidelines": "05_korean_legal_mipvu_guidelines.txt",
            "validation_check": "06_validation_check.txt",
        }

    def _build_openai_client(self) -> Any | None:
        api_key = os.getenv("OPENAI_API_KEY", "").strip()
        if not api_key or OpenAI is None:
            return None
        return OpenAI(api_key=api_key)

    def load_prompt(self, name: str) -> str:
        """Load one prompt file by logical name."""
        file_name = self.prompt_files.get(name)
        if not file_name:
            return ""
        path = self.prompt_dir / file_name
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    @staticmethod
    def build_prompt(system_role: str, task_prompt: str, input_text: str) -> str:
        """Build a single user prompt while keeping system role visible."""
        return f"{system_role.strip()}\n\n{task_prompt.strip()}\n\n{input_text.strip()}\n"

    @staticmethod
    def _safe_empty_for_stage(stage: str) -> dict[str, Any]:
        if stage == "candidate_extract":
            return {"candidates": []}
        if stage == "mipvu_judge":
            return {"judgments": []}
        return {"metaphors": []}

    @staticmethod
    def _extract_first_json_object(raw_text: str) -> dict[str, Any] | None:
        """Parse full JSON first, then scan for the first valid JSON object."""
        text = (raw_text or "").strip()
        if not text:
            return None
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else None
        except JSONDecodeError:
            pass

        decoder = json.JSONDecoder()
        for idx, char in enumerate(text):
            if char != "{":
                continue
            try:
                parsed, _ = decoder.raw_decode(text[idx:])
            except JSONDecodeError:
                continue
            if isinstance(parsed, dict):
                return parsed
        return None

    def _llm_json_call(self, stage: str, prompt: str) -> dict[str, Any]:
        """Call OpenAI and return parsed JSON with safe fallbacks."""
        if self.client is None:
            if not self._warned_no_llm:
                print("[prompt_annotator] WARNING: OPENAI_API_KEY/openai package unavailable. Returning empty annotations.")
                self._warned_no_llm = True
            return self._safe_empty_for_stage(stage)

        messages = [
            {"role": "system", "content": "Return only valid JSON. No markdown, no prose."},
            {"role": "user", "content": prompt},
        ]
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0,
                response_format={"type": "json_object"},
            )
        except TypeError:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                temperature=0,
            )
        except Exception as exc:  # noqa: BLE001
            print(f"[prompt_annotator] WARNING: LLM call failed at {stage}: {exc}")
            return self._safe_empty_for_stage(stage)

        raw = response.choices[0].message.content if response.choices else ""
        parsed = self._extract_first_json_object(raw or "")
        if parsed is None:
            print(f"[prompt_annotator] WARNING: invalid JSON from LLM at {stage}.")
            return self._safe_empty_for_stage(stage)
        return parsed

    @staticmethod
    def _as_list(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return [item for item in value if isinstance(item, dict)]
        return []

    @staticmethod
    def _safe_string(value: Any) -> str:
        return value.strip() if isinstance(value, str) else ""

    def _parse_candidate_extract_response(self, response: dict[str, Any]) -> dict[str, Any]:
        candidates = self._as_list(response.get("candidates"))
        for idx, candidate in enumerate(candidates, start=1):
            candidate.setdefault("candidate_id", f"C{idx:03d}")
            candidate.setdefault("morpheme_or_pos_tags", [])
            candidate.setdefault("is_exception_candidate", False)
            candidate.setdefault("exception_reason", "")
        return {"candidates": candidates}

    def _parse_mipvu_judge_response(self, response: dict[str, Any]) -> dict[str, Any]:
        judgments = self._as_list(response.get("judgments"))
        for judgment in judgments:
            judgment.setdefault("basic_meaning_source", "unavailable")
            judgment.setdefault("confidence", 0.0)
        return {"judgments": judgments}

    def _parse_metaphor_classify_response(self, response: dict[str, Any]) -> dict[str, Any]:
        metaphors = self._as_list(response.get("metaphors"))
        return {"metaphors": metaphors}

    def _compare_with_dictionary(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Attach 표준국어대사전 basic meaning lookup to each candidate."""
        enriched: list[dict[str, Any]] = []
        for candidate in candidates:
            surface = self._safe_string(candidate.get("surface_expression"))
            lemma = self._safe_string(candidate.get("lemma")) or surface
            pos_tag = self._safe_string(candidate.get("primary_pos"))
            dictionary = self.dictionary_client.lookup_basic_meaning(term=lemma, pos=pos_tag or None)

            updated = dict(candidate)
            updated["dictionary_lookup"] = dictionary
            updated["basic_meaning_from_dict"] = self._safe_string(dictionary.get("definition"))
            updated["basic_meaning_source"] = "stdict" if dictionary.get("status") == "ok" else "unavailable"
            enriched.append(updated)
        return enriched

    def _stage_candidate_extract(self, text: str) -> dict[str, Any]:
        system_role = self.load_prompt("system_role")
        guidelines = self.load_prompt("mipvu_guidelines")
        task = self.load_prompt("candidate_extract").replace("{{INPUT_TEXT}}", text)
        prompt = self.build_prompt(system_role, f"{guidelines}\n\n{task}", text)
        return self._parse_candidate_extract_response(self._llm_json_call("candidate_extract", prompt))

    def _stage_mipvu_judge(self, enriched_candidates: list[dict[str, Any]]) -> dict[str, Any]:
        system_role = self.load_prompt("system_role")
        guidelines = self.load_prompt("mipvu_guidelines")
        payload = json.dumps({"candidates": enriched_candidates}, ensure_ascii=False)
        task = self.load_prompt("mipvu_judge").replace("{{CANDIDATES_JSON}}", payload)
        prompt = self.build_prompt(system_role, f"{guidelines}\n\n{task}", payload)
        return self._parse_mipvu_judge_response(self._llm_json_call("mipvu_judge", prompt))

    def _stage_metaphor_classify(
        self,
        text: str,
        candidates: list[dict[str, Any]],
        judgments: list[dict[str, Any]],
        pipeline: str,
    ) -> dict[str, Any]:
        system_role = self.load_prompt("system_role")
        guidelines = self.load_prompt("mipvu_guidelines")
        schema_ref = self.load_prompt("annotation_schema")
        stage_input = {
            "pipeline": pipeline,
            "input_text": text,
            "schema_reference": schema_ref,
            "candidates": candidates,
            "judgments": judgments,
        }
        payload = json.dumps(stage_input, ensure_ascii=False)
        task = self.load_prompt("metaphor_classify").replace("{{PIPELINE_INPUT}}", payload)
        prompt = self.build_prompt(system_role, f"{guidelines}\n\n{task}", payload)
        return self._parse_metaphor_classify_response(self._llm_json_call("metaphor_classify", prompt))

    def run_pipeline(self, text: str, pipeline: str = "simple") -> dict[str, Any]:
        """Run annotation and keep defensible intermediate artifacts."""
        normalized_text = text.strip()
        metadata = {
            "annotator": "prompt",
            "pipeline": pipeline,
            "model": self.model,
            "dictionary_available": self.dictionary_client.is_available(),
        }
        if not normalized_text:
            return {"metaphors": [], "metadata": metadata, "stage_outputs": {}}

        if pipeline == "simple":
            classified = self._stage_metaphor_classify(normalized_text, [], [], pipeline="simple")
            return {
                "metaphors": classified["metaphors"],
                "metadata": metadata,
                "stage_outputs": {"simple_classification": classified},
            }

        extracted = self._stage_candidate_extract(normalized_text)
        candidates = extracted["candidates"]
        enriched_candidates = self._compare_with_dictionary(candidates)
        judged = self._stage_mipvu_judge(enriched_candidates)
        classified = self._stage_metaphor_classify(
            normalized_text,
            enriched_candidates,
            judged["judgments"],
            pipeline="staged",
        )

        return {
            "metaphors": classified["metaphors"],
            "metadata": metadata,
            "stage_outputs": {
                "candidate_extract": extracted,
                "dictionary_lookup": {"candidates": enriched_candidates},
                "mipvu_judge": judged,
                "metaphor_classify": classified,
            },
        }

    def annotate(self, text: str, pipeline: str = "simple") -> dict:
        result = self.run_pipeline(text=text, pipeline=pipeline)
        if not isinstance(result.get("metaphors"), list):
            result["metaphors"] = []
        return result

