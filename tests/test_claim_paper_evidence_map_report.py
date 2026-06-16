"""Tests for claim-paper evidence map report."""

from tech_cartography.evidence.claim_paper_evidence_map import build_claim_paper_evidence_map
from tech_cartography.reports.claim_paper_evidence_map_report import (
  build_claim_paper_evidence_map_summary,
  render_claim_paper_evidence_map_markdown,
)


def test_report_markdown_sections() -> None:
  result = build_claim_paper_evidence_map(
    [
      {
        "publication_number": "US1",
        "title": "Carbon fiber",
        "element_id": "e1",
        "element_type": "process",
        "element_text": "carbonization",
        "normalized_terms": ["carbonization"],
        "support_status": "claim_only",
      },
    ],
    [],
  )
  summary = build_claim_paper_evidence_map_summary(result)
  markdown = render_claim_paper_evidence_map_markdown(summary)
  assert "Patent Claim × Paper Evidence Map" in markdown
  assert "## 1. Summary" in markdown
  assert "## 2. Patent-level Evidence Maps" in markdown
  assert "## 5. Evidence Gaps" in markdown
  assert "## 6. Caveats" in markdown
