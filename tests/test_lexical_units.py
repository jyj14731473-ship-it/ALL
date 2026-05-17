from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import pytest

from all_metaphor.config import RuntimeSettings
from all_metaphor.lexical_units import (
    MAX_CONTEXT_CHARACTERS,
    MAX_CONTEXT_WINDOW,
    build_local_context,
    segment_lexical_units,
)
from all_metaphor.observability import RunObserver
from all_metaphor.schemas import LexicalUnit


@dataclass(frozen=True)
class FakeLoadedDocument:
    raw_text: str
    source_file: Path = Path("judgment.txt")

    @property
    def character_count(self) -> int:
        return len(self.raw_text)


def _assert_offsets(text: str, units: list[LexicalUnit]) -> None:
    for unit in units:
        assert text[unit.start_char : unit.end_char] == unit.surface


def test_segment_lexical_units_splits_on_whitespace() -> None:
    text = "권리의 성립 여부를 판단한다."
    units = segment_lexical_units(FakeLoadedDocument(text))

    assert [unit.surface for unit in units] == ["권리의", "성립", "여부를", "판단한다."]
    _assert_offsets(text, units)


def test_segment_lexical_units_preserves_offsets_with_multiple_spaces() -> None:
    text = "원고는   청구를  제기하였다."
    units = segment_lexical_units(FakeLoadedDocument(text))

    assert [unit.surface for unit in units] == ["원고는", "청구를", "제기하였다."]
    assert [unit.start_char for unit in units] == [0, 6, 11]
    _assert_offsets(text, units)


def test_segment_lexical_units_preserves_offsets_with_newlines_and_tabs() -> None:
    text = "제1항은\n다음과\t같다."
    units = segment_lexical_units(FakeLoadedDocument(text))

    assert [unit.surface for unit in units] == ["제1항은", "다음과", "같다."]
    _assert_offsets(text, units)


def test_segment_lexical_units_keeps_punctuation_attached_to_surface() -> None:
    text = "피고는 주장하였다. 원고는 반박하였다."
    units = segment_lexical_units(FakeLoadedDocument(text))

    assert units[1].surface == "주장하였다."
    assert units[-1].surface == "반박하였다."
    _assert_offsets(text, units)


def test_segment_lexical_units_assigns_sentence_ids_after_terminal_punctuation() -> None:
    text = "첫 문장이다. 둘째인가? 셋째다! 넷째다"
    units = segment_lexical_units(FakeLoadedDocument(text))

    assert [unit.sentence_id for unit in units] == [
        "sentence-000001",
        "sentence-000001",
        "sentence-000002",
        "sentence-000003",
        "sentence-000004",
    ]
    _assert_offsets(text, units)


def test_segment_lexical_units_assigns_sentence_ids_with_closing_quote() -> None:
    text = '그는 "아니다." 다음 문장이다.'
    units = segment_lexical_units(FakeLoadedDocument(text))

    assert [unit.surface for unit in units] == ["그는", '"아니다."', "다음", "문장이다."]
    assert [unit.sentence_id for unit in units] == [
        "sentence-000001",
        "sentence-000001",
        "sentence-000002",
        "sentence-000002",
    ]
    _assert_offsets(text, units)


def test_segment_lexical_units_does_not_split_latin_dotted_abbreviation() -> None:
    text = "U.S.A. 기준을 적용한다. 다음"
    units = segment_lexical_units(FakeLoadedDocument(text))

    assert [unit.sentence_id for unit in units] == [
        "sentence-000001",
        "sentence-000001",
        "sentence-000001",
        "sentence-000002",
    ]
    _assert_offsets(text, units)


def test_segment_lexical_units_skips_blank_lines() -> None:
    text = "\n\n  첫문장이다.\n\n\t둘째다."
    units = segment_lexical_units(FakeLoadedDocument(text))

    assert [unit.surface for unit in units] == ["첫문장이다.", "둘째다."]
    _assert_offsets(text, units)


def test_segment_lexical_units_initializes_pre_morphology_fields() -> None:
    units = segment_lexical_units(FakeLoadedDocument("성립 여부"))

    assert units[0].lemma is None
    assert units[0].pos is None
    assert units[0].is_candidate is True
    assert units[0].filter_reason is None


def test_build_local_context_uses_window_around_target() -> None:
    units = segment_lexical_units(FakeLoadedDocument("하나 둘 셋 넷 다섯"), context_window=1)

    assert build_local_context(units, target_idx=2, window=1) == "둘 셋 넷"


def test_build_local_context_limits_to_100_characters() -> None:
    text = " ".join(["가나다라마바사아자차"] * 20)
    units = segment_lexical_units(FakeLoadedDocument(text), context_window=10)

    context = build_local_context(units, target_idx=10, window=10)

    assert len(context) <= MAX_CONTEXT_CHARACTERS
    assert units[10].surface in context


def test_build_local_context_truncates_long_target_surface() -> None:
    text = "가" * 120
    units = segment_lexical_units(FakeLoadedDocument(text))

    context = build_local_context(units, target_idx=0)

    assert context == "가" * MAX_CONTEXT_CHARACTERS


def test_build_local_context_rejects_window_above_max() -> None:
    units = segment_lexical_units(FakeLoadedDocument("하나 둘 셋"))

    with pytest.raises(ValueError):
        build_local_context(units, target_idx=0, window=MAX_CONTEXT_WINDOW + 1)


def test_segment_lexical_units_rejects_window_above_max() -> None:
    with pytest.raises(ValueError):
        segment_lexical_units(
            FakeLoadedDocument("하나 둘 셋"),
            context_window=MAX_CONTEXT_WINDOW + 1,
        )


def test_build_local_context_rejects_out_of_range_target() -> None:
    units = segment_lexical_units(FakeLoadedDocument("하나 둘 셋"))

    with pytest.raises(IndexError):
        build_local_context(units, target_idx=3)


def test_segment_lexical_units_updates_observer_count() -> None:
    settings = RuntimeSettings(
        openai_api_key="test-openai-key",
        openai_model="test-model",
        krdict_api_key="test-krdict-key",
    )
    observer = RunObserver(settings)

    segment_lexical_units(FakeLoadedDocument("하나 둘 셋"), observer=observer)

    assert observer.metrics.lexical_unit_count == 3
