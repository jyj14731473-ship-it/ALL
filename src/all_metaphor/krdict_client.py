"""Standard Korean Language Dictionary API client."""

from __future__ import annotations

import time
import unicodedata
import xml.etree.ElementTree as ET
from collections.abc import Callable
from types import TracebackType
from typing import Protocol, cast
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from all_metaphor.config import RuntimeSettings
from all_metaphor.errors import DictApiFailure
from all_metaphor.schemas import DictionaryMeaning

KRDICT_SEARCH_ENDPOINT = "https://opendict.korean.go.kr/api/search"
DEFAULT_TIMEOUT_SECONDS = 10.0
DEFAULT_MAX_RETRIES = 3
DEFAULT_BACKOFF_INITIAL_SECONDS = 0.5


class BinaryResponse(Protocol):
    """Minimal context-managed binary response returned by urllib."""

    def __enter__(self) -> BinaryResponse:
        """Enter response context."""

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> bool | None:
        """Exit response context."""

    def read(self) -> bytes:
        """Return response body bytes."""


class UrlOpenLike(Protocol):
    """Callable compatible with the urlopen subset used by KrdictClient."""

    def __call__(self, request: Request, *, timeout: float) -> BinaryResponse:
        """Open a prepared request with a per-request timeout."""


class KrdictClient:
    """Lookup dictionary meanings with per-client in-memory caching."""

    def __init__(
        self,
        settings: RuntimeSettings,
        *,
        timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
        max_retries: int = DEFAULT_MAX_RETRIES,
        backoff_initial_seconds: float = DEFAULT_BACKOFF_INITIAL_SECONDS,
        opener: UrlOpenLike | None = None,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        if timeout_seconds <= 0:
            msg = "timeout_seconds must be positive"
            raise ValueError(msg)
        if max_retries < 0:
            msg = "max_retries must be non-negative"
            raise ValueError(msg)
        if backoff_initial_seconds < 0:
            msg = "backoff_initial_seconds must be non-negative"
            raise ValueError(msg)

        self._settings: RuntimeSettings = settings
        self._timeout_seconds: float = timeout_seconds
        self._max_retries: int = max_retries
        self._backoff_initial_seconds: float = backoff_initial_seconds
        self._opener: UrlOpenLike = opener or _default_urlopen
        self._sleep: Callable[[float], None] = sleep
        self._cache: dict[str, tuple[DictionaryMeaning, ...]] = {}

    def lookup(self, lemma: str) -> list[DictionaryMeaning]:
        """Lookup all dictionary senses for one normalized lemma."""
        cache_key = _normalize_lemma(lemma)
        if cache_key == "":
            return []
        if cache_key not in self._cache:
            self._cache[cache_key] = tuple(self._lookup_uncached(cache_key))
        return _copy_meanings(self._cache[cache_key])

    def _lookup_uncached(self, lemma: str) -> list[DictionaryMeaning]:
        attempts = self._max_retries + 1
        last_error: BaseException | None = None
        for attempt_index in range(attempts):
            try:
                return self._fetch_and_parse(lemma)
            except (HTTPError, URLError, TimeoutError, OSError, ET.ParseError) as exc:
                last_error = exc
                if attempt_index == attempts - 1:
                    break
                self._sleep(self._backoff_seconds(attempt_index))

        error_name = type(last_error).__name__ if last_error is not None else "unknown error"
        raise DictApiFailure(
            f"Dictionary API lookup failed for lemma={lemma!r} after {attempts} attempts "
            f"({error_name})"
        )

    def _fetch_and_parse(self, lemma: str) -> list[DictionaryMeaning]:
        request = self._build_request(lemma)
        with self._opener(request, timeout=self._timeout_seconds) as response:
            payload = response.read()
        return _parse_dictionary_meanings(payload)

    def _build_request(self, lemma: str) -> Request:
        params = {
            "q": lemma,
            "key": self._settings.krdict_api_key.get_secret_value(),
            "part": "word",
            "sort": "dict",
            "start": "1",
            "num": "10",
        }
        return Request(
            f"{KRDICT_SEARCH_ENDPOINT}?{urlencode(params)}",
            headers={"User-Agent": "ALL_Metaphor/0.1"},
            method="GET",
        )

    def _backoff_seconds(self, attempt_index: int) -> float:
        return float(self._backoff_initial_seconds * (2**attempt_index))


def _default_urlopen(request: Request, *, timeout: float) -> BinaryResponse:
    return cast(BinaryResponse, urlopen(request, timeout=timeout))


def _normalize_lemma(lemma: str) -> str:
    return unicodedata.normalize("NFC", lemma.strip())


def _parse_dictionary_meanings(payload: bytes) -> list[DictionaryMeaning]:
    root = ET.fromstring(payload)
    meanings: list[DictionaryMeaning] = []
    for sense in _iter_elements_by_local_name(root, "sense"):
        definition = _find_child_text(sense, "definition")
        if definition is None:
            continue
        sense_id = _find_child_text(sense, "sense_no")
        meanings.append(DictionaryMeaning(sense_id=sense_id, definition=definition))
    return meanings


def _iter_elements_by_local_name(root: ET.Element, local_name: str) -> list[ET.Element]:
    return [element for element in root.iter() if _local_name(element.tag) == local_name]


def _find_child_text(element: ET.Element, local_name: str) -> str | None:
    for child in element:
        if _local_name(child.tag) == local_name:
            text = child.text.strip() if child.text is not None else ""
            return text or None
    return None


def _local_name(tag: str) -> str:
    return tag.rsplit("}", maxsplit=1)[-1]


def _copy_meanings(meanings: tuple[DictionaryMeaning, ...]) -> list[DictionaryMeaning]:
    return [meaning.model_copy(deep=True) for meaning in meanings]


__all__ = [
    "DEFAULT_BACKOFF_INITIAL_SECONDS",
    "DEFAULT_MAX_RETRIES",
    "DEFAULT_TIMEOUT_SECONDS",
    "KRDICT_SEARCH_ENDPOINT",
    "BinaryResponse",
    "KrdictClient",
    "UrlOpenLike",
]
