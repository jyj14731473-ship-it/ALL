"""Dictionary helper used by the MIPVU node."""

from __future__ import annotations

from typing import Any

from annotation.dictionary_client import StandardKoreanDictionaryClient


class DictionaryTool:
    """Thin wrapper around the National Korean Dictionary client."""

    def __init__(self) -> None:
        self.client = StandardKoreanDictionaryClient()

    def lookup(self, term: str, pos: str | None = None) -> dict[str, Any]:
        return self.client.lookup_basic_meaning(term, pos)
