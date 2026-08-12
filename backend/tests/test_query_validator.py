"""Unit tests for backend/utils/validators.py (citation validation)"""

from backend.utils.validators import validate_citations, ValidationResult


def test_validate_citations_valid() -> None:
    answer = "Panel A-001 voltage is 112V [EID-1].\n\nUnknowns: None."
    valid_ids = {"EID-1", "EID-2"}

    res = validate_citations(answer, valid_ids)
    assert res.valid is True
    assert res.cited_ids == ["EID-1"]
    assert res.invalid_citations == []
    assert res.errors == []


def test_validate_citations_invalid_eid() -> None:
    answer = "Panel A-001 voltage is 112V [EID-999]."
    valid_ids = {"EID-1", "EID-2"}

    res = validate_citations(answer, valid_ids)
    assert res.valid is False
    assert "EID-999" in res.invalid_citations
    assert len(res.errors) >= 1


def test_validate_citations_uncited_claims() -> None:
    answer = "The voltage is 112V."
    valid_ids = {"EID-1"}

    res = validate_citations(answer, valid_ids)
    assert res.valid is False
    assert any("without any evidence citations" in err for err in res.errors)


def test_validate_citations_insufficient_evidence() -> None:
    answer = "INSUFFICIENT_EVIDENCE"
    valid_ids = set()

    res = validate_citations(answer, valid_ids)
    assert res.valid is True


def test_validate_citations_extracts_unknowns() -> None:
    answer = "The voltage is 112V [EID-1].\n\nUnknowns:\n- Serial number of Panel A-001 not visible."
    valid_ids = {"EID-1"}

    res = validate_citations(answer, valid_ids)
    assert res.valid is True
    assert len(res.unknown_sections) == 1
    assert "Serial number" in res.unknown_sections[0]
