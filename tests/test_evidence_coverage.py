"""Tests for evidence coverage."""

from tech_cartography.evidence.evidence_coverage import (
  assign_evidence_level,
  detect_independent_claims,
  evaluate_evidence_coverage,
  extract_examples,
)


def test_detect_independent_claims() -> None:
  claims = "Claim 1. A carbon fiber manufacturing method.\nClaim 2. ..."
  found = detect_independent_claims(claims)
  assert found
  assert "請求項1" in "".join(detect_independent_claims("請求項1 炭素繊維の製造方法"))


def test_high_fulltext_evidence() -> None:
  coverage = evaluate_evidence_coverage(
    {
      "claims": "Claim 1. A method",
      "description": "Detailed description with examples section",
      "examples": "Example 1: carbonization at 1200C",
      "measured_properties": ["5.5 GPa"],
    },
  )
  assert coverage["evidence_level"] == "high_fulltext_evidence"


def test_medium_fulltext_evidence() -> None:
  coverage = evaluate_evidence_coverage(
    {"claims": "Claim 1", "description": "Description text"},
  )
  assert assign_evidence_level(coverage) == "medium_fulltext_evidence"


def test_metadata_only() -> None:
  coverage = evaluate_evidence_coverage({"title": "Only metadata"})
  assert coverage["evidence_level"] == "metadata_only"


def test_extract_examples_from_description() -> None:
  text = "Background info.\nExamples\nExample 1: PAN carbonization"
  assert extract_examples(text) is not None
