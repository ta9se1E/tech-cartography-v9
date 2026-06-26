"""Tests for v8 patent triage adapter (Phase 27J.1)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tech_cartography.runtime.v8_large_candidate_schema import V8LargeCandidateRecord
from tech_cartography.services.v8_large_candidate_import import import_large_candidates
from tech_cartography.services.v8_patent_triage_adapter import (
  FALLBACK_WARNING,
  large_candidate_to_triage_dict,
  patent_triage_available,
  score_large_candidates_with_triage,
)

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "v8_large_candidate_fixture.csv"
CASE_ID = "case_01_pan_graphitization"


def test_patent_triage_available() -> None:
  assert patent_triage_available() is True


def test_large_candidate_to_triage_dict() -> None:
  rec = V8LargeCandidateRecord(
    candidate_id="c1",
    case_id=CASE_ID,
    publication_number="US5176959",
    title="test",
    abstract="pan carbonization",
  )
  d = large_candidate_to_triage_dict(rec)
  assert d["publication_number"] == "US5176959"
  assert "carbonization" in d["abstract"]


@pytest.fixture
def imported_root(tmp_path: Path) -> Path:
  (tmp_path / "cases" / CASE_ID).mkdir(parents=True)
  import_large_candidates(case_id=CASE_ID, input_path=FIXTURE, project_root=tmp_path)
  return tmp_path


def test_adapter_uses_patent_triage(imported_root: Path) -> None:
  from tech_cartography.services.v8_large_candidate_import import load_large_candidates_csv

  recs = load_large_candidates_csv(imported_root / "cases" / CASE_ID / "source_candidates_large.csv")
  result = score_large_candidates_with_triage(recs, case_id=CASE_ID, project_root=imported_root)
  assert result.triage_engine == "patent_triage"
  assert "patent_triage" in result.ranking_policy
  assert result.scored_records
  assert all(r.positive_reasons or r.heuristic_score >= 0 for r in result.scored_records)


def test_adapter_fallback_when_triage_unavailable(imported_root: Path, monkeypatch) -> None:
  from tech_cartography.services.v8_large_candidate_import import load_large_candidates_csv

  monkeypatch.setattr(
    "tech_cartography.services.v8_patent_triage_adapter.patent_triage_available",
    lambda: False,
  )
  recs = load_large_candidates_csv(imported_root / "cases" / CASE_ID / "source_candidates_large.csv")
  result = score_large_candidates_with_triage(recs, case_id=CASE_ID, project_root=imported_root)
  assert result.triage_engine == "fallback_large_candidate_heuristic"
  assert FALLBACK_WARNING in result.warnings
