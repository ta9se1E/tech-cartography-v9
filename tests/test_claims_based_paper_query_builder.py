"""Tests for claims-based paper query builder (Phase 18C)."""

from __future__ import annotations

from tech_cartography.domain.claim_element import ClaimElement
from tech_cartography.evidence.claims_based_paper_query_builder import (
  CLAIMS_ONLY_CAVEAT,
  build_claims_paper_query_candidates,
  build_claims_paper_query_plan,
  determine_source_scope,
)


def _manual_record() -> dict:
  return {
    "publication_number": "US-12565719-B2",
    "title": "Carbon fiber manufacturing",
    "retrieval_status": "manual_claims_loaded",
    "claims": (
      "1. A carbon fiber comprising a PAN precursor fiber subjected to oxidation "
      "and carbonization, wherein the carbon fiber has a tensile strength of at least 5 GPa "
      "and an elastic modulus of at least 250 GPa."
    ),
    "evidence_level": "low_fulltext_evidence",
  }


def test_manual_claims_generate_queries() -> None:
  rows = build_claims_paper_query_candidates(_manual_record())
  assert rows
  joined = " ".join(row["query"].lower() for row in rows)
  assert "carbon fiber" in joined or "pan" in joined or "carbonization" in joined


def test_claims_only_confidence_is_medium_or_lower() -> None:
  rows = build_claims_paper_query_candidates(_manual_record())
  assert all(row["confidence"] in {"medium", "low"} for row in rows)
  assert all(row["confidence"] != "high" for row in rows)
  assert all(row["confidence"] != "limited" for row in rows)


def test_priority_terms_in_queries() -> None:
  rows = build_claims_paper_query_candidates(_manual_record())
  joined = " ".join(row["query"].lower() for row in rows)
  assert any(term in joined for term in ("pan", "carbon fiber", "carbonization", "tensile strength", "modulus"))


def test_no_description_emits_caveat() -> None:
  rows = build_claims_paper_query_candidates(_manual_record())
  assert any(CLAIMS_ONLY_CAVEAT.split("。")[0] in row["caveat_japanese"] for row in rows)
  property_rows = [row for row in rows if row["query_type"] == "property_condition"]
  if property_rows:
    assert property_rows[0]["confidence"] == "low"


def test_empty_claims_emit_no_claim_queries() -> None:
  record = {
    "publication_number": "US-1",
    "title": "Carbon fiber from PAN precursor",
    "abstract": "PAN oxidation carbonization tensile strength",
    "retrieval_status": "metadata_only",
  }
  rows = build_claims_paper_query_candidates(record)
  assert rows
  assert all(row["source_scope"] == "metadata_only" for row in rows)
  assert all(row["confidence"] == "low" for row in rows)


def test_claim_element_combinations_in_plan() -> None:
  record = _manual_record()
  elements = [
    ClaimElement(
      element_id="e1",
      publication_number="US-12565719-B2",
      claim_number="1",
      element_type="material",
      element_text="PAN precursor fiber",
      normalized_terms=["PAN", "precursor fiber"],
      source_section="claims",
      evidence_snippet="PAN precursor fiber",
    ),
    ClaimElement(
      element_id="e2",
      publication_number="US-12565719-B2",
      claim_number="1",
      element_type="process",
      element_text="oxidation and carbonization",
      normalized_terms=["oxidation", "carbonization"],
      source_section="claims",
      evidence_snippet="oxidation and carbonization",
    ),
    ClaimElement(
      element_id="e3",
      publication_number="US-12565719-B2",
      claim_number="1",
      element_type="property",
      element_text="tensile strength modulus",
      normalized_terms=["tensile strength", "modulus"],
      source_section="claims",
      evidence_snippet="tensile strength modulus",
    ),
  ]
  plan = build_claims_paper_query_plan([record], {"elements": elements})
  assert plan["total_queries"] > 0
  joined = " ".join(plan["query_examples"]).lower()
  assert "pan" in joined or "carbon" in joined


def test_source_scope_manual_claims_only() -> None:
  assert determine_source_scope(_manual_record()) == "manual_claims_only"
