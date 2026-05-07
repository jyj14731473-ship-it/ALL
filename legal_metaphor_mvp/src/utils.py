"""Utility helpers for lightweight MVP scripts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def ensure_parent(path: Path) -> None:
    """Create parent directory if missing."""
    path.parent.mkdir(parents=True, exist_ok=True)


def read_text(path: Path) -> str:
    """Read UTF-8 text safely. Return empty string if file is missing."""
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def write_text(path: Path, content: str) -> None:
    """Write UTF-8 text, creating parent directories as needed."""
    ensure_parent(path)
    path.write_text(content, encoding="utf-8")


def read_json(path: Path, default: Any | None = None) -> Any:
    """Read JSON safely; return default on missing/empty/invalid input."""
    if default is None:
        default = {}
    text = read_text(path).strip()
    if not text:
        return default
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return default


def write_json(path: Path, data: Any) -> None:
    """Write pretty JSON with UTF-8 encoding."""
    ensure_parent(path)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    """Read JSONL safely. Ignore blank lines and comment lines starting with #."""
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        try:
            value = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(value, dict):
            rows.append(value)
    return rows


def write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    """Write list of dictionaries as JSONL."""
    ensure_parent(path)
    lines = [json.dumps(row, ensure_ascii=False) for row in rows]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def slugify(value: str) -> str:
    """Create a simple slug for RDF local names."""
    cleaned = "".join(ch.lower() if ch.isalnum() else "_" for ch in value.strip())
    while "__" in cleaned:
        cleaned = cleaned.replace("__", "_")
    return cleaned.strip("_") or "unknown"


def escape_turtle_literal(value: str) -> str:
    """Escape double quote and backslash for Turtle string literals."""
    return value.replace("\\", "\\\\").replace('"', '\\"')

