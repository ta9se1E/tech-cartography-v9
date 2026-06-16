"""Tests for paper evidence mapper."""

from tech_cartography.evidence.paper_evidence_mapper import (
  build_paper_evidence_links,
  classify_evidence_relation,
  compute_paper_claim_relevance,
  deduplicate_papers,
)


def _element(**overrides) -> dict:
  base = {
    "publication_number": "US2024000001A1",
    "element_id": "e1",
    "element_type": "process",
    "element_text": "surface treatment and interface adhesion",
    "normalized_terms": ["surface treatment", "interface adhesion"],
  }
  base.update(overrides)
  return base


def _paper(**overrides) -> dict:
  base = {
    "paper_id": "W1",
    "title": "Carbon fiber surface treatment for interface adhesion",
    "abstract": "Surface treatment improves interface adhesion in carbon fiber composites.",
    "doi": "10.1000/test",
    "openalex_id": "https://openalex.org/W1",
    "landing_page_url": "https://example.org/paper",
    "source_name": "Carbon Journal",
    "publication_year": 2020,
    "display_url": "https://example.org/paper",
    "element_id": "e1",
    "publication_number": "US2024000001A1",
    "query_priority": "high",
  }
  base.update(overrides)
  return base


def test_supporting_evidence_candidate_link() -> None:
  links = build_paper_evidence_links([_paper()], [_element()])
  assert links
  assert links[0]["evidence_relation"] == "supporting_evidence_candidate"


def test_background_evidence_for_generic_carbon_fiber() -> None:
  element = _element(
    element_type="material",
    element_text="carbon fiber",
    normalized_terms=["carbon fiber"],
  )
  paper = _paper(
    title="Overview of carbon fiber manufacturing",
    abstract="General carbon fiber background review.",
    element_id="e1",
  )
  relevance = compute_paper_claim_relevance(paper, element)
  relation = classify_evidence_relation(
    relevance,
    {"quality_level": "medium"},
  )
  assert relation == "background_evidence"


def test_weak_match_single_term() -> None:
  element = _element(
    element_text="bundle structure",
    normalized_terms=["bundle"],
    element_type="structure",
  )
  paper = _paper(
    title="Carbon fiber bundle processing",
    abstract="No matching technical detail.",
    element_id="e1",
  )
  relevance = compute_paper_claim_relevance(paper, element)
  relation = classify_evidence_relation(relevance, {"quality_level": "medium"})
  assert relation == "weak_match"


def test_deduplicate_by_doi() -> None:
  papers = [
    {"paper_id": "W1", "doi": "10.1000/a", "openalex_id": "https://openalex.org/W1"},
    {"paper_id": "W1-dup", "doi": "10.1000/a", "openalex_id": "https://openalex.org/W1"},
    {"paper_id": "W2", "openalex_id": "https://openalex.org/W2"},
  ]
  deduped = deduplicate_papers(papers)
  assert len(deduped) == 2
