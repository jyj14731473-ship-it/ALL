"""KonLPy Okt morphology analysis for lexical units."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol

from all_metaphor.errors import KonlpyAnalysisFailure
from all_metaphor.observability import RunObserver
from all_metaphor.schemas import AnalysisError, LexicalUnit

CONTENT_POS_PRIORITY: tuple[str, ...] = ("Verb", "Adjective", "Noun", "Adverb")
CONTENT_POS_TAGS: frozenset[str] = frozenset(CONTENT_POS_PRIORITY)
ANALYZE_MORPHOLOGY_STAGE = "analyze_morphology"


class OktLike(Protocol):
    """Minimal protocol for KonLPy's Okt analyzer."""

    def pos(
        self,
        phrase: str,
        norm: bool = False,
        stem: bool = False,
    ) -> list[tuple[str, str]]:
        """Return `(morpheme, POS)` pairs for a phrase."""


_OKT_ANALYZER: OktLike | None = None


def analyze_morphology(
    units: list[LexicalUnit],
    *,
    analyzer: OktLike | None = None,
    observer: RunObserver | None = None,
    error_entries: list[AnalysisError] | None = None,
) -> list[LexicalUnit]:
    """Attach representative lemma and POS to lexical units using KonLPy Okt.

    A KonLPy failure for one lexical unit is recorded and skipped without
    stopping analysis of the remaining units.
    """
    active_analyzer = analyzer or _get_default_analyzer()
    analyzed_units: list[LexicalUnit] = []
    for unit in units:
        try:
            morphemes = active_analyzer.pos(unit.surface, norm=False, stem=True)
        except Exception as exc:
            error = KonlpyAnalysisFailure(
                f"KonLPy Okt analysis failed for unit_id={unit.unit_id}: {exc}"
            )
            if error_entries is not None:
                error_entries.append(error.to_error_entry(stage=ANALYZE_MORPHOLOGY_STAGE))
            if observer is not None:
                observer.log_event(
                    "unit_error",
                    stage=ANALYZE_MORPHOLOGY_STAGE,
                    metadata={
                        "unit_id": unit.unit_id,
                        "error_code": error.error_code.value,
                    },
                )
            continue

        lemma, pos = _select_representative_analysis(morphemes)
        analyzed_units.append(unit.model_copy(update={"lemma": lemma, "pos": pos}))
    return analyzed_units


def _get_default_analyzer() -> OktLike:
    global _OKT_ANALYZER  # noqa: PLW0603
    if _OKT_ANALYZER is None:
        from konlpy.tag import Okt

        _OKT_ANALYZER = Okt()
    return _OKT_ANALYZER


def _select_representative_analysis(
    morphemes: Sequence[tuple[str, str]],
) -> tuple[str | None, str | None]:
    if not morphemes:
        return None, None

    content_morphemes = [(morpheme, pos) for morpheme, pos in morphemes if pos in CONTENT_POS_TAGS]
    if not content_morphemes:
        return None, morphemes[0][1]

    representative_pos = _representative_pos(content_morphemes)
    lemma = "".join(morpheme for morpheme, _pos in content_morphemes)
    return lemma, representative_pos


def _representative_pos(content_morphemes: Sequence[tuple[str, str]]) -> str:
    content_pos_tags = {pos for _morpheme, pos in content_morphemes}
    for pos in CONTENT_POS_PRIORITY:
        if pos in content_pos_tags:
            return pos
    return content_morphemes[0][1]


__all__ = [
    "ANALYZE_MORPHOLOGY_STAGE",
    "CONTENT_POS_PRIORITY",
    "CONTENT_POS_TAGS",
    "OktLike",
    "analyze_morphology",
]
