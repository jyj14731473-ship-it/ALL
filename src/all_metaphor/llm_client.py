"""OpenAI-backed MIPVU metaphor judgment client."""

from __future__ import annotations

import json
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol, TypedDict, cast

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from all_metaphor.config import RuntimeSettings
from all_metaphor.errors import LlmValidationError, OpenAiApiFailure
from all_metaphor.observability import RunObserver
from all_metaphor.schemas import (
    DictionaryMeaning,
    LexicalUnit,
    MetaphorCandidate,
    MetaphorType,
    MipvuDecision,
)

JUDGE_METAPHOR_STAGE = "judge_metaphor"
LLM_TEMPERATURE = 0.0
DEFAULT_SEED = 42
DEFAULT_BATCH_SIZE = 10
MAX_BATCH_SIZE = 15
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_INITIAL_SECONDS = 0.5

SYSTEM_PROMPT = """\
You are ALL_Metaphor, a careful MIPVU-based metaphor judgment assistant for Korean legal judgment text.

Apply MIPVU at the lexical-unit level:
1. Identify the lexical unit.
2. Determine its contextual meaning from the provided local context only.
3. Use the provided Standard Korean Language Dictionary meanings as possible basic meanings.
4. Decide whether the contextual meaning contrasts with a more basic meaning.
5. Decide whether the contextual meaning can be understood by comparison with that basic meaning.
6. Return one decision: metaphorical, non_metaphorical, or unresolved.

Important Korean legal-domain rules:
- Treat legal terms of art as non-metaphorical by default when used in their conventional legal sense.
- Examples such as "권리의 성립", "의무의 이행", "성립", and "이행" should not be marked metaphorical merely because a general dictionary sense sounds more concrete.
- Prefer unresolved when evidence is insufficient.
- Mark unresolved if dictionary meanings are missing, basic meaning is unclear, contextual meaning cannot be paraphrased confidently, confidence is below 0.5, or legal-domain ambiguity remains.
- Focus on indirect metaphor. direct and implicit metaphor handling are TBD; use them only with explicit evidence.
- Do not invent dictionary meanings. Use only the supplied dictionary meanings.
- Do not infer from the full judgment. Use only the supplied local_context.

Return JSON only. No markdown, no comments, no extra text.
"""

USER_PROMPT_TEMPLATE = """\
Judge the following Korean legal lexical-unit candidates.

Required output shape:
{{
  "results": [
    {{
      "candidate_id": "string",
      "mipvu_decision": "metaphorical | non_metaphorical | unresolved",
      "metaphor_type": "indirect | direct | implicit | null",
      "contextual_meaning": "string | null",
      "basic_meaning": "string | null",
      "meaning_contrast": "string | null",
      "confidence": 0.0,
      "rationale": "string"
    }}
  ]
}}

Constraints:
- Include exactly one result for each input candidate_id.
- confidence must be between 0.0 and 1.0.
- metaphor_type must be null unless mipvu_decision is metaphorical.
- If mipvu_decision is unresolved, explain the uncertainty in rationale.
- If the candidate is conventional legal terminology in this context, choose non_metaphorical.

Candidates:
{candidates_json}
"""

REPAIR_PROMPT_TEMPLATE = """\
Your previous response was not valid JSON for the required schema.

Do not change the substantive judgments unless required to satisfy the schema.
Return JSON only with this exact top-level shape:
{{"results":[...]}}

Original candidates:
{candidates_json}

Invalid response:
{invalid_response}
"""


class ChatMessage(TypedDict):
    """Chat completion message payload."""

    role: Literal["system", "user"]
    content: str


class ChatMessageResponseLike(Protocol):
    """Subset of OpenAI chat message response used by this client."""

    content: str | None


class ChatChoiceLike(Protocol):
    """Subset of OpenAI chat completion choice used by this client."""

    message: ChatMessageResponseLike


class ChatUsageLike(Protocol):
    """Subset of OpenAI token usage used by this client."""

    prompt_tokens: int | None
    completion_tokens: int | None
    total_tokens: int | None


class ChatCompletionResponseLike(Protocol):
    """Subset of OpenAI chat completion response used by this client."""

    choices: Sequence[ChatChoiceLike]
    usage: ChatUsageLike | None


class ChatCompletionsLike(Protocol):
    """Callable OpenAI chat completions surface."""

    def create(
        self,
        *,
        model: str,
        messages: Sequence[ChatMessage],
        temperature: float,
        seed: int | None,
        response_format: Mapping[str, str],
    ) -> ChatCompletionResponseLike:
        """Create one chat completion."""


class _StrictBaseModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class _LlmJudgment(_StrictBaseModel):
    candidate_id: str
    mipvu_decision: MipvuDecision
    metaphor_type: MetaphorType | None = None
    contextual_meaning: str | None = None
    basic_meaning: str | None = None
    meaning_contrast: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str

    @model_validator(mode="after")
    def validate_metaphor_type_consistency(self) -> _LlmJudgment:
        if self.mipvu_decision is not MipvuDecision.METAPHORICAL and self.metaphor_type is not None:
            msg = "metaphor_type must be null unless mipvu_decision is metaphorical"
            raise ValueError(msg)
        return self


class _LlmBatchResponse(_StrictBaseModel):
    results: list[_LlmJudgment]


@dataclass(frozen=True, slots=True)
class _PromptBatch:
    candidates: list[MetaphorCandidate]
    prompt_candidates: list[dict[str, object]]


class LlmClient:
    """Judge metaphor candidates with OpenAI JSON responses."""

    def __init__(
        self,
        settings: RuntimeSettings,
        *,
        observer: RunObserver | None = None,
        batch_size: int = DEFAULT_BATCH_SIZE,
        seed: int | None = DEFAULT_SEED,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_initial_seconds: float = DEFAULT_BACKOFF_INITIAL_SECONDS,
        chat_completions: ChatCompletionsLike | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if batch_size <= 0:
            msg = "batch_size must be positive"
            raise ValueError(msg)
        if max_retries < 0:
            msg = "max_retries must be non-negative"
            raise ValueError(msg)
        if backoff_initial_seconds < 0:
            msg = "backoff_initial_seconds must be non-negative"
            raise ValueError(msg)

        self._settings = settings
        self._observer = observer
        self._batch_size = min(batch_size, MAX_BATCH_SIZE)
        self._seed = seed
        self._max_retries = max_retries
        self._backoff_initial_seconds = backoff_initial_seconds
        self._chat_completions = chat_completions or _default_chat_completions(settings)
        self._sleep = sleep

    def judge_candidates(
        self,
        candidates: list[MetaphorCandidate],
        *,
        lexical_units_by_id: Mapping[str, LexicalUnit] | None = None,
    ) -> list[MetaphorCandidate]:
        """Fill MIPVU judgment fields for metaphor candidates."""
        updated_by_id: dict[str, MetaphorCandidate] = {}
        llm_ready_candidates: list[MetaphorCandidate] = []
        for candidate in candidates:
            if not candidate.dictionary_meanings:
                updated_by_id[candidate.candidate_id] = _mark_unresolved(
                    candidate,
                    "Dictionary lookup returned no result; candidate remains unresolved.",
                )
            else:
                llm_ready_candidates.append(candidate)

        for batch in _build_prompt_batches(
            llm_ready_candidates,
            lexical_units_by_id=lexical_units_by_id or {},
            batch_size=self._batch_size,
        ):
            batch_results = self._judge_batch(batch)
            updated_by_id.update({candidate.candidate_id: candidate for candidate in batch_results})

        judged = [updated_by_id.get(candidate.candidate_id, candidate) for candidate in candidates]
        if self._observer is not None:
            unresolved_count = sum(
                1 for candidate in judged if candidate.mipvu_decision is MipvuDecision.UNRESOLVED
            )
            if unresolved_count > 0:
                self._observer.increment_unresolved_candidates(unresolved_count)
        return judged

    def _judge_batch(self, batch: _PromptBatch) -> list[MetaphorCandidate]:
        candidates_json = _dump_candidates_json(batch.prompt_candidates)
        messages = _build_messages(candidates_json)
        raw_response = self._create_completion(messages, len(batch.candidates), repair=False)
        try:
            parsed_response = _parse_llm_response(raw_response, batch.candidates)
        except LlmValidationError:
            repair_messages = _build_repair_messages(candidates_json, raw_response)
            repair_response = self._create_completion(
                repair_messages,
                len(batch.candidates),
                repair=True,
            )
            try:
                parsed_response = _parse_llm_response(repair_response, batch.candidates)
            except LlmValidationError as exc:
                if self._observer is not None:
                    self._observer.increment_llm_validation_failures(len(batch.candidates))
                return [
                    _mark_unresolved(
                        candidate,
                        "LLM response validation failed; candidate remains unresolved.",
                        error=exc,
                    )
                    for candidate in batch.candidates
                ]

        return [
            _apply_judgment(candidate, parsed_response[candidate.candidate_id])
            for candidate in batch.candidates
        ]

    def _create_completion(
        self,
        messages: Sequence[ChatMessage],
        batch_size: int,
        *,
        repair: bool,
    ) -> str:
        attempts = self._max_retries + 1
        last_error: BaseException | None = None
        for attempt_index in range(attempts):
            try:
                if self._observer is not None:
                    self._observer.increment_llm_request_count()
                    self._observer.log_event(
                        "llm_request",
                        stage=JUDGE_METAPHOR_STAGE,
                        metadata={
                            "model": self._settings.openai_model,
                            "temperature": LLM_TEMPERATURE,
                            "seed": self._seed,
                            "batch_size": batch_size,
                            "repair": repair,
                        },
                    )
                response = self._chat_completions.create(
                    model=self._settings.openai_model,
                    messages=messages,
                    temperature=LLM_TEMPERATURE,
                    seed=self._seed,
                    response_format={"type": "json_object"},
                )
                _track_token_usage(response, self._observer)
                return _response_content(response)
            except Exception as exc:  # noqa: BLE001
                last_error = exc
                if attempt_index == attempts - 1:
                    break
                self._sleep(self._backoff_seconds(attempt_index))

        error_name = type(last_error).__name__ if last_error is not None else "unknown error"
        raise OpenAiApiFailure(
            f"OpenAI API request failed after {attempts} attempts ({error_name})"
        )

    def _backoff_seconds(self, attempt_index: int) -> float:
        return float(self._backoff_initial_seconds * (2**attempt_index))


def _default_chat_completions(settings: RuntimeSettings) -> ChatCompletionsLike:
    from openai import OpenAI

    client = OpenAI(api_key=settings.openai_api_key.get_secret_value())
    return cast(ChatCompletionsLike, client.chat.completions)


def _build_prompt_batches(
    candidates: list[MetaphorCandidate],
    *,
    lexical_units_by_id: Mapping[str, LexicalUnit],
    batch_size: int,
) -> list[_PromptBatch]:
    batches: list[_PromptBatch] = []
    current_candidates: list[MetaphorCandidate] = []
    current_prompt_candidates: list[dict[str, object]] = []
    current_sentence_id: str | None = None

    for candidate in candidates:
        lexical_unit = lexical_units_by_id.get(candidate.unit_id)
        sentence_id = lexical_unit.sentence_id if lexical_unit is not None else None
        should_flush = bool(current_candidates) and (
            len(current_candidates) >= batch_size or sentence_id != current_sentence_id
        )
        if should_flush:
            batches.append(_PromptBatch(current_candidates, current_prompt_candidates))
            current_candidates = []
            current_prompt_candidates = []

        current_sentence_id = sentence_id
        current_candidates.append(candidate)
        current_prompt_candidates.append(_candidate_prompt_payload(candidate, lexical_unit))

    if current_candidates:
        batches.append(_PromptBatch(current_candidates, current_prompt_candidates))
    return batches


def _candidate_prompt_payload(
    candidate: MetaphorCandidate,
    lexical_unit: LexicalUnit | None,
) -> dict[str, object]:
    payload: dict[str, object] = {
        "candidate_id": candidate.candidate_id,
        "unit_id": candidate.unit_id,
        "dictionary_query": candidate.dictionary_query,
        "dictionary_meanings": [
            _dictionary_meaning_payload(meaning) for meaning in candidate.dictionary_meanings
        ],
    }
    if lexical_unit is not None:
        payload.update(
            {
                "surface": lexical_unit.surface,
                "lemma": lexical_unit.lemma,
                "pos": lexical_unit.pos,
                "local_context": lexical_unit.local_context,
            }
        )
    return payload


def _dictionary_meaning_payload(meaning: DictionaryMeaning) -> dict[str, str | None]:
    return {
        "sense_id": meaning.sense_id,
        "definition": meaning.definition,
    }


def _dump_candidates_json(prompt_candidates: list[dict[str, object]]) -> str:
    return json.dumps(prompt_candidates, ensure_ascii=False, sort_keys=True)


def _build_messages(candidates_json: str) -> list[ChatMessage]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": USER_PROMPT_TEMPLATE.format(candidates_json=candidates_json)},
    ]


def _build_repair_messages(candidates_json: str, invalid_response: str) -> list[ChatMessage]:
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        {
            "role": "user",
            "content": REPAIR_PROMPT_TEMPLATE.format(
                candidates_json=candidates_json,
                invalid_response=invalid_response,
            ),
        },
    ]


def _parse_llm_response(
    raw_response: str,
    candidates: Sequence[MetaphorCandidate],
) -> dict[str, _LlmJudgment]:
    try:
        parsed_json = json.loads(raw_response)
        batch_response = _LlmBatchResponse.model_validate(parsed_json)
    except (json.JSONDecodeError, ValidationError) as exc:
        raise LlmValidationError("LLM response is not valid metaphor-judgment JSON") from exc

    judgments_by_id: dict[str, _LlmJudgment] = {}
    for judgment in batch_response.results:
        if judgment.candidate_id in judgments_by_id:
            raise LlmValidationError(
                f"LLM response contains duplicate candidate_id={judgment.candidate_id!r}"
            )
        judgments_by_id[judgment.candidate_id] = judgment

    expected_ids = {candidate.candidate_id for candidate in candidates}
    if set(judgments_by_id) != expected_ids:
        raise LlmValidationError("LLM response candidate_id set does not match request")
    return judgments_by_id


def _response_content(response: ChatCompletionResponseLike) -> str:
    if not response.choices:
        raise OpenAiApiFailure("OpenAI response contained no choices")
    content = response.choices[0].message.content
    if content is None or content.strip() == "":
        raise OpenAiApiFailure("OpenAI response contained empty content")
    return content


def _track_token_usage(response: ChatCompletionResponseLike, observer: RunObserver | None) -> None:
    if observer is None or response.usage is None:
        return
    observer.add_token_usage(
        prompt_tokens=response.usage.prompt_tokens or 0,
        completion_tokens=response.usage.completion_tokens or 0,
        total_tokens=response.usage.total_tokens or 0,
    )


def _apply_judgment(
    candidate: MetaphorCandidate,
    judgment: _LlmJudgment,
) -> MetaphorCandidate:
    return _copy_candidate(
        candidate,
        {
            "mipvu_decision": judgment.mipvu_decision,
            "metaphor_type": judgment.metaphor_type,
            "contextual_meaning": judgment.contextual_meaning,
            "basic_meaning": judgment.basic_meaning,
            "meaning_contrast": judgment.meaning_contrast,
            "confidence": judgment.confidence,
            "llm_rationale": judgment.rationale,
        },
    )


def _mark_unresolved(
    candidate: MetaphorCandidate,
    rationale: str,
    *,
    error: LlmValidationError | None = None,
) -> MetaphorCandidate:
    errors = list(candidate.errors)
    if error is not None:
        errors.append(
            error.to_error_entry(stage=JUDGE_METAPHOR_STAGE, candidate_id=candidate.candidate_id)
        )
    return _copy_candidate(
        candidate,
        {
            "mipvu_decision": MipvuDecision.UNRESOLVED,
            "metaphor_type": None,
            "meaning_contrast": None,
            "confidence": 0.0,
            "llm_rationale": rationale,
            "errors": errors,
        },
    )


def _copy_candidate(
    candidate: MetaphorCandidate, update: Mapping[str, object]
) -> MetaphorCandidate:
    data = candidate.model_dump(mode="python")
    data.update(update)
    return MetaphorCandidate.model_validate(data)


__all__ = [
    "DEFAULT_BATCH_SIZE",
    "DEFAULT_BACKOFF_INITIAL_SECONDS",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_SEED",
    "JUDGE_METAPHOR_STAGE",
    "LLM_TEMPERATURE",
    "MAX_BATCH_SIZE",
    "SYSTEM_PROMPT",
    "ChatCompletionsLike",
    "ChatCompletionResponseLike",
    "ChatMessage",
    "LlmClient",
]
