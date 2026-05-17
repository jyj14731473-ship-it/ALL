"""Word-level lexical-unit segmentation for Korean judgment text."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Protocol

from all_metaphor.observability import RunObserver
from all_metaphor.schemas import LexicalUnit

DEFAULT_CONTEXT_WINDOW = 10
MAX_CONTEXT_WINDOW = 30
MAX_CONTEXT_CHARACTERS = 100

_TOKEN_PATTERN = re.compile(r"\S+")
_LATIN_DOTTED_ABBREVIATION_PATTERN = re.compile(r"(?:[A-Za-z]\.){2,}")
_SENTENCE_ENDING_CHARACTERS = frozenset({".", "?", "!", "…"})
_TRAILING_CLOSERS = "\"'”’»›)]}〉》」』"


class LoadedDocumentLike(Protocol):
    """Structural input type produced by `io.load_input`."""

    raw_text: str
    source_file: Path
    character_count: int


def segment_lexical_units(
    document: LoadedDocumentLike,
    *,
    context_window: int = DEFAULT_CONTEXT_WINDOW,
    observer: RunObserver | None = None,
) -> list[LexicalUnit]:
    """Segment raw judgment text into word-level lexical units with offsets."""
    _validate_window(context_window)
    units = _build_units_without_context(document.raw_text)
    units_with_context = [
        unit.model_copy(
            update={
                "local_context": build_local_context(units, index, context_window),
                "local_context_char_count": len(build_local_context(units, index, context_window)),
            }
        )
        for index, unit in enumerate(units)
    ]
    if observer is not None:
        observer.set_lexical_unit_count(len(units_with_context))
    return units_with_context


def build_local_context(
    units: list[LexicalUnit],
    target_idx: int,
    window: int = DEFAULT_CONTEXT_WINDOW,
) -> str:
    """Build a bounded local context string around one target lexical unit."""
    _validate_window(window)
    if target_idx < 0 or target_idx >= len(units):
        raise IndexError("target_idx is out of range")

    start = max(0, target_idx - window)
    end = min(len(units), target_idx + window + 1)
    while start <= target_idx < end:
        context = _join_surfaces(units[start:end])
        if len(context) <= MAX_CONTEXT_CHARACTERS:
            return context
        left_distance = target_idx - start
        right_distance = end - target_idx - 1
        if left_distance >= right_distance and start < target_idx:
            start += 1
        elif end - 1 > target_idx:
            end -= 1
        elif start < target_idx:
            start += 1
        else:
            break

    return units[target_idx].surface[:MAX_CONTEXT_CHARACTERS]


def _build_units_without_context(text: str) -> list[LexicalUnit]:
    units: list[LexicalUnit] = []
    sentence_index = 1
    for unit_index, match in enumerate(_TOKEN_PATTERN.finditer(text), start=1):
        surface = match.group(0)
        sentence_id = f"sentence-{sentence_index:06d}"
        units.append(
            LexicalUnit(
                unit_id=f"unit-{unit_index:06d}",
                surface=surface,
                lemma=None,
                pos=None,
                start_char=match.start(),
                end_char=match.end(),
                sentence_id=sentence_id,
                local_context="",
                local_context_char_count=0,
                is_candidate=True,
                filter_reason=None,
            )
        )
        if _is_sentence_ending(surface):
            sentence_index += 1
    return units


def _is_sentence_ending(surface: str) -> bool:
    stripped = surface.rstrip(_TRAILING_CLOSERS)
    if stripped == "":
        return False
    if _LATIN_DOTTED_ABBREVIATION_PATTERN.fullmatch(stripped):
        return False
    return stripped[-1] in _SENTENCE_ENDING_CHARACTERS


def _validate_window(window: int) -> None:
    if window < 0 or window > MAX_CONTEXT_WINDOW:
        raise ValueError(f"window must be between 0 and {MAX_CONTEXT_WINDOW}")


def _join_surfaces(units: list[LexicalUnit]) -> str:
    return " ".join(unit.surface for unit in units)


__all__ = [
    "DEFAULT_CONTEXT_WINDOW",
    "MAX_CONTEXT_CHARACTERS",
    "MAX_CONTEXT_WINDOW",
    "LoadedDocumentLike",
    "build_local_context",
    "segment_lexical_units",
]
