"""Lemma grouping for reconstructed POS nodes."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any

EXCLUDED_LEMMA_GROUP_POS = {"조사", "수사", "기호", "어미", "접사", "어근", "미분류"}


def build_lemma_groups(sentences: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Group content-word occurrences by (lemma, pos), including singletons."""
    groups: OrderedDict[tuple[str, str], dict[str, Any]] = OrderedDict()
    next_group_id = 1
    for sentence_item in sentences:
        sentence_id = str(sentence_item.get("sentence_id", ""))
        sentence = str(sentence_item.get("sentence", ""))
        pos_nodes = sentence_item.get("pos_nodes", [])
        if not isinstance(pos_nodes, list):
            continue
        for node in pos_nodes:
            if not isinstance(node, dict):
                continue
            lemma = str(node.get("lemma", ""))
            pos = str(node.get("pos", ""))
            if pos in EXCLUDED_LEMMA_GROUP_POS:
                continue
            key = (lemma, pos)
            if key not in groups:
                groups[key] = {
                    "lemma_group_id": f"lg{next_group_id:03d}",
                    "lemma": lemma,
                    "pos": pos,
                    "occurrences": [],
                }
                next_group_id += 1
            groups[key]["occurrences"].append(
                {
                    "sentence_id": sentence_id,
                    "node_id": str(node.get("node_id", "")),
                    "surface": str(node.get("surface", "")),
                    "sentence": sentence,
                }
            )
    return list(groups.values())
