"""Tests for claim element extractor."""

from tech_cartography.evidence.claim_element_extractor import (
  classify_claim_phrase,
  extract_claim_elements_from_claim,
  extract_claim_elements_from_record,
  extract_numerical_conditions,
  normalize_claim_terms,
)


def test_pan_carbonization_extraction() -> None:
  claim = "A PAN-based precursor fiber is carbonized under nitrogen atmosphere."
  elements = extract_claim_elements_from_claim("US2024000001A1", claim, claim_number="1")
  types = {element.element_type for element in elements}
  terms = [term.lower() for element in elements for term in element.normalized_terms]
  assert "process" in types or "material" in types
  assert any("carbonization" in term or "pan" in term for term in terms)


def test_surface_interface_extraction() -> None:
  phrase = "a carbon fiber with surface treatment and interface adhesion"
  assert classify_claim_phrase(phrase) in {"process", "property", "structure"}
  assert "surface treatment" in normalize_claim_terms(phrase)


def test_bundle_prepreg_extraction() -> None:
  phrase = "a carbon fiber bundle prepreg laminate for aerospace composite"
  element_type = classify_claim_phrase(phrase)
  assert element_type in {"structure", "application", "material"}


def test_numerical_condition_extraction() -> None:
  text = "carbonized at 850 to 1800 °C for 10 min with 4.0 GPa tensile strength and 0.1 to 5 wt%"
  values = extract_numerical_conditions(text)
  assert any("850" in value for value in values)
  assert any("GPa" in value for value in values)
  assert any("min" in value.lower() for value in values)


def test_japanese_terms() -> None:
  phrase = "炭素繊維の炭化および表面処理により引張強度を向上させる方法"
  terms = normalize_claim_terms(phrase)
  assert any(term in terms for term in ("炭化", "表面処理", "引張強度"))


def test_metadata_only_without_claims() -> None:
  result = extract_claim_elements_from_record(
    {
      "publication_number": "US2024000002A1",
      "title": "Carbon fiber aerospace composite",
      "abstract": "Composite pressure vessel application",
      "claims": "",
      "evidence_level": "metadata_only",
    },
  )
  assert result["extraction_status"] in {"metadata_only", "skipped_no_claims"}
