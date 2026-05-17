from __future__ import annotations

from pathlib import Path

import pytest
from pydantic import ValidationError

from all_metaphor.config import PROJECT_ROOT, PathSettings, RuntimeSettings, load_settings
from all_metaphor.errors import MissingEnvVar
from all_metaphor.schemas import ErrorCode


def test_path_settings_defaults_are_project_root_absolute_paths() -> None:
    settings = PathSettings()

    assert settings.data_input_dir == PROJECT_ROOT / "data" / "input"
    assert settings.intermediate_output_dir == PROJECT_ROOT / "outputs" / "intermediate"
    assert settings.rdf_output_dir == PROJECT_ROOT / "outputs" / "rdf"
    assert settings.data_input_dir.is_absolute()
    assert settings.intermediate_output_dir.is_absolute()
    assert settings.rdf_output_dir.is_absolute()


def test_load_settings_reads_required_environment_variables(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("KRDICT_API_KEY", raising=False)
    monkeypatch.delenv("ALL_LOG_LEVEL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=test-openai-key",
                "OPENAI_MODEL=test-model",
                "KRDICT_API_KEY=test-krdict-key",
                "ALL_LOG_LEVEL=DEBUG",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(env_file)

    assert settings.openai_api_key.get_secret_value() == "test-openai-key"
    assert settings.openai_model == "test-model"
    assert settings.krdict_api_key.get_secret_value() == "test-krdict-key"
    assert settings.log_level == "DEBUG"


def test_load_settings_defaults_log_level_to_info(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_MODEL", raising=False)
    monkeypatch.delenv("KRDICT_API_KEY", raising=False)
    monkeypatch.delenv("ALL_LOG_LEVEL", raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=test-openai-key",
                "OPENAI_MODEL=test-model",
                "KRDICT_API_KEY=test-krdict-key",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(env_file)

    assert settings.log_level == "INFO"


@pytest.mark.parametrize("env_name", ["OPENAI_API_KEY", "OPENAI_MODEL", "KRDICT_API_KEY"])
def test_load_settings_rejects_missing_required_environment_variable(
    env_name: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    values = {
        "OPENAI_API_KEY": "test-openai-key",
        "OPENAI_MODEL": "test-model",
        "KRDICT_API_KEY": "test-krdict-key",
    }
    values.pop(env_name)
    for name in ["OPENAI_API_KEY", "OPENAI_MODEL", "KRDICT_API_KEY", "ALL_LOG_LEVEL"]:
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(f"{name}={value}" for name, value in values.items()),
        encoding="utf-8",
    )

    with pytest.raises(MissingEnvVar) as exc_info:
        load_settings(env_file)

    assert exc_info.value.error_code is ErrorCode.MISSING_ENV_VAR
    assert env_name in exc_info.value.message


def test_load_settings_rejects_blank_required_environment_variable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ["OPENAI_API_KEY", "OPENAI_MODEL", "KRDICT_API_KEY", "ALL_LOG_LEVEL"]:
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=test-openai-key",
                "OPENAI_MODEL=   ",
                "KRDICT_API_KEY=test-krdict-key",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(MissingEnvVar) as exc_info:
        load_settings(env_file)

    assert "OPENAI_MODEL" in exc_info.value.message


def test_load_settings_strips_environment_variable_values(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ["OPENAI_API_KEY", "OPENAI_MODEL", "KRDICT_API_KEY", "ALL_LOG_LEVEL"]:
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=  test-openai-key  ",
                "OPENAI_MODEL=  test-model  ",
                "KRDICT_API_KEY=  test-krdict-key  ",
                "ALL_LOG_LEVEL=  WARNING  ",
            ]
        ),
        encoding="utf-8",
    )

    settings = load_settings(env_file)

    assert settings.openai_api_key.get_secret_value() == "test-openai-key"
    assert settings.openai_model == "test-model"
    assert settings.krdict_api_key.get_secret_value() == "test-krdict-key"
    assert settings.log_level == "WARNING"


def test_runtime_settings_rejects_unknown_log_level() -> None:
    with pytest.raises(ValidationError):
        RuntimeSettings(
            openai_api_key="test-openai-key",
            openai_model="test-model",
            krdict_api_key="test-krdict-key",
            log_level="TRACE",
        )


def test_load_settings_rejects_unknown_log_level(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    for name in ["OPENAI_API_KEY", "OPENAI_MODEL", "KRDICT_API_KEY", "ALL_LOG_LEVEL"]:
        monkeypatch.delenv(name, raising=False)
    env_file = tmp_path / ".env"
    env_file.write_text(
        "\n".join(
            [
                "OPENAI_API_KEY=test-openai-key",
                "OPENAI_MODEL=test-model",
                "KRDICT_API_KEY=test-krdict-key",
                "ALL_LOG_LEVEL=TRACE",
            ]
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        load_settings(env_file)


def test_runtime_settings_rejects_extra_field() -> None:
    with pytest.raises(ValidationError):
        RuntimeSettings(
            openai_api_key="test-openai-key",
            openai_model="test-model",
            krdict_api_key="test-krdict-key",
            extra_field="not allowed",
        )
