"""Annotation backend package.

Backends:
- PromptAnnotator (default MVP backend)
- FineTunedAnnotator (optional backend)
"""

from .base import BaseAnnotator
from .finetuned_annotator import FineTunedAnnotator
from .prompt_annotator import PromptAnnotator

__all__ = ["BaseAnnotator", "PromptAnnotator", "FineTunedAnnotator"]

