"""Lightweight structured logging and metrics for ALL_Metaphor runs."""

from __future__ import annotations

import json
import logging
from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from time import perf_counter
from uuid import uuid4

from all_metaphor.config import LogLevel, RuntimeSettings
from all_metaphor.errors import AllMetaphorError
from all_metaphor.schemas import ContextWindow, RunMetadata, TokenUsage

_LOGGER_NAME = "all_metaphor.observability"
_LOG_LEVELS: dict[LogLevel, int] = {
    "DEBUG": logging.DEBUG,
    "INFO": logging.INFO,
    "WARNING": logging.WARNING,
    "ERROR": logging.ERROR,
    "CRITICAL": logging.CRITICAL,
}
_SENSITIVE_KEY_MARKERS = (
    "api_key",
    "secret",
    "password",
    "credential",
    "access_token",
    "refresh_token",
    "bearer",
)
_TEXT_KEY_MARKERS = (
    "raw_text",
    "document_text",
    "judgment_text",
    "full_text",
)


@dataclass(slots=True)
class RunMetrics:
    """Mutable counters collected during one pipeline run."""

    input_file_path: str | None = None
    character_count: int = 0
    lexical_unit_count: int = 0
    candidate_count: int = 0
    filtered_candidate_count: int = 0
    dictionary_lookup_count: int = 0
    llm_request_count: int = 0
    rdf_triple_count: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    dictionary_api_failures: int = 0
    llm_validation_failures: int = 0
    skipped_candidates: int = 0
    unresolved_candidates: int = 0


class RunObserver:
    """Run-scoped observer for JSON logging and pipeline metrics."""

    def __init__(
        self,
        settings: RuntimeSettings,
        *,
        run_id: str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.settings = settings
        self.run_id = run_id or str(uuid4())
        self.started_at = datetime.now(UTC)
        self.metrics = RunMetrics()
        self._logger = logger or logging.getLogger(_LOGGER_NAME)
        self._logger.setLevel(_LOG_LEVELS[settings.log_level])

    @contextmanager
    def stage(
        self,
        stage: str,
        metadata: Mapping[str, object] | None = None,
    ) -> Iterator[None]:
        """Log start/end events for one pipeline stage and re-raise errors."""
        started = perf_counter()
        self.log_event("stage_start", stage=stage, metadata=metadata)
        try:
            yield
        except Exception as exc:
            duration_ms = self._duration_ms(started)
            error_code = exc.error_code.value if isinstance(exc, AllMetaphorError) else None
            self._emit_event(
                "stage_error",
                stage=stage,
                metadata=metadata,
                duration_ms=duration_ms,
                error_type=type(exc).__name__,
                error_code=error_code,
            )
            raise
        self._emit_event(
            "stage_end",
            stage=stage,
            metadata=metadata,
            duration_ms=self._duration_ms(started),
        )

    def log_event(
        self,
        event: str,
        *,
        stage: str | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> None:
        """Log one JSON event without including raw text or secrets."""
        self._emit_event(event, stage=stage, metadata=metadata)

    def set_input_file_path(self, path: str | Path) -> None:
        self.metrics.input_file_path = str(path)

    def set_character_count(self, count: int) -> None:
        _require_non_negative(count, "character_count")
        self.metrics.character_count = count

    def set_lexical_unit_count(self, count: int) -> None:
        _require_non_negative(count, "lexical_unit_count")
        self.metrics.lexical_unit_count = count

    def set_candidate_count(self, count: int) -> None:
        _require_non_negative(count, "candidate_count")
        self.metrics.candidate_count = count

    def set_filtered_candidate_count(self, count: int) -> None:
        _require_non_negative(count, "filtered_candidate_count")
        self.metrics.filtered_candidate_count = count

    def increment_dictionary_lookup_count(self, amount: int = 1) -> None:
        self.metrics.dictionary_lookup_count = _increment(
            self.metrics.dictionary_lookup_count,
            amount,
            "dictionary_lookup_count",
        )

    def increment_llm_request_count(self, amount: int = 1) -> None:
        self.metrics.llm_request_count = _increment(
            self.metrics.llm_request_count,
            amount,
            "llm_request_count",
        )

    def set_rdf_triple_count(self, count: int) -> None:
        _require_non_negative(count, "rdf_triple_count")
        self.metrics.rdf_triple_count = count

    def add_token_usage(
        self,
        *,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
        total_tokens: int = 0,
    ) -> None:
        _require_non_negative(prompt_tokens, "prompt_tokens")
        _require_non_negative(completion_tokens, "completion_tokens")
        _require_non_negative(total_tokens, "total_tokens")
        self.metrics.prompt_tokens += prompt_tokens
        self.metrics.completion_tokens += completion_tokens
        self.metrics.total_tokens += total_tokens

    def increment_dictionary_api_failures(self, amount: int = 1) -> None:
        self.metrics.dictionary_api_failures = _increment(
            self.metrics.dictionary_api_failures,
            amount,
            "dictionary_api_failures",
        )

    def increment_llm_validation_failures(self, amount: int = 1) -> None:
        self.metrics.llm_validation_failures = _increment(
            self.metrics.llm_validation_failures,
            amount,
            "llm_validation_failures",
        )

    def increment_skipped_candidates(self, amount: int = 1) -> None:
        self.metrics.skipped_candidates = _increment(
            self.metrics.skipped_candidates,
            amount,
            "skipped_candidates",
        )

    def increment_unresolved_candidates(self, amount: int = 1) -> None:
        self.metrics.unresolved_candidates = _increment(
            self.metrics.unresolved_candidates,
            amount,
            "unresolved_candidates",
        )

    def finalize(self, input_path: str | None = None) -> RunMetadata:
        """Build run metadata for the intermediate JSON document."""
        return RunMetadata(
            run_id=self.run_id,
            started_at=self.started_at,
            completed_at=datetime.now(UTC),
            input_path=input_path or self.metrics.input_file_path or "",
            openai_model=self.settings.openai_model,
            openai_temperature=0.0,
            openai_seed=None,
            context_window=ContextWindow(),
            token_usage=TokenUsage(
                prompt_tokens=self.metrics.prompt_tokens,
                completion_tokens=self.metrics.completion_tokens,
                total_tokens=self.metrics.total_tokens,
            ),
        )

    @staticmethod
    def _duration_ms(started: float) -> float:
        return round((perf_counter() - started) * 1000, 3)

    def _emit_event(
        self,
        event: str,
        *,
        stage: str | None = None,
        metadata: Mapping[str, object] | None = None,
        duration_ms: float | None = None,
        error_type: str | None = None,
        error_code: str | None = None,
    ) -> None:
        record: dict[str, object] = {
            "event": event,
            "run_id": self.run_id,
            "timestamp": datetime.now(UTC).isoformat(),
            "metadata": _sanitize_metadata(metadata or {}),
        }
        if stage is not None:
            record["stage"] = stage
        if duration_ms is not None:
            record["duration_ms"] = duration_ms
        if error_type is not None:
            record["error_type"] = error_type
        if error_code is not None:
            record["error_code"] = error_code
        self._logger.info(json.dumps(record, ensure_ascii=False, sort_keys=True))


def _require_non_negative(value: int, name: str) -> None:
    if value < 0:
        raise ValueError(f"{name} must be non-negative")


def _increment(current: int, amount: int, name: str) -> int:
    _require_non_negative(amount, name)
    return current + amount


def _sanitize_metadata(metadata: Mapping[str, object]) -> dict[str, object]:
    sanitized: dict[str, object] = {}
    for key, value in metadata.items():
        if _should_redact_key(key):
            sanitized[key] = "[REDACTED]"
        else:
            sanitized[key] = _sanitize_value(value)
    return sanitized


def _sanitize_value(value: object) -> object:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return _sanitize_metadata({str(key): item for key, item in value.items()})
    if isinstance(value, list | tuple):
        return [_sanitize_value(item) for item in value]
    return str(value)


def _should_redact_key(key: str) -> bool:
    normalized = key.lower()
    if normalized == "key" or normalized.endswith("_key"):
        return True
    return any(marker in normalized for marker in (*_SENSITIVE_KEY_MARKERS, *_TEXT_KEY_MARKERS))


__all__ = [
    "RunMetrics",
    "RunObserver",
]
