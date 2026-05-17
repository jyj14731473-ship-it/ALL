"""Pydantic models for ALL_Metaphor intermediate JSON."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Final, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

SchemaVersion = Literal["0.1"]
ProjectName = Literal["ALL"]
AgentName = Literal["ALL_Metaphor"]
DictionarySource = Literal["standard_korean_language_dictionary"]

SCHEMA_VERSION: Final[SchemaVersion] = "0.1"
PROJECT_NAME: Final[ProjectName] = "ALL"
AGENT_NAME: Final[AgentName] = "ALL_Metaphor"
STANDARD_KOREAN_LANGUAGE_DICTIONARY: Final[DictionarySource] = "standard_korean_language_dictionary"


class _StrictBaseModel(BaseModel):
    """Base model that keeps the intermediate schema closed and explicit."""

    model_config = ConfigDict(extra="forbid")


class RunStatus(StrEnum):
    """Top-level pipeline execution status."""

    COMPLETED = "completed"
    PARTIAL = "partial"
    FAILED = "failed"


class MipvuDecision(StrEnum):
    """MIPVU decision for one metaphor candidate."""

    METAPHORICAL = "metaphorical"
    NON_METAPHORICAL = "non_metaphorical"
    UNRESOLVED = "unresolved"


class MetaphorType(StrEnum):
    """Supported metaphor type values."""

    INDIRECT = "indirect"
    DIRECT = "direct"
    IMPLICIT = "implicit"


class ErrorCode(StrEnum):
    """Approved intermediate error codes derived from the AGENTS Error Policy."""

    DICT_API_FAILURE = "DICT_API_FAILURE"
    LLM_VALIDATION_ERROR = "LLM_VALIDATION_ERROR"
    KONLPY_ANALYSIS_FAILURE = "KONLPY_ANALYSIS_FAILURE"
    OPENAI_API_FAILURE = "OPENAI_API_FAILURE"
    RDF_SERIALIZATION_FAILURE = "RDF_SERIALIZATION_FAILURE"
    MISSING_ENV_VAR = "MISSING_ENV_VAR"
    INVALID_FILE_EXTENSION = "INVALID_FILE_EXTENSION"
    MISSING_INPUT_FILE = "MISSING_INPUT_FILE"
    EMPTY_INPUT_FILE = "EMPTY_INPUT_FILE"
    INVALID_TEXT_ENCODING = "INVALID_TEXT_ENCODING"
    VALIDATION_ERROR = "VALIDATION_ERROR"
    OUTPUT_WRITE_ERROR = "OUTPUT_WRITE_ERROR"


class ContextWindow(_StrictBaseModel):
    """Bounded local context window configuration."""

    tokens_before: int = Field(
        default=10,
        ge=0,
        le=30,
        description="Number of tokens to include before a lexical unit.",
    )
    tokens_after: int = Field(
        default=10,
        ge=0,
        le=30,
        description="Number of tokens to include after a lexical unit.",
    )
    max_tokens_each_side: int = Field(
        default=30,
        ge=0,
        description="Maximum allowed tokens on either side of a lexical unit.",
    )
    max_characters: int = Field(
        default=100,
        ge=0,
        description="Maximum local context character count per lexical unit.",
    )


class TokenUsage(_StrictBaseModel):
    """OpenAI token usage counters."""

    prompt_tokens: int = Field(
        default=0,
        ge=0,
        description="Prompt tokens reported by the OpenAI API.",
    )
    completion_tokens: int = Field(
        default=0,
        ge=0,
        description="Completion tokens reported by the OpenAI API.",
    )
    total_tokens: int = Field(
        default=0,
        ge=0,
        description="Total tokens reported by the OpenAI API.",
    )


class RunMetadata(_StrictBaseModel):
    """Run-level metadata for one pipeline execution."""

    run_id: str = Field(description="Unique identifier for one pipeline run.")
    started_at: datetime = Field(description="Run start timestamp as an ISO-8601 value.")
    completed_at: datetime | None = Field(
        default=None,
        description="Run completion timestamp as an ISO-8601 value, or null if unfinished.",
    )
    input_path: str = Field(description="Input judgment text file path.")
    openai_model: str = Field(description="OpenAI model name read from environment configuration.")
    openai_temperature: float = Field(
        default=0.0,
        ge=0.0,
        description="OpenAI temperature used for metaphor judgment.",
    )
    openai_seed: int | None = Field(
        default=None,
        description="OpenAI seed used for reproducible metaphor judgment, when available.",
    )
    context_window: ContextWindow = Field(
        default_factory=ContextWindow,
        description="Bounded lexical-unit local context window settings.",
    )
    token_usage: TokenUsage = Field(
        default_factory=TokenUsage,
        description="OpenAI token usage counters for this run.",
    )


class DocumentMetadata(_StrictBaseModel):
    """Source document metadata."""

    document_id: str = Field(description="Stable identifier for the source judgment document.")
    source_file: str = Field(description="Source judgment text file name or path.")
    character_count: int = Field(
        ge=0,
        description="Number of characters in the source judgment document.",
    )


class LexicalUnit(_StrictBaseModel):
    """Word-level lexical unit with offsets and candidate metadata."""

    unit_id: str = Field(description="Stable identifier for this lexical unit.")
    surface: str = Field(description="Original surface form from the judgment text.")
    lemma: str | None = Field(
        default=None,
        description="Dictionary form or normalized lemma for this lexical unit.",
    )
    pos: str | None = Field(
        default=None,
        description="Part-of-speech tag from KonLPy's Okt analyzer.",
    )
    start_char: int = Field(
        ge=0,
        description="Start character offset of the lexical unit in the source text.",
    )
    end_char: int = Field(
        ge=0,
        description="End character offset of the lexical unit in the source text.",
    )
    sentence_id: str | None = Field(
        default=None,
        description="Identifier of the sentence containing this lexical unit, when available.",
    )
    local_context: str = Field(description="Bounded local context around this lexical unit.")
    local_context_char_count: int = Field(
        ge=0,
        le=100,
        description="Character count of the bounded local context string.",
    )
    is_candidate: bool = Field(description="Whether this lexical unit is a metaphor candidate.")
    filter_reason: str | None = Field(
        default=None,
        description="Reason this lexical unit was filtered out, or null if it remains a candidate.",
    )


class DictionaryMeaning(_StrictBaseModel):
    """Dictionary meaning returned for a candidate lexical unit."""

    sense_id: str | None = Field(
        default=None,
        description="Dictionary sense identifier, when provided by the source API.",
    )
    definition: str = Field(description="Dictionary definition text.")
    source: DictionarySource = Field(
        default=STANDARD_KOREAN_LANGUAGE_DICTIONARY,
        description="Dictionary source for this meaning.",
    )


class AnalysisError(_StrictBaseModel):
    """Structured error captured during intermediate analysis."""

    error_code: ErrorCode = Field(description="Approved intermediate error code.")
    stage: str = Field(description="Pipeline stage where this error occurred.")
    candidate_id: str | None = Field(
        default=None,
        description="Candidate identifier associated with this error, or null for run-level errors.",
    )
    message: str = Field(description="Human-readable error message.")
    retryable: bool = Field(description="Whether the failed operation can be retried.")
    timestamp: datetime = Field(description="Error timestamp as an ISO-8601 value.")


class MetaphorCandidate(_StrictBaseModel):
    """MIPVU metaphor candidate and judgment evidence."""

    candidate_id: str = Field(description="Stable identifier for this metaphor candidate.")
    unit_id: str = Field(description="Lexical unit identifier this candidate is derived from.")
    dictionary_query: str = Field(description="Dictionary lookup query used for this candidate.")
    dictionary_meanings: list[DictionaryMeaning] = Field(
        default_factory=list,
        description="Dictionary meanings returned for the candidate lookup query.",
    )
    contextual_meaning: str | None = Field(
        default=None,
        description="Meaning of the lexical unit in its local legal context.",
    )
    basic_meaning: str | None = Field(
        default=None,
        description="More basic dictionary meaning used for MIPVU comparison.",
    )
    meaning_contrast: str | None = Field(
        default=None,
        description="Evidence-backed contrast between contextual and basic meaning.",
    )
    mipvu_decision: MipvuDecision = Field(description="MIPVU decision for this candidate.")
    metaphor_type: MetaphorType | None = Field(
        default=None,
        description="Metaphor type when metaphorical, or null otherwise.",
    )
    source_domain: str | None = Field(
        default=None,
        description="Source domain label when evidence supports one.",
    )
    target_domain: str | None = Field(
        default=None,
        description="Target domain label when evidence supports one.",
    )
    confidence: float = Field(
        ge=0.0,
        le=1.0,
        description="LLM-reported probability that the lexical unit is metaphorical.",
    )
    llm_rationale: str | None = Field(
        default=None,
        description="LLM rationale for the MIPVU judgment, when available.",
    )
    errors: list[AnalysisError] = Field(
        default_factory=list,
        description="Candidate-level errors captured during analysis.",
    )

    @model_validator(mode="after")
    def validate_metaphor_type_consistency(self) -> Self:
        """Reject metaphor types for non-metaphorical or unresolved candidates."""
        if self.mipvu_decision is not MipvuDecision.METAPHORICAL and self.metaphor_type is not None:
            msg = "metaphor_type must be null unless mipvu_decision is metaphorical"
            raise ValueError(msg)
        return self


class RdfMetadata(_StrictBaseModel):
    """RDF output metadata."""

    output_path: str | None = Field(
        default=None,
        description="Turtle output path, or null if RDF was skipped or not generated.",
    )
    triple_count: int = Field(
        default=0,
        ge=0,
        description="Number of RDF triples generated.",
    )
    confidence_threshold: float = Field(
        default=0.5,
        ge=0.0,
        le=1.0,
        description="Confidence threshold for RDF inclusion.",
    )


class IntermediateAnalysis(_StrictBaseModel):
    """Top-level intermediate JSON document for ALL_Metaphor."""

    schema_version: SchemaVersion = Field(
        default=SCHEMA_VERSION,
        description="Intermediate JSON schema version.",
    )
    project: ProjectName = Field(
        default=PROJECT_NAME,
        description="Project name.",
    )
    agent: AgentName = Field(
        default=AGENT_NAME,
        description="Agent name.",
    )
    status: RunStatus = Field(description="Top-level run status.")
    run: RunMetadata = Field(description="Run-level metadata.")
    document: DocumentMetadata = Field(description="Source document metadata.")
    lexical_units: list[LexicalUnit] = Field(
        default_factory=list,
        description="Word-level lexical units extracted from the source document.",
    )
    candidates: list[MetaphorCandidate] = Field(
        default_factory=list,
        description="Metaphor candidates and judgment evidence.",
    )
    rdf: RdfMetadata = Field(
        default_factory=RdfMetadata,
        description="RDF output metadata.",
    )
    errors: list[AnalysisError] = Field(
        default_factory=list,
        description="Top-level analysis errors.",
    )


__all__ = [
    "AGENT_NAME",
    "PROJECT_NAME",
    "SCHEMA_VERSION",
    "STANDARD_KOREAN_LANGUAGE_DICTIONARY",
    "AgentName",
    "AnalysisError",
    "ContextWindow",
    "DictionaryMeaning",
    "DictionarySource",
    "DocumentMetadata",
    "ErrorCode",
    "IntermediateAnalysis",
    "LexicalUnit",
    "MetaphorCandidate",
    "MetaphorType",
    "MipvuDecision",
    "ProjectName",
    "RdfMetadata",
    "RunMetadata",
    "RunStatus",
    "SchemaVersion",
    "TokenUsage",
]
