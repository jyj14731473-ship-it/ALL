from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Literal

import pytest

from all_metaphor.config import RuntimeSettings
from all_metaphor.errors import OpenAiApiFailure
from all_metaphor.llm_client import (
    JUDGE_METAPHOR_STAGE,
    LLM_TEMPERATURE,
    MAX_BATCH_SIZE,
    LlmClient,
)
from all_metaphor.observability import RunObserver
from all_metaphor.schemas import (
    DictionaryMeaning,
    ErrorCode,
    LexicalUnit,
    MetaphorCandidate,
    MipvuDecision,
)


@dataclass
class FakeMessageResponse:
    content: str | None


@dataclass
class FakeChoice:
    message: FakeMessageResponse


@dataclass
class FakeUsage:
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None


@dataclass
class FakeChatResponse:
    choices: list[FakeChoice]
    usage: FakeUsage | None = None


class FakeChatCompletions:
    def __init__(
        self,
        outcomes: list[str | BaseException],
        *,
        usage: FakeUsage | None = None,
    ) -> None:
        self.outcomes = outcomes
        self.usage = usage
        self.calls: list[dict[str, object]] = []

    def create(
        self,
        *,
        model: str,
        messages: list[dict[Literal["role", "content"], str]],
        temperature: float,
        seed: int | None,
        response_format: dict[str, str],
    ) -> FakeChatResponse:
        self.calls.append(
            {
                "model": model,
                "messages": messages,
                "temperature": temperature,
                "seed": seed,
                "response_format": response_format,
            }
        )
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, BaseException):
            raise outcome
        return FakeChatResponse(
            choices=[FakeChoice(message=FakeMessageResponse(content=outcome))],
            usage=self.usage,
        )


@pytest.fixture
def settings() -> RuntimeSettings:
    return RuntimeSettings(
        openai_api_key="test-openai-key",
        openai_model="test-model",
        krdict_api_key="test-krdict-key",
    )


def make_candidate(
    candidate_id: str,
    *,
    unit_id: str | None = None,
    dictionary_query: str = "성립",
    dictionary_meanings: list[DictionaryMeaning] | None = None,
) -> MetaphorCandidate:
    return MetaphorCandidate(
        candidate_id=candidate_id,
        unit_id=unit_id or candidate_id.replace("candidate", "unit"),
        dictionary_query=dictionary_query,
        dictionary_meanings=dictionary_meanings
        if dictionary_meanings is not None
        else [DictionaryMeaning(sense_id="sense-1", definition="일이나 관계가 이루어짐.")],
        contextual_meaning=None,
        basic_meaning=None,
        meaning_contrast=None,
        mipvu_decision=MipvuDecision.UNRESOLVED,
        metaphor_type=None,
        source_domain=None,
        target_domain=None,
        confidence=0.0,
        llm_rationale=None,
        errors=[],
    )


def make_unit(
    unit_id: str,
    *,
    surface: str = "성립",
    sentence_id: str | None = "sentence-000001",
    local_context: str = "계약의 성립 여부를 판단한다.",
) -> LexicalUnit:
    return LexicalUnit(
        unit_id=unit_id,
        surface=surface,
        lemma=surface,
        pos="Noun",
        start_char=0,
        end_char=len(surface),
        sentence_id=sentence_id,
        local_context=local_context,
        local_context_char_count=len(local_context),
        is_candidate=True,
        filter_reason=None,
    )


def llm_json(candidate_id: str, *, decision: str = "non_metaphorical") -> str:
    return json.dumps(
        {
            "results": [
                {
                    "candidate_id": candidate_id,
                    "mipvu_decision": decision,
                    "metaphor_type": "indirect" if decision == "metaphorical" else None,
                    "contextual_meaning": "계약 관계가 법적으로 이루어진다는 의미",
                    "basic_meaning": "일이나 관계가 이루어진다는 사전적 의미",
                    "meaning_contrast": "법률 관습적 의미로 사용됨",
                    "confidence": 0.84,
                    "rationale": "법률 전문용어의 관습적 의미에 가깝다.",
                }
            ]
        },
        ensure_ascii=False,
    )


def extract_prompt_candidates(call: dict[str, object]) -> list[dict[str, object]]:
    messages = call["messages"]
    assert isinstance(messages, list)
    user_message = messages[1]
    assert isinstance(user_message, dict)
    content = user_message["content"]
    assert isinstance(content, str)
    candidates_json = content.split("Candidates:\n", maxsplit=1)[1]
    parsed = json.loads(candidates_json)
    assert isinstance(parsed, list)
    return parsed


def test_judge_candidates_updates_candidate_fields(settings: RuntimeSettings) -> None:
    fake_chat = FakeChatCompletions([llm_json("candidate-000001")])
    candidate = make_candidate("candidate-000001", unit_id="unit-000001")
    lexical_unit = make_unit("unit-000001")

    judged = LlmClient(settings, chat_completions=fake_chat).judge_candidates(
        [candidate],
        lexical_units_by_id={"unit-000001": lexical_unit},
    )

    assert judged[0].mipvu_decision is MipvuDecision.NON_METAPHORICAL
    assert judged[0].metaphor_type is None
    assert judged[0].contextual_meaning == "계약 관계가 법적으로 이루어진다는 의미"
    assert judged[0].basic_meaning == "일이나 관계가 이루어진다는 사전적 의미"
    assert judged[0].meaning_contrast == "법률 관습적 의미로 사용됨"
    assert judged[0].confidence == 0.84
    assert judged[0].llm_rationale == "법률 전문용어의 관습적 의미에 가깝다."

    call = fake_chat.calls[0]
    assert call["model"] == "test-model"
    assert call["temperature"] == LLM_TEMPERATURE
    assert call["seed"] == 42
    assert call["response_format"] == {"type": "json_object"}
    prompt_candidates = extract_prompt_candidates(call)
    assert prompt_candidates[0]["local_context"] == "계약의 성립 여부를 판단한다."
    assert prompt_candidates[0]["surface"] == "성립"


def test_judge_candidates_repairs_invalid_json_once(settings: RuntimeSettings) -> None:
    fake_chat = FakeChatCompletions(["not json", llm_json("candidate-000001")])
    candidate = make_candidate("candidate-000001")

    judged = LlmClient(settings, chat_completions=fake_chat).judge_candidates([candidate])

    assert judged[0].mipvu_decision is MipvuDecision.NON_METAPHORICAL
    assert len(fake_chat.calls) == 2
    repair_messages = fake_chat.calls[1]["messages"]
    assert isinstance(repair_messages, list)
    repair_user_message = repair_messages[1]["content"]
    assert isinstance(repair_user_message, str)
    assert "Invalid response:" in repair_user_message
    assert "not json" in repair_user_message


def test_judge_candidates_marks_batch_unresolved_after_failed_repair(
    settings: RuntimeSettings,
) -> None:
    observer = RunObserver(settings, run_id="run-llm-validation")
    fake_chat = FakeChatCompletions(["not json", '{"results": []}'])
    candidates = [make_candidate("candidate-000001"), make_candidate("candidate-000002")]

    judged = LlmClient(settings, observer=observer, chat_completions=fake_chat).judge_candidates(
        candidates
    )

    assert [candidate.mipvu_decision for candidate in judged] == [
        MipvuDecision.UNRESOLVED,
        MipvuDecision.UNRESOLVED,
    ]
    assert [candidate.confidence for candidate in judged] == [0.0, 0.0]
    assert all(candidate.errors for candidate in judged)
    assert judged[0].errors[0].error_code is ErrorCode.LLM_VALIDATION_ERROR
    assert judged[0].errors[0].stage == JUDGE_METAPHOR_STAGE
    assert observer.metrics.llm_validation_failures == 2
    assert observer.metrics.unresolved_candidates == 2


def test_judge_candidates_skips_candidates_without_dictionary_meanings(
    settings: RuntimeSettings,
) -> None:
    fake_chat = FakeChatCompletions([])
    candidate = make_candidate(
        "candidate-000001",
        dictionary_meanings=[],
    )

    judged = LlmClient(settings, chat_completions=fake_chat).judge_candidates([candidate])

    assert judged[0].mipvu_decision is MipvuDecision.UNRESOLVED
    assert judged[0].confidence == 0.0
    assert "Dictionary lookup returned no result" in (judged[0].llm_rationale or "")
    assert fake_chat.calls == []


def test_judge_candidates_splits_batches_by_sentence_and_hard_cap(
    settings: RuntimeSettings,
) -> None:
    candidates = [
        make_candidate(f"candidate-{index:06d}", unit_id=f"unit-{index:06d}")
        for index in range(1, 18)
    ]
    units = {
        f"unit-{index:06d}": make_unit(
            f"unit-{index:06d}",
            sentence_id="sentence-000001" if index <= 16 else "sentence-000002",
        )
        for index in range(1, 18)
    }
    fake_chat = FakeChatCompletions(
        [
            json.dumps(
                {
                    "results": [
                        {
                            "candidate_id": f"candidate-{index:06d}",
                            "mipvu_decision": "non_metaphorical",
                            "metaphor_type": None,
                            "contextual_meaning": "context",
                            "basic_meaning": "basic",
                            "meaning_contrast": None,
                            "confidence": 0.6,
                            "rationale": "ok",
                        }
                        for index in batch
                    ]
                }
            )
            for batch in [range(1, 16), range(16, 17), range(17, 18)]
        ]
    )

    judged = LlmClient(
        settings,
        chat_completions=fake_chat,
        batch_size=99,
    ).judge_candidates(candidates, lexical_units_by_id=units)

    assert len(judged) == 17
    assert len(fake_chat.calls) == 3
    assert [len(extract_prompt_candidates(call)) for call in fake_chat.calls] == [
        MAX_BATCH_SIZE,
        1,
        1,
    ]


def test_judge_candidates_retries_openai_failures_then_succeeds(
    settings: RuntimeSettings,
) -> None:
    sleep_calls: list[float] = []
    fake_chat = FakeChatCompletions(
        [
            RuntimeError("temporary"),
            RuntimeError("temporary"),
            llm_json("candidate-000001"),
        ]
    )

    judged = LlmClient(
        settings,
        chat_completions=fake_chat,
        sleep=sleep_calls.append,
        backoff_initial_seconds=0.25,
    ).judge_candidates([make_candidate("candidate-000001")])

    assert judged[0].mipvu_decision is MipvuDecision.NON_METAPHORICAL
    assert len(fake_chat.calls) == 3
    assert sleep_calls == [0.25, 0.5]


def test_judge_candidates_raises_openai_failure_without_secret() -> None:
    settings = RuntimeSettings(
        openai_api_key="super-secret-openai-key",
        openai_model="test-model",
        krdict_api_key="test-krdict-key",
    )
    fake_chat = FakeChatCompletions(
        [
            RuntimeError("super-secret-openai-key leaked by lower layer"),
            RuntimeError("super-secret-openai-key leaked by lower layer"),
        ]
    )

    with pytest.raises(OpenAiApiFailure) as exc_info:
        LlmClient(
            settings,
            chat_completions=fake_chat,
            max_retries=1,
            sleep=lambda _seconds: None,
        ).judge_candidates([make_candidate("candidate-000001")])

    assert "super-secret-openai-key" not in str(exc_info.value)
    assert "RuntimeError" in str(exc_info.value)
    assert exc_info.value.retryable is True


def test_judge_candidates_tracks_tokens_and_request_metadata(
    settings: RuntimeSettings,
    caplog: pytest.LogCaptureFixture,
) -> None:
    observer = RunObserver(settings, run_id="run-llm")
    caplog.set_level(logging.INFO, logger="all_metaphor.observability")
    fake_chat = FakeChatCompletions(
        [llm_json("candidate-000001")],
        usage=FakeUsage(prompt_tokens=11, completion_tokens=7, total_tokens=18),
    )

    LlmClient(settings, observer=observer, chat_completions=fake_chat).judge_candidates(
        [make_candidate("candidate-000001")]
    )

    assert observer.metrics.llm_request_count == 1
    assert observer.metrics.prompt_tokens == 11
    assert observer.metrics.completion_tokens == 7
    assert observer.metrics.total_tokens == 18
    records = [json.loads(record.message) for record in caplog.records]
    request_record = next(record for record in records if record["event"] == "llm_request")
    assert request_record["metadata"] == {
        "batch_size": 1,
        "model": "test-model",
        "repair": False,
        "seed": 42,
        "temperature": 0.0,
    }


def test_judge_candidates_does_not_log_context_or_api_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = RuntimeSettings(
        openai_api_key="super-secret-openai-key",
        openai_model="test-model",
        krdict_api_key="test-krdict-key",
    )
    observer = RunObserver(settings, run_id="run-security")
    caplog.set_level(logging.INFO, logger="all_metaphor.observability")
    fake_chat = FakeChatCompletions([llm_json("candidate-000001")])
    sensitive_context = "이 문장은 로그에 나오면 안 된다."

    LlmClient(settings, observer=observer, chat_completions=fake_chat).judge_candidates(
        [make_candidate("candidate-000001", unit_id="unit-000001")],
        lexical_units_by_id={
            "unit-000001": make_unit("unit-000001", local_context=sensitive_context)
        },
    )

    log_text = "\n".join(record.message for record in caplog.records)
    assert "super-secret-openai-key" not in log_text
    assert sensitive_context not in log_text


def test_client_rejects_invalid_settings(settings: RuntimeSettings) -> None:
    with pytest.raises(ValueError, match="batch_size must be positive"):
        LlmClient(settings, batch_size=0)
    with pytest.raises(ValueError, match="max_retries must be non-negative"):
        LlmClient(settings, max_retries=-1)
    with pytest.raises(ValueError, match="backoff_initial_seconds must be non-negative"):
        LlmClient(settings, backoff_initial_seconds=-0.1)


@pytest.mark.integration
def test_judge_candidates_with_real_openai_smoke() -> None:
    if os.environ.get("RUN_OPENAI_INTEGRATION") != "1":
        pytest.skip("Set RUN_OPENAI_INTEGRATION=1 to call the real OpenAI API.")
    api_key = os.environ.get("OPENAI_API_KEY")
    model = os.environ.get("OPENAI_MODEL")
    if api_key is None or api_key.strip() == "" or model is None or model.strip() == "":
        pytest.skip("OPENAI_API_KEY and OPENAI_MODEL are required for OpenAI smoke test.")

    settings = RuntimeSettings(
        openai_api_key=api_key,
        openai_model=model,
        krdict_api_key="test-krdict-key",
    )
    judged = LlmClient(settings).judge_candidates(
        [
            make_candidate(
                "candidate-000001",
                unit_id="unit-000001",
                dictionary_query="성립",
            )
        ],
        lexical_units_by_id={"unit-000001": make_unit("unit-000001")},
    )

    assert len(judged) == 1
    assert judged[0].mipvu_decision in {
        MipvuDecision.METAPHORICAL,
        MipvuDecision.NON_METAPHORICAL,
        MipvuDecision.UNRESOLVED,
    }
