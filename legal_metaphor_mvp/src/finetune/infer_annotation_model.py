"""CLI wrapper for optional fine-tuned annotation inference."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from annotation.finetuned_annotator import FineTunedAnnotator  # noqa: E402
from utils import read_text, write_json  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run fine-tuned annotation inference (optional backend).")
    parser.add_argument("--input", type=Path, default=Path("data/input.txt"))
    parser.add_argument("--output", type=Path, default=Path("data/output/metaphors_finetuned.json"))
    parser.add_argument("--pipeline", type=str, default="simple", choices=["simple", "staged"])
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    text = read_text(args.input)
    annotator = FineTunedAnnotator()
    result = annotator.annotate(text=text, pipeline=args.pipeline)
    write_json(args.output, result)
    print(f"[infer_annotation_model] saved: {args.output}")


if __name__ == "__main__":
    main()

