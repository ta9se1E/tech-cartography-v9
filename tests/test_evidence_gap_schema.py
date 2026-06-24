"""Evidence Gap schema tests (Phase 25V)."""

from __future__ import annotations

import pytest

from tech_cartography.runtime.evidence_gap_schema import (
  build_evidence_gap,
  default_safety_flags,
  validate_evidence_gap,
)


def test_build_evidence_gap_valid() -> None:
  gap = build_evidence_gap(
    theme_name="Carbon Fiber Intelligence",
    observation="Web signals unverified",
    source_types=["web_signal"],
    support_level="single_candidate_source",
    what_is_known="1 candidate URL",
    what_is_unknown="Primary source verification",
    missing_evidence="Human URL check",
    why_it_matters="Candidates are not facts",
    next_verification_action="Open URL and verify",
    recommended_owner="human_reviewer",
    urgency="high",
    confidence_label="candidate",
    source_artifact_paths=["/tmp/collection.json"],
  )
  assert validate_evidence_gap(gap) == []
  assert gap["caution_flags"]["no_legal_judgement"] is True


def test_human_verified_not_allowed() -> None:
  with pytest.raises(ValueError, match="human_verified"):
    build_evidence_gap(
      theme_name="T",
      observation="x",
      source_types=["web_signal"],
      support_level="human_verified",
      what_is_known="a",
      what_is_unknown="b",
      missing_evidence="c",
      why_it_matters="d",
      next_verification_action="e",
      recommended_owner="researcher",
      urgency="low",
      confidence_label="needs_review",
    )


def test_default_safety_flags() -> None:
  flags = default_safety_flags()
  assert flags["candidate_information_only"] is True
  assert flags["legal_judgement"] is False
  assert flags["no_external_api_call"] is True
