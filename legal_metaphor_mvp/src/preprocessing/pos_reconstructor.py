"""Reconstruct simplified Korean POS word nodes from Mecab morphemes."""

from __future__ import annotations

from typing import Any, NamedTuple

from preprocessing.mecab_analyzer import MorphPart


class NormalizedMorphPart(NamedTuple):
    surface: str
    tag: str
    semantic: str = ""
    expression: str = ""

NOUN_TAGS = {"NNG", "NNP", "NNB", "NNBC"}
DERIVABLE_BASE_TAGS = NOUN_TAGS | {"XR", "SH", "SL"}
JOSA_TAGS = {"JKS", "JKC", "JKG", "JKO", "JKB", "JKV", "JKQ", "JC", "JX"}
ENDING_TAGS = {"EP", "EF", "EC", "ETN", "ETM"}
SYMBOL_TAGS = {"SF", "SE", "SSO", "SSC", "SC", "SY"}
DERIVED_HADA_KEY = "_derived_hada"


def reconstruct_pos_nodes(mecab_parts: list[MorphPart], sentence_id: str) -> list[dict[str, Any]]:
    """Build restored simplified POS word nodes from a Mecab part sequence."""
    parts = [_normalize_part(part) for part in mecab_parts]
    nodes: list[dict[str, Any]] = []
    i = 0

    while i < len(parts):
        surface = _part_surface(parts[i])
        tag = _part_tag(parts[i])
        primary = _primary_tag(tag)

        if _is_symbol(tag):
            node_parts = [parts[i]]
            nodes.append(_with_node_id(_make_node(node_parts, surface, "기호"), sentence_id, len(nodes) + 1))
            i += 1
            continue

        if _is_standalone_ending(tag):
            node_parts = [parts[i]]
            nodes.append(_with_node_id(_make_node(node_parts, surface, "어미"), sentence_id, len(nodes) + 1))
            i += 1
            continue

        if primary in {"XSN", "XSA", "XSV"}:
            node_parts = [parts[i]]
            nodes.append(_with_node_id(_make_node(node_parts, surface, "접사"), sentence_id, len(nodes) + 1))
            i += 1
            continue

        if primary == "XPN":
            node, i = _consume_prefixed_base(parts, i)
            if node:
                nodes.append(_with_node_id(node, sentence_id, len(nodes) + 1))
            else:
                node_parts = [parts[i - 1]]
                nodes.append(_with_node_id(_make_node(node_parts, _surface(node_parts), "접사"), sentence_id, len(nodes) + 1))
            continue

        if primary in DERIVABLE_BASE_TAGS:
            node, i = _consume_derivable_base(parts, i, [])
            if node:
                nodes.append(_with_node_id(node, sentence_id, len(nodes) + 1))
            elif primary == "XR":
                node_parts = [parts[i - 1]]
                nodes.append(_with_node_id(_make_node(node_parts, _surface(node_parts), "어근"), sentence_id, len(nodes) + 1))
            continue

        if primary in {"VV", "VX"}:
            node_parts, i = _consume_with_endings(parts, i)
            nodes.append(_with_node_id(_make_node(node_parts, _predicate_lemma(node_parts) + "다", "동사"), sentence_id, len(nodes) + 1))
            continue

        if primary in {"VA", "VCN"}:
            node_parts, i = _consume_with_endings(parts, i)
            nodes.append(_with_node_id(_make_node(node_parts, _predicate_lemma(node_parts) + "다", "형용사"), sentence_id, len(nodes) + 1))
            continue

        if primary == "VCP":
            node_parts, i = _consume_with_endings(parts, i)
            nodes.append(_with_node_id(_make_node(node_parts, "이다", "조사"), sentence_id, len(nodes) + 1))
            continue

        single_pos = _single_pos(primary)
        if single_pos:
            node_parts = [parts[i]]
            nodes.append(_with_node_id(_make_node(node_parts, surface, single_pos), sentence_id, len(nodes) + 1))
            i += 1
            continue

        node_parts = [parts[i]]
        nodes.append(_with_node_id(_make_node(node_parts, surface, "미분류"), sentence_id, len(nodes) + 1))
        i += 1

    return nodes


def _consume_prefixed_base(parts: list[MorphPart], start: int) -> tuple[dict[str, Any] | None, int]:
    prefix_parts: list[MorphPart] = []
    i = start
    while i < len(parts) and _primary_tag(_part_tag(parts[i])) == "XPN":
        prefix_parts.append(parts[i])
        i += 1
    if i >= len(parts) or _primary_tag(_part_tag(parts[i])) not in DERIVABLE_BASE_TAGS:
        return _make_node(prefix_parts, _surface(prefix_parts), "접사"), max(i, start + 1)

    node, next_i = _consume_derivable_base(parts, i, prefix_parts)
    if node:
        return node, next_i

    base_tag = _primary_tag(_part_tag(parts[i]))
    node_parts = prefix_parts + [parts[i]]
    surface = _surface(node_parts)
    if base_tag == "XR":
        return _make_node(node_parts, surface, "어근"), i + 1
    return _make_node(node_parts, surface, "명사"), i + 1


def _consume_derivable_base(
    parts: list[MorphPart],
    base_index: int,
    prefix_parts: list[MorphPart],
) -> tuple[dict[str, Any] | None, int]:
    base_part = parts[base_index]
    base_tag = _primary_tag(_part_tag(base_part))
    base_parts = prefix_parts + [base_part]
    base_surface = _surface(base_parts)
    i = base_index + 1

    if i < len(parts) and _primary_tag(_part_tag(parts[i])) == "XSV":
        node_parts, next_i = _consume_derivation_with_endings(parts, base_parts, i)
        node = _make_derived_predicate_node(node_parts, base_parts, "동사", base_surface)
        return node, next_i

    if i < len(parts) and _primary_tag(_part_tag(parts[i])) == "XSA":
        node_parts, next_i = _consume_derivation_with_endings(parts, base_parts, i)
        node = _make_derived_predicate_node(node_parts, base_parts, "형용사", base_surface)
        return node, next_i

    if i < len(parts) and _primary_tag(_part_tag(parts[i])) == "XSN":
        node_parts = list(base_parts)
        while i < len(parts) and _primary_tag(_part_tag(parts[i])) == "XSN":
            node_parts.append(parts[i])
            i += 1
        surface = _surface(node_parts)
        return _make_node(node_parts, surface, "명사"), i

    if base_tag in NOUN_TAGS or base_tag in {"SH", "SL"}:
        return _make_node(base_parts, base_surface, "명사"), i

    return None, i


def _consume_derivation_with_endings(
    parts: list[MorphPart],
    base_parts: list[MorphPart],
    derivation_index: int,
) -> tuple[list[MorphPart], int]:
    node_parts = list(base_parts)
    node_parts.append(parts[derivation_index])
    i = derivation_index + 1
    while i < len(parts) and _is_standalone_ending(_part_tag(parts[i])):
        node_parts.append(parts[i])
        i += 1
    return node_parts, i


def _consume_with_endings(parts: list[MorphPart], start: int) -> tuple[list[MorphPart], int]:
    node_parts = [parts[start]]
    i = start + 1
    while i < len(parts) and _is_standalone_ending(_part_tag(parts[i])):
        node_parts.append(parts[i])
        i += 1
    return node_parts, i


def _make_node(parts: list[MorphPart], lemma: str, pos: str) -> dict[str, Any]:
    return {
        "surface": _surface(parts),
        "lemma": lemma,
        "pos": pos,
        "mecab_parts": [[_part_surface(part), _part_tag(part)] for part in parts],
    }


def _make_derived_predicate_node(
    node_parts: list[MorphPart],
    base_parts: list[MorphPart],
    default_pos: str,
    base_surface: str,
) -> dict[str, Any]:
    derivation_part = node_parts[len(base_parts)]
    ending_parts = node_parts[len(base_parts) + 1 :]
    pos = _initial_derived_predicate_pos(base_parts[-1], derivation_part, ending_parts, default_pos)
    node = _make_node(node_parts, base_surface + "하다", pos)
    node[DERIVED_HADA_KEY] = {
        "base_semantic": _part_semantic(base_parts[-1]),
        "derivation_surface": _part_surface(derivation_part),
        "derivation_tag": _part_tag(derivation_part),
        "ending_surfaces": [_part_surface(part) for part in ending_parts],
        "ending_tags": [_part_tag(part) for part in ending_parts],
    }
    return node


def _with_node_id(node: dict[str, Any], sentence_id: str, index: int) -> dict[str, Any]:
    return {"node_id": f"{sentence_id}_w{index:03d}", **node}


def _surface(parts: list[MorphPart]) -> str:
    return "".join(_part_surface(part) for part in parts)


def normalize_derived_hada_pos(sentence_items: list[dict[str, Any]]) -> None:
    """Normalize document-local XSV/XSA ambiguity for derived 하다 predicates."""
    groups: dict[str, list[dict[str, Any]]] = {}
    for sentence_item in sentence_items:
        for node in sentence_item.get("pos_nodes", []):
            if isinstance(node, dict) and DERIVED_HADA_KEY in node:
                groups.setdefault(str(node.get("lemma", "")), []).append(node)

    for nodes in groups.values():
        target_pos = _resolve_derived_hada_group(nodes)
        if target_pos:
            for node in nodes:
                node["pos"] = target_pos


def finalize_pos_nodes(sentence_items: list[dict[str, Any]]) -> None:
    """Apply document-level normalization and remove internal reconstruction hints."""
    normalize_derived_hada_pos(sentence_items)
    _strip_internal_pos_fields(sentence_items)


def _strip_internal_pos_fields(sentence_items: list[dict[str, Any]]) -> None:
    for sentence_item in sentence_items:
        for node in sentence_item.get("pos_nodes", []):
            if isinstance(node, dict):
                node.pop(DERIVED_HADA_KEY, None)


def _initial_derived_predicate_pos(
    base_part: MorphPart,
    derivation_part: MorphPart,
    ending_parts: list[MorphPart],
    default_pos: str,
) -> str:
    if _first_ending_surface(ending_parts) == "게":
        return "형용사"
    if _part_semantic(base_part) == "정적사태":
        return "형용사"
    if _part_semantic(base_part) == "행위":
        return "동사"
    return default_pos


def _resolve_derived_hada_group(nodes: list[dict[str, Any]]) -> str:
    current_pos = {str(node.get("pos", "")) for node in nodes}
    if not {"동사", "형용사"} <= current_pos:
        return ""

    semantics = {
        str(node.get(DERIVED_HADA_KEY, {}).get("base_semantic", ""))
        for node in nodes
        if str(node.get(DERIVED_HADA_KEY, {}).get("base_semantic", ""))
    }
    if "행위" in semantics:
        return "동사"
    if semantics == {"정적사태"}:
        return "형용사"

    verb_score = 0
    adjective_score = 0
    for node in nodes:
        verb_delta, adjective_delta = _derived_hada_evidence_score(node.get(DERIVED_HADA_KEY, {}))
        verb_score += verb_delta
        adjective_score += adjective_delta
    if verb_score > adjective_score:
        return "동사"
    if adjective_score > verb_score:
        return "형용사"
    return ""


def _derived_hada_evidence_score(meta: object) -> tuple[int, int]:
    if not isinstance(meta, dict):
        return 0, 0

    semantic = str(meta.get("base_semantic", ""))
    derivation_tag = str(meta.get("derivation_tag", ""))
    derivation_surface = str(meta.get("derivation_surface", ""))
    ending_surfaces = meta.get("ending_surfaces", [])
    if not isinstance(ending_surfaces, list):
        ending_surfaces = []
    first_ending = str(ending_surfaces[0]) if ending_surfaces else ""

    verb_score = 0
    adjective_score = 0
    if semantic == "행위":
        verb_score += 3
    elif semantic == "정적사태":
        adjective_score += 3

    if first_ending == "게":
        adjective_score += 3
    elif _primary_tag(derivation_tag) == "XSV":
        if _is_finite_or_nominalized_derivation(derivation_tag):
            verb_score += 3
        elif first_ending in {"고", "여", "아", "어", "도록", "기"}:
            verb_score += 2
        elif first_ending in {"는", "던"} or derivation_surface.endswith("는"):
            verb_score += 3
        else:
            verb_score += 1
    elif _primary_tag(derivation_tag) == "XSA":
        adjective_score += 1

    return verb_score, adjective_score


def _first_ending_surface(parts: list[MorphPart]) -> str:
    return _part_surface(parts[0]) if parts else ""


def _predicate_lemma(parts: list[MorphPart]) -> str:
    if not parts:
        return ""
    expression_stem = _expression_first_stem(_part_expression(parts[0]))
    if expression_stem:
        return expression_stem
    return _part_surface(parts[0])


def _expression_first_stem(expression: str) -> str:
    if not expression:
        return ""
    first = expression.split("+", maxsplit=1)[0]
    fields = first.split("/")
    if len(fields) < 2:
        return ""
    stem, tag = fields[0], fields[1]
    if _primary_tag(tag) in {"VV", "VX", "VA", "VCN"}:
        return stem
    return ""


def _is_finite_or_nominalized_derivation(tag: str) -> bool:
    tags = _tag_parts(tag)
    return bool(tags & {"EF", "ETN"})


def _normalize_part(part: MorphPart) -> NormalizedMorphPart:
    surface = str(part[0])
    tag = str(part[1])
    semantic = ""
    if len(part) > 2 and part[2] is not None:
        semantic = str(part[2])
    expression = ""
    if len(part) > 3 and part[3] is not None:
        expression = str(part[3])
    return NormalizedMorphPart(surface=surface, tag=tag, semantic=semantic, expression=expression)


def _part_surface(part: MorphPart) -> str:
    return part.surface if isinstance(part, NormalizedMorphPart) else str(part[0])


def _part_tag(part: MorphPart) -> str:
    return part.tag if isinstance(part, NormalizedMorphPart) else str(part[1])


def _part_semantic(part: MorphPart) -> str:
    if isinstance(part, NormalizedMorphPart):
        return part.semantic
    return str(part[2]) if len(part) > 2 and part[2] is not None else ""


def _part_expression(part: MorphPart) -> str:
    if isinstance(part, NormalizedMorphPart):
        return part.expression
    return str(part[3]) if len(part) > 3 and part[3] is not None else ""


def _primary_tag(tag: str) -> str:
    return str(tag).split("+", maxsplit=1)[0]


def _tag_parts(tag: str) -> set[str]:
    return {part for part in str(tag).split("+") if part}


def _is_standalone_ending(tag: str) -> bool:
    primary = _primary_tag(tag)
    return primary in ENDING_TAGS or primary.startswith("E")


def _is_symbol(tag: str) -> bool:
    tags = _tag_parts(tag)
    return bool(tags & SYMBOL_TAGS)


def _single_pos(primary_tag: str) -> str:
    if primary_tag in JOSA_TAGS:
        return "조사"
    if primary_tag == "NP":
        return "대명사"
    if primary_tag in {"NR", "SN"}:
        return "수사"
    if primary_tag == "MM":
        return "관형사"
    if primary_tag in {"MAG", "MAJ"}:
        return "부사"
    if primary_tag == "IC":
        return "감탄사"
    return ""
