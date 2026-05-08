"""Sentence splitting helpers.

The production path uses kss when it is installed. A small regex fallback keeps
the preprocessing module usable in lightweight test environments.
"""

from __future__ import annotations

import re
from html import unescape


def split_sentences(text: str) -> list[str]:
    """Split judgment text into sentence strings while preserving punctuation."""
    raw_text = normalize_judgment_text(text)
    if not raw_text.strip():
        return []

    blocks = _split_structural_blocks(raw_text)
    sentences: list[str] = []
    try:
        import kss  # type: ignore[import-not-found]

        for block in blocks:
            split = kss.split_sentences(block)
            sentences.extend(str(sentence).strip() for sentence in split if str(sentence).strip())
    except Exception:
        for block in blocks:
            sentences.extend(_split_sentences_fallback(block))

    return sentences


def _split_sentences_fallback(text: str) -> list[str]:
    normalized = re.sub(r"\s+", " ", text.replace("\n", " ")).strip()
    if not normalized:
        return []
    parts = re.split(r"(?<=[.!?。！？])\s+", normalized)
    return [part.strip() for part in parts if part.strip()]


def normalize_judgment_text(text: str) -> str:
    """Normalize lightweight service markup without changing legal wording."""
    raw_text = unescape(text or "")
    raw_text = re.sub(r"<br\s*/?>", "\n", raw_text, flags=re.IGNORECASE)
    raw_text = re.sub(r"</p\s*>", "\n", raw_text, flags=re.IGNORECASE)
    raw_text = re.sub(r"<[^>]+>", "", raw_text)
    return raw_text


def _split_structural_blocks(text: str) -> list[str]:
    """Pre-split court-service text by line and bracketed legal headings."""
    blocks: list[str] = []
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        blocks.extend(_split_inline_heading(line))
    return blocks


def _split_inline_heading(line: str) -> list[str]:
    heading_match = re.match(r"^(【[^】]+】)\s*(.+)$", line)
    if heading_match:
        heading = heading_match.group(1).strip()
        rest = heading_match.group(2).strip()
        return [heading, rest] if rest else [heading]
    return [line]
