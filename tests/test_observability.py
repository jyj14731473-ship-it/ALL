from __future__ import annotations

import json
import logging
from pathlib import Path

import pytest

from all_metaphor.config import RuntimeSettings
from all_metaphor.errors import MissingInputFile
from all_metaphor.observability import RunObserver
from all_metaphor.schemas import RunMetadata


@pytest.fixture
def settings() -> RuntimeSettings:
    return RuntimeSettings(
        openai_api_key="sk-test-secret",
        openai_model="test-model",
        krdict_api_key="krdict-test-secret",
        log_level="INFO",
    )


@pytest.fixture
def logger() -> logging.Logger:
    return logging.getLogger("tests.observability")


def _messages(caplog: pytest.LogCaptureFixture) -> list[dict[str, object]]:
    return [json.loads(record.message) for record in caplog.records]


def test_run_observer_accumulates_metrics(settings: RuntimeSettings) -> None:
    observer = RunObserver(settings, run_id="run-001")

    observer.set_input_file_path(Path("data/input/example.txt"))
    observer.set_character_count(100)
    observer.set_lexical_unit_count(20)
    observer.set_candidate_count(10)
    observer.set_filtered_candidate_count(4)
    observer.increment_dictionary_lookup_count()
    observer.increment_dictionary_lookup_count(2)
    observer.increment_llm_request_count(3)
    observer.set_rdf_triple_count(7)
    observer.add_token_usage(prompt_tokens=11, completion_tokens=5, total_tokens=16)
    observer.add_token_usage(prompt_tokens=2, completion_tokens=1, total_tokens=3)
    observer.increment_dictionary_api_failures()
    observer.increment_llm_validation_failures(2)
    observer.increment_skipped_candidates(3)
    observer.increment_unresolved_candidates(4)

    assert observer.metrics.input_file_path == "data\\input\\example.txt"
    assert observer.metrics.character_count == 100
    assert observer.metrics.lexical_unit_count == 20
    assert observer.metrics.candidate_count == 10
    assert observer.metrics.filtered_candidate_count == 4
    assert observer.metrics.dictionary_lookup_count == 3
    assert observer.metrics.llm_request_count == 3
    assert observer.metrics.rdf_triple_count == 7
    assert observer.metrics.prompt_tokens == 13
    assert observer.metrics.completion_tokens == 6
    assert observer.metrics.total_tokens == 19
    assert observer.metrics.dictionary_api_failures == 1
    assert observer.metrics.llm_validation_failures == 2
    assert observer.metrics.skipped_candidates == 3
    assert observer.metrics.unresolved_candidates == 4


def test_stage_logs_json_start_and_end(
    settings: RuntimeSettings,
    logger: logging.Logger,
    caplog: pytest.LogCaptureFixture,
) -> None:
    observer = RunObserver(settings, run_id="run-json", logger=logger)

    with (
        caplog.at_level(logging.INFO, logger=logger.name),
        observer.stage("load_input", metadata={"input_file_path": Path("data/input/a.txt")}),
    ):
        observer.set_character_count(12)

    messages = _messages(caplog)
    assert [message["event"] for message in messages] == ["stage_start", "stage_end"]
    assert messages[0]["run_id"] == "run-json"
    assert messages[0]["stage"] == "load_input"
    assert messages[0]["metadata"] == {"input_file_path": "data\\input\\a.txt"}
    assert isinstance(messages[1]["duration_ms"], float)


def test_stage_logs_error_and_reraises(
    settings: RuntimeSettings,
    logger: logging.Logger,
    caplog: pytest.LogCaptureFixture,
) -> None:
    observer = RunObserver(settings, run_id="run-error", logger=logger)

    with (
        caplog.at_level(logging.INFO, logger=logger.name),
        pytest.raises(MissingInputFile),
        observer.stage("load_input"),
    ):
        raise MissingInputFile("missing")

    messages = _messages(caplog)
    assert [message["event"] for message in messages] == ["stage_start", "stage_error"]
    assert messages[1]["error_type"] == "MissingInputFile"
    assert messages[1]["error_code"] == "MISSING_INPUT_FILE"
    assert isinstance(messages[1]["duration_ms"], float)


def test_log_event_redacts_sensitive_metadata(
    settings: RuntimeSettings,
    logger: logging.Logger,
    caplog: pytest.LogCaptureFixture,
) -> None:
    observer = RunObserver(settings, run_id="run-secret", logger=logger)

    with caplog.at_level(logging.INFO, logger=logger.name):
        observer.log_event(
            "custom",
            metadata={
                "openai_api_key": settings.openai_api_key,
                "nested": {"KRDICT_API_KEY": settings.krdict_api_key},
                "raw_text": "판결문 전체 텍스트",
                "safe": "value",
            },
        )

    raw_log = caplog.records[0].message
    message = json.loads(raw_log)
    metadata = message["metadata"]
    assert "sk-test-secret" not in raw_log
    assert "krdict-test-secret" not in raw_log
    assert "판결문 전체 텍스트" not in raw_log
    assert metadata == {
        "openai_api_key": "[REDACTED]",
        "nested": {"KRDICT_API_KEY": "[REDACTED]"},
        "raw_text": "[REDACTED]",
        "safe": "value",
    }


def test_finalize_returns_run_metadata(settings: RuntimeSettings) -> None:
    observer = RunObserver(settings, run_id="run-final")
    observer.set_input_file_path("data/input/example.txt")
    observer.add_token_usage(prompt_tokens=10, completion_tokens=4, total_tokens=14)

    metadata = observer.finalize()

    assert isinstance(metadata, RunMetadata)
    assert metadata.run_id == "run-final"
    assert metadata.input_path == "data/input/example.txt"
    assert metadata.openai_model == "test-model"
    assert metadata.openai_temperature == 0.0
    assert metadata.openai_seed is None
    assert metadata.completed_at is not None
    assert metadata.token_usage.prompt_tokens == 10
    assert metadata.token_usage.completion_tokens == 4
    assert metadata.token_usage.total_tokens == 14


def test_observer_uses_settings_log_level(settings: RuntimeSettings) -> None:
    error_settings = settings.model_copy(update={"log_level": "ERROR"})
    logger = logging.getLogger("tests.observability.level")

    RunObserver(error_settings, logger=logger)

    assert logger.level == logging.ERROR


def test_negative_metric_value_is_rejected(settings: RuntimeSettings) -> None:
    observer = RunObserver(settings)

    with pytest.raises(ValueError):
        observer.set_character_count(-1)


def test_negative_increment_value_is_rejected(settings: RuntimeSettings) -> None:
    observer = RunObserver(settings)

    with pytest.raises(ValueError):
        observer.increment_dictionary_lookup_count(-1)
