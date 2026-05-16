"""Lightweight validator for metaphor annotation JSON schema."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from utils import read_json

REQUIRED_FIELDS = [
    "metaphor_id",
    "source_candidate_id",
    "surface_expression",
    "context_sentence",
    "legal_concept",
    "target_domain",
    "source_domain",
    "conceptual_metaphor",
    "metaphor_type",
    "is_legal_domain_specific",
    "opinion_type",
    "confidence",
    "rationale_brief",
]

VALID_METAPHOR_TYPES = {"structural", "ontological", "orientational", "uncertain"}
VALID_OPINION_TYPES = {"majority", "dissenting", "concurring", "unknown"}


def validate_item(item: dict[str, Any], idx: int) -> list[str]:
    errors: list[str] = []
    for key in REQUIRED_FIELDS:
        if key not in item:
            errors.append(f"metaphors[{idx}] missing field: {key}")

    if not str(item.get("surface_expression", "")).strip():
        errors.append(f"metaphors[{idx}] empty surface_expression")

    m_type = str(item.get("metaphor_type", ""))
    if m_type and m_type not in VALID_METAPHOR_TYPES:
        errors.append(f"metaphors[{idx}] invalid metaphor_type: {m_type}")

    o_type = str(item.get("opinion_type", ""))
    if o_type and o_type not in VALID_OPINION_TYPES:
        errors.append(f"metaphors[{idx}] invalid opinion_type: {o_type}")

    conf = item.get("confidence")
    if conf is not None and not isinstance(conf, (int, float)):
        errors.append(f"metaphors[{idx}] confidence must be numeric")
    return errors


def validate_payload(payload: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    metaphors = payload.get("metaphors")
    if not isinstance(metaphors, list):
        return ["top-level 'metaphors' must be a list"]
    for idx, item in enumerate(metaphors):
        if not isinstance(item, dict):
            errors.append(f"metaphors[{idx}] must be an object")
            continue
        errors.extend(validate_item(item, idx))
    return errors


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Validate metaphor annotation JSON schema.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/output/metaphors_raw.json"),
        help="Path to annotation JSON file.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = read_json(args.input, default={})
    if not payload:
        print(f"[validate_schema] Empty or missing JSON: {args.input}")
        return
    if not isinstance(payload, dict):
        print("[validate_schema] INVALID: top-level must be JSON object.")
        return
    errors = validate_payload(payload)
    if errors:
        print("[validate_schema] INVALID")
        for err in errors:
            print(f"- {err}")
        return
    print("[validate_schema] VALID")


if __name__ == "__main__":
    main()

