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


if __name__ == "__main__":
    unittest.main()
