"""Optional fine-tuned annotation backend."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from annotation.base import BaseAnnotator


class FineTunedAnnotator(BaseAnnotator):
    """Inference backend for a future fine-tuned annotation model.

    Notes:
    - This class does inference only (placeholder for now).
    - It does not train models.
    - It does not perform RDF conversion.
    """

    def __init__(self, config_path: Path | None = None) -> None:
        project_root = Path(__file__).resolve().parents[2]
        self.config_path = config_path or (project_root / "models" / "ft_model_config.json")
        self.config = self._load_config()

    def _load_config(self) -> dict[str, Any]:
        if not self.config_path.exists():
            return {}
        try:
            return json.loads(self.config_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            print(f"[finetuned_annotator] WARNING: invalid config JSON: {self.config_path}")
            return {}

    def _is_configured(self) -> bool:
        enabled = bool(self.config.get("enabled", False))
        model_name = str(self.config.get("model_name", "")).strip()
        return enabled and bool(model_name)

    def _infer_placeholder(self, text: str, pipeline: str) -> dict:
        """Placeholder for future fine-tuned model inference.

        TODO:
        - Load provider-specific fine-tuned model.
        - Run inference that returns canonical annotation JSON.
        """
        _ = text
        _ = pipeline
        return {"metaphors": []}

    def annotate(self, text: str, pipeline: str = "simple") -> dict:
        if not text.strip():
            return {"metaphors": []}

        if not self._is_configured():
            print("[finetuned_annotator] WARNING: no fine-tuned model configured. Returning empty annotation.")
            return {"metaphors": []}

        result = self._infer_placeholder(text, pipeline=pipeline)
        if not isinstance(result, dict):
            return {"metaphors": []}
        metaphors = result.get("metaphors", [])
        if not isinstance(metaphors, list):
            return {"metaphors": []}
        return {"metaphors": metaphors}

