"""Tests for source quality agent."""

from tech_cartography.evidence.source_quality_agent import (
  build_display_url,
  evaluate_paper_source_quality,
)


def test_high_quality_paper() -> None:
  paper = {
    "paper_id": "W1",
    "title": "Carbon fiber tensile strength",
    "doi": "10.1000/test",
    "source_name": "Carbon Journal",
    "publication_year": 2021,
    "landing_page_url": "https://example.org/paper",
    "openalex_id": "https://openalex.org/W1",
    "cited_by_count": 5,
    "abstract": "Abstract text",
  }
  paper["display_url"] = build_display_url(paper)
  result = evaluate_paper_source_quality(paper)
  assert result.quality_level == "high"
  assert result.recommended_use == "cite_as_evidence_candidate"


def test_low_quality_without_url() -> None:
  paper = {
    "paper_id": "W2",
    "title": "Untitled candidate",
  }
  result = evaluate_paper_source_quality(paper)
  assert result.quality_level in {"low", "unknown"}
  assert result.recommended_use == "do_not_cite"
