"""Main entry point for annotation execution.

Official default pipeline is the LangGraph-based MIPVU-RDF workflow.
Legacy prompt/fine-tuned backends remain available for development use.
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import Any

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - optional at runtime
    def load_dotenv(*_args: object, **_kwargs: object) -> bool:
        return False

from annotation.base import BaseAnnotator
from annotation.finetuned_annotator import FineTunedAnnotator
from annotation.prompt_annotator import PromptAnnotator
from graph.annotation_graph import run_annotation_graph
from rdf.convert import convert_payload_to_turtle
from utils import read_text, write_json, write_text


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
        help="Annotation backend for legacy pipelines. Default: prompt.",
    )
    parser.add_argument(
        "--pipeline",
        type=str,
        default="graph",
        choices=["graph", "staged", "legacy-simple"],
        help="Pipeline mode for annotation backend.",
    )
    parser.add_argument(
        "--prompt-dir",
        type=Path,
        default=Path("src/prompts"),
        help="Canonical prompt directory used by prompt annotator and graph nodes.",
    )
    parser.add_argument("--model", type=str, default=None, help="Optional model name for future integration.")
    parser.add_argument("--ttl-output", type=Path, default=None, help="Optional RDF Turtle output path.")
    parser.add_argument("--document-id", type=str, default="", help="Optional document identifier.")
    parser.add_argument("--case-id", type=str, default="", help="Optional case identifier.")
    return parser.parse_args()


def _llm_available() -> bool:
    return bool(os.getenv("OPENAI_API_KEY", "").strip())


def _validation_status(payload: dict[str, Any]) -> str:
    results = payload.get("validation_results", [])
    if not isinstance(results, list):
        return "ok"
    for item in results:
        if not isinstance(item, dict):
            continue
        if item.get("repair_needed"):
            return "needs_repair"
        issues = item.get("issues", [])
        if isinstance(issues, list) and any(isinstance(issue, dict) and issue.get("severity") == "error" for issue in issues):
            return "needs_repair"
    return "ok"


def _normalize_graph_payload(
    state: dict[str, Any],
    *,
    pipeline: str,
    annotator: str,
    prompt_dir: Path,
    llm_available: bool,
) -> dict[str, Any]:
    metadata = dict(state.get("metadata", {}))
    metadata.update(
        {
            "pipeline": pipeline,
            "annotator": annotator,
            "official_pipeline": pipeline == "graph",
            "prompt_directory": str(prompt_dir),
            "llm_available": llm_available,
        }
    )
    validation_status = _validation_status(state)
    metadata["validation_status"] = validation_status
    payload = {
        "document_id": state.get("document_id", ""),
        "case_id": state.get("case_id", ""),
        "candidates": state.get("candidates", []),
        "mipvu_annotations": state.get("mipvu_annotations", []),
        "metaphor_annotations": state.get("metaphor_annotations", []),
        "rdf_mappings": state.get("rdf_mappings", []),
        "validation_results": state.get("validation_results", []),
        "human_review_items": state.get("human_review_items", []),
        "rdf_output": state.get("rdf_output", ""),
        "errors": list(state.get("errors", [])),
        "metadata": metadata,
        "status": "needs_repair" if validation_status == "needs_repair" else state.get("status", "completed"),
    }
    if not llm_available and not any("OPENAI_API_KEY" in str(item) for item in payload["errors"]):
        payload["errors"].append("[main] OPENAI_API_KEY가 없어 graph pipeline의 LLM 단계가 빈 결과 또는 fallback 결과를 반환했습니다.")
    return payload


def _normalize_legacy_payload(
    annotation: dict[str, Any],
    *,
    document_id: str,
    case_id: str,
    pipeline: str,
    annotator: str,
    prompt_dir: Path,
    llm_available: bool,
) -> dict[str, Any]:
    stage_outputs = annotation.get("stage_outputs", {}) if isinstance(annotation.get("stage_outputs"), dict) else {}
    candidates = stage_outputs.get("candidate_extract", {}).get("candidates", []) if isinstance(stage_outputs.get("candidate_extract"), dict) else []
    mipvu_annotations = stage_outputs.get("mipvu_judge", {}).get("judgments", []) if isinstance(stage_outputs.get("mipvu_judge"), dict) else []
    metaphor_annotations = annotation.get("metaphors", []) if isinstance(annotation.get("metaphors"), list) else []
    payload = {
        "document_id": document_id,
        "case_id": case_id,
        "candidates": candidates,
        "mipvu_annotations": mipvu_annotations,
        "metaphor_annotations": metaphor_annotations,
        "rdf_mappings": [],
        "validation_results": [],
        "human_review_items": [],
        "rdf_output": "",
        "errors": [],
        "metadata": {
            "pipeline": pipeline,
            "annotator": annotator,
            "official_pipeline": False,
            "experimental": annotator == "finetuned",
            "prompt_directory": str(prompt_dir),
            "llm_available": llm_available,
            "validation_status": "ok",
        },
        "status": "completed",
    }
    if not llm_available:
        payload["errors"].append("[main] OPENAI_API_KEY가 없어 legacy pipeline의 LLM 단계가 빈 결과를 반환했을 수 있습니다.")
    return payload


def main() -> None:
    load_dotenv()
    args = parse_args()
    input_text = read_text(args.input)
    document_id = args.document_id or args.input.stem
    case_id = args.case_id
    llm_available = _llm_available()

    if args.pipeline == "graph":
        state = run_annotation_graph(raw_text=input_text, document_id=document_id, case_id=case_id)
        output_payload = _normalize_graph_payload(
            state,
            pipeline="graph",
            annotator=args.annotator,
            prompt_dir=args.prompt_dir,
            llm_available=llm_available,
        )
        if args.annotator == "finetuned":
            output_payload["errors"].append("[main] graph pipeline은 현재 prompt-based LangGraph 경로만 공식 지원합니다. finetuned backend 요청은 무시되었습니다.")
            output_payload["metadata"]["experimental_finetuned_requested"] = True
    else:
        annotator = select_annotator(args.annotator, prompt_dir=args.prompt_dir, model=args.model)
        legacy_pipeline = "legacy-simple" if args.pipeline == "legacy-simple" else "staged"
        annotation = annotator.annotate(text=input_text, pipeline=legacy_pipeline)
        if not isinstance(annotation, dict):
            annotation = {"metaphors": []}
        output_payload = _normalize_legacy_payload(
            annotation,
            document_id=document_id,
            case_id=case_id,
            pipeline=legacy_pipeline,
            annotator=args.annotator,
            prompt_dir=args.prompt_dir,
            llm_available=llm_available,
        )
        output_payload["rdf_output"] = convert_payload_to_turtle(output_payload, output_payload.get("validation_results", []))

    if args.ttl_output:
        if not output_payload.get("rdf_output"):
            output_payload["rdf_output"] = convert_payload_to_turtle(output_payload, output_payload.get("validation_results", []))
        write_text(args.ttl_output, str(output_payload.get("rdf_output", "")))

    write_json(args.output, output_payload)
    print(f"[main] annotator={args.annotator} pipeline={args.pipeline} status={output_payload.get('status', 'completed')}")
    print(f"[main] saved: {args.output}")
    if args.ttl_output:
        print(f"[main] ttl saved: {args.ttl_output}")


if __name__ == "__main__":
    main()
