from __future__ import annotations

import json
import logging

import pytest

from all_metaphor.candidate_filter import (
    FILTER_CANDIDATES_STAGE,
    FilterReason,
    filter_candidates,
    summarize_candidate_filter,
)
from all_metaphor.config import RuntimeSettings
from all_metaphor.observability import RunObserver
from all_metaphor.schemas import LexicalUnit


def make_unit(
    unit_id: str,
    surface: str,
    *,
    lemma: str | None,
    pos: str | None,
    start_char: int = 0,
) -> LexicalUnit:
    return LexicalUnit(
        unit_id=unit_id,
        surface=surface,
        lemma=lemma,
        pos=pos,
        start_char=start_char,
        end_char=start_char + len(surface),
        sentence_id="sentence-000001",
        local_context=surface,
        local_context_char_count=len(surface),
        is_candidate=True,
        filter_reason=None,
    )


@pytest.mark.parametrize(
    "pos",
    [
        "Josa",
        "Eomi",
        "PreEomi",
        "Suffix",
        "Punctuation",
        "Number",
        "Foreign",
        "Alpha",
        "Unknown",
        "Determiner",
        "Conjunction",
        "Exclamation",
    ],
)
def test_filter_candidates_excludes_pos_tags(pos: str) -> None:
    unit = make_unit("unit-000001", "토큰", lemma="토큰", pos=pos)

    filtered = filter_candidates([unit])

    assert filtered[0].is_candidate is False
    assert filtered[0].filter_reason == FilterReason.EXCLUDED_POS.value


def test_filter_candidates_excludes_missing_pos() -> None:
    unit = make_unit("unit-000001", "권리", lemma="권리", pos=None)

    filtered = filter_candidates([unit])

    assert filtered[0].is_candidate is False
    assert filtered[0].filter_reason == FilterReason.MISSING_POS.value


@pytest.mark.parametrize("pos", ["Noun", "Verb", "Adjective", "Adverb"])
def test_filter_candidates_keeps_content_pos(pos: str) -> None:
    unit = make_unit("unit-000001", "흘렀다", lemma="흐르다", pos=pos)

    filtered = filter_candidates([unit])

    assert filtered[0].is_candidate is True
    assert filtered[0].filter_reason is None


def test_filter_candidates_keeps_single_character_noun_but_excludes_other_single_character_pos() -> (
    None
):
    noun = make_unit("unit-000001", "법", lemma="법", pos="Noun", start_char=0)
    verb = make_unit("unit-000002", "가", lemma="가", pos="Verb", start_char=2)

    filtered = filter_candidates([noun, verb])

    assert filtered[0].is_candidate is True
    assert filtered[0].filter_reason is None
    assert filtered[1].is_candidate is False
    assert filtered[1].filter_reason == FilterReason.SINGLE_CHARACTER_NON_NOUN.value


@pytest.mark.parametrize(
    ("surface", "lemma"),
    [
        ("제3조", "제3조"),
        ("1990년", "1990년"),
        ("문언", "문언2"),
    ],
)
def test_filter_candidates_excludes_tokens_containing_numbers(surface: str, lemma: str) -> None:
    unit = make_unit("unit-000001", surface, lemma=lemma, pos="Noun")

    filtered = filter_candidates([unit])

    assert filtered[0].is_candidate is False
    assert filtered[0].filter_reason == FilterReason.CONTAINS_NUMBER.value


@pytest.mark.parametrize(
    ("surface", "lemma", "pos"),
    [
        ("주문", "주문", "Noun"),
        ("이유", "이유", "Noun"),
        ("사건", "사건", "Noun"),
        ("원고는", "원고", "Noun"),
        ("피고가", "피고", "Noun"),
        ("한다", "하다", "Verb"),
        ("이다", "이다", "Adjective"),
        ("있다", "있다", "Adjective"),
    ],
)
def test_filter_candidates_excludes_legal_boilerplate(
    surface: str,
    lemma: str,
    pos: str,
) -> None:
    unit = make_unit("unit-000001", surface, lemma=lemma, pos=pos)

    filtered = filter_candidates([unit])

    assert filtered[0].is_candidate is False
    assert filtered[0].filter_reason == FilterReason.LEGAL_BOILERPLATE.value


def test_filter_candidates_keeps_quoted_or_parenthesized_text_by_default() -> None:
    quoted = make_unit("unit-000001", '"권리"', lemma='"권리"', pos="Noun", start_char=0)
    parenthesized = make_unit("unit-000002", "(의무)", lemma="(의무)", pos="Noun", start_char=5)

    filtered = filter_candidates([quoted, parenthesized])

    assert [unit.is_candidate for unit in filtered] == [True, True]
    assert [unit.filter_reason for unit in filtered] == [None, None]


def test_filter_candidates_preserves_excluded_units_and_input_order() -> None:
    units = [
        make_unit("unit-000001", "권리", lemma="권리", pos="Noun", start_char=0),
        make_unit("unit-000002", "의", lemma=None, pos="Josa", start_char=3),
        make_unit("unit-000003", "흘렀다", lemma="흐르다", pos="Verb", start_char=5),
    ]

    filtered = filter_candidates(units)

    assert [unit.unit_id for unit in filtered] == ["unit-000001", "unit-000002", "unit-000003"]
    assert [unit.start_char for unit in filtered] == [0, 3, 5]
    assert len(filtered) == len(units)
    assert filtered[1].is_candidate is False


def test_filter_candidates_is_idempotent() -> None:
    units = [
        make_unit("unit-000001", "권리", lemma="권리", pos="Noun", start_char=0),
        make_unit("unit-000002", "제3조", lemma="제3조", pos="Noun", start_char=3),
    ]

    first = filter_candidates(units)
    second = filter_candidates(first)

    assert [unit.model_dump() for unit in second] == [unit.model_dump() for unit in first]


def test_filter_candidates_does_not_mutate_input_units() -> None:
    unit = make_unit("unit-000001", "의", lemma=None, pos="Josa")

    filtered = filter_candidates([unit])

    assert unit.is_candidate is True
    assert unit.filter_reason is None
    assert filtered[0].is_candidate is False
    assert filtered[0].filter_reason == FilterReason.EXCLUDED_POS.value


def test_summarize_candidate_filter_counts_reasons() -> None:
    units = filter_candidates(
        [
            make_unit("unit-000001", "권리", lemma="권리", pos="Noun", start_char=0),
            make_unit("unit-000002", "의", lemma=None, pos="Josa", start_char=3),
            make_unit("unit-000003", "제3조", lemma="제3조", pos="Noun", start_char=5),
            make_unit("unit-000004", "피고", lemma="피고", pos="Noun", start_char=9),
        ]
    )

    stats = summarize_candidate_filter(units)

    assert stats.input_unit_count == 4
    assert stats.candidate_count == 1
    assert stats.filtered_count == 3
    assert stats.filter_reason_counts == {
        FilterReason.CONTAINS_NUMBER.value: 1,
        FilterReason.EXCLUDED_POS.value: 1,
        FilterReason.LEGAL_BOILERPLATE.value: 1,
    }


def test_filter_candidates_records_observability_metrics(caplog: pytest.LogCaptureFixture) -> None:
    settings = RuntimeSettings(
        openai_api_key="test-openai-key",
        openai_model="test-model",
        krdict_api_key="test-krdict-key",
    )
    observer = RunObserver(settings, run_id="run-candidate-filter")
    caplog.set_level(logging.INFO, logger="all_metaphor.observability")

    filter_candidates(
        [
            make_unit("unit-000001", "권리", lemma="권리", pos="Noun", start_char=0),
            make_unit("unit-000002", "의", lemma=None, pos="Josa", start_char=3),
            make_unit("unit-000003", "제3조", lemma="제3조", pos="Noun", start_char=5),
        ],
        observer=observer,
    )

    assert observer.metrics.candidate_count == 1
    assert observer.metrics.filtered_candidate_count == 2
    assert observer.metrics.skipped_candidates == 2

    records = [json.loads(record.message) for record in caplog.records]
    summary = next(record for record in records if record["event"] == "candidate_filter_summary")
    assert summary["stage"] == FILTER_CANDIDATES_STAGE
    assert summary["metadata"] == {
        "input_unit_count": 3,
        "candidate_count": 1,
        "filtered_count": 2,
        "filter_reason_counts": {
            FilterReason.CONTAINS_NUMBER.value: 1,
            FilterReason.EXCLUDED_POS.value: 1,
        },
    }


def test_filter_candidates_handles_empty_input() -> None:
    filtered = filter_candidates([])

    assert filtered == []
    assert summarize_candidate_filter(filtered).as_metadata() == {
        "input_unit_count": 0,
        "candidate_count": 0,
        "filtered_count": 0,
        "filter_reason_counts": {},
    }
