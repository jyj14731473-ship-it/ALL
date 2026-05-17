from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pytest

from all_metaphor import pipeline
from all_metaphor.config import RuntimeSettings
from all_metaphor.errors import MissingInputFile
from all_metaphor.io import LoadedDocument
from all_metaphor.observability import RunObserver
from all_metaphor.schemas import (
    DictionaryMeaning,
    DocumentMetadata,
    IntermediateAnalysis,
    LexicalUnit,
    MetaphorCandidate,
    MetaphorType,
    MipvuDecision,
    RunMetadata,
    RunStatus,
)


def make_settings(secret: str = "sk-secret-value") -> RuntimeSettings:
    return RuntimeSettings(
        openai_api_key=secret,
        openai_model="test-model",
        krdict_api_key="test-krdict-key",
    )


def make_loaded_document(
    *,
    raw_text: str = "계약의 성립 여부를 판단한다.",
    source_file: Path = Path("C:/ALL/sample.txt"),
) -> LoadedDocument:
    return LoadedDocument(
        raw_text=raw_text,
        source_file=source_file,
        character_count=len(raw_text),
    )


def make_unit(
    unit_id: str = "unit-001",
    *,
    surface: str = "성립",
    lemma: str | None = "성립",
    pos: str | None = "Noun",
    is_candidate: bool = True,
    filter_reason: str | None = None,
    local_context: str = "계약의 성립 여부를 판단한다.",
) -> LexicalUnit:
    return LexicalUnit(
        unit_id=unit_id,
        surface=surface,
        lemma=lemma,
        pos=pos,
        start_char=0,
        end_char=len(surface),
        sentence_id="sentence-001",
        local_context=local_context,
        local_context_char_count=len(local_context),
        is_candidate=is_candidate,
        filter_reason=filter_reason,
    )


def meaning() -> DictionaryMeaning:
    return DictionaryMeaning(sense_id="sense-001", definition="어떤 일이 이루어짐.")


def make_intermediate(
    *,
    candidates: list[MetaphorCandidate] | None = None,
    lexical_units: list[LexicalUnit] | None = None,
) -> IntermediateAnalysis:
    timestamp = datetime(2026, 5, 17, 12, 0, tzinfo=UTC)
    return IntermediateAnalysis(
        status=RunStatus.COMPLETED,
        run=RunMetadata(
            run_id="run-001",
            started_at=timestamp,
            input_path="sample.txt",
            openai_model="test-model",
        ),
        document=DocumentMetadata(
            document_id="sample",
            source_file="sample.txt",
            character_count=42,
        ),
        lexical_units=lexical_units or [make_unit()],
        candidates=candidates or [],
    )


def make_mappable(candidate: MetaphorCandidate) -> MetaphorCandidate:
    return candidate.model_copy(
        update={
            "mipvu_decision": MipvuDecision.METAPHORICAL,
            "metaphor_type": MetaphorType.INDIRECT,
            "contextual_meaning": "법률 요건이 갖추어짐.",
            "basic_meaning": "어떤 일이 이루어짐.",
            "meaning_contrast": "법률 요건의 성취를 일의 성립과 비교함.",
            "source_domain": "일의 성립",
            "target_domain": "법률관계",
            "confidence": 0.8,
            "llm_rationale": "MIPVU comparison rationale.",
        },
        deep=True,
    )


def install_successful_pipeline_fakes(
    monkeypatch: pytest.MonkeyPatch,
    events: list[str],
    *,
    loaded_document: LoadedDocument | None = None,
    sensitive_context: str = "계약의 성립 여부를 판단한다.",
) -> dict[str, Any]:
    loaded = loaded_document or make_loaded_document()
    segmented_units = [
        make_unit("unit-001", lemma=None, pos=None, local_context=sensitive_context),
        make_unit(
            "unit-002", surface="한다.", lemma=None, pos=None, local_context=sensitive_context
        ),
    ]
    analyzed_units = [
        make_unit("unit-001", local_context=sensitive_context),
        make_unit(
            "unit-002",
            surface="한다.",
            lemma="하다",
            pos="Verb",
            local_context=sensitive_context,
        ),
    ]
    filtered_units = [
        make_unit("unit-001", local_context=sensitive_context),
        make_unit(
            "unit-002",
            surface="한다.",
            lemma="하다",
            pos="Verb",
            is_candidate=False,
            filter_reason="legal_boilerplate",
            local_context=sensitive_context,
        ),
    ]
    captured: dict[str, Any] = {}

    def fake_load_input(input_path: Path) -> LoadedDocument:
        events.append("load_input")
        captured["input_path"] = input_path
        return loaded

    def fake_segment_lexical_units(
        document: LoadedDocument,
        *,
        observer: RunObserver | None = None,
    ) -> list[LexicalUnit]:
        events.append("segment_lexical_units")
        captured["segment_document"] = document
        return segmented_units

    def fake_analyze_morphology(
        units: list[LexicalUnit],
        *,
        observer: RunObserver | None = None,
        error_entries: list[Any] | None = None,
    ) -> list[LexicalUnit]:
        events.append("analyze_morphology")
        captured["morphology_units"] = units
        return analyzed_units

    def fake_filter_candidates(
        units: list[LexicalUnit],
        *,
        observer: RunObserver | None = None,
    ) -> list[LexicalUnit]:
        events.append("filter_candidates")
        captured["filter_units"] = units
        return filtered_units

    class FakeKrdictClient:
        def __init__(self, settings: RuntimeSettings) -> None:
            events.append("krdict_client_init")
            captured["krdict_settings"] = settings

        def lookup(self, lemma: str) -> list[DictionaryMeaning]:
            events.append("lookup_dictionary_meanings")
            captured.setdefault("dictionary_queries", []).append(lemma)
            return [meaning()]

    class FakeLlmClient:
        def __init__(
            self,
            settings: RuntimeSettings,
            *,
            observer: RunObserver | None = None,
        ) -> None:
            events.append("llm_client_init")
            captured["llm_settings"] = settings

        def judge_candidates(
            self,
            candidates: list[MetaphorCandidate],
            *,
            lexical_units_by_id: dict[str, LexicalUnit] | None = None,
        ) -> list[MetaphorCandidate]:
            events.append("judge_candidates")
            captured["llm_candidates"] = candidates
            captured["lexical_units_by_id"] = lexical_units_by_id
            return [make_mappable(candidate) for candidate in candidates]

    def fake_validate_intermediate(
        payload: IntermediateAnalysis,
        *,
        observer: RunObserver | None = None,
    ) -> IntermediateAnalysis:
        events.append("validate_intermediate")
        validated = payload.model_copy(deep=True)
        captured["pre_validation_payload"] = payload
        captured["validated_payload"] = validated
        return validated

    def fake_map_rdf(
        payload: IntermediateAnalysis,
        *,
        observer: RunObserver | None = None,
    ) -> str:
        events.append("map_rdf")
        captured["rdf_payload"] = payload
        if observer is not None:
            observer.set_rdf_triple_count(7)
        return "@prefix ex: <http://example.org/legal-metaphor#> .\n"

    monkeypatch.setattr(pipeline, "load_input", fake_load_input)
    monkeypatch.setattr(pipeline, "segment_lexical_units", fake_segment_lexical_units)
    monkeypatch.setattr(pipeline, "analyze_morphology", fake_analyze_morphology)
    monkeypatch.setattr(pipeline, "filter_candidates", fake_filter_candidates)
    monkeypatch.setattr(pipeline, "KrdictClient", FakeKrdictClient)
    monkeypatch.setattr(pipeline, "LlmClient", FakeLlmClient)
    monkeypatch.setattr(pipeline, "validate_intermediate", fake_validate_intermediate)
    monkeypatch.setattr(pipeline, "map_rdf", fake_map_rdf)
    return captured


def test_run_pipeline_calls_nodes_in_order(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    captured = install_successful_pipeline_fakes(monkeypatch, events)

    result = pipeline.run_pipeline(Path("C:/ALL/sample.txt"), make_settings())

    assert events == [
        "load_input",
        "segment_lexical_units",
        "analyze_morphology",
        "filter_candidates",
        "krdict_client_init",
        "lookup_dictionary_meanings",
        "llm_client_init",
        "judge_candidates",
        "validate_intermediate",
        "map_rdf",
    ]
    assert isinstance(result.intermediate, IntermediateAnalysis)
    assert result.turtle_text.startswith("@prefix ex:")
    assert result.total_candidates == 1
    assert result.mapped_count == 1
    assert result.skipped_count == 0
    assert captured["dictionary_queries"] == ["성립"]


def test_run_pipeline_does_not_write_files(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    install_successful_pipeline_fakes(monkeypatch, events)

    def fail_write_outputs(*args: object, **kwargs: object) -> tuple[Path, Path]:
        raise AssertionError("run_pipeline must not write files")

    monkeypatch.setattr(pipeline, "write_outputs", fail_write_outputs)

    result = pipeline.run_pipeline(Path("C:/ALL/sample.txt"), make_settings())

    assert result.json_output_path is None
    assert result.turtle_output_path is None


def test_run_pipeline_to_files_writes_outputs_once(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[IntermediateAnalysis, str, Path, Path]] = []
    json_path = Path("outputs/intermediate/sample.json")
    turtle_path = Path("outputs/rdf/sample.ttl")
    intermediate = make_intermediate()

    def fake_run_pipeline(
        input_path: Path,
        settings: RuntimeSettings,
        *,
        observer: RunObserver | None = None,
    ) -> pipeline.PipelineResult:
        return pipeline.PipelineResult(
            input_path=input_path,
            intermediate=intermediate,
            turtle_text="@prefix ex: <http://example.org/legal-metaphor#> .\n",
            total_candidates=0,
            mapped_count=0,
            skipped_count=0,
        )

    def fake_write_outputs(
        payload: IntermediateAnalysis,
        turtle_text: str,
        json_output_path: Path,
        turtle_output_path: Path,
    ) -> tuple[Path, Path]:
        calls.append((payload, turtle_text, json_output_path, turtle_output_path))
        return json_output_path, turtle_output_path

    monkeypatch.setattr(pipeline, "run_pipeline", fake_run_pipeline)
    monkeypatch.setattr(pipeline, "write_outputs", fake_write_outputs)

    result = pipeline.run_pipeline_to_files(
        Path("C:/ALL/sample.txt"),
        json_path,
        turtle_path,
        make_settings(),
    )

    assert len(calls) == 1
    assert calls[0][0].rdf.output_path == str(turtle_path)
    assert calls[0][1].startswith("@prefix ex:")
    assert calls[0][2:] == (json_path, turtle_path)
    assert result.json_output_path == json_path
    assert result.turtle_output_path == turtle_path
    assert result.intermediate.rdf.output_path == str(turtle_path)


def test_llm_client_receives_filtered_candidates_and_lexical_units(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[str] = []
    captured = install_successful_pipeline_fakes(monkeypatch, events)

    pipeline.run_pipeline(Path("C:/ALL/sample.txt"), make_settings())

    llm_candidates = captured["llm_candidates"]
    lexical_units_by_id = captured["lexical_units_by_id"]
    assert [candidate.unit_id for candidate in llm_candidates] == ["unit-001"]
    assert set(lexical_units_by_id) == {"unit-001", "unit-002"}
    assert lexical_units_by_id["unit-001"].is_candidate is True
    assert lexical_units_by_id["unit-002"].is_candidate is False


def test_validation_result_is_rdf_source_of_truth(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    captured = install_successful_pipeline_fakes(monkeypatch, events)

    pipeline.run_pipeline(Path("C:/ALL/sample.txt"), make_settings())

    assert captured["rdf_payload"] is captured["validated_payload"]
    assert captured["rdf_payload"] is not captured["pre_validation_payload"]


def test_document_id_uses_input_stem_without_full_path(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    install_successful_pipeline_fakes(
        monkeypatch,
        events,
        loaded_document=make_loaded_document(source_file=Path("C:/ALL/sample.txt")),
    )

    result = pipeline.run_pipeline(Path("C:/ALL/sample.txt"), make_settings())

    assert result.intermediate.document.document_id == "sample"
    assert result.intermediate.document.source_file == "sample.txt"
    assert result.intermediate.run.input_path == "sample.txt"


def test_observer_summary_logs_are_safe(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    events: list[str] = []
    sensitive_context = "이 판결문 원문은 로그에 나오면 안 된다."
    secret = "sk-secret-value"
    install_successful_pipeline_fakes(monkeypatch, events, sensitive_context=sensitive_context)
    settings = make_settings(secret)
    observer = RunObserver(settings, run_id="run-pipeline")
    caplog.set_level(logging.INFO, logger="all_metaphor.observability")

    pipeline.run_pipeline(Path("C:/ALL/sample.txt"), settings, observer=observer)

    log_text = "\n".join(record.message for record in caplog.records)
    assert sensitive_context not in log_text
    assert secret not in log_text
    records = [json.loads(record.message) for record in caplog.records]
    assert any(record["event"] == "pipeline_summary" for record in records)
    summary = next(record for record in records if record["event"] == "pipeline_summary")
    assert summary["metadata"] == {
        "document_id": "sample",
        "mapped_count": 1,
        "skipped_count": 0,
        "total_candidates": 1,
    }


def test_run_pipeline_propagates_load_input_error(monkeypatch: pytest.MonkeyPatch) -> None:
    raw_text = "이 판결문 원문은 예외 메시지에 나오면 안 된다."

    def fake_load_input(input_path: Path) -> LoadedDocument:
        raise MissingInputFile("Input file does not exist: sample.txt")

    monkeypatch.setattr(pipeline, "load_input", fake_load_input)

    with pytest.raises(MissingInputFile) as exc_info:
        pipeline.run_pipeline(Path("C:/ALL/sample.txt"), make_settings())

    assert "Input file does not exist: sample.txt" in str(exc_info.value)
    assert raw_text not in str(exc_info.value)


def test_pipeline_tests_patch_external_clients(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[str] = []
    captured = install_successful_pipeline_fakes(monkeypatch, events)

    pipeline.run_pipeline(Path("C:/ALL/sample.txt"), make_settings())

    assert captured["krdict_settings"].openai_model == "test-model"
    assert captured["llm_settings"].openai_model == "test-model"
