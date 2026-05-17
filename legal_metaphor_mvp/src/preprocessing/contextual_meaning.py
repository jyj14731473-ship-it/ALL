"""Extract contextual meanings for corrected lemma groups with an LLM."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from typing import Any

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils import read_json, write_json

PROMPT_VERSION = "contextual_meaning_v2"
DEFAULT_MODEL = "gpt-5.4-mini"
DEFAULT_BATCH_SIZE = 100


def extract_contextual_meanings(
    pos_payload: dict[str, Any],
    *,
    prompt_path: Path | None = None,
    source_text: str = "",
    model: str = DEFAULT_MODEL,
    batch_size: int = DEFAULT_BATCH_SIZE,
    cache_dir: Path | None = None,
    resume: bool = True,
    max_retries: int = 3,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Call an LLM and return POS JSON with contextual meanings attached plus a report."""
    groups = load_lemma_groups_from_payload(pos_payload)
    prompt = load_contextual_meaning_prompt(prompt_path or default_prompt_path())
    batches = build_contextual_meaning_batches(groups, batch_size=batch_size, source_text=source_text)
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)

    load_dotenv_if_available()
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set.")

    from openai import OpenAI

    client = OpenAI()
    batch_results = []
    for batch in batches:
        output_path = cache_dir / f"{batch['batch_id']}_output.json" if cache_dir else None
        if resume and output_path and output_path.exists():
            cached = read_json(output_path, default={})
            if (
                isinstance(cached, dict)
                and cached.get("prompt_version") == PROMPT_VERSION
                and cached.get("input_hash") == batch.get("input_hash")
            ):
                batch_results.append(cached)
                continue
        result = review_contextual_meaning_batch(
            client=client,
            model=model,
            prompt=prompt,
            batch=batch,
            max_retries=max_retries,
        )
        if output_path:
            write_json(output_path, result)
        batch_results.append(result)

    output, report = merge_contextual_meaning_results(pos_payload, groups, batch_results)
    report["summary"]["batch_count"] = len(batches)
    report["summary"]["batch_size"] = batch_size
    report["summary"]["model"] = model
    return output, report


def build_contextual_meaning_batches(
    groups: list[dict[str, Any]],
    *,
    batch_size: int = DEFAULT_BATCH_SIZE,
    source_text: str = "",
) -> list[dict[str, Any]]:
    if batch_size <= 0:
        raise ValueError("batch_size must be positive")
    batches = []
    sorted_groups = sorted(groups, key=lambda group: lemma_group_sort_key(group.get("lemma_group_id", "")))
    for batch_index, start in enumerate(range(0, len(sorted_groups), batch_size), start=1):
        batch_groups = sorted_groups[start : start + batch_size]
        payload = {
            "batch_id": f"batch_{batch_index:03d}",
            "prompt_version": PROMPT_VERSION,
            "group_count": len(batch_groups),
            "document_text": source_text,
            "lemma_groups": [make_contextual_meaning_input(group) for group in batch_groups],
        }
        payload["input_hash"] = batch_input_hash(payload)
        batches.append(payload)
    return batches


def make_contextual_meaning_input(group: dict[str, Any]) -> dict[str, Any]:
    return {
        "lemma_group_id": str(group.get("lemma_group_id", "")),
        "lemma": str(group.get("lemma", "")),
        "occurrences": [
            {
                "sentence_id": str(occurrence.get("sentence_id", "")),
                "surface": str(occurrence.get("surface", "")),
                "sentence": str(occurrence.get("sentence", "")),
            }
            for occurrence in group.get("occurrences", [])
            if isinstance(occurrence, dict)
        ],
    }


def review_contextual_meaning_batch(
    *,
    client: Any,
    model: str,
    prompt: str,
    batch: dict[str, Any],
    max_retries: int,
) -> dict[str, Any]:
    batch_json = json.dumps(batch, ensure_ascii=False, indent=2)
    messages = [
        {
            "role": "user",
            "content": prompt.replace("{{BATCH_JSON}}", batch_json),
        }
    ]
    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = client.chat.completions.create(
                model=model,
                messages=messages,
                response_format={"type": "json_object"},
                max_completion_tokens=12000,
                reasoning_effort="low",
            )
            content = response.choices[0].message.content or "{}"
            return normalize_contextual_meaning_result(json.loads(content), batch)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < max_retries:
                time.sleep(2**attempt)
    raise RuntimeError(f"contextual meaning batch failed after {max_retries} attempts: {last_error}")


def normalize_contextual_meaning_result(result: object, batch: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(result, dict):
        result = {}
    input_groups = {
        str(group.get("lemma_group_id", "")): group for group in batch.get("lemma_groups", []) if isinstance(group, dict)
    }
    raw_items = result.get("contextual_meanings", [])
    by_id: dict[str, dict[str, str]] = {}
    issues = []
    for item in raw_items if isinstance(raw_items, list) else []:
        if not isinstance(item, dict):
            continue
        group_id = str(item.get("lemma_group_id", ""))
        input_group = input_groups.get(group_id)
        if input_group is None:
            continue
        meaning = str(item.get("contextual_meaning", "")).strip()
        if not meaning:
            issues.append({"lemma_group_id": group_id, "issue": "empty_contextual_meaning"})
            meaning = "WIDLII: 문맥상 의미를 확정하기 어렵다."
        by_id[group_id] = {
            "lemma_group_id": group_id,
            "lemma": str(input_group.get("lemma", "")),
            "contextual_meaning": meaning,
        }

    normalized = []
    for group_id, input_group in input_groups.items():
        item = by_id.get(group_id)
        if item is None:
            issues.append({"lemma_group_id": group_id, "issue": "missing_contextual_meaning"})
            item = {
                "lemma_group_id": group_id,
                "lemma": str(input_group.get("lemma", "")),
                "contextual_meaning": "WIDLII: 문맥상 의미를 확정하기 어렵다.",
            }
        normalized.append(item)
    return {
        "prompt_version": PROMPT_VERSION,
        "input_hash": batch.get("input_hash", ""),
        "batch_id": batch.get("batch_id", ""),
        "contextual_meanings": normalized,
        "issues": issues,
        "batch_summary": result.get("batch_summary", {}),
    }


def merge_contextual_meaning_results(
    pos_payload: dict[str, Any],
    groups: list[dict[str, Any]],
    batch_results: list[dict[str, Any]],
) -> tuple[dict[str, Any], dict[str, Any]]:
    by_id = {}
    issues = []
    for result in batch_results:
        for item in result.get("contextual_meanings", []):
            if isinstance(item, dict):
                by_id[str(item.get("lemma_group_id", ""))] = item
        for issue in result.get("issues", []):
            if isinstance(issue, dict):
                issues.append(issue)

    contextualized_payload = copy.deepcopy(pos_payload)
    payload_groups = contextualized_payload.get("lemma_groups", [])
    if not isinstance(payload_groups, list):
        payload_groups = []
        contextualized_payload["lemma_groups"] = payload_groups

    missing = []
    for group in payload_groups:
        if not isinstance(group, dict):
            continue
        group_id = str(group.get("lemma_group_id", ""))
        item = by_id.get(group_id)
        if item is None:
            missing.append(group_id)
            item = {
                "lemma_group_id": group_id,
                "lemma": str(group.get("lemma", "")),
                "contextual_meaning": "WIDLII: 문맥상 의미를 확정하기 어렵다.",
            }
        meaning = str(item.get("contextual_meaning", "")).strip()
        if not meaning:
            missing.append(group_id)
            meaning = "WIDLII: 문맥상 의미를 확정하기 어렵다."
        group["contextual_meaning"] = meaning

    report = {
        "prompt_version": PROMPT_VERSION,
        "summary": {
            "input_groups": len(groups),
            "output_contextualized_groups": len([group for group in payload_groups if isinstance(group, dict)]),
            "output_contextual_meanings": len([group for group in payload_groups if isinstance(group, dict)]),
            "missing_contextual_meanings": len(missing),
            "issues": len(issues),
        },
        "missing_lemma_group_ids": missing,
        "issues": issues,
    }
    return contextualized_payload, report


def load_lemma_groups_from_payload(payload: dict[str, Any]) -> list[dict[str, Any]]:
    groups = payload.get("lemma_groups", [])
    if not isinstance(groups, list):
        raise ValueError("input payload does not contain lemma_groups list")
    return [strip_group(group) for group in groups if isinstance(group, dict)]


def strip_group(group: dict[str, Any]) -> dict[str, Any]:
    return {
        "lemma_group_id": str(group.get("lemma_group_id", "")),
        "lemma": str(group.get("lemma", "")),
        "occurrences": [
            {
                "sentence_id": str(occurrence.get("sentence_id", "")),
                "surface": str(occurrence.get("surface", "")),
                "sentence": str(occurrence.get("sentence", "")),
            }
            for occurrence in group.get("occurrences", [])
            if isinstance(occurrence, dict)
        ],
    }


def load_contextual_meaning_prompt(path: Path) -> str:
    if not path.exists():
        raise FileNotFoundError(f"Missing prompt file: {path}")
    return path.read_text(encoding="utf-8")


def batch_input_hash(payload: dict[str, Any]) -> str:
    stable_payload = {
        "document_text": payload.get("document_text", ""),
        "lemma_groups": payload.get("lemma_groups", []),
    }
    stable = json.dumps(stable_payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()[:16]


def lemma_group_sort_key(group_id: object) -> tuple[int, str]:
    text = str(group_id)
    digits = "".join(ch for ch in text if ch.isdigit())
    return (int(digits) if digits else 10**9, text)


def default_prompt_path() -> Path:
    return Path(__file__).resolve().parents[1] / "prompts" / "contextual_meaning.md"


def infer_report_output_path(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.stem}_report.json")


def infer_cache_dir(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.stem}_batches")


def load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Extract lemma group contextual meanings with an LLM.")
    parser.add_argument("--input", type=Path, default=Path("data/output/pos_nodes_corrected.json"))
    parser.add_argument("--text-input", type=Path, default=None, help="Original judgment text to include in each LLM batch.")
    parser.add_argument("--output", type=Path, default=Path("data/output/pos_nodes_contextualized.json"))
    parser.add_argument("--report-output", type=Path, default=None)
    parser.add_argument("--prompt", type=Path, default=default_prompt_path())
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE)
    parser.add_argument("--cache-dir", type=Path, default=None)
    parser.add_argument("--no-resume", action="store_true")
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--prepare-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = read_json(args.input, default={})
    if not isinstance(payload, dict):
        raise SystemExit(f"Input JSON must be an object: {args.input}")

    if args.prepare_only:
        groups = load_lemma_groups_from_payload(payload)
        source_text = args.text_input.read_text(encoding="utf-8") if args.text_input else ""
        batches = build_contextual_meaning_batches(groups, batch_size=args.batch_size, source_text=source_text)
        cache_dir = args.cache_dir or infer_cache_dir(args.output)
        cache_dir.mkdir(parents=True, exist_ok=True)
        for batch in batches:
            write_json(cache_dir / f"{batch['batch_id']}_input.json", batch)
        print(f"prepared contextual meaning batches={len(batches)} groups={len(groups)} cache_dir={cache_dir}")
        return

    output, report = extract_contextual_meanings(
        payload,
        prompt_path=args.prompt,
        source_text=args.text_input.read_text(encoding="utf-8") if args.text_input else "",
        model=args.model,
        batch_size=args.batch_size,
        cache_dir=args.cache_dir or infer_cache_dir(args.output),
        resume=not args.no_resume,
        max_retries=args.max_retries,
    )
    write_json(args.output, output)
    write_json(args.report_output or infer_report_output_path(args.output), report)
    print(
        "contextualized POS JSON complete "
        f"input_groups={report['summary']['input_groups']} "
        f"output={report['summary']['output_contextualized_groups']} "
        f"missing={report['summary']['missing_contextual_meanings']} "
        f"issues={report['summary']['issues']} "
        f"path={args.output}"
    )


if __name__ == "__main__":
    main()
