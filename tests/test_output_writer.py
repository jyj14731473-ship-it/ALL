from __future__ import annotations

import json
from collections.abc import Sequence
from datetime import UTC, datetime
from pathlib import Path

import pytest

from all_metaphor.errors import OutputWriteError
from all_metaphor.output_writer import write_intermediate_json, write_outputs, write_turtle
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


def make_lexical_unit(
    unit_id: str = "unit-001",
    *,
    local_context: str = "계약의 성립 여부를 판단한다.",
) -> LexicalUnit:
    return LexicalUnit(
        unit_id=unit_id,
        surface="성립",
        lemma="성립",
        pos="Noun",
        start_char=0,
        end_char=2,
        sentence_id="sentence-001",
        local_context=local_context,
        local_context_char_count=len(local_context),
        is_candidate=True,
        filter_reason=None,
    )


def make_candidate(candidate_id: str = "candidate-001") -> MetaphorCandidate:
    return MetaphorCandidate(
        candidate_id=candidate_id,
        unit_id="unit-001",
        dictionary_query="성립",
        dictionary_meanings=[
            DictionaryMeaning(sense_id="sense-001", definition="어떤 일이 이루어짐.")
        ],
        contextual_meaning="법률 요건이 갖추어짐.",
        basic_meaning="어떤 일이 이루어짐.",
        meaning_contrast="법률 요건의 성취를 일의 성립과 비교함.",
        mipvu_decision=MipvuDecision.METAPHORICAL,
        metaphor_type=MetaphorType.INDIRECT,
        source_domain="일의 성립",
        target_domain="법률관계",
        confidence=0.8,
        llm_rationale="MIPVU comparison rationale.",
        errors=[],
    )


def make_payload(
    candidates: Sequence[MetaphorCandidate] | None = None,
    *,
    local_context: str = "계약의 성립 여부를 판단한다.",
) -> IntermediateAnalysis:
    timestamp = datetime(2026, 5, 17, 12, 0, tzinfo=UTC)
    return IntermediateAnalysis(
        status=RunStatus.COMPLETED,
        run=RunMetadata(
            run_id="run-001",
            started_at=timestamp,
            input_path="data/input/example.txt",
            openai_model="test-model",
        ),
        document=DocumentMetadata(
            document_id="doc-001",
            source_file="example.txt",
            character_count=42,
        ),
        lexical_units=[make_lexical_unit(local_context=local_context)],
        candidates=list(candidates if candidates is not None else [make_candidate()]),
    )


def test_write_intermediate_json_saves_utf8_json(tmp_path: Path) -> None:
    output_path = tmp_path / "nested" / "intermediate.json"
    payload = make_payload()

    written_path = write_intermediate_json(payload, output_path)

    assert written_path == output_path
    assert output_path.is_file()
    content = output_path.read_text(encoding="utf-8")
    parsed = json.loads(content)
    assert content.endswith("\n")
    assert "성립" in content
    assert "\\uc131" not in content
    assert parsed["candidates"][0]["candidate_id"] == "candidate-001"


def test_write_turtle_saves_text_with_trailing_newline(tmp_path: Path) -> None:
    output_path = tmp_path / "rdf" / "analysis.ttl"
    turtle_text = '@prefix ex: <http://example.org/legal-metaphor#> .\nex:a ex:b "값" .'

    written_path = write_turtle(turtle_text, output_path)

    assert written_path == output_path
    assert output_path.is_file()
    assert output_path.read_text(encoding="utf-8") == f"{turtle_text}\n"


def test_write_turtle_preserves_existing_trailing_newline(tmp_path: Path) -> None:
    output_path = tmp_path / "analysis.ttl"
    turtle_text = "@prefix ex: <http://example.org/legal-metaphor#> .\n"

    write_turtle(turtle_text, output_path)

    assert output_path.read_text(encoding="utf-8") == turtle_text


def test_write_output_creates_parent_directories(tmp_path: Path) -> None:
    output_path = tmp_path / "missing" / "parents" / "intermediate.json"

    write_intermediate_json(make_payload(), output_path)

    assert output_path.parent.is_dir()
    assert output_path.is_file()


def test_write_outputs_saves_json_and_turtle(tmp_path: Path) -> None:
    json_path = tmp_path / "intermediate" / "analysis.json"
    turtle_path = tmp_path / "rdf" / "analysis.ttl"

    written_json, written_turtle = write_outputs(
        make_payload(),
        "@prefix ex: <http://example.org/legal-metaphor#> .",
        json_path,
        turtle_path,
    )

    assert (written_json, written_turtle) == (json_path, turtle_path)
    assert json_path.is_file()
    assert turtle_path.is_file()


def test_write_intermediate_json_rejects_directory_path(tmp_path: Path) -> None:
    sensitive_context = "이 판결문 원문은 예외 메시지에 나오면 안 된다."
    secret = "sk-secret-value"

    with pytest.raises(OutputWriteError) as exc_info:
        write_intermediate_json(make_payload(local_context=sensitive_context), tmp_path)

    error_message = str(exc_info.value)
    assert "Output path is a directory" in error_message
    assert sensitive_context not in error_message
    assert secret not in error_message


def test_write_turtle_rejects_directory_path_without_content_leak(tmp_path: Path) -> None:
    turtle_text = "이 Turtle 본문 전체는 예외 메시지에 나오면 안 된다. sk-secret-value"

    with pytest.raises(OutputWriteError) as exc_info:
        write_turtle(turtle_text, tmp_path)

    error_message = str(exc_info.value)
    assert "Output path is a directory" in error_message
    assert turtle_text not in error_message
    assert "sk-secret-value" not in error_message


def test_write_intermediate_json_wraps_write_failure_without_payload_leak(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    sensitive_context = "이 판결문 원문은 예외 메시지에 나오면 안 된다."

    def fail_write_text(
        self: Path,
        data: str,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> int:
        raise PermissionError("permission denied while writing sensitive file content")

    monkeypatch.setattr(Path, "write_text", fail_write_text)

    with pytest.raises(OutputWriteError) as exc_info:
        write_intermediate_json(
            make_payload(local_context=sensitive_context),
            tmp_path / "analysis.json",
        )

    error_message = str(exc_info.value)
    assert error_message == "Failed to write intermediate JSON output"
    assert sensitive_context not in error_message
    assert "sensitive file content" not in error_message


def test_write_turtle_wraps_write_failure_without_text_leak(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    turtle_text = "비밀 Turtle 본문 sk-secret-value"

    def fail_write_text(
        self: Path,
        data: str,
        encoding: str | None = None,
        errors: str | None = None,
        newline: str | None = None,
    ) -> int:
        raise PermissionError("permission denied while writing turtle text")

    monkeypatch.setattr(Path, "write_text", fail_write_text)

    with pytest.raises(OutputWriteError) as exc_info:
        write_turtle(turtle_text, tmp_path / "analysis.ttl")

    error_message = str(exc_info.value)
    assert error_message == "Failed to write Turtle output"
    assert turtle_text not in error_message
    assert "sk-secret-value" not in error_message


def test_output_writer_does_not_import_validation_rdf_llm_or_openai() -> None:
    source = Path("src/all_metaphor/output_writer.py").read_text(encoding="utf-8")

    assert "openai" not in source
    assert "llm_client" not in source
    assert "rdf_mapper" not in source
    assert "validation" not in source
