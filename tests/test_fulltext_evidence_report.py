"""Tests for full text evidence report."""

from tech_cartography.reports.fulltext_evidence_report import (
  build_fulltext_evidence_summary,
  render_fulltext_evidence_markdown,
)


def test_report_markdown_sections() -> None:
  result = {
    "total_candidates": 2,
    "us_fulltext_candidates": 1,
    "manual_required_candidates": 1,
    "cache_hits": 0,
    "blocked_by_cost_guard": 0,
    "total_estimated_gb": 0.1,
    "total_estimated_usd": 0.5,
    "maximum_bytes_billed_gb": 50.0,
    "mode": "dry_run",
    "retrieved_records": [
      {
        "publication_number": "US2024000001A1",
        "title": "PAN carbon fiber",
        "assignee": "Toray",
        "source_route": "us_bigquery_fulltext_candidate",
        "evidence_level": "medium_fulltext_evidence",
        "evidence_coverage": {
          "has_claims": True,
          "has_independent_claim": True,
          "has_description": True,
          "has_examples": False,
          "has_measured_properties": False,
        },
        "retrieval_status": "dry_run_only",
      },
    ],
    "manual_required_records": [
      {
        "publication_number": "JP2020000001",
        "title": "JP patent",
        "country": "JP",
      },
    ],
  }
  summary = build_fulltext_evidence_summary(result)
  markdown = render_fulltext_evidence_markdown(summary)
  assert "Top5 Full Text Evidence Collection" in markdown
  assert "## 1. Summary" in markdown
  assert "## 2. Retrieved Full Text Records" in markdown
  assert "## 3. Manual Full Text Required" in markdown
