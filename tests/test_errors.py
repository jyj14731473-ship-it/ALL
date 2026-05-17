from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

import pytest

from all_metaphor.errors import (
    AllMetaphorError,
    DictApiFailure,
    EmptyInputFile,
    IntermediateValidationError,
    InvalidFileExtension,
    InvalidTextEncoding,
    KonlpyAnalysisFailure,
    LlmValidationError,
    MissingEnvVar,
    MissingInputFile,
    OpenAiApiFailure,
    OutputWriteError,
    RdfSerializationFailure,
)
from all_metaphor.schemas import AnalysisError, ErrorCode

ExceptionFactory = Callable[[str], AllMetaphorError]


@pytest.mark.parametrize(
    ("factory", "error_code", "retryable"),
    [
        (DictApiFailure, ErrorCode.DICT_API_FAILURE, True),
        (LlmValidationError, ErrorCode.LLM_VALIDATION_ERROR, False),
        (KonlpyAnalysisFailure, ErrorCode.KONLPY_ANALYSIS_FAILURE, False),
        (OpenAiApiFailure, ErrorCode.OPENAI_API_FAILURE, True),
        (RdfSerializationFailure, ErrorCode.RDF_SERIALIZATION_FAILURE, False),
        (IntermediateValidationError, ErrorCode.VALIDATION_ERROR, False),
        (OutputWriteError, ErrorCode.OUTPUT_WRITE_ERROR, False),
        (MissingEnvVar, ErrorCode.MISSING_ENV_VAR, False),
        (InvalidFileExtension, ErrorCode.INVALID_FILE_EXTENSION, False),
        (MissingInputFile, ErrorCode.MISSING_INPUT_FILE, False),
        (EmptyInputFile, ErrorCode.EMPTY_INPUT_FILE, False),
        (InvalidTextEncoding, ErrorCode.INVALID_TEXT_ENCODING, False),
    ],
)
def test_concrete_error_sets_code_and_retryable(
    factory: ExceptionFactory,
    error_code: ErrorCode,
    retryable: bool,
) -> None:
    error = factory("failure message")

    assert isinstance(error, AllMetaphorError)
    assert error.error_code is error_code
    assert error.message == "failure message"
    assert error.retryable is retryable
    assert str(error) == "failure message"


def test_to_error_entry_returns_analysis_error() -> None:
    error = DictApiFailure("dictionary timeout")

    entry = error.to_error_entry(stage="lookup_dictionary_meanings", candidate_id="candidate-001")

    assert isinstance(entry, AnalysisError)
    assert entry.error_code is ErrorCode.DICT_API_FAILURE
    assert entry.stage == "lookup_dictionary_meanings"
    assert entry.candidate_id == "candidate-001"
    assert entry.message == "dictionary timeout"
    assert entry.retryable is True


def test_to_error_entry_sets_utc_timestamp() -> None:
    before = datetime.now(UTC)
    entry = MissingInputFile("missing input").to_error_entry(stage="load_input")
    after = datetime.now(UTC)

    assert entry.timestamp.tzinfo is UTC
    assert before <= entry.timestamp <= after


def test_to_error_entry_defaults_candidate_id_to_none() -> None:
    entry = MissingEnvVar("OPENAI_API_KEY is required").to_error_entry(stage="config")

    assert entry.candidate_id is None
