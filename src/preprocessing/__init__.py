"""Judgment text preprocessing for 9-POS word reconstruction."""

from preprocessing.main import build_pos_json

__all__ = ["build_pos_json", "correct_pos_json_payload", "extract_contextual_meanings"]


def __getattr__(name: str):
    if name == "correct_pos_json_payload":
        from preprocessing.lemma_group_sanity import correct_pos_json_payload

        return correct_pos_json_payload
    if name == "extract_contextual_meanings":
        from preprocessing.contextual_meaning import extract_contextual_meanings

        return extract_contextual_meanings
    raise AttributeError(name)
