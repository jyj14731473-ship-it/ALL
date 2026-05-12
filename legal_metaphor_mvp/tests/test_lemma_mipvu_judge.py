"""Tests for lemma-level MIPVU input shaping and normalization."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from nodes import mipvu_judge  # noqa: E402
from schemas.annotation import create_empty_state  # noqa: E402


class LemmaMipvuInputTests(unittest.TestCase):
    def test_build_inputs_ignores_pos_and_deduplicates_sentences(self) -> None:
        contextual_payload = {
            "lemma_groups": [
                {
                    "lemma_group_id": "lg001",
                    "lemma": "이유",
                    "pos": "명사",
                    "contextual_meaning": "판단의 근거를 뜻한다.",
                    "occurrences": [
                        {"sentence": "상고이유를 판단한다."},
                        {"sentence": "상고이유를 판단한다."},
                        {"sentence": "다음과 같은 이유로 수긍하기 어렵다."},
                    ],
                }
            ]
        }
        dictionary_payload = {
            "lemma_dictionary_results": [
                {
                    "lemma_group_id": "lg001",
                    "lemma": "이유",
                    "pos": "명사",
                    "exists_in_dictionary": True,
                    "status": "ok",
                    "definitions": [{"sup_no": "4", "definition": "어떠한 결론이나 결과에 이른 까닭이나 근거."}],
                }
            ]
        }

        records = mipvu_judge.build_lemma_mipvu_inputs(contextual_payload, dictionary_payload)

        self.assertEqual(len(records), 1)
        self.assertNotIn("pos", records[0])
        self.assertEqual(records[0]["lemma_group_id"], "lg001")
        self.assertEqual(records[0]["occurrence_count"], 3)
        self.assertEqual(
            records[0]["sample_sentences"],
            ["상고이유를 판단한다.", "다음과 같은 이유로 수긍하기 어렵다."],
        )
        self.assertEqual(records[0]["definitions"][0]["sup_no"], "4")

    def test_batch_lemma_inputs_uses_25_items(self) -> None:
        records = [{"lemma_group_id": f"lg{idx:03d}"} for idx in range(53)]

        batches = mipvu_judge.batch_lemma_inputs(records)

        self.assertEqual([len(batch) for batch in batches], [25, 25, 3])


class LemmaMipvuNormalizationTests(unittest.TestCase):
    def test_missing_dictionary_definitions_fallback_has_no_pos(self) -> None:
        source = {
            "lemma_group_id": "lg999",
            "lemma": "없는말",
            "contextual_meaning": "문맥 의미",
            "occurrence_count": 1,
            "sample_sentences": ["예문"],
            "definitions": [],
        }

        fallback = mipvu_judge._fallback_judgment(source, "사전 뜻 후보가 없습니다.")

        self.assertNotIn("pos", fallback)
        self.assertEqual(fallback["mipvu_label"], "uncertain")
        self.assertEqual(fallback["lakoff_johnson_type"], "uncertain")
        self.assertTrue(fallback["needs_human_review"])
        self.assertEqual(fallback["original_meaning"], "")

    def test_normalize_preserves_selected_dictionary_meaning_and_label_alias(self) -> None:
        source = {
            "lemma_group_id": "lg002",
            "lemma": "이유",
            "contextual_meaning": "판단의 근거를 뜻한다.",
            "occurrence_count": 2,
            "sample_sentences": ["상고이유를 판단한다."],
            "definitions": [{"sup_no": "4", "definition": "어떠한 결론이나 결과에 이른 까닭이나 근거."}],
        }
        raw = {
            "lemma_group_id": "lg002",
            "selected_sup_no": "4",
            "original_meaning": "LLM이 살짝 바꾼 문장",
            "original_meaning_selection_reason": "문맥상 근거 의미이기 때문이다.",
            "meaning_contrast": "두 의미가 거의 같다.",
            "comparison_possible": True,
            "target_domain": "법적 판단의 근거",
            "source_domain": "근거",
            "conceptual_metaphor": "LEGAL REASONING IS GROUND",
            "concept_mapping_reason": "non_MRW에서는 비워져야 한다.",
            "lakoff_johnson_type": "structural",
            "lakoff_johnson_type_reason": "non_MRW에서는 비워져야 한다.",
            "mipvu_label": "not_mrw",
            "confidence": 0.82,
        }

        normalized = mipvu_judge.normalize_lemma_judgment(raw, source)

        self.assertEqual(normalized["selected_sup_no"], "4")
        self.assertEqual(normalized["original_meaning"], "어떠한 결론이나 결과에 이른 까닭이나 근거.")
        self.assertEqual(normalized["mipvu_label"], "non_MRW")
        self.assertEqual(normalized["target_domain"], "")
        self.assertEqual(normalized["source_domain"], "")
        self.assertEqual(normalized["conceptual_metaphor"], "")
        self.assertEqual(normalized["concept_mapping_reason"], "")
        self.assertEqual(normalized["lakoff_johnson_type"], "not_applicable")
        self.assertEqual(normalized["lakoff_johnson_type_reason"], "")
        self.assertNotIn("target_concept", normalized)
        self.assertNotIn("source_concept", normalized)
        self.assertNotIn("pos", normalized)
        self.assertNotIn("candidate_id", normalized)
        self.assertNotIn("sentence_id", normalized)
        self.assertNotIn("token", normalized)

    def test_normalize_keeps_concepts_for_mrw_candidate(self) -> None:
        source = {
            "lemma_group_id": "lg011",
            "lemma": "맡기다",
            "contextual_meaning": "법관의 자유판단에 재량을 부여한다.",
            "occurrence_count": 1,
            "sample_sentences": ["증거의 증명력은 법관의 자유판단에 맡겨져 있다."],
            "definitions": [{"sup_no": "0", "definition": "어떤 일에 대한 책임을 지고 담당하게 하다."}],
        }
        raw = {
            "lemma_group_id": "lg011",
            "selected_sup_no": "0",
            "meaning_contrast": "책임을 담당하게 하는 일반 의미가 재량 부여 문맥으로 쓰였다.",
            "distinctness": True,
            "comparison_possible": True,
            "similarity": True,
            "target_domain": "증거 증명력에 대한 법관의 재량 판단",
            "source_domain": "책임이나 일을 누군가에게 맡기는 행위",
            "conceptual_metaphor": "LEGAL DISCRETION IS DELEGATED RESPONSIBILITY",
            "concept_mapping_reason": "판단 권한을 어떤 일의 담당으로 표현한다.",
            "lakoff_johnson_type": "structural metaphor",
            "lakoff_johnson_type_reason": "법적 판단 권한을 업무 위임 구조로 이해하게 한다.",
            "mipvu_label": "MRW_candidate",
            "confidence": 0.74,
        }

        normalized = mipvu_judge.normalize_lemma_judgment(raw, source)

        self.assertEqual(normalized["mipvu_label"], "MRW_candidate")
        self.assertEqual(normalized["target_domain"], "증거 증명력에 대한 법관의 재량 판단")
        self.assertEqual(normalized["source_domain"], "책임이나 일을 누군가에게 맡기는 행위")
        self.assertEqual(normalized["conceptual_metaphor"], "LEGAL DISCRETION IS DELEGATED RESPONSIBILITY")
        self.assertEqual(normalized["concept_mapping_reason"], "판단 권한을 어떤 일의 담당으로 표현한다.")
        self.assertEqual(normalized["lakoff_johnson_type"], "structural")
        self.assertEqual(normalized["lakoff_johnson_type_reason"], "법적 판단 권한을 업무 위임 구조로 이해하게 한다.")

    def test_normalize_maps_personification_to_ontological(self) -> None:
        source = {
            "lemma_group_id": "lg012",
            "lemma": "살아나다",
            "contextual_meaning": "주장이 다시 효력을 얻는다.",
            "occurrence_count": 1,
            "sample_sentences": ["그 주장은 다시 살아났다."],
            "definitions": [{"sup_no": "1", "definition": "생명을 지니게 되다."}],
        }
        raw = {
            "lemma_group_id": "lg012",
            "selected_sup_no": "1",
            "distinctness": True,
            "comparison_possible": True,
            "similarity": True,
            "target_domain": "주장의 효력 회복",
            "source_domain": "생명체의 생존",
            "conceptual_metaphor": "ARGUMENT VALIDITY IS LIFE",
            "concept_mapping_reason": "효력 회복을 생명 회복으로 표현한다.",
            "lakoff_johnson_type": "personification",
            "lakoff_johnson_type_reason": "추상적 주장을 살아 있는 행위자처럼 다룬다.",
            "mipvu_label": "MRW",
            "confidence": 0.88,
        }

        normalized = mipvu_judge.normalize_lemma_judgment(raw, source)

        self.assertEqual(normalized["lakoff_johnson_type"], "ontological")
        self.assertEqual(normalized["lakoff_johnson_type_reason"], "추상적 주장을 살아 있는 행위자처럼 다룬다.")
        self.assertEqual(normalized["conceptual_metaphor"], "ARGUMENT VALIDITY IS LIFE")


class LemmaMipvuNodeTests(unittest.TestCase):
    def test_node_uses_mocked_llm_response(self) -> None:
        contextual_payload = {
            "lemma_groups": [
                {
                    "lemma_group_id": "lg001",
                    "lemma": "이유",
                    "contextual_meaning": "판단의 근거를 뜻한다.",
                    "occurrences": [{"sentence": "상고이유를 판단한다."}],
                }
            ]
        }
        dictionary_payload = {
            "lemma_dictionary_results": [
                {
                    "lemma_group_id": "lg001",
                    "lemma": "이유",
                    "exists_in_dictionary": True,
                    "status": "ok",
                    "definitions": [{"sup_no": "4", "definition": "어떠한 결론이나 결과에 이른 까닭이나 근거."}],
                }
            ]
        }
        mocked_response = {
            "judgments": [
                {
                    "lemma_group_id": "lg001",
                    "selected_sup_no": "4",
                    "original_meaning_selection_reason": "근거 의미가 문맥과 일치한다.",
                    "meaning_contrast": "의미 차이가 작다.",
                    "comparison_possible": True,
                    "target_domain": "ignored",
                    "source_domain": "ignored",
                    "conceptual_metaphor": "IGNORED IS IGNORED",
                    "concept_mapping_reason": "ignored",
                    "lakoff_johnson_type": "orientational",
                    "lakoff_johnson_type_reason": "ignored",
                    "mipvu_label": "non-MRW",
                    "confidence": 0.9,
                }
            ]
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            contextual_path = Path(tmpdir) / "contextual.json"
            dictionary_path = Path(tmpdir) / "dictionary.json"
            contextual_path.write_text(json.dumps(contextual_payload, ensure_ascii=False), encoding="utf-8")
            dictionary_path.write_text(json.dumps(dictionary_payload, ensure_ascii=False), encoding="utf-8")

            with (
                patch.object(mipvu_judge, "DEFAULT_CONTEXTUAL_JSON_PATH", contextual_path),
                patch.object(mipvu_judge, "DEFAULT_DICTIONARY_LOOKUP_PATH", dictionary_path),
                patch.object(mipvu_judge, "call_structured_chain", return_value=mocked_response) as llm_call,
            ):
                result = mipvu_judge.mipvu_judge_node(create_empty_state(raw_text="본문"))

        self.assertEqual(len(result["mipvu_annotations"]), 1)
        annotation = result["mipvu_annotations"][0]
        self.assertEqual(annotation["selected_sup_no"], "4")
        self.assertEqual(annotation["original_meaning"], "어떠한 결론이나 결과에 이른 까닭이나 근거.")
        self.assertEqual(annotation["mipvu_label"], "non_MRW")
        self.assertEqual(annotation["target_domain"], "")
        self.assertEqual(annotation["source_domain"], "")
        self.assertEqual(annotation["conceptual_metaphor"], "")
        self.assertEqual(annotation["lakoff_johnson_type"], "not_applicable")
        self.assertEqual(annotation["lakoff_johnson_type_reason"], "")
        self.assertNotIn("target_concept", annotation)
        self.assertNotIn("source_concept", annotation)
        self.assertNotIn("pos", annotation)
        llm_call.assert_called_once()


if __name__ == "__main__":
    unittest.main()
