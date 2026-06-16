"""Tests for claim element report."""

from tech_cartography.domain.claim_element import ClaimElement
from tech_cartography.reports.claim_element_pipeline import run_claim_element_pipeline
from tech_cartography.reports.claim_element_report import (
  build_claim_element_summary,
  render_claim_element_markdown,
)


def _sample_record() -> dict:
  return {
    "publication_number": "US2024000001A1",
    "title": "PAN carbon fiber process",
    "assignee": "Toray",
    "claims": (
      "Claim 1. A PAN-based precursor fiber is carbonized under nitrogen atmosphere; "
      "surface treatment improves interface adhesion; tensile strength is 4.0 GPa."
    ),
    "independent_claims": ["Claim 1. A PAN-based precursor fiber is carbonized."],
    "description": "The PAN precursor is carbonized and surface treated for adhesion.",
    "examples": "Example 1: carbonization at 850 to 1800 °C for 10 min.",
    "measured_properties": ["4.0 GPa", "tensile strength"],
    "evidence_level": "high_fulltext_evidence",
  }


def test_report_markdown_sections() -> None:
  result = run_claim_element_pipeline([_sample_record()])
  summary = build_claim_element_summary(result)
  markdown = render_claim_element_markdown(summary)
  assert "Claim Element Extraction Report" in markdown
  assert "## 1. Summary" in markdown
  assert "## 3. Claim Elements by Type" in markdown
  assert "## 5. Paper Query Candidates" in markdown
  assert summary["total_claim_elements"] > 0
