"""Placeholder evaluator for fine-tuned annotation model."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils import read_jsonl  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate annotation model placeholder.")
    parser.add_argument("--gold", type=Path, default=Path("data/annotations/gold.jsonl"))
    parser.add_argument("--pred", type=Path, default=Path("data/output/metaphors_finetuned.jsonl"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    gold = read_jsonl(args.gold)
    pred = read_jsonl(args.pred)

    print("[evaluate_annotation_model] Placeholder evaluation only.")
    print(f"[evaluate_annotation_model] gold rows: {len(gold)}")
    print(f"[evaluate_annotation_model] pred rows: {len(pred)}")
    print("[evaluate_annotation_model] TODO metrics:")
    print("- metaphor detection precision/recall/F1")
    print("- metaphor judgment accuracy")
    print("- source_domain classification accuracy")
    print("- target_domain classification accuracy")
    print("- metaphor_type accuracy")
    print("- JSON schema validity")


if __name__ == "__main__":
    main()

