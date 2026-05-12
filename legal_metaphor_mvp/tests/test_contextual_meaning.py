"""Tests for contextual meaning payload shaping."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from preprocessing.contextual_meaning import merge_contextual_meaning_results, reorder_contextualized_payload  # noqa: E402


class ContextualMeaningOrderingTests(unittest.TestCase):
    def test_merge_places_contextual_meaning_before_occurrences(self) -> None:
        payload = {
            "document_id": "doc001",
            "lemma_groups": [
                {
                    "lemma_group_id": "lg001",
                    "lemma": "공소",
                    "pos": "명사",
                    "occurrences": [{"sentence_id": "s001"}],
                }
            ],
        }
        batch_results = [
            {
                "contextual_meanings": [
                    {
                        "lemma_group_id": "lg001",
                        "lemma": "공소",
                        "contextual_meaning": "검사가 법원에 형사재판을 청구하는 행위.",
                    }
                ],
                "issues": [],
            }
        ]

        output, _ = merge_contextual_meaning_results(payload, payload["lemma_groups"], batch_results)

        self.assertEqual(
            list(output["lemma_groups"][0].keys()),
            ["lemma_group_id", "lemma", "pos", "contextual_meaning", "occurrences"],
        )

    def test_reorder_existing_contextualized_payload(self) -> None:
        payload = {
            "lemma_groups": [
                {
                    "lemma_group_id": "lg001",
                    "lemma": "공소",
                    "pos": "명사",
                    "occurrences": [],
                    "contextual_meaning": "문맥 의미",
                }
            ]
        }

        output = reorder_contextualized_payload(payload)

        self.assertEqual(
            list(output["lemma_groups"][0].keys()),
            ["lemma_group_id", "lemma", "pos", "contextual_meaning", "occurrences"],
        )


if __name__ == "__main__":
    unittest.main()
