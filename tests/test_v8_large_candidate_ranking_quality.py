"""Quality tests for v8 ranking explanation (Phase 27J.1)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.runtime.v8_ranking_explanation_schema import RANKING_EXPLANATION_NOTICES


def test_ranking_notices_no_legal_claims() -> None:
  blob = " ".join(RANKING_EXPLANATION_NOTICES).lower()
  assert "法的価値" in blob or "法的" in blob
  assert "fto" in blob or "侵害" in blob
  assert "deep dive" in blob.lower() or "深掘り" in blob


def test_shortlist_service_references_triage() -> None:
  text = Path("src/tech_cartography/services/v8_large_candidate_shortlist.py").read_text(encoding="utf-8")
  assert "score_large_candidates_with_triage" in text
  assert "ranking_policy" in text
  assert "triage_engine" in text


def test_patent_triage_module_exists() -> None:
  path = Path("src/tech_cartography/services/patent_triage.py")
  assert path.exists()
  text = path.read_text(encoding="utf-8")
  assert "include_term_hit" in text or "include_terms" in text
  assert "exclude_term" in text or "exclude_terms" in text
