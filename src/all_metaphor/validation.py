"""Deterministic intermediate JSON validation before RDF mapping."""

from __future__ import annotations

from dataclasses import dataclass

from all_metaphor.errors import IntermediateValidationError
from all_metaphor.observability import RunObserver
from all_metaphor.schemas import (
    AnalysisError,
    IntermediateAnalysis,
    MetaphorCandidate,
    MipvuDecision,
)

VALIDATE_INTERMEDIATE_STAGE = "validate_intermediate"
_DICTIONARY_REQUIRED_MESSAGE = "dictionary meanings required for MIPVU comparison"


@dataclass(frozen=True, slots=True)
class ValidationStats:
    """Summary of deterministic validation changes."""

    total_candidates: int
    invalid_count: int
    normalized_count: int
    duplicate_candidate_count: int
    missing_unit_count: int

    def as_metadata(self) -> dict[str, int]:
        return {
            "total_candidates": self.total_candidates,
            "invalid_count": self.invalid_count,
            "normalized_count": self.normalized_count,
            "duplicate_candidate_count": self.duplicate_candidate_count,
            "missing_unit_count": self.missing_unit_count,
        }


@dataclass(frozen=True, slots=True)
class _CandidateValidationResult:
    candidate: MetaphorCandidate
    invalid: bool
    normalized: bool
    duplicate_candidate: bool
    missing_unit: bool


def validate_intermediate(
    payload: IntermediateAnalysis,
    *,
    observer: RunObserver | None = None,
) -> IntermediateAnalysis:
    """Validate and normalize intermediate analysis without stopping the run."""
    seen_candidate_ids: set[str] = set()
    lexical_unit_ids = {unit.unit_id for unit in payload.lexical_units}
    results: list[_CandidateValidationResult] = []

    for candidate in payload.candidates:
        is_duplicate = candidate.candidate_id in seen_candidate_ids
        if not is_duplicate:
            seen_candidate_ids.add(candidate.candidate_id)
        results.append(
            _validate_candidate(
                candidate,
                lexical_unit_ids=lexical_unit_ids,
                is_duplicate=is_duplicate,
            )
        )

    validated_payload = payload.model_copy(
        update={"candidates": [result.candidate for result in results]},
        deep=True,
    )
    if observer is not None:
        stats = _build_stats(results)
        observer.log_event(
            "intermediate_validation_summary",
            stage=VALIDATE_INTERMEDIATE_STAGE,
            metadata=stats.as_metadata(),
        )
    return validated_payload


def is_rdf_mappable(candidate: MetaphorCandidate) -> bool:
    """Return whether a candidate has all fields required for metaphor RDF triples."""
    return (
        candidate.mipvu_decision is MipvuDecision.METAPHORICAL
        and candidate.metaphor_type is not None
        and _has_text(candidate.contextual_meaning)
        and _has_text(candidate.basic_meaning)
        and _has_text(candidate.meaning_contrast)
        and _has_text(candidate.source_domain)
        and _has_text(candidate.target_domain)
    )


def _validate_candidate(
    candidate: MetaphorCandidate,
    *,
    lexical_unit_ids: set[str],
    is_duplicate: bool,
) -> _CandidateValidationResult:
    errors: list[AnalysisError] = []
    invalid = False
    normalized = False
    missing_unit = candidate.unit_id not in lexical_unit_ids

    if is_duplicate:
        invalid = True
        errors.append(_validation_error("duplicate candidate_id", candidate.candidate_id))
    if missing_unit:
        invalid = True
        errors.append(_validation_error("candidate unit_id not found", candidate.candidate_id))

    if candidate.mipvu_decision is MipvuDecision.METAPHORICAL:
        if not candidate.dictionary_meanings:
            invalid = True
            errors.append(_validation_error(_DICTIONARY_REQUIRED_MESSAGE, candidate.candidate_id))
        missing_fields = _missing_metaphorical_fields(candidate)
        if missing_fields:
            invalid = True
            errors.append(
                _validation_error(
                    f"metaphorical candidate missing required fields: {', '.join(missing_fields)}",
                    candidate.candidate_id,
                )
            )

    if invalid:
        return _CandidateValidationResult(
            candidate=_make_unresolved(candidate, errors),
            invalid=True,
            normalized=True,
            duplicate_candidate=is_duplicate,
            missing_unit=missing_unit,
        )

    if candidate.mipvu_decision in {MipvuDecision.NON_METAPHORICAL, MipvuDecision.UNRESOLVED}:
        candidate, normalized = _normalize_non_metaphorical_fields(candidate)

    return _CandidateValidationResult(
        candidate=candidate,
        invalid=False,
        normalized=normalized,
        duplicate_candidate=False,
        missing_unit=False,
    )


def _normalize_non_metaphorical_fields(
    candidate: MetaphorCandidate,
) -> tuple[MetaphorCandidate, bool]:
    if (
        candidate.metaphor_type is None
        and candidate.source_domain is None
        and candidate.target_domain is None
    ):
        return candidate, False

    errors = [
        *candidate.errors,
        _validation_error(
            "non-metaphorical or unresolved candidate cannot carry metaphor domains",
            candidate.candidate_id,
        ),
    ]
    return (
        candidate.model_copy(
            update={
                "metaphor_type": None,
                "source_domain": None,
                "target_domain": None,
                "errors": errors,
            },
            deep=True,
        ),
        True,
    )


def _make_unresolved(
    candidate: MetaphorCandidate,
    errors: list[AnalysisError],
) -> MetaphorCandidate:
    return candidate.model_copy(
        update={
            "mipvu_decision": MipvuDecision.UNRESOLVED,
            "metaphor_type": None,
            "source_domain": None,
            "target_domain": None,
            "confidence": 0.0,
            "errors": [*candidate.errors, *errors],
        },
        deep=True,
    )


def _missing_metaphorical_fields(candidate: MetaphorCandidate) -> list[str]:
    missing: list[str] = []
    if candidate.metaphor_type is None:
        missing.append("metaphor_type")
    if not _has_text(candidate.contextual_meaning):
        missing.append("contextual_meaning")
    if not _has_text(candidate.basic_meaning):
        missing.append("basic_meaning")
    if not _has_text(candidate.meaning_contrast):
        missing.append("meaning_contrast")
    if not _has_text(candidate.source_domain):
        missing.append("source_domain")
    if not _has_text(candidate.target_domain):
        missing.append("target_domain")
    return missing


def _has_text(value: str | object | None) -> bool:
    return isinstance(value, str) and value.strip() != ""


def _validation_error(message: str, candidate_id: str) -> AnalysisError:
    return IntermediateValidationError(message).to_error_entry(
        stage=VALIDATE_INTERMEDIATE_STAGE,
        candidate_id=candidate_id,
    )


def _build_stats(results: list[_CandidateValidationResult]) -> ValidationStats:
    return ValidationStats(
        total_candidates=len(results),
        invalid_count=sum(1 for result in results if result.invalid),
        normalized_count=sum(1 for result in results if result.normalized),
        duplicate_candidate_count=sum(1 for result in results if result.duplicate_candidate),
        missing_unit_count=sum(1 for result in results if result.missing_unit),
    )


__all__ = [
    "VALIDATE_INTERMEDIATE_STAGE",
    "ValidationStats",
    "is_rdf_mappable",
    "validate_intermediate",
]
