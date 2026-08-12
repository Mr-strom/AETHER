"""Input validation and citation post-processing utilities."""

from __future__ import annotations

import re
from typing import List, Set
from pydantic import BaseModel, Field

ALLOWED_EXTENSIONS = {
    "pdf", "docx", "doc", "txt", "md", "csv", "xlsx", "xls",
    "png", "jpg", "jpeg", "webp", "mp3", "wav", "mp4", "mkv"
}


def is_allowed_file_type(filename: str) -> bool:
    """Check if file extension is supported for ingestion."""
    ext = filename.split(".")[-1].lower() if "." in filename else ""
    return ext in ALLOWED_EXTENSIONS


class ValidationResult(BaseModel):
    """Result payload for citation verification."""

    valid: bool = True
    cited_ids: List[str] = Field(default_factory=list)
    invalid_citations: List[str] = Field(default_factory=list)
    unknown_sections: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    per_claim_scores: List[float] = Field(default_factory=list)


def validate_citations(answer_text: str, valid_ids: Set[str]) -> ValidationResult:
    """Verify cited [EID-xxx] tags in answer_text against the set of valid evidence IDs.

    Args:
        answer_text: Synthesized answer string from LLM.
        valid_ids: Set of valid evidence IDs retrieved for the query (e.g. {"EID-1", "EID-2"}).

    Returns:
        ValidationResult object indicating validity, invalid citations, and unknown sections.
    """
    if not answer_text or not answer_text.strip():
        return ValidationResult(
            valid=False,
            cited_ids=[],
            invalid_citations=[],
            unknown_sections=[],
            errors=["Empty answer text"],
            per_claim_scores=[],
        )

    # Normalize valid_ids to uppercase
    norm_valid_ids = {vid.upper() for vid in valid_ids}

    # Extract all [EID-xxx] citations using regex
    raw_citations = re.findall(r"\[(EID-[\w-]+)\]", answer_text, re.IGNORECASE)
    cited_ids = sorted(list({c.upper() for c in raw_citations}))

    invalid_citations = [cid for cid in cited_ids if cid not in norm_valid_ids]

    # Extract Unknowns: section if present
    unknown_sections: List[str] = []
    unknown_match = re.search(r"Unknowns:\s*(.*)", answer_text, re.IGNORECASE | re.DOTALL)
    if unknown_match:
        unknown_text = unknown_match.group(1).strip()
        if unknown_text and unknown_text.lower() != "none":
            unknown_sections = [line.strip() for line in unknown_text.splitlines() if line.strip()]

    errors: List[str] = []
    if invalid_citations:
        errors.append(f"Invalid citations detected (not in retrieved evidence): {invalid_citations}")

    # Check if answer contains claims but no citations (unless answer is INSUFFICIENT_EVIDENCE)
    if "INSUFFICIENT_EVIDENCE" not in answer_text and not cited_ids:
        errors.append("Factual claims provided without any evidence citations.")

    is_valid = len(errors) == 0

    # Calculate claim scores: 1.0 if cited correctly, 0.0 if invalid
    per_claim_scores = [1.0 if cid in norm_valid_ids else 0.0 for cid in cited_ids]

    return ValidationResult(
        valid=is_valid,
        cited_ids=cited_ids,
        invalid_citations=invalid_citations,
        unknown_sections=unknown_sections,
        errors=errors,
        per_claim_scores=per_claim_scores,
    )
