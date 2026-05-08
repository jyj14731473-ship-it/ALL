"""Mecab analyzer adapters.

The preferred runtime backend is python-mecab-ko. If it is not installed, the
adapter tries konlpy.tag.Mecab. The final fallback is intentionally small and is
only meant to make tests and local smoke runs deterministic without native Mecab
dependencies.
"""

from __future__ import annotations

from typing import Protocol

MorphPart = tuple[str, str] | tuple[str, str, str] | tuple[str, str, str, str]


class MorphAnalyzer(Protocol):
    def pos(self, sentence: str) -> list[MorphPart]:
        """Return Mecab-like parts, optionally with internal feature hints."""
        ...


class PythonMecabKoAnalyzer:
    """Adapter for the python-mecab-ko package."""

    def __init__(self) -> None:
        from mecab import MeCab  # type: ignore[import-not-found]

        self._mecab = MeCab()

    def pos(self, sentence: str) -> list[MorphPart]:
        parsed = _normalize_parse_result(self._mecab.parse(sentence))
        if parsed:
            return parsed
        return _normalize_pos_result(self._mecab.pos(sentence))


class KonlpyMecabAnalyzer:
    """Adapter for konlpy.tag.Mecab."""

    def __init__(self) -> None:
        from konlpy.tag import Mecab  # type: ignore[import-not-found]

        self._mecab = Mecab()

    def pos(self, sentence: str) -> list[MorphPart]:
        return _normalize_pos_result(self._mecab.pos(sentence))


class FallbackMecabAnalyzer:
    """Tiny Mecab-like fallback for tests and dependency-light environments."""

    _DERIVED_VERBS = {
        "인정하였다": "인정",
        "침해하였다": "침해",
    }
    _DERIVED_ADJECTIVES = {
        "명백하다": "명백",
        "가능하다": "가능",
    }
    _LIGHT_VERBS = {
        "하였다": "하",
        "했다": "하",
    }
    _PRONOUNS = {"그"}
    _ADVERBS = {"그러나"}
    _JOSA = [
        ("으로", "JKB"),
        ("에서", "JKB"),
        ("에게", "JKB"),
        ("까지", "JX"),
        ("부터", "JX"),
        ("는", "JX"),
        ("은", "JX"),
        ("의", "JKG"),
        ("을", "JKO"),
        ("를", "JKO"),
        ("이", "JKS"),
        ("가", "JKS"),
        ("에", "JKB"),
        ("도", "JX"),
        ("만", "JX"),
        ("와", "JC"),
        ("과", "JC"),
        ("로", "JKB"),
    ]
    _PUNCTUATION_TAGS = {
        ".": "SF",
        "?": "SF",
        "!": "SF",
        ",": "SC",
        ";": "SC",
        ":": "SC",
        "(": "SSO",
        ")": "SSC",
        "[": "SSO",
        "]": "SSC",
    }

    def pos(self, sentence: str) -> list[MorphPart]:
        parts: list[MorphPart] = []
        for eojeol in sentence.split():
            parts.extend(self._analyze_eojeol(eojeol))
        return parts

    def _analyze_eojeol(self, eojeol: str) -> list[MorphPart]:
        token = eojeol.strip()
        if not token:
            return []

        trailing: list[MorphPart] = []
        while token and token[-1] in self._PUNCTUATION_TAGS:
            ch = token[-1]
            trailing.insert(0, (ch, self._PUNCTUATION_TAGS[ch]))
            token = token[:-1]

        parts: list[MorphPart] = []
        if token:
            parts.extend(self._analyze_core(token))
        parts.extend(trailing)
        return parts

    def _analyze_core(self, token: str) -> list[MorphPart]:
        if token in self._DERIVED_VERBS:
            return [(self._DERIVED_VERBS[token], "NNG"), ("하", "XSV"), ("였", "EP"), ("다", "EF")]
        if token in self._DERIVED_ADJECTIVES:
            return [(self._DERIVED_ADJECTIVES[token], "XR"), ("하", "XSA"), ("다", "EF")]
        if token in self._LIGHT_VERBS:
            return [(self._LIGHT_VERBS[token], "VV"), ("였", "EP"), ("다", "EF")]
        if token in self._PRONOUNS:
            return [(token, "NP")]
        if token in self._ADVERBS:
            return [(token, "MAJ")]
        if token.isdigit():
            return [(token, "SN")]

        for josa, tag in self._JOSA:
            if token.endswith(josa) and len(token) > len(josa):
                stem = token[: -len(josa)]
                return [(stem, "NNG"), (josa, tag)]
        return [(token, "NNG")]


def get_default_analyzer() -> MorphAnalyzer:
    """Return the best available Mecab analyzer for the current environment."""
    for analyzer_cls in (PythonMecabKoAnalyzer, KonlpyMecabAnalyzer):
        try:
            return analyzer_cls()
        except Exception:
            continue
    return FallbackMecabAnalyzer()


def _normalize_pos_result(raw_result: object) -> list[MorphPart]:
    normalized: list[MorphPart] = []
    if not isinstance(raw_result, list):
        return normalized
    for item in raw_result:
        if not isinstance(item, (tuple, list)) or len(item) < 2:
            continue
        surface, tag = item[0], item[1]
        normalized.append((str(surface), str(tag)))
    return normalized


def _normalize_parse_result(raw_result: object) -> list[MorphPart]:
    normalized: list[MorphPart] = []
    if not isinstance(raw_result, list):
        return normalized
    for item in raw_result:
        surface = getattr(item, "surface", None)
        feature = getattr(item, "feature", None)
        tag = getattr(feature, "pos", None)
        if surface is None or tag is None:
            continue
        semantic = getattr(feature, "semantic", None)
        expression = getattr(feature, "expression", None)
        normalized.append(
            (
                str(surface),
                str(tag),
                "" if semantic is None else str(semantic),
                "" if expression is None else str(expression),
            )
        )
    return normalized
