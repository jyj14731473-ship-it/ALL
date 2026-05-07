"""Deterministic conversion from canonical annotation JSON to RDF Turtle."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from utils import escape_turtle_literal, read_json, slugify, write_text


def normalize_records(payload: Any) -> list[dict[str, Any]]:
    """Extract metaphor list from canonical payload."""
    if isinstance(payload, dict):
        rows = payload.get("metaphors")
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    return []


def to_turtle(records: list[dict[str, Any]]) -> str:
    """Render deterministic Turtle with fixed predicates."""
    lines = [
        "@prefix ex: <http://example.org/legal-metaphor#> .",
        "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
        "",
    ]
    if not records:
        lines.append("# No metaphor instances found.")
        return "\n".join(lines) + "\n"

    for idx, rec in enumerate(records, start=1):
        m_id = str(rec.get("metaphor_id") or f"M{idx}")
        c_id = str(rec.get("source_candidate_id") or f"C{idx:03d}")
        cm_label = str(rec.get("conceptual_metaphor") or "UnknownConceptualMetaphor")
        source_label = str(rec.get("source_domain") or "UnknownSourceDomain")
        target_label = str(rec.get("target_domain") or "UnknownTargetDomain")
        legal_label = str(rec.get("legal_concept") or "UnknownLegalConcept")

        m_uri = f"ex:metaphor_{slugify(m_id)}_{idx}"
        cm_uri = f"ex:cm_{slugify(cm_label)}"
        source_uri = f"ex:source_{slugify(source_label)}"
        target_uri = f"ex:target_{slugify(target_label)}"
        legal_uri = f"ex:legal_{slugify(legal_label)}"

        surface = escape_turtle_literal(str(rec.get("surface_expression", "")))
        context = escape_turtle_literal(str(rec.get("context_sentence", "")))
        m_type = escape_turtle_literal(str(rec.get("metaphor_type", "uncertain")))
        opinion = escape_turtle_literal(str(rec.get("opinion_type", "unknown")))
        conf = rec.get("confidence", 0.0)
        if not isinstance(conf, (int, float)):
            conf = 0.0

        lines.extend(
            [
                f"{m_uri} a ex:MetaphorInstance ;",
                f'  ex:hasSurfaceExpression "{surface}" ;',
                f'  ex:hasContextSentence "{context}" ;',
                f"  ex:hasLegalConcept {legal_uri} ;",
                f"  ex:hasTargetDomain {target_uri} ;",
                f"  ex:hasSourceDomain {source_uri} ;",
                f"  ex:realizesConceptualMetaphor {cm_uri} ;",
                f'  ex:hasMetaphorType "{m_type}" ;',
                f'  ex:appearsInOpinionType "{opinion}" ;',
                f'  ex:hasConfidence "{float(conf):.4f}"^^xsd:decimal ;',
                f'  ex:derivedFromCandidate "{escape_turtle_literal(c_id)}" .',
                "",
                f"{cm_uri} a ex:ConceptualMetaphor .",
                f"{source_uri} a ex:SourceDomain .",
                f"{target_uri} a ex:TargetDomain .",
                f"{legal_uri} a ex:LegalConcept .",
                "",
            ]
        )
    return "\n".join(lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert annotation JSON to RDF Turtle (deterministic).")
    parser.add_argument("--input", type=Path, default=Path("data/output/metaphors_raw.json"))
    parser.add_argument("--output", type=Path, default=Path("data/output/metaphors.ttl"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = read_json(args.input, default={})
    records = normalize_records(payload)
    turtle = to_turtle(records)
    write_text(args.output, turtle)
    print(f"[rdf_convert] saved: {args.output}")


if __name__ == "__main__":
    main()

