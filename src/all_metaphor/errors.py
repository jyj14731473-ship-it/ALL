"""Project-specific exceptions for ALL_Metaphor."""

from __future__ import annotations

from datetime import UTC, datetime

from all_metaphor.schemas import AnalysisError, ErrorCode


class AllMetaphorError(Exception):
    """Base exception for all ALL_Metaphor project errors."""

    error_code: ErrorCode
    message: str
    retryable: bool

    def __init__(
        self,
        message: str,
        *,
        error_code: ErrorCode,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.retryable = retryable

    def to_error_entry(self, stage: str, candidate_id: str | None = None) -> AnalysisError:
        """Convert this exception into an intermediate JSON error entry."""
        return AnalysisError(
            error_code=self.error_code,
            stage=stage,
            candidate_id=candidate_id,
            message=self.message,
            retryable=self.retryable,
            timestamp=datetime.now(UTC),
        )


class DictApiFailure(AllMetaphorError):  # noqa: N818
    """Dictionary API failure."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.DICT_API_FAILURE,
            retryable=True,
        )


class LlmValidationError(AllMetaphorError):
    """LLM response validation failure."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.LLM_VALIDATION_ERROR,
        )


class IntermediateValidationError(AllMetaphorError):
    """Intermediate validation failure."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.VALIDATION_ERROR,
        )


class KonlpyAnalysisFailure(AllMetaphorError):  # noqa: N818
    """KonLPy Okt analysis failure."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.KONLPY_ANALYSIS_FAILURE,
        )


class OpenAiApiFailure(AllMetaphorError):  # noqa: N818
    """OpenAI API failure."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.OPENAI_API_FAILURE,
            retryable=True,
        )


class RdfSerializationFailure(AllMetaphorError):  # noqa: N818
    """RDF serialization failure."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.RDF_SERIALIZATION_FAILURE,
        )


class OutputWriteError(AllMetaphorError):
    """Output file write failure."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.OUTPUT_WRITE_ERROR,
        )


class MissingEnvVar(AllMetaphorError):  # noqa: N818
    """Required environment variable is missing."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.MISSING_ENV_VAR,
        )


class InvalidFileExtension(AllMetaphorError):  # noqa: N818
    """Input file extension is invalid."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.INVALID_FILE_EXTENSION,
        )


class MissingInputFile(AllMetaphorError):  # noqa: N818
    """Input file does not exist."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.MISSING_INPUT_FILE,
        )


class EmptyInputFile(AllMetaphorError):  # noqa: N818
    """Input file exists but contains no text."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.EMPTY_INPUT_FILE,
        )


class InvalidTextEncoding(AllMetaphorError):  # noqa: N818
    """Input file cannot be decoded as UTF-8 text."""

    def __init__(self, message: str) -> None:
        super().__init__(
            message,
            error_code=ErrorCode.INVALID_TEXT_ENCODING,
        )


__all__ = [
    "AllMetaphorError",
    "DictApiFailure",
    "EmptyInputFile",
    "InvalidFileExtension",
    "InvalidTextEncoding",
    "KonlpyAnalysisFailure",
    "LlmValidationError",
    "MissingEnvVar",
    "MissingInputFile",
    "OpenAiApiFailure",
    "OutputWriteError",
    "RdfSerializationFailure",
    "IntermediateValidationError",
]
