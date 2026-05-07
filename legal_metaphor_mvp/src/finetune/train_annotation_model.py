"""Placeholder trainer for annotation fine-tuning.

No heavy ML dependency is added in MVP.
Integrate provider-specific training APIs later.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils import read_json, write_json  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Train annotation model placeholder.")
    parser.add_argument("--train", type=Path, default=Path("data/finetune/train.jsonl"))
    parser.add_argument("--valid", type=Path, default=Path("data/finetune/valid.jsonl"))
    parser.add_argument("--config", type=Path, default=Path("models/ft_model_config.json"))
    parser.add_argument("--provider", type=str, default="openai")
    parser.add_argument("--model-name", type=str, default="")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.train.exists():
        print(f"[train_annotation_model] missing train file: {args.train}")
        return
    if not args.valid.exists():
        print(f"[train_annotation_model] missing valid file: {args.valid}")
        return

    # TODO:
    # - OpenAI fine-tuning API call
    # - local SFT call
    # - other provider-specific training orchestration
    print("[train_annotation_model] Placeholder training only. No real training executed.")

    current = read_json(args.config, default={})
    if not isinstance(current, dict):
        current = {}

    placeholder_name = args.model_name.strip() or current.get("model_name", "")
    updated = {
        "enabled": bool(placeholder_name),
        "provider": args.provider,
        "model_name": placeholder_name,
        "status": "placeholder_config_updated",
        "notes": "Set model_name after actual fine-tuning job is created.",
    }
    write_json(args.config, updated)
    print(f"[train_annotation_model] updated config: {args.config}")


if __name__ == "__main__":
    main()

