"""Base interface for interchangeable annotation backends."""

from __future__ import annotations

from typing import Protocol


class BaseAnnotator(Protocol):
    """Base annotator protocol.

    All backends must return canonical annotation JSON:
    {
      "metaphors": [...]
    }
    """

    def annotate(self, text: str, pipeline: str = "simple") -> dict:
        """Annotate legal text into canonical metaphor JSON."""
        ...

