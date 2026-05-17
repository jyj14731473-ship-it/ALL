"""Command-line entrypoint for ALL_Metaphor."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TextIO, cast

from all_metaphor.config import RuntimeSettings, load_settings
from all_metaphor.errors import AllMetaphorError
from all_metaphor.pipeline import PipelineResult, run_pipeline_to_files

_PACKAGE_NAME = "ALL"
_DEFAULT_VERSION = "0.1.0"
_SENSITIVE_MARKERS = (
    "FAKE_API_KEY_SECRET",
    "LOCAL_CONTEXT_SECRET",
    "RAW_LLM_RESPONSE_SECRET",
    "FULL_JUDGMENT_TEXT_SECRET",
    "api_key",
    "secret",
    "local_context",
    "raw_llm_response",
    "full_judgment_text",
)


@dataclass(frozen=True, slots=True)
class CliArgs:
    """Parsed CLI arguments."""

    input_path: Path
    json_output_path: Path
    ttl_output_path: Path
    env_file: Path
    verbose: bool


def main(argv: list[str] | None = None) -> int:
    """Parse CLI arguments, run the pipeline, and return a process exit code."""
    args = _parse_args(argv)
    try:
        settings = _settings_for_cli(load_settings(args.env_file), verbose=args.verbose)
        result = run_pipeline_to_files(
            input_path=args.input_path,
            json_output_path=args.json_output_path,
            turtle_output_path=args.ttl_output_path,
            settings=settings,
        )
    except AllMetaphorError as exc:
        _print_all_metaphor_error(exc, sys.stderr)
        return 1
    except Exception:
        print("Unexpected error while running ALL_Metaphor pipeline.", file=sys.stderr)
        return 2

    _print_success_summary(result, args, sys.stdout)
    return 0


def _parse_args(argv: Sequence[str] | None) -> CliArgs:
    parser = argparse.ArgumentParser(
        prog="all-metaphor",
        description="Run the ALL_Metaphor legal metaphor analysis pipeline.",
    )
    parser.add_argument(
        "-i",
        "--input",
        dest="input_path",
        type=Path,
        required=True,
        help="Input UTF-8 .txt judgment file path.",
    )
    parser.add_argument(
        "--json-output",
        dest="json_output_path",
        type=Path,
        required=True,
        help="Intermediate analysis JSON output path.",
    )
    parser.add_argument(
        "--ttl-output",
        dest="ttl_output_path",
        type=Path,
        required=True,
        help="RDF Turtle output path.",
    )
    parser.add_argument(
        "--env-file",
        dest="env_file",
        type=Path,
        default=Path(".env"),
        help="Path to the .env file used for runtime settings.",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Use DEBUG log level for pipeline observer output.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version=f"ALL_Metaphor {_project_version()}",
    )
    namespace = parser.parse_args(argv)
    return CliArgs(
        input_path=cast(Path, namespace.input_path),
        json_output_path=cast(Path, namespace.json_output_path),
        ttl_output_path=cast(Path, namespace.ttl_output_path),
        env_file=cast(Path, namespace.env_file),
        verbose=bool(namespace.verbose),
    )


def _settings_for_cli(settings: RuntimeSettings, *, verbose: bool) -> RuntimeSettings:
    if not verbose:
        return settings
    return settings.model_copy(update={"log_level": "DEBUG"})


def _print_success_summary(result: PipelineResult, args: CliArgs, stream: TextIO) -> None:
    json_output_path = result.json_output_path or args.json_output_path
    turtle_output_path = result.turtle_output_path or args.ttl_output_path
    print("ALL_Metaphor pipeline completed.", file=stream)
    print(f"Input: {_safe_display_path(args.input_path, name_only=True)}", file=stream)
    print(f"Intermediate JSON: {_safe_display_path(json_output_path)}", file=stream)
    print(f"Turtle RDF: {_safe_display_path(turtle_output_path)}", file=stream)
    print(f"Total candidates: {result.total_candidates}", file=stream)
    print(f"Mapped candidates: {result.mapped_count}", file=stream)
    print(f"Skipped candidates: {result.skipped_count}", file=stream)


def _print_all_metaphor_error(error: AllMetaphorError, stream: TextIO) -> None:
    print(f"ALL_Metaphor pipeline failed: {error.error_code.value}", file=stream)


def _safe_display_path(path: Path, *, name_only: bool = False) -> str:
    value = path.name if name_only else str(path)
    return _redact_sensitive_text(value)


def _redact_sensitive_text(value: str) -> str:
    lowered = value.lower()
    for marker in _SENSITIVE_MARKERS:
        if marker.lower() in lowered:
            return "[REDACTED]"
    return value


def _project_version() -> str:
    try:
        return version(_PACKAGE_NAME)
    except PackageNotFoundError:
        return _DEFAULT_VERSION


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "CliArgs",
    "main",
]
