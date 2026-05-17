"""Sanity-clean lemma groups after deterministic POS preprocessing."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
import sys
import time
from collections import OrderedDict
from pathlib import Path
from typing import Any

SRC_DIR = Path(__file__).resolve().parents[1]
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from utils import read_json, write_json

ALLOWED_POS = {
    "명사",
    "대명사",
    "수사",
    "동사",
    "형용사",
    "조사",
    "관형사",
    "부사",
    "감탄사",
    "기호",
    "어미",
    "접사",
    "어근",
    "미분류",
}

APPLY_CONFIDENCE = {"high", "medium"}
PROMPT_VERSION = "sanity_v1"


def correct_pos_json_payload(
    payload: dict[str, Any],
    *,
    use_gpt: bool = False,
    prompt_dir: Path | None = None,
    model: str = "gpt-5.4-mini",
    batch_size: int = 100,
    max_occurrences_per_group: int = 8,
    max_sentence_chars: int = 420,
    max_retries: int = 3,
    cache_dir: Path | None = None,
    resume: bool = True,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a corrected copy of a full POS JSON payload plus a report."""
    corrected_payload = copy.deepcopy(payload)
    groups = load_lemma_groups_from_data(payload, Path("<payload>"))
    report = make_empty_report()
    working_groups = groups

    if use_gpt:
        prompt_dir = prompt_dir or default_prompt_dir()
        batch_results = run_gpt_sanity_review(
            groups=working_groups,
            prompt_dir=prompt_dir,
            model=model,
            batch_size=batch_size,
            max_occurrences_per_group=max_occurrences_per_group,
            max_sentence_chars=max_sentence_chars,
            max_retries=max_retries,
            cache_dir=cache_dir,
            resume=resume,
        )
        model_groups, model_report = apply_corrections(working_groups, batch_results)
        apply_node_updates(corrected_payload, working_groups, model_report["applied_corrections"])
        working_groups = model_groups
        extend_report(report, model_report, stage="gpt")

    local_groups, local_report = apply_obvious_cleanups(working_groups)
    apply_node_updates(corrected_payload, working_groups, local_report["applied_corrections"])
    working_groups = local_groups
    extend_report(report, local_report, stage="local")

    corrected_groups, reindex_report = reindex_lemma_group_ids(working_groups)
    corrected_payload["lemma_groups"] = corrected_groups
    report["reindex_report"] = reindex_report
    report["summary"] = {
        "input_groups": len(groups),
        "output_groups": len(corrected_groups),
        "applied_corrections": len(report["applied_corrections"]),
        "ignored_corrections": len(report["ignored_corrections"]),
        "applied_drops": len(report["applied_drops"]),
        "issues": len(report["issues"]),
        "merged_groups": len(report["merge_report"]),
        "reindexed_groups": len(reindex_report),
    }
    return corrected_payload, report


def run_gpt_sanity_review(
    *,
    groups: list[dict[str, Any]],
    prompt_dir: Path,
    model: str,
    batch_size: int,
    max_occurrences_per_group: int,
    max_sentence_chars: int,
    max_retries: int,
    cache_dir: Path | None,
    resume: bool,
) -> list[dict[str, Any]]:
    load_dotenv_if_available()
    if not os.environ.get("OPENAI_API_KEY"):
        raise RuntimeError("OPENAI_API_KEY is not set.")

    from openai import OpenAI

    prompt = load_sanity_prompt(prompt_dir)
    client = OpenAI()
    batch_payloads = build_batch_payloads(
        groups=groups,
        batch_size=batch_size,
        max_occurrences_per_group=max_occurrences_per_group,
        max_sentence_chars=max_sentence_chars,
    )
    if cache_dir:
        cache_dir.mkdir(parents=True, exist_ok=True)

    results = []
    for batch in batch_payloads:
        output_path = cache_dir / f"{batch['batch_id']}_output.json" if cache_dir else None
        if resume and output_path and output_path.exists():
            cached = read_json(output_path, default={})
            if (
                isinstance(cached, dict)
                and cached.get("prompt_version") == PROMPT_VERSION
                and cached.get("input_hash") == batch.get("input_hash")
            ):
                results.append(cached)
                continue
        result = review_batch(
            client=client,
            model=model,
            batch=batch,
            prompt_template=prompt,
            max_retries=max_retries,
        )
        if output_path:
            write_json(output_path, result)
        results.append(result)
    return results


def load_sanity_prompt(prompt_dir: Path) -> str:
    prompt_path = prompt_dir / "lemma_group_sanity.md"
    if not prompt_path.exists():
        raise FileNotFoundError(f"Missing prompt file: {prompt_path}")
    return prompt_path.read_text(encoding="utf-8")


def review_batch(
    *,
    client: Any,
    model: str,
    batch: dict[str, Any],
    prompt_template: str,
    max_retries: int,
) -> dict[str, Any]:
    batch_json = json.dumps(batch, ensure_ascii=False, indent=2)
    messages = [
        {"role": "user", "content": prompt_template.replace("{{BATCH_JSON}}", batch_json)},
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
            return normalize_model_result(json.loads(content), batch)
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt < max_retries:
                time.sleep(2**attempt)
    raise RuntimeError(f"GPT lemma group sanity review failed after {max_retries} attempts: {last_error}")


def build_batch_payloads(
    *,
    groups: list[dict[str, Any]],
    batch_size: int,
    max_occurrences_per_group: int,
    max_sentence_chars: int,
) -> list[dict[str, Any]]:
    payloads = []
    sorted_groups = sorted(groups, key=lambda group: lemma_group_sort_key(group.get("lemma_group_id", "")))
    for batch_index, start in enumerate(range(0, len(sorted_groups), batch_size), start=1):
        batch_groups = sorted_groups[start : start + batch_size]
        review_groups = [
            make_review_view(group, max_occurrences_per_group, max_sentence_chars) for group in batch_groups
        ]
        payload = {
            "batch_id": f"batch_{batch_index:03d}",
            "prompt_version": PROMPT_VERSION,
            "group_count": len(batch_groups),
            "allowed_pos": sorted(ALLOWED_POS),
            "lemma_groups": review_groups,
        }
        payload["input_hash"] = batch_input_hash(payload)
        payloads.append(payload)
    return payloads


def make_review_view(group: dict[str, Any], max_occurrences: int, max_sentence_chars: int) -> dict[str, Any]:
    occurrences = group.get("occurrences", [])
    sample_occurrences = []
    for occurrence in occurrences[:max_occurrences]:
        sentence = str(occurrence.get("sentence", ""))
        sample_occurrences.append(
            {
                "sentence_id": occurrence.get("sentence_id", ""),
                "node_id": occurrence.get("node_id", ""),
                "surface": occurrence.get("surface", ""),
                "sentence": sentence[:max_sentence_chars],
            }
        )
    return {
        "lemma_group_id": group.get("lemma_group_id", ""),
        "lemma": group.get("lemma", ""),
        "pos": group.get("pos", ""),
        "occurrence_count": len(occurrences),
        "surfaces": sorted({str(occurrence.get("surface", "")) for occurrence in occurrences if occurrence}),
        "sample_occurrences": sample_occurrences,
    }


def normalize_model_result(result: object, batch: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(result, dict):
        result = {}
    input_groups = {group["lemma_group_id"]: group for group in batch.get("lemma_groups", [])}
    corrections = []
    for correction in result.get("corrections", []):
        if not isinstance(correction, dict):
            continue
        group_id = str(correction.get("lemma_group_id", ""))
        corrected_lemma = str(correction.get("corrected_lemma", "")).strip()
        corrected_pos = str(correction.get("corrected_pos", ""))
        confidence = str(correction.get("confidence", "low"))
        input_group = input_groups.get(group_id)
        if input_group is None or corrected_pos not in ALLOWED_POS:
            continue
        original_lemma = str(input_group.get("lemma", ""))
        original_pos = str(input_group.get("pos", ""))
        if not corrected_lemma:
            corrected_lemma = original_lemma
        if corrected_lemma == original_lemma and corrected_pos == original_pos:
            continue
        corrections.append(
            {
                "lemma_group_id": group_id,
                "corrected_lemma": corrected_lemma,
                "corrected_pos": corrected_pos,
                "confidence": confidence if confidence in {"high", "medium", "low"} else "low",
                "issue_types": correction.get("issue_types", []),
                "reason": str(correction.get("reason", "")),
            }
        )

    drop_groups = []
    for drop_group in result.get("drop_groups", []):
        if not isinstance(drop_group, dict):
            continue
        group_id = str(drop_group.get("lemma_group_id", ""))
        if group_id not in input_groups:
            continue
        confidence = str(drop_group.get("confidence", "low"))
        drop_groups.append(
            {
                "lemma_group_id": group_id,
                "confidence": confidence if confidence in {"high", "medium", "low"} else "low",
                "issue_types": drop_group.get("issue_types", []),
                "reason": str(drop_group.get("reason", "")),
            }
        )

    issues = []
    for issue in result.get("issues", []):
        if not isinstance(issue, dict):
            continue
        group_id = str(issue.get("lemma_group_id", ""))
        if group_id not in input_groups:
            continue
        issues.append(
            {
                "lemma_group_id": group_id,
                "issue_type": str(issue.get("issue_type", "uncertain")),
                "confidence": str(issue.get("confidence", "low")),
                "suggested_lemma": str(issue.get("suggested_lemma", "")),
                "suggested_pos": str(issue.get("suggested_pos", "")),
                "reason": str(issue.get("reason", "")),
            }
        )
    return {
        "prompt_version": PROMPT_VERSION,
        "input_hash": batch.get("input_hash", ""),
        "batch_id": batch.get("batch_id", ""),
        "corrections": corrections,
        "drop_groups": drop_groups,
        "issues": issues,
        "batch_summary": result.get("batch_summary", {}),
    }


def apply_corrections(
    groups: list[dict[str, Any]],
    batch_results: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    corrections_by_id = {}
    drops_by_id = {}
    issues = []
    for result in batch_results:
        for correction in result.get("corrections", []):
            confidence = correction.get("confidence", "low")
            if confidence in APPLY_CONFIDENCE:
                corrections_by_id[correction["lemma_group_id"]] = correction
        for drop_group in result.get("drop_groups", []):
            confidence = drop_group.get("confidence", "low")
            if confidence in APPLY_CONFIDENCE:
                drops_by_id[drop_group["lemma_group_id"]] = drop_group
        issues.extend(result.get("issues", []))

    applied = []
    ignored = []
    dropped = []
    normalized_groups = []
    for group in groups:
        group_id = group.get("lemma_group_id", "")
        updated = strip_group_for_review(group)
        drop_group = drops_by_id.get(group_id)
        if drop_group:
            dropped.append(
                {
                    "lemma_group_id": group_id,
                    "lemma": updated.get("lemma", ""),
                    "pos": updated.get("pos", ""),
                    "occurrence_count": len(updated.get("occurrences", [])),
                    "confidence": drop_group.get("confidence", ""),
                    "issue_types": drop_group.get("issue_types", []),
                    "reason": drop_group.get("reason", ""),
                }
            )
            continue
        correction = corrections_by_id.get(group_id)
        if correction:
            current = {"lemma": updated["lemma"], "pos": updated["pos"]}
            if not should_apply_model_correction(updated, correction):
                ignored.append(
                    {
                        "lemma_group_id": group_id,
                        "from": current,
                        "suggested_to": {
                            "lemma": correction.get("corrected_lemma") or updated["lemma"],
                            "pos": correction.get("corrected_pos") or updated["pos"],
                        },
                        "confidence": correction.get("confidence", ""),
                        "issue_types": correction.get("issue_types", []),
                        "reason": correction.get("reason", ""),
                    }
                )
                normalized_groups.append(updated)
                continue
            updated["lemma"] = correction.get("corrected_lemma") or updated["lemma"]
            updated["pos"] = correction.get("corrected_pos") or updated["pos"]
            applied.append(
                {
                    "lemma_group_id": group_id,
                    "from": current,
                    "to": {"lemma": updated["lemma"], "pos": updated["pos"]},
                    "confidence": correction.get("confidence", ""),
                    "issue_types": correction.get("issue_types", []),
                    "reason": correction.get("reason", ""),
                }
            )
        normalized_groups.append(updated)

    merged_groups, merge_report = merge_duplicate_groups(normalized_groups)
    return merged_groups, {
        "applied_corrections": applied,
        "ignored_corrections": ignored,
        "applied_drops": dropped,
        "issues": issues,
        "merge_report": merge_report,
    }


def apply_obvious_cleanups(groups: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Fix only high-certainty lemma/POS nonsense without model calls."""
    noun_lemmas = {str(group.get("lemma", "")) for group in groups if group.get("pos") == "명사"}
    applied = []
    normalized_groups = []

    for group in groups:
        updated = strip_group_for_review(group)
        current = {"lemma": updated["lemma"], "pos": updated["pos"]}
        repair = find_obvious_surface_lemma_repair(updated, noun_lemmas)
        if repair:
            updated["lemma"] = repair["lemma"]
            updated["pos"] = repair["pos"]
            applied.append(
                {
                    "lemma_group_id": updated.get("lemma_group_id", ""),
                    "from": current,
                    "to": {"lemma": updated["lemma"], "pos": updated["pos"]},
                    "confidence": "high",
                    "issue_types": ["obvious_lemma_error", "pos_error"],
                    "reason": repair["reason"],
                }
            )
        normalized_groups.append(updated)

    merged_groups, merge_report = merge_duplicate_groups(normalized_groups)
    return merged_groups, {
        "applied_corrections": applied,
        "ignored_corrections": [],
        "applied_drops": [],
        "issues": [],
        "merge_report": merge_report,
    }


def find_obvious_surface_lemma_repair(
    group: dict[str, Any],
    noun_lemmas: set[str],
) -> dict[str, str] | None:
    lemma = str(group.get("lemma", ""))
    pos = str(group.get("pos", ""))
    surfaces = unique_occurrence_surfaces(group)
    if len(surfaces) != 1:
        return None
    surface = surfaces[0]
    if pos not in {"동사", "형용사"} or not lemma.endswith("다") or lemma == surface:
        return None
    if surface not in noun_lemmas:
        return None
    return {
        "lemma": surface,
        "pos": "명사",
        "reason": (
            f"표면형 '{surface}'가 별도 명사 lemma로 존재하는데 "
            f"현재 group은 '{lemma}/{pos}'로 복원되어 명백한 표제어 오류로 보입니다."
        ),
    }


def should_apply_model_correction(group: dict[str, Any], correction: dict[str, Any]) -> bool:
    """Apply GPT corrections only when they fix lemma nonsense, not style-level POS."""
    corrected_lemma = str(correction.get("corrected_lemma") or group.get("lemma", ""))
    return corrected_lemma != str(group.get("lemma", ""))


def apply_node_updates(payload: dict[str, Any], groups: list[dict[str, Any]], corrections: list[dict[str, Any]]) -> None:
    groups_by_id = {str(group.get("lemma_group_id", "")): group for group in groups}
    nodes_by_id = index_pos_nodes(payload)
    for correction in corrections:
        group = groups_by_id.get(str(correction.get("lemma_group_id", "")))
        if not group:
            continue
        target = correction.get("to", {})
        lemma = str(target.get("lemma", ""))
        pos = str(target.get("pos", ""))
        if not lemma or not pos:
            continue
        for occurrence in group.get("occurrences", []):
            node_id = str(occurrence.get("node_id", ""))
            if "+" in node_id:
                continue
            node = nodes_by_id.get(node_id)
            if node is None:
                continue
            node["lemma"] = lemma
            node["pos"] = pos


def index_pos_nodes(payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    nodes = {}
    for sentence in payload.get("sentences", []):
        if not isinstance(sentence, dict):
            continue
        for node in sentence.get("pos_nodes", []):
            if isinstance(node, dict):
                nodes[str(node.get("node_id", ""))] = node
    return nodes


def load_lemma_groups(path: Path) -> list[dict[str, Any]]:
    return load_lemma_groups_from_data(read_json(path, default={}), path)


def load_lemma_groups_from_data(data: Any, path: Path) -> list[dict[str, Any]]:
    if isinstance(data, dict):
        groups = data.get("lemma_groups", [])
    else:
        groups = data
    if not isinstance(groups, list):
        raise ValueError(f"Cannot find lemma_groups list in {path}")
    return [strip_group_for_review(group) for group in groups if isinstance(group, dict)]


def strip_group_for_review(group: dict[str, Any]) -> dict[str, Any]:
    cleaned = {
        "lemma_group_id": str(group.get("lemma_group_id", "")),
        "lemma": str(group.get("lemma", "")),
        "pos": str(group.get("pos", group.get("pos_9", ""))),
        "occurrences": [],
    }
    for occurrence in group.get("occurrences", []):
        if not isinstance(occurrence, dict):
            continue
        cleaned["occurrences"].append(
            {
                "sentence_id": str(occurrence.get("sentence_id", "")),
                "node_id": str(occurrence.get("node_id", "")),
                "surface": str(occurrence.get("surface", "")),
                "sentence": str(occurrence.get("sentence", "")),
            }
        )
    return cleaned


def merge_duplicate_groups(groups: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    merged: OrderedDict[tuple[str, str], dict[str, Any]] = OrderedDict()
    report = []
    for group in groups:
        key = (group.get("lemma", ""), group.get("pos", ""))
        if key not in merged:
            merged[key] = {
                "lemma_group_id": group.get("lemma_group_id", ""),
                "lemma": group.get("lemma", ""),
                "pos": group.get("pos", ""),
                "occurrences": [],
            }
        else:
            report.append(
                {
                    "target_lemma_group_id": merged[key]["lemma_group_id"],
                    "merged_lemma_group_id": group.get("lemma_group_id", ""),
                    "lemma": key[0],
                    "pos": key[1],
                }
            )
        existing_node_ids = {occurrence.get("node_id", "") for occurrence in merged[key]["occurrences"]}
        for occurrence in group.get("occurrences", []):
            node_id = occurrence.get("node_id", "")
            if node_id and node_id in existing_node_ids:
                continue
            merged[key]["occurrences"].append(occurrence)
            existing_node_ids.add(node_id)
    return list(merged.values()), report


def reindex_lemma_group_ids(groups: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, str]]]:
    reindexed = []
    report = []
    for index, group in enumerate(groups, start=1):
        updated = strip_group_for_review(group)
        old_id = updated.get("lemma_group_id", "")
        new_id = f"lg{index:03d}"
        updated["lemma_group_id"] = new_id
        if old_id != new_id:
            report.append(
                {
                    "from": old_id,
                    "to": new_id,
                    "lemma": updated.get("lemma", ""),
                    "pos": updated.get("pos", ""),
                }
            )
        reindexed.append(updated)
    return reindexed, report


def unique_occurrence_surfaces(group: dict[str, Any]) -> list[str]:
    return sorted(
        {
            str(occurrence.get("surface", ""))
            for occurrence in group.get("occurrences", [])
            if isinstance(occurrence, dict) and occurrence.get("surface")
        }
    )


def make_empty_report() -> dict[str, Any]:
    return {
        "prompt_version": PROMPT_VERSION,
        "stages": [],
        "applied_corrections": [],
        "ignored_corrections": [],
        "applied_drops": [],
        "issues": [],
        "merge_report": [],
        "reindex_report": [],
    }


def extend_report(target: dict[str, Any], source: dict[str, Any], *, stage: str) -> None:
    target["stages"].append(stage)
    for key in ["applied_corrections", "ignored_corrections", "applied_drops", "issues", "merge_report"]:
        for item in source.get(key, []):
            copied = dict(item)
            copied.setdefault("stage", stage)
            target[key].append(copied)


def batch_input_hash(payload: dict[str, Any]) -> str:
    stable = json.dumps(payload.get("lemma_groups", []), ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(stable.encode("utf-8")).hexdigest()[:16]


def lemma_group_sort_key(group_id: object) -> tuple[int, str]:
    text = str(group_id)
    digits = "".join(ch for ch in text if ch.isdigit())
    return (int(digits) if digits else 10**9, text)


def default_prompt_dir() -> Path:
    return Path(__file__).resolve().parents[1] / "prompts"


def infer_corrected_output_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}_corrected{input_path.suffix or '.json'}")


def infer_report_output_path(output_path: Path) -> Path:
    return output_path.with_name(f"{output_path.stem}_report.json")


def load_dotenv_if_available() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return
    load_dotenv()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply lemma group sanity cleanup to POS JSON.")
    parser.add_argument("--input", type=Path, default=Path("data/output/pos_nodes.json"))
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--report-output", type=Path, default=None)
    parser.add_argument("--gpt", action="store_true", help="Run GPT sanity scan after local cleanup.")
    parser.add_argument("--model", type=str, default="gpt-5.4-mini")
    parser.add_argument("--prompt-dir", type=Path, default=default_prompt_dir())
    parser.add_argument("--batch-size", type=int, default=100)
    parser.add_argument("--max-occurrences-per-group", type=int, default=8)
    parser.add_argument("--max-sentence-chars", type=int, default=420)
    parser.add_argument("--max-retries", type=int, default=3)
    parser.add_argument("--cache-dir", type=Path, default=None)
    parser.add_argument("--no-resume", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_path = args.output or infer_corrected_output_path(args.input)
    report_path = args.report_output or infer_report_output_path(output_path)
    cache_dir = args.cache_dir
    if args.gpt and cache_dir is None:
        cache_dir = output_path.with_name(f"{output_path.stem}_batches")

    payload = read_json(args.input, default={})
    if not isinstance(payload, dict):
        raise SystemExit(f"Input JSON must be an object: {args.input}")
    corrected, report = correct_pos_json_payload(
        payload,
        use_gpt=args.gpt,
        prompt_dir=args.prompt_dir,
        model=args.model,
        batch_size=args.batch_size,
        max_occurrences_per_group=args.max_occurrences_per_group,
        max_sentence_chars=args.max_sentence_chars,
        max_retries=args.max_retries,
        cache_dir=cache_dir,
        resume=not args.no_resume,
    )
    write_json(output_path, corrected)
    write_json(report_path, report)
    print(
        "lemma group sanity complete "
        f"input_groups={report['summary']['input_groups']} "
        f"output_groups={report['summary']['output_groups']} "
        f"corrections={report['summary']['applied_corrections']} "
        f"drops={report['summary']['applied_drops']} "
        f"ignored={report['summary']['ignored_corrections']} "
        f"issues={report['summary']['issues']} "
        f"output={output_path}"
    )


if __name__ == "__main__":
    main()
