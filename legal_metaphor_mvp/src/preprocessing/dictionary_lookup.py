"""Build lemma-level Standard Korean Dictionary lookup JSON."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from preprocessing.dictionary_client import StandardKoreanDictionaryClient
from utils import read_json, write_json


DEFAULT_OUTPUT = Path("data/output/lemma_dictionary_lookup.json")


def build_lemma_dictionary_lookup_payload(
    pos_payload: dict[str, Any],
    *,
    source_path: Path | str = "",
    client: StandardKoreanDictionaryClient | None = None,
    page_size: int | None = None,
) -> dict[str, Any]:
    """Return dictionary lookup output for every lemma group in a POS payload."""
    load_dotenv_if_available()
    dictionary = client or StandardKoreanDictionaryClient()
    groups = load_lemma_groups(pos_payload)
    results: list[dict[str, Any]] = []

    for group in groups:
        lemma = str(group.get("lemma", "")).strip()
        lookup = dictionary.lookup_dictionary_entries(lemma, page_size=page_size)
        item = {
            "lemma_group_id": str(group.get("lemma_group_id", "")),
            "lemma": lemma,
            "pos": str(group.get("pos", "")),
            "exists_in_dictionary": bool(lookup.get("exists_in_dictionary", False)),
            "status": str(lookup.get("status", "request_failed")),
            "total": int(lookup.get("total", 0)) if isinstance(lookup.get("total", 0), int) else 0,
            "definitions": lookup.get("definitions", []) if isinstance(lookup.get("definitions", []), list) else [],
        }
        if lookup.get("message"):
            item["message"] = str(lookup.get("message", ""))
        results.append(item)

    found_count = sum(1 for item in results if item.get("exists_in_dictionary"))
    return {
        "document_id": str(pos_payload.get("document_id", "")),
        "source_path": str(source_path),
        "summary": {
            "lemma_group_count": len(results),
            "found_count": found_count,
            "missing_count": len(results) - found_count,
        },
        "lemma_dictionary_results": results,
    }


def load_lemma_groups(pos_payload: dict[str, Any]) -> list[dict[str, Any]]:
    groups = pos_payload.get("lemma_groups", [])
    if not isinstance(groups, list):
        raise ValueError("input payload does not contain lemma_groups list")
    return [group for group in groups if isinstance(group, dict)]


def load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build lemma dictionary lookup JSON.")
    parser.add_argument("--input", type=Path, default=Path("data/output/pos_nodes_contextualized.json"))
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument(
        "--page-size",
        type=int,
        default=None,
        help="Dictionary API page size. Defaults to STDICT_PAGE_SIZE or 100.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = read_json(args.input, default={})
    if not isinstance(payload, dict):
        raise SystemExit(f"Input JSON must be an object: {args.input}")

    output = build_lemma_dictionary_lookup_payload(payload, source_path=args.input, page_size=args.page_size)
    write_json(args.output, output)
    summary = output["summary"]
    print(
        "lemma dictionary lookup complete "
        f"groups={summary['lemma_group_count']} "
        f"found={summary['found_count']} "
        f"missing={summary['missing_count']} "
        f"path={args.output}"
    )


if __name__ == "__main__":
    main()
