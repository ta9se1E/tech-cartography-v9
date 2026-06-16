"""Tests for business view report."""

from tech_cartography.agents.business_view_agent import run_business_view_assessment
from tech_cartography.reports.business_view_report import (
  build_business_view_summary,
  render_business_view_markdown,
)


def test_report_markdown_sections() -> None:
  result = run_business_view_assessment(
    [
      {
        "publication_number": "US1",
        "patent_title": "Carbon fiber",
        "overall_technical_confidence": "medium",
        "overall_technical_score": 0.55,
      },
    ],
    [
      {
        "publication_number": "US1",
        "patent_title": "Carbon fiber",
        "overall_technical_confidence": "medium",
        "overall_technical_score": 0.55,
      },
    ],
    [
      {
        "publication_number": "US1",
        "relation": "business_signal_candidate",
        "signal_type": "partnership",
        "source_quality_level": "medium",
        "source_title": "Partnership signal",
      },
    ],
  )
  summary = build_business_view_summary(result)
  markdown = render_business_view_markdown(summary)
  assert "Business View Assessment Report" in markdown
  assert "## 1. Summary" in markdown
  assert "## 2. Patent Business Assessments" in markdown
  assert "## 4. SME Opportunity View" in markdown
  assert "## 6. Caveats" in markdown
