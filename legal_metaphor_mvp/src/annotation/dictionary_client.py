"""Client for National Institute of Korean Language standard dictionary API.

Reference:
- https://stdict.korean.go.kr/openapi/openApiInfo.do
"""

from __future__ import annotations

import json
import os
import urllib.parse
import urllib.request
from typing import Any


class StandardKoreanDictionaryClient:
    """Minimal API wrapper for 표준국어대사전 Open API."""

    def __init__(self) -> None:
        self.api_key = os.getenv("STDICT_API_KEY", "").strip()
        self.endpoint = os.getenv("STDICT_API_URL", "https://stdict.korean.go.kr/api/search.do").strip()

    def is_available(self) -> bool:
        return bool(self.api_key)

    def lookup_basic_meaning(self, term: str, pos: str | None = None) -> dict[str, Any]:
        """Look up basic meaning for a term.

        Returns a normalized dictionary object. If API key is missing or request fails,
        returns a non-crashing fallback payload.
        """
        word = (term or "").strip()
        if not word:
            return {
                "term": "",
                "definition": "",
                "pos": pos or "",
                "source": "stdict",
                "status": "empty_term",
            }

        if not self.api_key:
            return {
                "term": word,
                "definition": "",
                "pos": pos or "",
                "source": "stdict",
                "status": "no_api_key",
                "message": "Set STDICT_API_KEY to enable dictionary lookup.",
            }

        params = {
            "key": self.api_key,
            "q": word,
            "req_type": "json",
            "start": "1",
            "num": "1",
            "method": "exact",
            "type1": "word",
        }
        if pos:
            # API doc uses numeric pos filter; keep optional and conservative.
            # TODO: map Korean POS labels to numeric values if strict filtering is required.
            pass

        url = f"{self.endpoint}?{urllib.parse.urlencode(params)}"
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001
            return {
                "term": word,
                "definition": "",
                "pos": pos or "",
                "source": "stdict",
                "status": "request_failed",
                "message": str(exc),
            }

        if not isinstance(payload, dict):
            return {
                "term": word,
                "definition": "",
                "pos": pos or "",
                "source": "stdict",
                "status": "invalid_response",
            }

        if "error" in payload:
            err = payload.get("error", {})
            return {
                "term": word,
                "definition": "",
                "pos": pos or "",
                "source": "stdict",
                "status": "api_error",
                "error_code": str(err.get("error_code", "")),
                "message": str(err.get("message", "")),
            }

        channel = payload.get("channel", {})
        item = channel.get("item", [])
        if isinstance(item, dict):
            item = [item]
        if not isinstance(item, list) or not item:
            return {
                "term": word,
                "definition": "",
                "pos": pos or "",
                "source": "stdict",
                "status": "not_found",
            }

        first = item[0]
        sense = first.get("sense", {})
        if isinstance(sense, list) and sense:
            sense = sense[0]
        definition = ""
        if isinstance(sense, dict):
            definition = str(sense.get("definition", "")).strip()

        return {
            "term": str(first.get("word", word)),
            "definition": definition,
            "pos": str(first.get("pos", pos or "")),
            "source": "stdict",
            "status": "ok",
            "link": str(sense.get("link", "")) if isinstance(sense, dict) else "",
        }

