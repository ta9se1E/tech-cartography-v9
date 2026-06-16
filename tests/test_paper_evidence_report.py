"""Tests for paper evidence report."""

from tech_cartography.reports.paper_evidence_report import (
  build_paper_evidence_summary,
  render_paper_evidence_markdown,
)


def test_report_markdown_sections() -> None:
  result = {
    "total_query_candidates": 2,
    "executed_queries": 1,
    "cache_hits": 1,
    "total_papers_raw": 3,
    "total_papers_dedup": 2,
    "mode": "execute",
    "evidence_links": [
      {
        "publication_number": "US1",
        "element_text": "surface treatment",
        "paper_title": "Carbon fiber surface treatment",
        "evidence_relation": "supporting_evidence_candidate",
        "relevance_score": 0.8,
        "source_quality_level": "high",
        "display_url": "https://example.org",
      },
    ],
    "evidence_by_patent": [
      {
        "publication_number": "US1",
        "linked_papers_count": 1,
        "claim_elements_linked": 1,
        "supporting_evidence_candidates": 1,
        "background_evidence": 0,
        "weak_matches": 0,
        "top_linked_papers": [],
      },
    ],
    "source_quality_results": [
      {"quality_level": "high", "recommended_use": "cite_as_evidence_candidate"},
    ],
  }
  summary = build_paper_evidence_summary(result)
  markdown = render_paper_evidence_markdown(summary)
  assert "OpenAlex Paper Evidence Report" in markdown
  assert "## 1. Summary" in markdown
  assert "## 2. Paper Evidence by Patent" in markdown
  assert "## 4. Source Quality" in markdown
