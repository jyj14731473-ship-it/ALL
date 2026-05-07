"""Main entry point for annotation execution.

Default backend is prompt-based.
Fine-tuned backend is optional and activated explicitly by CLI.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from dotenv import load_dotenv

from annotation.base import BaseAnnotator
from annotation.finetuned_annotator import FineTunedAnnotator
from annotation.prompt_annotator import PromptAnnotator
from utils import read_text, write_json


def select_annotator(annotator_name: str, prompt_dir: Path, model: str | None = None) -> BaseAnnotator:
    """Select annotation backend by CLI option."""
    if annotator_name == "finetuned":
        return FineTunedAnnotator()
    return PromptAnnotator(prompt_dir=prompt_dir, model=model)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run legal metaphor annotation pipeline.")
    parser.add_argument("--input", type=Path, default=Path("data/input.txt"), help="Input legal text path.")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/output/metaphors_raw.json"),
        help="Output annotation JSON path.",
    )
    parser.add_argument(
        "--annotator",
        type=str,
        default="prompt",
        choices=["prompt", "finetuned"],
        help="Annotation backend. Default: prompt.",
    )
    parser.add_argument(
        "--pipeline",
        type=str,
        default="simple",
        choices=["simple", "staged"],
        help="Pipeline mode for annotation backend.",
    )
    parser.add_argument(
        "--prompt-dir",
        type=Path,
        default=Path("prompts"),
        help="Prompt directory used by prompt annotator.",
    )
    parser.add_argument("--model", type=str, default=None, help="Optional model name for future integration.")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()
    input_text = read_text(args.input)

    annotator = select_annotator(args.annotator, prompt_dir=args.prompt_dir, model=args.model)
    annotation = annotator.annotate(text=input_text, pipeline=args.pipeline)

    # Keep canonical shape stable.
    if not isinstance(annotation, dict) or "metaphors" not in annotation:
        annotation = {"metaphors": [], "stage_outputs": {}}
    if not isinstance(annotation.get("metaphors"), list):
        annotation["metaphors"] = []

    write_json(args.output, annotation)
    print(f"[main] annotator={args.annotator} pipeline={args.pipeline}")
    print(f"[main] saved: {args.output}")


if __name__ == "__main__":
    main()
