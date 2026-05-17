from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from all_metaphor import cli
from all_metaphor.config import RuntimeSettings
from all_metaphor.errors import MissingInputFile
from all_metaphor.pipeline import PipelineResult
from all_metaphor.schemas import DocumentMetadata, IntermediateAnalysis, RunMetadata, RunStatus


def make_settings(secret: str = "sk-test-secret") -> RuntimeSettings:
    return RuntimeSettings(
        openai_api_key=secret,
        openai_model="test-model",
        krdict_api_key="test-krdict-key",
    )


def make_intermediate() -> IntermediateAnalysis:
    timestamp = datetime(2026, 5, 17, 12, 0, tzinfo=UTC)
    return IntermediateAnalysis(
        status=RunStatus.COMPLETED,
        run=RunMetadata(
            run_id="run-cli",
            started_at=timestamp,
            input_path="sample.txt",
            openai_model="test-model",
        ),
        document=DocumentMetadata(
            document_id="sample",
            source_file="sample.txt",
            character_count=42,
        ),
    )


def make_result(
    *,
    input_path: Path = Path("sample.txt"),
    json_output_path: Path | None = Path("out/intermediate.json"),
    turtle_output_path: Path | None = Path("out/result.ttl"),
    total_candidates: int = 12,
    mapped_count: int = 3,
    skipped_count: int = 9,
    turtle_text: str = "@prefix ex: <http://example.org/legal-metaphor#> .\n",
) -> PipelineResult:
    return PipelineResult(
        input_path=input_path,
        intermediate=make_intermediate(),
        turtle_text=turtle_text,
        json_output_path=json_output_path,
        turtle_output_path=turtle_output_path,
        total_candidates=total_candidates,
        mapped_count=mapped_count,
        skipped_count=skipped_count,
    )


def patch_settings(
    monkeypatch: pytest.MonkeyPatch,
    *,
    settings: RuntimeSettings | None = None,
) -> dict[str, Any]:
    captured: dict[str, Any] = {}

    def fake_load_settings(env_file: str | Path = ".env") -> RuntimeSettings:
        captured["env_file"] = env_file
        return settings or make_settings()

    monkeypatch.setattr(cli, "load_settings", fake_load_settings)
    return captured


def test_cli_success_calls_pipeline_and_prints_summary(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    captured = patch_settings(monkeypatch)

    def fake_run_pipeline_to_files(
        *,
        input_path: Path,
        json_output_path: Path,
        turtle_output_path: Path,
        settings: RuntimeSettings,
    ) -> PipelineResult:
        captured["input_path"] = input_path
        captured["json_output_path"] = json_output_path
        captured["turtle_output_path"] = turtle_output_path
        captured["settings"] = settings
        return make_result(
            input_path=input_path,
            json_output_path=json_output_path,
            turtle_output_path=turtle_output_path,
        )

    monkeypatch.setattr(cli, "run_pipeline_to_files", fake_run_pipeline_to_files)

    exit_code = cli.main(
        [
            "--input",
            "sample.txt",
            "--json-output",
            "out/intermediate.json",
            "--ttl-output",
            "out/result.ttl",
        ]
    )

    output = capsys.readouterr()
    assert exit_code == 0
    assert output.err == ""
    assert "ALL_Metaphor pipeline completed." in output.out
    assert "Input: sample.txt" in output.out
    assert "Intermediate JSON: out\\intermediate.json" in output.out or (
        "Intermediate JSON: out/intermediate.json" in output.out
    )
    assert "Turtle RDF: out\\result.ttl" in output.out or (
        "Turtle RDF: out/result.ttl" in output.out
    )
    assert "Total candidates: 12" in output.out
    assert "Mapped candidates: 3" in output.out
    assert "Skipped candidates: 9" in output.out
    assert captured["input_path"] == Path("sample.txt")
    assert captured["json_output_path"] == Path("out/intermediate.json")
    assert captured["turtle_output_path"] == Path("out/result.ttl")
    assert isinstance(captured["settings"], RuntimeSettings)
    assert captured["env_file"] == Path(".env")


def test_cli_uses_env_file_and_verbose_log_level(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured = patch_settings(monkeypatch, settings=make_settings())

    def fake_run_pipeline_to_files(
        *,
        input_path: Path,
        json_output_path: Path,
        turtle_output_path: Path,
        settings: RuntimeSettings,
    ) -> PipelineResult:
        captured["settings"] = settings
        return make_result()

    monkeypatch.setattr(cli, "run_pipeline_to_files", fake_run_pipeline_to_files)

    exit_code = cli.main(
        [
            "--input",
            "sample.txt",
            "--json-output",
            "out/intermediate.json",
            "--ttl-output",
            "out/result.ttl",
            "--env-file",
            ".env.test",
            "--verbose",
        ]
    )

    assert exit_code == 0
    assert captured["env_file"] == Path(".env.test")
    assert captured["settings"].log_level == "DEBUG"


def test_cli_missing_required_arguments_exits() -> None:
    with pytest.raises(SystemExit) as exc_info:
        cli.main([])

    assert exc_info.value.code == 2


def test_cli_handles_all_metaphor_error_safely(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    patch_settings(monkeypatch)

    def fake_run_pipeline_to_files(
        *,
        input_path: Path,
        json_output_path: Path,
        turtle_output_path: Path,
        settings: RuntimeSettings,
    ) -> PipelineResult:
        raise MissingInputFile("FAKE_API_KEY_SECRET LOCAL_CONTEXT_SECRET RAW_LLM_RESPONSE_SECRET")

    monkeypatch.setattr(cli, "run_pipeline_to_files", fake_run_pipeline_to_files)

    exit_code = cli.main(
        [
            "--input",
            "sample.txt",
            "--json-output",
            "out/intermediate.json",
            "--ttl-output",
            "out/result.ttl",
        ]
    )

    output = capsys.readouterr()
    assert exit_code == 1
    assert output.out == ""
    assert "ALL_Metaphor pipeline failed: MISSING_INPUT_FILE" in output.err
    assert "Traceback" not in output.err
    assert "FAKE_API_KEY_SECRET" not in output.err
    assert "LOCAL_CONTEXT_SECRET" not in output.err
    assert "RAW_LLM_RESPONSE_SECRET" not in output.err


def test_cli_handles_unexpected_exception_safely(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    patch_settings(monkeypatch)

    def fake_run_pipeline_to_files(
        *,
        input_path: Path,
        json_output_path: Path,
        turtle_output_path: Path,
        settings: RuntimeSettings,
    ) -> PipelineResult:
        raise RuntimeError("FULL_JUDGMENT_TEXT_SECRET FAKE_API_KEY_SECRET")

    monkeypatch.setattr(cli, "run_pipeline_to_files", fake_run_pipeline_to_files)

    exit_code = cli.main(
        [
            "--input",
            "sample.txt",
            "--json-output",
            "out/intermediate.json",
            "--ttl-output",
            "out/result.ttl",
        ]
    )

    output = capsys.readouterr()
    assert exit_code == 2
    assert output.out == ""
    assert "Unexpected error while running ALL_Metaphor pipeline." in output.err
    assert "Traceback" not in output.err
    assert "FULL_JUDGMENT_TEXT_SECRET" not in output.err
    assert "FAKE_API_KEY_SECRET" not in output.err


def test_cli_stdout_redacts_sensitive_result_paths(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    patch_settings(monkeypatch)
    secrets = [
        "FAKE_API_KEY_SECRET",
        "LOCAL_CONTEXT_SECRET",
        "RAW_LLM_RESPONSE_SECRET",
        "FULL_JUDGMENT_TEXT_SECRET",
    ]

    def fake_run_pipeline_to_files(
        *,
        input_path: Path,
        json_output_path: Path,
        turtle_output_path: Path,
        settings: RuntimeSettings,
    ) -> PipelineResult:
        return make_result(
            input_path=Path("FULL_JUDGMENT_TEXT_SECRET.txt"),
            json_output_path=Path("out/FAKE_API_KEY_SECRET.json"),
            turtle_output_path=Path("out/LOCAL_CONTEXT_SECRET.ttl"),
            turtle_text="RAW_LLM_RESPONSE_SECRET",
        )

    monkeypatch.setattr(cli, "run_pipeline_to_files", fake_run_pipeline_to_files)

    exit_code = cli.main(
        [
            "--input",
            "FULL_JUDGMENT_TEXT_SECRET.txt",
            "--json-output",
            "out/FAKE_API_KEY_SECRET.json",
            "--ttl-output",
            "out/LOCAL_CONTEXT_SECRET.ttl",
        ]
    )

    output = capsys.readouterr()
    assert exit_code == 0
    for secret in secrets:
        assert secret not in output.out
        assert secret not in output.err


def test_cli_module_does_not_import_analysis_dependencies() -> None:
    source = Path("src/all_metaphor/cli.py").read_text(encoding="utf-8")

    assert "openai" not in source
    assert "konlpy" not in source
    assert "rdflib" not in source
    assert "load_input" not in source
    assert "LlmClient" not in source
    assert "map_rdf" not in source
    assert "run_pipeline_to_files" in source


def test_cli_has_python_module_entrypoint_guard() -> None:
    source = Path("src/all_metaphor/cli.py").read_text(encoding="utf-8")

    assert 'if __name__ == "__main__":' in source
    assert "raise SystemExit(main())" in source
