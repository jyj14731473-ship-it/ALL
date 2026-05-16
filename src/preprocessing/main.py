"""Build sentence-level 9-POS nodes and lemma groups from judgment text."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from preprocessing.lemma_grouper import build_lemma_groups
from preprocessing.mecab_analyzer import get_default_analyzer
from preprocessing.pos_reconstructor import finalize_pos_nodes, reconstruct_pos_nodes
from preprocessing.sentence_splitter import split_sentences
from utils import read_text, write_json


def build_pos_json(text: str, document_id: str = "doc001") -> dict:
    """Build sentence POS nodes and lemma grouping JSON from full judgment text."""
    analyzer = get_default_analyzer()
    sentence_items: list[dict[str, Any]] = []

    for sentence_index, sentence in enumerate(split_sentences(text), start=1):
        sentence_id = f"s{sentence_index:03d}"
        mecab_parts = analyzer.pos(sentence)
        pos_nodes = reconstruct_pos_nodes(mecab_parts, sentence_id)
        sentence_items.append(
            {
                "sentence_id": sentence_id,
                "sentence": sentence,
                "pos_nodes": pos_nodes,
            }
        )
    finalize_pos_nodes(sentence_items)

    return {
        "document_id": document_id,
        "sentences": sentence_items,
        "lemma_groups": build_lemma_groups(sentence_items),
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run preprocessing through optional GPT contextual meaning.")
    parser.add_argument("--input", type=Path, default=Path("data/input.txt"))
    parser.add_argument("--output", type=Path, default=Path("data/output/pos_nodes.json"))
    parser.add_argument("--document-id", type=str, default="doc001")
    parser.add_argument(
        "--full",
        action="store_true",
        help="Run the complete GPT pipeline: POS, lemma sanity correction, and contextual meaning.",
    )
    parser.add_argument("--no-resume", action="store_true", help="Ignore GPT batch caches for every GPT stage.")
    parser.add_argument(
        "--corrected-output",
        type=Path,
        default=None,
        help="Optional corrected POS JSON output path. Defaults to <output>_corrected.json when sanity flags are used.",
    )
    parser.add_argument("--lemma-sanity", action="store_true", help="Apply local lemma group sanity cleanup after writing output.")
    parser.add_argument("--lemma-sanity-gpt", action="store_true", help="Run GPT sanity scan plus local cleanup.")
    parser.add_argument("--lemma-sanity-model", type=str, default=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--lemma-sanity-prompt-dir", type=Path, default=Path("src/prompts"))
    parser.add_argument("--lemma-sanity-cache-dir", type=Path, default=None)
    parser.add_argument("--lemma-sanity-no-resume", action="store_true")
    parser.add_argument(
        "--contextual-meaning",
        action="store_true",
        help="Run GPT contextual meaning after POS/sanity output is prepared.",
    )
    parser.add_argument("--contextual-output", type=Path, default=Path("data/output/pos_nodes_contextualized.json"))
    parser.add_argument("--contextual-report-output", type=Path, default=None)
    parser.add_argument("--contextual-prompt", type=Path, default=None)
    parser.add_argument("--contextual-model", type=str, default=os.getenv("OPENAI_MODEL", "gpt-4.1-mini"))
    parser.add_argument("--contextual-batch-size", type=int, default=100)
    parser.add_argument("--contextual-cache-dir", type=Path, default=None)
    parser.add_argument("--contextual-no-resume", action="store_true")
    parser.add_argument("--contextual-max-retries", type=int, default=3)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.full:
        args.lemma_sanity_gpt = True
        args.contextual_meaning = True

    source_text = read_text(args.input)
    payload = build_pos_json(source_text, document_id=args.document_id)
    write_json(args.output, payload)
    print(
        "POS JSON complete "
        f"sentences={len(payload['sentences'])} "
        f"lemma_groups={len(payload['lemma_groups'])} "
        f"path={args.output}"
    )

    pipeline_payload = payload
    if args.corrected_output or args.lemma_sanity or args.lemma_sanity_gpt:
        from preprocessing.lemma_group_sanity import (
            correct_pos_json_payload,
            infer_corrected_output_path,
            infer_report_output_path,
        )

        corrected_output = args.corrected_output or infer_corrected_output_path(args.output)
        cache_dir = args.lemma_sanity_cache_dir
        if args.lemma_sanity_gpt and cache_dir is None:
            cache_dir = corrected_output.with_name(f"{corrected_output.stem}_batches")
        corrected_payload, report = correct_pos_json_payload(
            payload,
            use_gpt=args.lemma_sanity_gpt,
            prompt_dir=args.lemma_sanity_prompt_dir,
            model=args.lemma_sanity_model,
            cache_dir=cache_dir,
            resume=not (args.no_resume or args.lemma_sanity_no_resume),
        )
        write_json(corrected_output, corrected_payload)
        write_json(infer_report_output_path(corrected_output), report)
        pipeline_payload = corrected_payload
        print(
            "corrected POS JSON complete "
            f"input_groups={report['summary']['input_groups']} "
            f"output={report['summary']['output_groups']} "
            f"issues={report['summary']['issues']} "
            f"path={corrected_output}"
        )

    if args.contextual_meaning:
        from preprocessing.contextual_meaning import (
            default_prompt_path,
            extract_contextual_meanings,
            infer_cache_dir,
            infer_report_output_path,
        )

        output, report = extract_contextual_meanings(
            pipeline_payload,
            prompt_path=args.contextual_prompt or default_prompt_path(),
            source_text=source_text,
            model=args.contextual_model,
            batch_size=args.contextual_batch_size,
            cache_dir=args.contextual_cache_dir or infer_cache_dir(args.contextual_output),
            resume=not (args.no_resume or args.contextual_no_resume),
            max_retries=args.contextual_max_retries,
        )
        write_json(args.contextual_output, output)
        write_json(args.contextual_report_output or infer_report_output_path(args.contextual_output), report)
        print(
            "contextualized POS JSON complete "
            f"input_groups={report['summary']['input_groups']} "
            f"output={report['summary']['output_contextualized_groups']} "
            f"missing={report['summary']['missing_contextual_meanings']} "
            f"issues={report['summary']['issues']} "
            f"path={args.contextual_output}"
        )


if __name__ == "__main__":
    main()
