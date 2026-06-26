"""Tests for patent_triage.py (Phase 27J.1)."""

from __future__ import annotations

from tech_cartography.services.patent_triage import (
  PatentTriageConfig,
  score_patent_candidate,
  triage_top_n,
)


def test_include_term_scoring() -> None:
  config = PatentTriageConfig(include_terms=["carbonization", "modulus"])
  result = score_patent_candidate(
    {
      "candidate_id": "c1",
      "publication_number": "US5176959",
      "title": "PAN carbonization process for carbon fiber modulus",
      "abstract": "stabilization and carbonization",
      "assignee": "Example Corp",
      "country_code": "US",
    },
    config,
  )
  assert result.total_score >= 4.0
  assert "carbonization" in result.matched_include_terms
  assert any(c.factor_name == "include_term_hit" for c in result.contributions)


def test_exclude_term_negative() -> None:
  config = PatentTriageConfig(include_terms=["pan"], exclude_terms=["ceramic"])
  result = score_patent_candidate(
    {
      "title": "ceramic pan coating",
      "abstract": "pan precursor",
      "publication_number": "US1111111",
      "country_code": "US",
    },
    config,
  )
  assert any(c.factor_name == "exclude_term_hit" for c in result.contributions)
  assert result.negative_reasons


def test_triage_top_n_ordering() -> None:
  config = PatentTriageConfig(include_terms=["fiber"])
  candidates = [
    {"candidate_id": "a", "title": "low relevance", "publication_number": "US1"},
    {"candidate_id": "b", "title": "carbon fiber bundle", "abstract": "fiber", "publication_number": "US2", "country_code": "US"},
  ]
  top = triage_top_n(candidates, config, top_n=1)
  assert len(top) == 1
  assert top[0].candidate_id == "b"
