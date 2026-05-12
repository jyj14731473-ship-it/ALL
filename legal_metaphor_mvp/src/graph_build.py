"""Build a local RDFLib knowledge graph from annotation JSON or Turtle."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from rdflib import Graph

from rdf.convert import convert_payload_to_turtle
from utils import read_json, write_text

JSON_SUFFIXES = {".json", ".jsonl"}


def graph_from_annotation_payload(payload: Any) -> Graph:
    """Convert canonical annotation JSON to Turtle and load it into RDFLib."""
    turtle = convert_payload_to_turtle(payload)
    graph = Graph()
    graph.parse(data=turtle, format="turtle")
    return graph


def graph_from_turtle(turtle_path: Path) -> Graph:
    """Load an existing Turtle file into RDFLib."""
    graph = Graph()
    graph.parse(turtle_path, format="turtle")
    return graph


def build_graph(input_path: Path) -> Graph:
    """Build a local RDF graph from JSON pipeline output or Turtle."""
    if input_path.suffix.lower() in JSON_SUFFIXES:
        payload = read_json(input_path, default={})
        return graph_from_annotation_payload(payload)
    return graph_from_turtle(input_path)


def serialize_graph(graph: Graph, output_path: Path, output_format: str = "turtle") -> None:
    """Serialize an RDFLib graph to disk."""
    serialized = graph.serialize(format=output_format)
    write_text(output_path, str(serialized))


def graph_stats(graph: Graph) -> dict[str, int]:
    """Return minimal graph statistics for CLI and tests."""
    return {"triple_count": len(graph)}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a local metaphor knowledge graph with RDFLib.")
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("data/output/graph_annotation.json"),
        help="Input annotation JSON or Turtle file path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/output/metaphor_kg.ttl"),
        help="Serialized knowledge graph output path.",
    )
    parser.add_argument(
        "--format",
        type=str,
        default="turtle",
        help="RDFLib serialization format, e.g. turtle, nt, json-ld.",
    )
    parser.add_argument(
        "--stats-output",
        type=Path,
        default=None,
        help="Optional JSON stats output path.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    graph = build_graph(args.input)
    serialize_graph(graph, args.output, args.format)
    stats = graph_stats(graph)
    if args.stats_output:
        write_text(args.stats_output, json.dumps(stats, ensure_ascii=False, indent=2))
    print(f"[graph_build] triples={stats['triple_count']}")
    print(f"[graph_build] saved: {args.output}")


if __name__ == "__main__":
    main()
