"""Tests for description support mapper."""

from tech_cartography.domain.claim_element import ClaimElement
from tech_cartography.evidence.claim_element_extractor import extract_claim_elements_from_claim
from tech_cartography.evidence.description_support_mapper import map_description_support


def _element(phrase: str, terms: list[str]) -> ClaimElement:
  elements = extract_claim_elements_from_claim("US2024000001A1", phrase, claim_number="1")
  return elements[0] if elements else ClaimElement(
    element_id="e1",
    publication_number="US2024000001A1",
    claim_number="1",
    element_type="process",
    element_text=phrase,
    normalized_terms=terms,
    source_section="claims",
    evidence_snippet=phrase,
    support_status="claim_only",
  )


def test_supported_by_description() -> None:
  element = _element(
    "PAN precursor carbonization process",
    ["pan", "carbonization"],
  )
  record = {
    "description": "The PAN precursor is carbonized in nitrogen atmosphere with improved modulus.",
    "examples": "",
    "measured_properties": [],
  }
  updated = map_description_support(record, [element])[0]
  assert updated.support_status == "supported_by_description"


def test_supported_by_examples() -> None:
  element = _element("surface treatment and interface adhesion", ["surface treatment", "interface adhesion"])
  record = {
    "description": "",
    "examples": "Example 1 used surface treatment to improve interface adhesion.",
    "measured_properties": [],
  }
  updated = map_description_support(record, [element])[0]
  assert updated.support_status == "supported_by_examples"


def test_claim_only() -> None:
  element = _element("carbon fiber bundle prepreg", ["carbon fiber bundle", "prepreg"])
  record = {"description": "", "examples": "", "measured_properties": []}
  updated = map_description_support(record, [element])[0]
  assert updated.support_status == "claim_only"
