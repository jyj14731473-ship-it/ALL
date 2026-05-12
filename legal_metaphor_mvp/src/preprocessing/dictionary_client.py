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
        self.certkey_no = os.getenv("STDICT_CERTKEY_NO", "").strip()
        self.type_search = os.getenv("STDICT_TYPE_SEARCH", "search").strip() or "search"
        self.req_type = os.getenv("STDICT_REQ_TYPE", "json").strip() or "json"
        self.page_size = self._read_page_size()

    def is_available(self) -> bool:
        return bool(self.api_key)

    def lookup_dictionary_entries(self, term: str, page_size: int | None = None) -> dict[str, Any]:
        """Look up all dictionary entries for a term and keep sup_no/definition pairs."""
        word = (term or "").strip()
        if not word:
            return {
                "term": "",
                "exists_in_dictionary": False,
                "status": "empty_term",
                "total": 0,
                "definitions": [],
            }

        if not self.api_key:
            return {
                "term": word,
                "exists_in_dictionary": False,
                "status": "no_api_key",
                "total": 0,
                "definitions": [],
                "message": "Set STDICT_API_KEY to enable dictionary lookup.",
            }

        size = max(1, page_size or self.page_size)
        definitions: list[dict[str, str]] = []
        total = 0
        start = 1
        status = "ok"
        message = ""
        seen: set[tuple[str, str]] = set()

        while True:
            try:
                payload = self._request_search_payload(word, start=start, num=size)
            except Exception as exc:  # noqa: BLE001
                status = "partial" if definitions else "request_failed"
                message = str(exc)
                break

            if not isinstance(payload, dict):
                status = "partial" if definitions else "invalid_response"
                break
            if "error" in payload:
                err = payload.get("error", {})
                status = "partial" if definitions else "api_error"
                message = str(err.get("message", ""))
                break

            channel = payload.get("channel", {})
            if not isinstance(channel, dict):
                status = "partial" if definitions else "invalid_response"
                break

            total = max(total, _safe_int(channel.get("total"), 0))
            items = _normalize_items(channel.get("item", []))
            for entry in _extract_definition_entries(items):
                key = (entry["sup_no"], entry["definition"])
                if key not in seen:
                    definitions.append(entry)
                    seen.add(key)

            if total <= 0 or not items:
                break
            page_step = _safe_int(channel.get("num"), 0) or len(items) or size
            start += max(1, page_step)
            if start > total:
                break

        if status == "ok" and not definitions:
            status = "not_found"

        result = {
            "term": word,
            "exists_in_dictionary": bool(definitions),
            "status": status,
            "total": total,
            "definitions": definitions,
        }
        if message:
            result["message"] = message
        return result

    def _request_search_payload(self, term: str, *, start: int = 1, num: int | None = None) -> dict[str, Any]:
        params: dict[str, Any] = {
            "key": self.api_key,
            "q": term,
            "type_search": self.type_search,
            "req_type": self.req_type,
            "start": start,
        }
        if num:
            params["num"] = num
        if self.certkey_no:
            params["certkey_no"] = self.certkey_no

        url = f"{self.endpoint}?{urllib.parse.urlencode(params)}"
        with urllib.request.urlopen(url, timeout=10) as response:
            payload_text = response.read().decode("utf-8")
        if not payload_text.strip():
            raise ValueError("Empty response body from stdict API.")
        payload = json.loads(payload_text)
        if not isinstance(payload, dict):
            raise ValueError("Invalid response body from stdict API.")
        return payload

    def _read_page_size(self) -> int:
        value = os.getenv("STDICT_PAGE_SIZE", "100").strip()
        try:
            parsed = int(value)
            return max(1, parsed)
        except ValueError:
            return 100


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _normalize_items(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _normalize_senses(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        return [value]
    if isinstance(value, list):
        return [item for item in value if isinstance(item, dict)]
    return []


def _extract_definition_entries(items: list[dict[str, Any]]) -> list[dict[str, str]]:
    entries: list[dict[str, str]] = []
    for item in items:
        sup_no = str(item.get("sup_no", "")).strip()
        for sense in _normalize_senses(item.get("sense", {})):
            definition = str(sense.get("definition", "")).strip()
            if definition:
                entries.append({"sup_no": sup_no, "definition": definition})
    return entries
