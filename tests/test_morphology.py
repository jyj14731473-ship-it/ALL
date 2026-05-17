from __future__ import annotations

from collections.abc import Mapping

import pytest

from all_metaphor.config import RuntimeSettings
from all_metaphor.morphology import ANALYZE_MORPHOLOGY_STAGE, analyze_morphology
from all_metaphor.observability import RunObserver
from all_metaphor.schemas import ErrorCode, LexicalUnit


class FakeOkt:
    def __init__(
        self,
        results: Mapping[str, list[tuple[str, str]]],
        failures: set[str] | None = None,
    ) -> None:
        self.results = results
        self.failures = failures or set()
        self.calls: list[tuple[str, bool, bool]] = []

    def pos(
        self,
        phrase: str,
        norm: bool = False,
        stem: bool = False,
    ) -> list[tuple[str, str]]:
        self.calls.append((phrase, norm, stem))
        if phrase in self.failures:
            raise RuntimeError("analysis failed")
        return self.results.get(phrase, [])


@pytest.fixture
def units() -> list[LexicalUnit]:
    return [
        LexicalUnit(
            unit_id="unit-000001",
            surface="권리의",
            lemma=None,
            pos=None,
            start_char=0,
            end_char=3,
            sentence_id="sentence-000001",
            local_context="권리의 성립",
            local_context_char_count=6,
            is_candidate=True,
            filter_reason=None,
        ),
        LexicalUnit(
            unit_id="unit-000002",
            surface="따랐다",
            lemma=None,
            pos=None,
            start_char=4,
            end_char=7,
            sentence_id="sentence-000001",
            local_context="원칙을 따랐다",
            local_context_char_count=8,
            is_candidate=True,
            filter_reason=None,
        ),
    ]


def test_analyze_morphology_attaches_noun_lemma_and_pos(units: list[LexicalUnit]) -> None:
    analyzer = FakeOkt({"권리의": [("권리", "Noun"), ("의", "Josa")]})

    analyzed = analyze_morphology([units[0]], analyzer=analyzer)

    assert analyzed[0].lemma == "권리"
    assert analyzed[0].pos == "Noun"
    assert analyzer.calls == [("권리의", False, True)]


def test_analyze_morphology_attaches_verb_stem(units: list[LexicalUnit]) -> None:
    analyzer = FakeOkt({"따랐다": [("따르다", "Verb")]})

    analyzed = analyze_morphology([units[1]], analyzer=analyzer)

    assert analyzed[0].lemma == "따르다"
    assert analyzed[0].pos == "Verb"


def test_analyze_morphology_combines_content_morphemes(units: list[LexicalUnit]) -> None:
    analyzer = FakeOkt({"성립하였다": [("성립", "Noun"), ("하다", "Verb")]})
    unit = units[0].model_copy(update={"surface": "성립하였다"})

    analyzed = analyze_morphology([unit], analyzer=analyzer)

    assert analyzed[0].lemma == "성립하다"
    assert analyzed[0].pos == "Verb"


def test_analyze_morphology_uses_pos_priority(units: list[LexicalUnit]) -> None:
    analyzer = FakeOkt({"빠르게": [("빠르다", "Adjective"), ("게", "Adverb")]})
    unit = units[0].model_copy(update={"surface": "빠르게"})

    analyzed = analyze_morphology([unit], analyzer=analyzer)

    assert analyzed[0].lemma == "빠르다게"
    assert analyzed[0].pos == "Adjective"


def test_analyze_morphology_keeps_non_content_pos_without_lemma(units: list[LexicalUnit]) -> None:
    analyzer = FakeOkt({"의": [("의", "Josa")]})
    unit = units[0].model_copy(update={"surface": "의"})

    analyzed = analyze_morphology([unit], analyzer=analyzer)

    assert analyzed[0].lemma is None
    assert analyzed[0].pos == "Josa"


def test_analyze_morphology_handles_empty_analysis(units: list[LexicalUnit]) -> None:
    analyzer = FakeOkt({"권리의": []})

    analyzed = analyze_morphology([units[0]], analyzer=analyzer)

    assert analyzed[0].lemma is None
    assert analyzed[0].pos is None


def test_analyze_morphology_skips_failed_unit_and_records_error(units: list[LexicalUnit]) -> None:
    analyzer = FakeOkt(
        {
            "권리의": [("권리", "Noun"), ("의", "Josa")],
            "따랐다": [("따르다", "Verb")],
        },
        failures={"권리의"},
    )
    error_entries = []

    analyzed = analyze_morphology(units, analyzer=analyzer, error_entries=error_entries)

    assert [unit.unit_id for unit in analyzed] == ["unit-000002"]
    assert len(error_entries) == 1
    assert error_entries[0].error_code is ErrorCode.KONLPY_ANALYSIS_FAILURE
    assert error_entries[0].stage == ANALYZE_MORPHOLOGY_STAGE
    assert "unit-000001" in error_entries[0].message


def test_analyze_morphology_logs_failed_unit(units: list[LexicalUnit]) -> None:
    analyzer = FakeOkt({"권리의": [("권리", "Noun")]}, failures={"권리의"})
    settings = RuntimeSettings(
        openai_api_key="test-openai-key",
        openai_model="test-model",
        krdict_api_key="test-krdict-key",
    )
    observer = RunObserver(settings, run_id="run-morphology")

    analyzed = analyze_morphology([units[0]], analyzer=analyzer, observer=observer)

    assert analyzed == []


@pytest.mark.integration
def test_analyze_morphology_with_real_okt_smoke(units: list[LexicalUnit]) -> None:
    try:
        from konlpy.tag import Okt

        analyzer = Okt()
    except Exception as exc:
        pytest.skip(f"KonLPy Okt unavailable: {exc}")

    analyzed = analyze_morphology([units[0]], analyzer=analyzer)

    assert len(analyzed) == 1
    assert analyzed[0].pos is not None
