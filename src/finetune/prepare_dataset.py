"""Prepare fine-tuning dataset files from human-reviewed gold annotations."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils import read_jsonl, write_jsonl  # noqa: E402


def _extract_input_text(row: dict[str, Any]) -> str:
    for key in ("input_text", "legal_text", "text", "document_text"):
        value = row.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def _extract_annotation(row: dict[str, Any]) -> dict[str, Any]:
    if isinstance(row.get("annotation"), dict):
        ann = row["annotation"]
        if isinstance(ann.get("metaphors"), list):
            return {"metaphors": ann["metaphors"]}
    if isinstance(row.get("metaphors"), list):
        return {"metaphors": row["metaphors"]}
    return {"metaphors": []}


def _to_finetune_example(row: dict[str, Any]) -> dict[str, Any]:
    input_text = _extract_input_text(row)
    annotation = _extract_annotation(row)
    # Lightweight provider-agnostic JSONL shape for annotation model training.
    return {
        "input": input_text,
        "output": json.dumps(annotation, ensure_ascii=False),
    }


def split_rows(rows: list[dict[str, Any]], train_ratio: float = 0.8, valid_ratio: float = 0.1) -> tuple[list, list, list]:
    n = len(rows)
    train_end = int(n * train_ratio)
    valid_end = train_end + int(n * valid_ratio)
    return rows[:train_end], rows[train_end:valid_end], rows[valid_end:]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Prepare train/valid/test data from gold.jsonl.")
    parser.add_argument("--input", type=Path, default=Path("data/annotations/gold.jsonl"))
    parser.add_argument("--out-dir", type=Path, default=Path("data/finetune"))
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    gold_rows = read_jsonl(args.input)
    examples = [_to_finetune_example(row) for row in gold_rows if isinstance(row, dict)]
    examples = [row for row in examples if row.get("input")]

    train_rows, valid_rows, test_rows = split_rows(examples)
    write_jsonl(args.out_dir / "train.jsonl", train_rows)
    write_jsonl(args.out_dir / "valid.jsonl", valid_rows)
    write_jsonl(args.out_dir / "test.jsonl", test_rows)

    print(f"[prepare_dataset] source rows: {len(gold_rows)}")
    print(f"[prepare_dataset] usable rows: {len(examples)}")
    print(f"[prepare_dataset] train/valid/test: {len(train_rows)}/{len(valid_rows)}/{len(test_rows)}")
    print(f"[prepare_dataset] saved in: {args.out_dir}")


if __name__ == "__main__":
    main()

