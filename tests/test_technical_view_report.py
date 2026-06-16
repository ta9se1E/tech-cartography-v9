"""Tests for technical view report."""

from tech_cartography.agents.technical_view_agent import run_technical_view_assessment
from tech_cartography.reports.technical_view_report import (
  build_technical_view_summary,
  render_technical_view_markdown,
)


def test_report_markdown_sections() -> None:
  result = run_technical_view_assessment(
    [
      {
        "publication_number": "US1",
        "patent_title": "Carbon fiber",
        "evidence_items": [
          {
            "element_id": "e1",
            "element_type": "process",
            "element_text": "carbonization",
            "claim_support_status": "supported_by_examples",
            "evidence_relation": "supporting_evidence_candidate",
            "source_quality_level": "high",
          },
        ],
      },
    ],
    [
      {
        "publication_number": "US1",
        "element_id": "e1",
        "element_type": "process",
        "evidence_relation": "supporting_evidence_candidate",
        "source_quality_level": "high",
        "claim_support_status": "supported_by_examples",
      },
    ],
    [],
  )
  summary = build_technical_view_summary(result)
  markdown = render_technical_view_markdown(summary)
  assert "Technical View Assessment Report" in markdown
  assert "## 1. Summary" in markdown
  assert "## 2. Patent Technical Assessments" in markdown
  assert "## 5. Caveats" in markdown
