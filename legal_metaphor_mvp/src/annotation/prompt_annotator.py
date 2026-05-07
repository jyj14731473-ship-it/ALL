"""Prompt-based annotation backend for MVP."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from annotation.base import BaseAnnotator
from annotation.dictionary_client import StandardKoreanDictionaryClient


class PromptAnnotator(BaseAnnotator):
    """Prompt-based annotator with separated LLM intervention points.

    Pipelines:
    - simple: one-step prompt annotation
    - staged: candidate extraction -> dictionary comparison -> MIPVU judgment -> classification
    """

    def __init__(self, prompt_dir: Path | None = None, model: str | None = None) -> None:
        project_root = Path(__file__).resolve().parents[2]
        self.prompt_dir = prompt_dir or (project_root / "prompts")
        self.model = model
        self.dictionary_client = StandardKoreanDictionaryClient()
        self.prompt_files = {
            "system_role": "00_system_role.txt",
            "candidate_extract": "01_candidate_extract.txt",
            "mipvu_judge": "02_mipvu_judge.txt",
            "metaphor_classify": "03_metaphor_classify.txt",
            "annotation_schema": "04_annotation_schema.txt",
            "validation_check": "06_validation_check.txt",
        }

    def load_prompt(self, name: str) -> str:
        file_name = self.prompt_files.get(name)
        if not file_name:
            return ""
        path = self.prompt_dir / file_name
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    @staticmethod
    def build_prompt(system_role: str, task_prompt: str, input_text: str) -> str:
        return f"{system_role.strip()}\n\n{task_prompt.strip()}\n\n{input_text.strip()}\n"

    @staticmethod
    def _parse_candidate_extract_response(raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict):
            return {"candidates": []}
        return {"candidates": [x for x in raw.get("candidates", []) if isinstance(x, dict)]}

    @staticmethod
    def _parse_mipvu_judge_response(raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict):
            return {"judgments": []}
        return {"judgments": [x for x in raw.get("judgments", []) if isinstance(x, dict)]}

    @staticmethod
    def _parse_metaphor_classify_response(raw: Any) -> dict[str, Any]:
        if not isinstance(raw, dict):
            return {"metaphors": []}
        return {"metaphors": [x for x in raw.get("metaphors", []) if isinstance(x, dict)]}

    def _llm_call_placeholder(self, stage: str, prompt: str) -> dict[str, Any]:
        """Placeholder for future LLM API calls.

        TODO:
        - Replace stub dict with real LLM client call using prompt.
        - Pass raw JSON response to the corresponding _parse_*_response method.
        """
        _ = prompt
        stubs: dict[str, dict[str, Any]] = {
            "candidate_extract": {"candidates": []},
            "mipvu_judge": {"judgments": []},
            "metaphor_classify": {"metaphors": []},
        }
        parsers = {
            "candidate_extract": self._parse_candidate_extract_response,
            "mipvu_judge": self._parse_mipvu_judge_response,
            "metaphor_classify": self._parse_metaphor_classify_response,
        }
        stub = stubs.get(stage, {"metaphors": []})
        parser = parsers.get(stage, self._parse_metaphor_classify_response)
        return parser(stub)

    @staticmethod
    def _as_list(value: Any) -> list[dict[str, Any]]:
        if isinstance(value, list):
            return [x for x in value if isinstance(x, dict)]
        return []

    @staticmethod
    def _safe_string(value: Any) -> str:
        if isinstance(value, str):
            return value.strip()
        return ""

    def _extract_exception_candidates(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Collect exception-sensitive candidates that need dictionary comparison first."""
        exception_candidates: list[dict[str, Any]] = []
        for candidate in candidates:
            flag = candidate.get("is_exception_candidate")
            reason = self._safe_string(candidate.get("exception_reason"))
            if flag is True or reason:
                exception_candidates.append(candidate)
        return exception_candidates

    def _compare_with_dictionary(self, candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Attach dictionary basic meaning results to candidate records."""
        enriched: list[dict[str, Any]] = []
        for candidate in candidates:
            surface = self._safe_string(candidate.get("surface_expression"))
            lemma = self._safe_string(candidate.get("lemma")) or surface
            pos_tag = self._safe_string(candidate.get("primary_pos"))
            dictionary = self.dictionary_client.lookup_basic_meaning(term=lemma, pos=pos_tag or None)

            updated = dict(candidate)
            updated["dictionary_lookup"] = dictionary
            updated["basic_meaning_from_dict"] = self._safe_string(dictionary.get("definition"))
            enriched.append(updated)
        return enriched

    def _stage_candidate_extract(self, text: str) -> dict[str, Any]:
        system_role = self.load_prompt("system_role")
        candidate_prompt = self.load_prompt("candidate_extract")
        if not system_role.strip() or not candidate_prompt.strip():
            return {"candidates": []}
        task_prompt = candidate_prompt.replace("{{INPUT_TEXT}}", text)
        final_prompt = self.build_prompt(system_role, task_prompt, text)
        response = self._llm_call_placeholder("candidate_extract", final_prompt)
        if not isinstance(response, dict):
            return {"candidates": []}
        response["candidates"] = self._as_list(response.get("candidates"))
        return response

    def _stage_mipvu_judge(self, enriched_candidates: list[dict[str, Any]]) -> dict[str, Any]:
        system_role = self.load_prompt("system_role")
        judge_prompt = self.load_prompt("mipvu_judge")
        if not system_role.strip() or not judge_prompt.strip():
            return {"judgments": []}
        payload = json.dumps({"candidates": enriched_candidates}, ensure_ascii=False)
        task_prompt = judge_prompt.replace("{{CANDIDATES_JSON}}", payload)
        final_prompt = self.build_prompt(system_role, task_prompt, payload)
        response = self._llm_call_placeholder("mipvu_judge", final_prompt)
        if not isinstance(response, dict):
            return {"judgments": []}
        response["judgments"] = self._as_list(response.get("judgments"))
        return response

    def _stage_metaphor_classify(
        self,
        text: str,
        candidates: list[dict[str, Any]],
        judgments: list[dict[str, Any]],
    ) -> dict[str, Any]:
        system_role = self.load_prompt("system_role")
        classify_prompt = self.load_prompt("metaphor_classify")
        schema_ref = self.load_prompt("annotation_schema")
        if not system_role.strip() or not classify_prompt.strip():
            return {"metaphors": []}

        stage_input = {
            "input_text": text,
            "schema_reference": schema_ref,
            "candidates": candidates,
            "judgments": judgments,
        }
        stage_input_str = json.dumps(stage_input, ensure_ascii=False)
        task_prompt = classify_prompt.replace("{{PIPELINE_INPUT}}", stage_input_str)
        final_prompt = self.build_prompt(system_role, task_prompt, stage_input_str)
        response = self._llm_call_placeholder("metaphor_classify", final_prompt)
        if not isinstance(response, dict):
            return {"metaphors": []}
        response["metaphors"] = self._as_list(response.get("metaphors"))
        return response

    def run_pipeline(self, text: str, pipeline: str = "simple") -> dict[str, Any]:
        """Run end-to-end annotation pipeline with explicit stage boundaries."""
        normalized_text = text.strip()
        if not normalized_text:
            return {"metaphors": [], "stage_outputs": {}}

        if pipeline == "simple":
            # MVP fast path: classify directly from text + schema reference.
            result = self._stage_metaphor_classify(normalized_text, candidates=[], judgments=[])
            return {"metaphors": self._as_list(result.get("metaphors")), "stage_outputs": {"pipeline": "simple"}}

        # staged path:
        # 1) 후보 추출(형태소/품사 태깅 + 예외 후보 플래그)
        stage1 = self._stage_candidate_extract(normalized_text)
        candidates = self._as_list(stage1.get("candidates"))

        # 2) 예외 후보 중심 사전 기본 의미 비교(표준국어대사전)
        #    - API key가 없으면 안전하게 no_api_key 상태로 유지.
        exception_candidates = self._extract_exception_candidates(candidates)
        if exception_candidates:
            enriched_exception = self._compare_with_dictionary(exception_candidates)
            enriched_candidates: list[dict[str, Any]] = []
            exception_by_candidate_id = {
                self._safe_string(item.get("candidate_id")): item for item in enriched_exception
            }
            for candidate in candidates:
                c_id = self._safe_string(candidate.get("candidate_id"))
                enriched_candidates.append(exception_by_candidate_id.get(c_id, dict(candidate)))
        else:
            enriched_candidates = self._compare_with_dictionary(candidates)

        # 3) MIPVU-informed 판정(맥락 의미 vs 사전 기반 기본 의미 비교)
        stage3 = self._stage_mipvu_judge(enriched_candidates)
        judgments = self._as_list(stage3.get("judgments"))

        # 4) 최종 은유 분류
        stage4 = self._stage_metaphor_classify(normalized_text, enriched_candidates, judgments)
        metaphors = self._as_list(stage4.get("metaphors"))

        return {
            "metaphors": metaphors,
            "stage_outputs": {
                "pipeline": "staged",
                "candidates": candidates,
                "candidates_enriched_with_dict": enriched_candidates,
                "judgments": judgments,
            },
        }

    def annotate(self, text: str, pipeline: str = "simple") -> dict:
        result = self.run_pipeline(text=text, pipeline=pipeline)
        metaphors = result.get("metaphors", [])
        if not isinstance(metaphors, list):
            return {"metaphors": [], "stage_outputs": {}}
        return {"metaphors": metaphors, "stage_outputs": result.get("stage_outputs", {})}
