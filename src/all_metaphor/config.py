"""Runtime configuration for ALL_Metaphor.

Call `load_settings()` once from `main.py`, then pass the returned
`RuntimeSettings` through the pipeline as an explicit dependency. Do not call
`load_settings()` directly from individual modules, and do not introduce a
settings singleton.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Literal, cast

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict, Field, SecretStr

from all_metaphor.errors import MissingEnvVar

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

LogLevel = Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]


class _StrictBaseModel(BaseModel):
    """Base settings model that rejects unknown fields."""

    model_config = ConfigDict(extra="forbid")


class PathSettings(_StrictBaseModel):
    """Project-root-based filesystem defaults."""

    data_input_dir: Path = Field(
        default=PROJECT_ROOT / "data" / "input",
        description="Default directory for input judgment text files.",
    )
    intermediate_output_dir: Path = Field(
        default=PROJECT_ROOT / "outputs" / "intermediate",
        description="Default directory for intermediate JSON outputs.",
    )
    rdf_output_dir: Path = Field(
        default=PROJECT_ROOT / "outputs" / "rdf",
        description="Default directory for RDF Turtle outputs.",
    )


class RuntimeSettings(_StrictBaseModel):
    """Runtime settings loaded from environment variables and project defaults."""

    openai_api_key: SecretStr = Field(description="OpenAI API key loaded from OPENAI_API_KEY.")
    openai_model: str = Field(description="OpenAI model name loaded from OPENAI_MODEL.")
    krdict_api_key: SecretStr = Field(
        description="Standard Korean Language Dictionary API key loaded from KRDICT_API_KEY.",
    )
    log_level: LogLevel = Field(
        default="INFO",
        description="Console log level loaded from ALL_LOG_LEVEL.",
    )
    paths: PathSettings = Field(
        default_factory=PathSettings,
        description="Project-root-based filesystem defaults.",
    )

    # TBD: llm: LLMSettings
    # TBD: context: ContextSettings
    # TBD: retry: RetrySettings


def _get_required_env(name: str) -> str:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        raise MissingEnvVar(f"Missing required environment variable: {name}")
    return value.strip()


def _get_optional_env(name: str, default: str) -> str:
    value = os.environ.get(name)
    if value is None or value.strip() == "":
        return default
    return value.strip()


def load_settings(env_file: str | Path = ".env") -> RuntimeSettings:
    """Load `.env`, validate required environment variables, and return settings.

    This function is intended to be called once from `main.py`. Pass the returned
    `RuntimeSettings` through the pipeline as an explicit dependency. Individual
    modules must not call this function directly, and this module must not become
    a singleton settings registry.
    """
    load_dotenv(env_file)
    return RuntimeSettings(
        openai_api_key=SecretStr(_get_required_env("OPENAI_API_KEY")),
        openai_model=_get_required_env("OPENAI_MODEL"),
        krdict_api_key=SecretStr(_get_required_env("KRDICT_API_KEY")),
        log_level=cast(LogLevel, _get_optional_env("ALL_LOG_LEVEL", "INFO")),
        paths=PathSettings(),
    )


__all__ = [
    "PROJECT_ROOT",
    "LogLevel",
    "PathSettings",
    "RuntimeSettings",
    "load_settings",
]
