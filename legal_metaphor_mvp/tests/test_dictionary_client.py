"""Smoke tests for dictionary lookup fallback behavior."""

from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from annotation.dictionary_client import StandardKoreanDictionaryClient  # noqa: E402
from preprocessing.dictionary_lookup import build_lemma_dictionary_lookup_payload  # noqa: E402


class DictionaryClientFallbackTests(unittest.TestCase):
    def test_lookup_without_api_key_does_not_crash(self) -> None:
        with patch.dict(os.environ, {"STDICT_API_KEY": ""}, clear=False):
            client = StandardKoreanDictionaryClient()
            result = client.lookup_basic_meaning("법질서")

        self.assertEqual(result.get("term"), "법질서")
        self.assertIn("definition", result)
        self.assertIn("source", result)
        self.assertEqual(result.get("source"), "unavailable")
        self.assertEqual(result.get("basic_meaning_source"), "unavailable")

    def test_full_lookup_without_api_key_does_not_crash(self) -> None:
        with patch.dict(os.environ, {"STDICT_API_KEY": ""}, clear=False):
            client = StandardKoreanDictionaryClient()
            result = client.lookup_dictionary_entries("법질서")

        self.assertEqual(result.get("term"), "법질서")
        self.assertFalse(result.get("exists_in_dictionary"))
        self.assertEqual(result.get("status"), "no_api_key")
        self.assertEqual(result.get("definitions"), [])

    def test_full_lookup_extracts_sup_no_and_definitions_from_list_items(self) -> None:
        payload = {
            "channel": {
                "total": 2,
                "num": 10,
                "item": [
                    {"sup_no": "1", "sense": {"definition": "첫 번째 뜻."}, "word": "공소"},
                    {"sup_no": "2", "sense": {"definition": "두 번째 뜻."}, "word": "공소"},
                ],
            }
        }
        with patch.dict(os.environ, {"STDICT_API_KEY": "test-key"}, clear=False):
            client = StandardKoreanDictionaryClient()
        with patch.object(client, "_request_search_payload", return_value=payload):
            result = client.lookup_dictionary_entries("공소")

        self.assertTrue(result.get("exists_in_dictionary"))
        self.assertEqual(result.get("status"), "ok")
        self.assertEqual(
            result.get("definitions"),
            [
                {"sup_no": "1", "definition": "첫 번째 뜻."},
                {"sup_no": "2", "definition": "두 번째 뜻."},
            ],
        )

    def test_full_lookup_extracts_sup_no_and_definition_from_single_item(self) -> None:
        payload = {
            "channel": {
                "total": 1,
                "num": 10,
                "item": {"sup_no": "8", "sense": {"definition": "항소의 전 용어."}, "word": "공소"},
            }
        }
        with patch.dict(os.environ, {"STDICT_API_KEY": "test-key"}, clear=False):
            client = StandardKoreanDictionaryClient()
        with patch.object(client, "_request_search_payload", return_value=payload):
            result = client.lookup_dictionary_entries("공소")

        self.assertTrue(result.get("exists_in_dictionary"))
        self.assertEqual(result.get("definitions"), [{"sup_no": "8", "definition": "항소의 전 용어."}])

    def test_full_lookup_paginates_until_total_is_exhausted(self) -> None:
        pages = {
            1: {
                "channel": {
                    "total": 3,
                    "num": 2,
                    "item": [
                        {"sup_no": "1", "sense": {"definition": "첫 번째 뜻."}},
                        {"sup_no": "2", "sense": {"definition": "두 번째 뜻."}},
                    ],
                }
            },
            3: {
                "channel": {
                    "total": 3,
                    "num": 2,
                    "item": [{"sup_no": "3", "sense": {"definition": "세 번째 뜻."}}],
                }
            },
        }
        calls = []

        def fake_request(term: str, *, start: int, num: int) -> dict:
            calls.append((term, start, num))
            return pages[start]

        with patch.dict(os.environ, {"STDICT_API_KEY": "test-key", "STDICT_PAGE_SIZE": "2"}, clear=False):
            client = StandardKoreanDictionaryClient()
        with patch.object(client, "_request_search_payload", side_effect=fake_request):
            result = client.lookup_dictionary_entries("공소")

        self.assertEqual(calls, [("공소", 1, 2), ("공소", 3, 2)])
        self.assertEqual(len(result.get("definitions", [])), 3)


class LemmaDictionaryLookupPayloadTests(unittest.TestCase):
    def test_payload_marks_missing_entries_when_api_key_is_absent(self) -> None:
        payload = {
            "document_id": "doc001",
            "lemma_groups": [
                {"lemma_group_id": "lg001", "lemma": "공소", "pos": "명사"},
                {"lemma_group_id": "lg002", "lemma": "판단하다", "pos": "동사"},
            ],
        }
        with patch.dict(os.environ, {"STDICT_API_KEY": ""}, clear=False):
            result = build_lemma_dictionary_lookup_payload(payload, source_path="contextual.json")

        self.assertEqual(result["document_id"], "doc001")
        self.assertEqual(result["source_path"], "contextual.json")
        self.assertEqual(result["summary"]["lemma_group_count"], 2)
        self.assertEqual(result["summary"]["found_count"], 0)
        self.assertEqual(result["summary"]["missing_count"], 2)
        self.assertEqual(result["lemma_dictionary_results"][0]["lemma_group_id"], "lg001")
        self.assertFalse(result["lemma_dictionary_results"][0]["exists_in_dictionary"])
        self.assertEqual(result["lemma_dictionary_results"][0]["status"], "no_api_key")


if __name__ == "__main__":
    unittest.main()
