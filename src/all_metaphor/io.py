"""Input loading utilities for ALL_Metaphor."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field

from all_metaphor.config import PROJECT_ROOT
from all_metaphor.errors import (
    EmptyInputFile,
    InvalidFileExtension,
    InvalidTextEncoding,
    MissingInputFile,
)


class LoadedDocument(BaseModel):
    """Loaded UTF-8 judgment text and source metadata."""

    model_config = ConfigDict(extra="forbid")

    raw_text: str = Field(description="Raw UTF-8 judgment text.")
    source_file: Path = Field(description="Resolved source text file path.")
    character_count: int = Field(
        ge=1,
        description="Number of characters in the loaded judgment text.",
    )


def _resolve_input_path(file_path: Path) -> Path:
    if file_path.is_absolute():
        return file_path
    return PROJECT_ROOT / file_path


def load_input(file_path: Path) -> LoadedDocument:
    """Load and validate a non-empty UTF-8 `.txt` judgment document."""
    resolved_path = _resolve_input_path(file_path).resolve()
    if not resolved_path.exists() or not resolved_path.is_file():
        raise MissingInputFile(f"Input file does not exist: {file_path}")
    if resolved_path.suffix.lower() != ".txt":
        raise InvalidFileExtension(f"Input file must have .txt extension: {file_path}")

    try:
        raw_text = resolved_path.read_text(encoding="utf-8")
    except UnicodeDecodeError as exc:
        raise InvalidTextEncoding(f"Input file must be UTF-8 encoded: {file_path}") from exc

    if raw_text.strip() == "":
        raise EmptyInputFile(f"Input file is empty: {file_path}")

    return LoadedDocument(
        raw_text=raw_text,
        source_file=resolved_path,
        character_count=len(raw_text),
    )


__all__ = [
    "LoadedDocument",
    "load_input",
]
