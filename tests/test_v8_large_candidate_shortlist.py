"""Tests for v8 large candidate shortlist (Phase 27J.0)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tech_cartography.services.v8_large_candidate_import import import_large_candidates
from tech_cartography.services.v8_large_candidate_shortlist import build_staged_shortlist

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "v8_large_candidate_fixture.csv"
CASE_ID = "case_01_pan_graphitization"


@pytest.fixture
def imported_root(tmp_path: Path) -> Path:
  (tmp_path / "cases" / CASE_ID).mkdir(parents=True)
  import_large_candidates(case_id=CASE_ID, input_path=FIXTURE, project_root=tmp_path)
  return tmp_path


def test_staged_shortlist_top_counts(imported_root: Path) -> None:
  pack = build_staged_shortlist(CASE_ID, project_root=imported_root, top100=100, top20=20, top5=5)
  sel = pack.selection
  assert sel.top5_count <= 5
  assert sel.top20_count <= 20
  assert sel.top100_count <= 100
  assert sel.top5_count >= 1
  assert Path(pack.manifest_path).exists()


def test_heuristic_score_and_reason(imported_root: Path) -> None:
  pack = build_staged_shortlist(CASE_ID, project_root=imported_root)
  from tech_cartography.services.v8_large_candidate_import import load_large_candidates_csv

  scored = load_large_candidates_csv(Path(pack.scored_path))
  assert scored
  assert all(r.score_reason for r in scored if r.heuristic_score > 0)
