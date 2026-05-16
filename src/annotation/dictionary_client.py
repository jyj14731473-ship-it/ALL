"""Client for National Institute of Korean Language standard dictionary API.

Reference:
- https://stdict.korean.go.kr/openapi/openApiInfo.do
"""

from __future__ import annotations

import concurrent.futures
import json
import os
import urllib.parse
import urllib.request
from typing import Any
from typing import Iterable

from datetime import datetime
from datetime import datetime


class StandardKoreanDictionaryClient:
    """Minimal API wrapper for 표준국어대사전 Open API."""

    def __init__(self) -> None:
        self.api_key = os.getenv("STDICT_API_KEY", "").strip()
        self.endpoint = os.getenv("STDICT_API_URL", "https://stdict.korean.go.kr/api/search.do").strip()
        self.certkey_no = os.getenv("STDICT_CERTKEY_NO", "").strip()
        self.type_search = os.getenv("STDICT_TYPE_SEARCH", "search").strip() or "search"
        self.req_type = os.getenv("STDICT_REQ_TYPE", "json").strip() or "json"
        self.batch_size = self._read_batch_size()

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
                "source": "unavailable",
                "basic_meaning_source": "unavailable",
                "status": "empty_term",
            }

        if not self.api_key:
            return {
                "term": word,
                "definition": "",
                "pos": pos or "",
                "source": "unavailable",
                "basic_meaning_source": "unavailable",
                "status": "no_api_key",
                "message": "Set STDICT_API_KEY to enable dictionary lookup.",
            }

        params = {
            "key": self.api_key,
            "q": word,
        }
        if self.certkey_no:
            params["certkey_no"] = self.certkey_no
        params["type_search"] = self.type_search
        params["req_type"] = self.req_type
        if pos:
            # API doc uses numeric pos filter; keep optional and conservative.
            # TODO: map Korean POS labels to numeric values if strict filtering is required.
            pass

        url = f"{self.endpoint}?{urllib.parse.urlencode(params)}"
        try:
            with urllib.request.urlopen(url, timeout=10) as response:
                raw = response.read()
                payload_text = raw.decode("utf-8")
                if not payload_text.strip():
                    return {
                        "term": word,
                        "definition": "",
                        "pos": pos or "",
                        "source": "unavailable",
                        "basic_meaning_source": "unavailable",
                        "status": "request_failed",
                        "message": "Empty response body from stdict API.",
                    }
                payload = json.loads(payload_text)
        except Exception as exc:  # noqa: BLE001
            return {
                "term": word,
                "definition": "",
                "pos": pos or "",
                "source": "unavailable",
                "basic_meaning_source": "unavailable",
                "status": "request_failed",
                "message": str(exc),
            }

        if not isinstance(payload, dict):
            return {
                "term": word,
                "definition": "",
                "pos": pos or "",
                "source": "unavailable",
                "basic_meaning_source": "unavailable",
                "status": "invalid_response",
            }

        if "error" in payload:
            err = payload.get("error", {})
            return {
                "term": word,
                "definition": "",
                "pos": pos or "",
                "source": "unavailable",
                "basic_meaning_source": "unavailable",
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
                "source": "unavailable",
                "basic_meaning_source": "unavailable",
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
            "basic_meaning_source": "stdict",
            "status": "ok",
            "link": str(sense.get("link", "")) if isinstance(sense, dict) else "",
        }

    def lookup_basic_meanings(
        self,
        terms: Iterable[tuple[str, str | None]],
        batch_size: int | None = None,
    ) -> list[dict[str, Any]]:
        """Look up basic meanings for terms in batches."""

        term_items = [(str(term or "").strip(), pos or None) for term, pos in terms]
        size = max(1, batch_size or self.batch_size)

        results: list[dict[str, Any]] = [{} for _ in range(len(term_items))]
        total = len(term_items)

        if total == 0:
            print("[dictionary] 사전 조회 대상이 없습니다.")
            return results

        total_batches = (total + size - 1) // size
        print(f"[dictionary] 사전 조회 시작: 대상={total}개, 배치={size}, 배치수={total_batches}개")

        for start in range(0, total, size):
            chunk = term_items[start : start + size]
            if not chunk:
                continue
            batch_idx = start // size + 1
            batch_start = datetime.now()
            print(f"[dictionary] batch {batch_idx}/{total_batches} 시작 ({len(chunk)}개)")

            with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(chunk), size)) as executor:
                future_to_idx = {
                    executor.submit(self.lookup_basic_meaning, term, pos): (start + offset)
                    for offset, (term, pos) in enumerate(chunk)
                }
                for future in concurrent.futures.as_completed(future_to_idx):
                    idx = future_to_idx[future]
                    results[idx] = future.result()
            batch_elapsed = datetime.now() - batch_start
            done = min(start + size, total)
            print(
                f"[dictionary] batch {batch_idx}/{total_batches} 완료: {done}/{total} (진행률 "
                f"{done/total:.1%}, 소요 {batch_elapsed.total_seconds():.1f}s)"
            )

        return results


    def _read_batch_size(self) -> int:
        value = os.getenv("STDICT_BATCH_SIZE", "50").strip()
        try:
            parsed = int(value)
            return max(1, parsed)
        except ValueError:
            return 50
