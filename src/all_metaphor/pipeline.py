"""Pipeline orchestration for ALL_Metaphor."""

from __future__ import annotations

from collections.abc import Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from all_metaphor.candidate_filter import filter_candidates
from all_metaphor.config import RuntimeSettings
from all_metaphor.errors import DictApiFailure
from all_metaphor.io import LoadedDocument, load_input
from all_metaphor.krdict_client import KrdictClient
from all_metaphor.lexical_units import segment_lexical_units
from all_metaphor.llm_client import LlmClient
from all_metaphor.morphology import analyze_morphology
from all_metaphor.observability import RunObserver
from all_metaphor.output_writer import write_outputs
from all_metaphor.rdf_mapper import map_rdf
from all_metaphor.schemas import (
    AnalysisError,
    DictionaryMeaning,
    DocumentMetadata,
    IntermediateAnalysis,
    LexicalUnit,
    MetaphorCandidate,
    MipvuDecision,
    RunStatus,
)
from all_metaphor.validation import is_rdf_mappable, validate_intermediate

LOAD_INPUT_STAGE = "load_input"
SEGMENT_LEXICAL_UNITS_STAGE = "segment_lexical_units"
ANALYZE_MORPHOLOGY_STAGE = "analyze_morphology"
FILTER_CANDIDATES_STAGE = "filter_candidates"
LOOKUP_DICTIONARY_MEANINGS_STAGE = "lookup_dictionary_meanings"
JUDGE_METAPHOR_STAGE = "judge_metaphor"
VALIDATE_INTERMEDIATE_STAGE = "validate_intermediate"
MAP_RDF_STAGE = "map_rdf"
WRITE_OUTPUTS_STAGE = "write_outputs"


@dataclass(frozen=True, slots=True)
class PipelineResult:
    """Result of one pipeline execution."""

    input_path: Path
    intermediate: IntermediateAnalysis
    turtle_text: str
    json_output_path: Path | None = None
    turtle_output_path: Path | None = None
    total_candidates: int = 0
    mapped_count: int = 0
    skipped_count: int = 0


def run_pipeline(
    input_path: Path,
    settings: RuntimeSettings,
    *,
    observer: RunObserver | None = None,
) -> PipelineResult:
    """Run the analysis pipeline without writing output files."""
    active_observer = observer or RunObserver(settings)
    analysis_errors: list[AnalysisError] = []

    with _stage(active_observer, LOAD_INPUT_STAGE, {"input_file": input_path.name}):
        loaded_document = load_input(input_path)
        active_observer.set_input_file_path(loaded_document.source_file.name)
        active_observer.set_character_count(loaded_document.character_count)

    document_id = _document_id(loaded_document.source_file)

    with _stage(active_observer, SEGMENT_LEXICAL_UNITS_STAGE, {"document_id": document_id}):
        lexical_units = segment_lexical_units(loaded_document, observer=active_observer)

    with _stage(
        active_observer,
        ANALYZE_MORPHOLOGY_STAGE,
        {"lexical_unit_count": len(lexical_units)},
    ):
        analyzed_units = analyze_morphology(
            lexical_units,
            observer=active_observer,
            error_entries=analysis_errors,
        )

    with _stage(
        active_observer,
        FILTER_CANDIDATES_STAGE,
        {"lexical_unit_count": len(analyzed_units)},
    ):
        filtered_units = filter_candidates(analyzed_units, observer=active_observer)

    with _stage(
        active_observer,
        LOOKUP_DICTIONARY_MEANINGS_STAGE,
        {"candidate_unit_count": sum(1 for unit in filtered_units if unit.is_candidate)},
    ):
        candidates = _lookup_dictionary_meanings(
            filtered_units,
            settings=settings,
            observer=active_observer,
        )

    lexical_units_by_id = {unit.unit_id: unit for unit in filtered_units}

    with _stage(active_observer, JUDGE_METAPHOR_STAGE, {"candidate_count": len(candidates)}):
        judged_candidates = LlmClient(settings, observer=active_observer).judge_candidates(
            candidates,
            lexical_units_by_id=lexical_units_by_id,
        )

    intermediate = _build_intermediate_analysis(
        loaded_document=loaded_document,
        document_id=document_id,
        lexical_units=filtered_units,
        candidates=judged_candidates,
        errors=analysis_errors,
        observer=active_observer,
    )

    with _stage(
        active_observer,
        VALIDATE_INTERMEDIATE_STAGE,
        {"candidate_count": len(intermediate.candidates)},
    ):
        validated_intermediate = validate_intermediate(intermediate, observer=active_observer)

    with _stage(
        active_observer,
        MAP_RDF_STAGE,
        {
            "candidate_count": len(validated_intermediate.candidates),
            "document_id": document_id,
        },
    ):
        turtle_text = map_rdf(validated_intermediate, observer=active_observer)

    final_intermediate = _finalize_intermediate(
        validated_intermediate,
        observer=active_observer,
        input_path=loaded_document.source_file.name,
    )
    mapped_count = _mapped_count(final_intermediate.candidates)
    result = PipelineResult(
        input_path=input_path,
        intermediate=final_intermediate,
        turtle_text=turtle_text,
        total_candidates=len(final_intermediate.candidates),
        mapped_count=mapped_count,
        skipped_count=len(final_intermediate.candidates) - mapped_count,
    )
    _log_pipeline_summary(active_observer, result, document_id=document_id)
    return result


def run_pipeline_to_files(
    input_path: Path,
    json_output_path: Path,
    turtle_output_path: Path,
    settings: RuntimeSettings,
    *,
    observer: RunObserver | None = None,
) -> PipelineResult:
    """Run the pipeline and persist the intermediate JSON and Turtle outputs."""
    active_observer = observer or RunObserver(settings)
    result = run_pipeline(input_path, settings, observer=active_observer)
    intermediate_for_output = _with_turtle_output_path(result.intermediate, turtle_output_path)

    with _stage(
        active_observer,
        WRITE_OUTPUTS_STAGE,
        {
            "json_output_path": str(json_output_path),
            "turtle_output_path": str(turtle_output_path),
        },
    ):
        written_json_path, written_turtle_path = write_outputs(
            intermediate_for_output,
            result.turtle_text,
            json_output_path,
            turtle_output_path,
        )

    return PipelineResult(
        input_path=result.input_path,
        intermediate=intermediate_for_output,
        turtle_text=result.turtle_text,
        json_output_path=written_json_path,
        turtle_output_path=written_turtle_path,
        total_candidates=result.total_candidates,
        mapped_count=result.mapped_count,
        skipped_count=result.skipped_count,
    )


def _lookup_dictionary_meanings(
    units: list[LexicalUnit],
    *,
    settings: RuntimeSettings,
    observer: RunObserver,
) -> list[MetaphorCandidate]:
    client = KrdictClient(settings)
    meanings_by_query: dict[str, list[DictionaryMeaning]] = {}
    lookup_error_messages_by_query: dict[str, str] = {}
    candidates: list[MetaphorCandidate] = []

    for candidate_index, unit in enumerate((unit for unit in units if unit.is_candidate), start=1):
        candidate_id = f"candidate-{candidate_index:06d}"
        dictionary_query = _dictionary_query(unit)
        errors: list[AnalysisError] = []
        if dictionary_query not in meanings_by_query:
            try:
                observer.increment_dictionary_lookup_count()
                meanings_by_query[dictionary_query] = client.lookup(dictionary_query)
            except DictApiFailure as exc:
                observer.increment_dictionary_api_failures()
                meanings_by_query[dictionary_query] = []
                lookup_error_messages_by_query[dictionary_query] = exc.message

        if dictionary_query in lookup_error_messages_by_query:
            errors.append(
                DictApiFailure(lookup_error_messages_by_query[dictionary_query]).to_error_entry(
                    stage=LOOKUP_DICTIONARY_MEANINGS_STAGE,
                    candidate_id=candidate_id,
                )
            )

        candidates.append(
            MetaphorCandidate(
                candidate_id=candidate_id,
                unit_id=unit.unit_id,
                dictionary_query=dictionary_query,
                dictionary_meanings=_copy_dictionary_meanings(meanings_by_query[dictionary_query]),
                mipvu_decision=MipvuDecision.UNRESOLVED,
                metaphor_type=None,
                confidence=0.0,
                llm_rationale=None,
                errors=errors,
            )
        )

    return candidates


def _build_intermediate_analysis(
    *,
    loaded_document: LoadedDocument,
    document_id: str,
    lexical_units: list[LexicalUnit],
    candidates: list[MetaphorCandidate],
    errors: list[AnalysisError],
    observer: RunObserver,
) -> IntermediateAnalysis:
    return IntermediateAnalysis(
        status=RunStatus.COMPLETED,
        run=observer.finalize(input_path=loaded_document.source_file.name),
        document=DocumentMetadata(
            document_id=document_id,
            source_file=loaded_document.source_file.name,
            character_count=loaded_document.character_count,
        ),
        lexical_units=lexical_units,
        candidates=candidates,
        errors=errors,
    )


def _finalize_intermediate(
    intermediate: IntermediateAnalysis,
    *,
    observer: RunObserver,
    input_path: str,
) -> IntermediateAnalysis:
    return intermediate.model_copy(
        update={
            "run": observer.finalize(input_path=input_path),
            "rdf": intermediate.rdf.model_copy(
                update={"triple_count": observer.metrics.rdf_triple_count},
            ),
        },
        deep=True,
    )


def _with_turtle_output_path(
    intermediate: IntermediateAnalysis,
    turtle_output_path: Path,
) -> IntermediateAnalysis:
    return intermediate.model_copy(
        update={
            "rdf": intermediate.rdf.model_copy(
                update={"output_path": str(turtle_output_path)},
            )
        },
        deep=True,
    )


@contextmanager
def _stage(
    observer: RunObserver,
    stage: str,
    metadata: Mapping[str, object] | None = None,
) -> Iterator[None]:
    with observer.stage(stage, metadata):
        yield


def _document_id(path: Path) -> str:
    return path.stem or "document"


def _dictionary_query(unit: LexicalUnit) -> str:
    lemma = unit.lemma.strip() if unit.lemma is not None else ""
    surface = unit.surface.strip()
    return lemma or surface


def _copy_dictionary_meanings(meanings: list[DictionaryMeaning]) -> list[DictionaryMeaning]:
    return [meaning.model_copy(deep=True) for meaning in meanings]


def _mapped_count(candidates: list[MetaphorCandidate]) -> int:
    return sum(1 for candidate in candidates if is_rdf_mappable(candidate))


def _log_pipeline_summary(
    observer: RunObserver,
    result: PipelineResult,
    *,
    document_id: str,
) -> None:
    observer.log_event(
        "pipeline_summary",
        stage="pipeline",
        metadata={
            "document_id": document_id,
            "total_candidates": result.total_candidates,
            "mapped_count": result.mapped_count,
            "skipped_count": result.skipped_count,
        },
    )


__all__ = [
    "ANALYZE_MORPHOLOGY_STAGE",
    "FILTER_CANDIDATES_STAGE",
    "JUDGE_METAPHOR_STAGE",
    "LOAD_INPUT_STAGE",
    "LOOKUP_DICTIONARY_MEANINGS_STAGE",
    "MAP_RDF_STAGE",
    "PipelineResult",
    "SEGMENT_LEXICAL_UNITS_STAGE",
    "VALIDATE_INTERMEDIATE_STAGE",
    "WRITE_OUTPUTS_STAGE",
    "run_pipeline",
    "run_pipeline_to_files",
]
