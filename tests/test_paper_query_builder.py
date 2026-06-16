"""Tests for paper query builder."""

from tech_cartography.domain.claim_element import ClaimElement
from tech_cartography.evidence.paper_query_builder import (
  build_paper_queries_for_element,
  prioritize_paper_queries,
)


def test_paper_query_generation() -> None:
  element = ClaimElement(
    element_id="e1",
    publication_number="US2024000001A1",
    claim_number="1",
    element_type="process",
    element_text="PAN carbonization with tensile strength",
    normalized_terms=["PAN", "carbonization", "tensile strength"],
    source_section="claims",
    evidence_snippet="PAN carbonization with tensile strength",
  )
  queries = build_paper_queries_for_element(element)
  assert queries
  assert queries[0]["query"]


def test_high_priority_material_process_property() -> None:
  element = ClaimElement(
    element_id="e2",
    publication_number="US2024000001A1",
    claim_number="1",
    element_type="property",
    element_text="PAN carbonization tensile strength",
    normalized_terms=["PAN", "carbonization", "tensile strength"],
    source_section="claims",
    evidence_snippet="PAN carbonization tensile strength",
  )
  queries = prioritize_paper_queries(build_paper_queries_for_element(element), top_n=5)
  assert any(query.get("priority") == "high" for query in queries)
