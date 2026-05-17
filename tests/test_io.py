from __future__ import annotations

from pathlib import Path

import pytest

from all_metaphor.errors import (
    EmptyInputFile,
    InvalidFileExtension,
    InvalidTextEncoding,
    MissingInputFile,
)
from all_metaphor.io import LoadedDocument, load_input


def test_load_input_reads_utf8_txt_file(tmp_path: Path) -> None:
    input_file = tmp_path / "judgment.txt"
    input_file.write_text("판결문 내용입니다.", encoding="utf-8")

    loaded = load_input(input_file)

    assert isinstance(loaded, LoadedDocument)
    assert loaded.raw_text == "판결문 내용입니다."
    assert loaded.source_file == input_file.resolve()
    assert loaded.character_count == len("판결문 내용입니다.")


def test_load_input_rejects_missing_file(tmp_path: Path) -> None:
    missing_file = tmp_path / "missing.txt"

    with pytest.raises(MissingInputFile):
        load_input(missing_file)


def test_load_input_rejects_non_txt_extension(tmp_path: Path) -> None:
    input_file = tmp_path / "judgment.pdf"
    input_file.write_text("판결문 내용입니다.", encoding="utf-8")

    with pytest.raises(InvalidFileExtension):
        load_input(input_file)


def test_load_input_rejects_empty_file(tmp_path: Path) -> None:
    input_file = tmp_path / "empty.txt"
    input_file.write_text("", encoding="utf-8")

    with pytest.raises(EmptyInputFile):
        load_input(input_file)


def test_load_input_rejects_whitespace_only_file(tmp_path: Path) -> None:
    input_file = tmp_path / "blank.txt"
    input_file.write_text(" \n\t ", encoding="utf-8")

    with pytest.raises(EmptyInputFile):
        load_input(input_file)


def test_load_input_rejects_non_utf8_file(tmp_path: Path) -> None:
    input_file = tmp_path / "euc_kr.txt"
    input_file.write_bytes("판결문".encode("euc-kr"))

    with pytest.raises(InvalidTextEncoding):
        load_input(input_file)


def test_loaded_document_rejects_extra_field() -> None:
    with pytest.raises(ValueError):
        LoadedDocument(
            raw_text="text",
            source_file=Path("judgment.txt"),
            character_count=4,
            extra_field="not allowed",
        )


def test_loaded_document_rejects_zero_character_count() -> None:
    with pytest.raises(ValueError):
        LoadedDocument(
            raw_text="",
            source_file=Path("judgment.txt"),
            character_count=0,
        )
