"""Deterministic conversion from canonical annotation JSON to RDF Turtle."""

from __future__ import annotations

import argparse
from pathlib import Path

from rdf.convert import convert_payload_to_turtle
from utils import read_json, write_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert annotation JSON to RDF Turtle (deterministic).")
    parser.add_argument("--input", type=Path, default=Path("data/output/metaphors_raw.json"))
    parser.add_argument("--output", type=Path, default=Path("data/output/metaphors.ttl"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = read_json(args.input, default={})
    turtle = convert_payload_to_turtle(payload)
    write_text(args.output, turtle)
    print(f"[rdf_convert] saved: {args.output}")


if __name__ == "__main__":
    main()

