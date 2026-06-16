"""Tests for evidence confidence."""

from tech_cartography.evidence.evidence_confidence import (
  assign_evidence_confidence,
  build_evidence_caveat,
  compute_evidence_score,
  upgrade_or_downgrade_relation,
)


def _link(**overrides) -> dict:
  base = {
    "evidence_relation": "supporting_evidence_candidate",
    "relevance_score": 0.8,
    "matched_terms": ["surface treatment", "interface adhesion"],
    "paper_title": "Carbon fiber surface treatment",
    "display_url": "https://example.org/paper",
    "source_quality_level": "high",
    "source_quality_score": 0.85,
  }
  base.update(overrides)
  return base


def test_supporting_high_quality_confidence() -> None:
  link = _link()
  element = {"support_status": "supported_by_examples", "element_type": "process"}
  quality = {"quality_level": "high", "quality_score": 0.85}
  score = compute_evidence_score(link, element, quality)
  updated = upgrade_or_downgrade_relation(link, element, quality)
  confidence = assign_evidence_confidence(score, updated["evidence_relation"], "high")
  assert score >= 0.5
  assert confidence in {"high", "medium"}


def test_weak_match_low_confidence() -> None:
  link = _link(
    evidence_relation="weak_match",
    relevance_score=0.2,
    matched_terms=["bundle"],
    source_quality_level="medium",
  )
  score = compute_evidence_score(link)
  confidence = assign_evidence_confidence(score, "weak_match", "medium")
  assert confidence == "low"


def test_generic_carbon_fiber_penalty() -> None:
  link = _link(
    matched_terms=["carbon fiber"],
    relevance_score=0.4,
    evidence_relation="background_evidence",
  )
  score = compute_evidence_score(link)
  assert score < 0.5


def test_caveat_mentions_candidate_not_proof() -> None:
  caveat = build_evidence_caveat("supporting_evidence_candidate", "medium", "high")
  assert "candidate" in caveat.lower()
  assert "proof" in caveat.lower()
