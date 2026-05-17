"""UTF-8 output writers for ALL_Metaphor pipeline artifacts."""

from __future__ import annotations

from pathlib import Path

from all_metaphor.errors import OutputWriteError
from all_metaphor.schemas import IntermediateAnalysis


def write_intermediate_json(
    payload: IntermediateAnalysis,
    output_path: Path,
) -> Path:
    """Write an intermediate analysis payload as UTF-8 JSON."""
    _ensure_writable_file_path(output_path)
    json_text = _ensure_trailing_newline(payload.model_dump_json(indent=2, ensure_ascii=False))
    _write_text(output_path, json_text, failure_message="Failed to write intermediate JSON output")
    return output_path


def write_turtle(
    turtle_text: str,
    output_path: Path,
) -> Path:
    """Write Turtle text as UTF-8 without parsing or remapping it."""
    _ensure_writable_file_path(output_path)
    _write_text(
        output_path,
        _ensure_trailing_newline(turtle_text),
        failure_message="Failed to write Turtle output",
    )
    return output_path


def write_outputs(
    payload: IntermediateAnalysis,
    turtle_text: str,
    json_output_path: Path,
    turtle_output_path: Path,
) -> tuple[Path, Path]:
    """Write intermediate JSON and Turtle outputs in sequence."""
    json_path = write_intermediate_json(payload, json_output_path)
    turtle_path = write_turtle(turtle_text, turtle_output_path)
    return json_path, turtle_path


def _ensure_writable_file_path(output_path: Path) -> None:
    if output_path.is_dir():
        raise OutputWriteError("Output path is a directory")
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OutputWriteError("Failed to prepare output directory") from exc


def _write_text(output_path: Path, text: str, *, failure_message: str) -> None:
    try:
        output_path.write_text(text, encoding="utf-8")
    except OSError as exc:
        raise OutputWriteError(failure_message) from exc


def _ensure_trailing_newline(text: str) -> str:
    if text.endswith("\n"):
        return text
    return f"{text}\n"


__all__ = [
    "write_intermediate_json",
    "write_outputs",
    "write_turtle",
]
