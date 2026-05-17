"""Candidate filtering for morphology-analyzed lexical units."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum

from all_metaphor.observability import RunObserver
from all_metaphor.schemas import LexicalUnit

FILTER_CANDIDATES_STAGE = "filter_candidates"


class FilterReason(StrEnum):
    """Stable filter reason strings recorded on excluded lexical units."""

    MISSING_POS = "missing_pos"
    EXCLUDED_POS = "excluded_pos"
    SINGLE_CHARACTER_NON_NOUN = "single_character_non_noun"
    CONTAINS_NUMBER = "contains_number"
    LEGAL_BOILERPLATE = "legal_boilerplate"


INCLUDED_POS_TAGS: frozenset[str] = frozenset(
    {
        "Noun",
        "Verb",
        "Adjective",
        "Adverb",
    }
)
EXCLUDED_POS_TAG_REASONS: dict[str, FilterReason] = {
    "Josa": FilterReason.EXCLUDED_POS,
    "Eomi": FilterReason.EXCLUDED_POS,
    "PreEomi": FilterReason.EXCLUDED_POS,
    "Suffix": FilterReason.EXCLUDED_POS,
    "Punctuation": FilterReason.EXCLUDED_POS,
    "Number": FilterReason.EXCLUDED_POS,
    "Foreign": FilterReason.EXCLUDED_POS,
    "Alpha": FilterReason.EXCLUDED_POS,
    "Unknown": FilterReason.EXCLUDED_POS,
    "Determiner": FilterReason.EXCLUDED_POS,
    "Conjunction": FilterReason.EXCLUDED_POS,
    "Exclamation": FilterReason.EXCLUDED_POS,
}
LEGAL_BOILERPLATE_TERMS: frozenset[str] = frozenset(
    {
        "주문",
        "이유",
        "사건",
        "원고",
        "피고",
    }
)
AUXILIARY_ONLY_TERMS: frozenset[str] = frozenset(
    {
        "한다",
        "하다",
        "이다",
        "있다",
    }
)
_NUMBER_PATTERN = re.compile(r"\d")


@dataclass(frozen=True, slots=True)
class CandidateFilterStats:
    """Candidate filter summary for observability metadata."""

    input_unit_count: int
    candidate_count: int
    filtered_count: int
    filter_reason_counts: dict[str, int]

    def as_metadata(self) -> dict[str, object]:
        return {
            "input_unit_count": self.input_unit_count,
            "candidate_count": self.candidate_count,
            "filtered_count": self.filtered_count,
            "filter_reason_counts": dict(self.filter_reason_counts),
        }


def filter_candidates(
    units: list[LexicalUnit],
    *,
    observer: RunObserver | None = None,
) -> list[LexicalUnit]:
    """Mark metaphor candidates while preserving lexical-unit order and content."""
    filtered_units = [
        unit.model_copy(update=_candidate_update(_filter_reason_for(unit))) for unit in units
    ]
    stats = summarize_candidate_filter(filtered_units)
    if observer is not None:
        observer.set_candidate_count(stats.candidate_count)
        observer.set_filtered_candidate_count(stats.filtered_count)
        observer.increment_skipped_candidates(stats.filtered_count)
        observer.log_event(
            "candidate_filter_summary",
            stage=FILTER_CANDIDATES_STAGE,
            metadata=stats.as_metadata(),
        )
    return filtered_units


def summarize_candidate_filter(units: list[LexicalUnit]) -> CandidateFilterStats:
    """Summarize candidate/filter counts for already-filtered lexical units."""
    reason_counts = Counter(
        unit.filter_reason
        for unit in units
        if not unit.is_candidate and unit.filter_reason is not None
    )
    candidate_count = sum(1 for unit in units if unit.is_candidate)
    filtered_count = len(units) - candidate_count
    return CandidateFilterStats(
        input_unit_count=len(units),
        candidate_count=candidate_count,
        filtered_count=filtered_count,
        filter_reason_counts=dict(sorted(reason_counts.items())),
    )


def _candidate_update(reason: FilterReason | None) -> dict[str, object]:
    if reason is None:
        return {"is_candidate": True, "filter_reason": None}
    return {"is_candidate": False, "filter_reason": reason.value}


def _filter_reason_for(unit: LexicalUnit) -> FilterReason | None:
    pos = unit.pos
    if pos is None or pos.strip() == "":
        return FilterReason.MISSING_POS
    if pos in EXCLUDED_POS_TAG_REASONS:
        return EXCLUDED_POS_TAG_REASONS[pos]
    if pos not in INCLUDED_POS_TAGS:
        return FilterReason.EXCLUDED_POS

    lookup_key = _lookup_key(unit)
    if _contains_number(unit.surface) or _contains_number(lookup_key):
        return FilterReason.CONTAINS_NUMBER
    if _is_legal_boilerplate(unit, lookup_key):
        return FilterReason.LEGAL_BOILERPLATE
    if len(lookup_key) == 1 and pos != "Noun":
        return FilterReason.SINGLE_CHARACTER_NON_NOUN
    return None


def _lookup_key(unit: LexicalUnit) -> str:
    lemma = unit.lemma.strip() if unit.lemma is not None else ""
    surface = unit.surface.strip()
    return lemma or surface


def _contains_number(value: str) -> bool:
    return _NUMBER_PATTERN.search(value) is not None


def _is_legal_boilerplate(unit: LexicalUnit, lookup_key: str) -> bool:
    terms = {unit.surface.strip(), lookup_key}
    return bool(terms & LEGAL_BOILERPLATE_TERMS) or bool(terms & AUXILIARY_ONLY_TERMS)


__all__ = [
    "AUXILIARY_ONLY_TERMS",
    "CandidateFilterStats",
    "EXCLUDED_POS_TAG_REASONS",
    "FILTER_CANDIDATES_STAGE",
    "FilterReason",
    "INCLUDED_POS_TAGS",
    "LEGAL_BOILERPLATE_TERMS",
    "filter_candidates",
    "summarize_candidate_filter",
]
