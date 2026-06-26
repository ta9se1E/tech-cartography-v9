"""Tests for v8 large candidate ranking explanation (Phase 27J.1)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from tech_cartography.services.v8_large_candidate_import import import_large_candidates
from tech_cartography.services.v8_large_candidate_shortlist import build_staged_shortlist

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "v8_large_candidate_fixture.csv"
CASE_ID = "case_01_pan_graphitization"
SECRET_RE = re.compile(r"(smtp_password|tavily_api_key|eyJhbGci)", re.IGNORECASE)


@pytest.fixture
def pack(tmp_path: Path):
  (tmp_path / "cases" / CASE_ID).mkdir(parents=True)
  import_large_candidates(case_id=CASE_ID, input_path=FIXTURE, project_root=tmp_path)
  return build_staged_shortlist(CASE_ID, project_root=tmp_path)


def test_ranking_explanation_files_generated(pack) -> None:
  out = Path(pack.output_dir)
  for fname in (
    "ranking_explanation.md",
    "ranking_explanation.json",
    "ranking_explanation.csv",
    "top5_ranking_explanation.md",
    "dropped_candidate_summary.md",
  ):
    assert (out / fname).exists(), fname

  manifest = json.loads((out / "large_candidate_shortlist_manifest.json").read_text(encoding="utf-8"))
  assert manifest.get("triage_engine")
  assert manifest.get("ranking_policy")


def test_top5_has_why_selected(pack) -> None:
  from tech_cartography.services.v8_large_candidate_import import load_large_candidates_csv

  top5 = load_large_candidates_csv(Path(pack.output_dir) / "large_candidate_top5.csv")
  assert top5
  assert all(r.why_selected or r.score_reason for r in top5)
  assert all(r.positive_reasons or r.heuristic_score > 0 for r in top5)


def test_dropped_summary_content(pack) -> None:
  text = (Path(pack.output_dir) / "dropped_candidate_summary.md").read_text(encoding="utf-8")
  assert "Dropped" in text or "Top5" in text


def test_ranking_explanation_no_secrets(pack) -> None:
  text = (Path(pack.output_dir) / "ranking_explanation.json").read_text(encoding="utf-8")
  assert not SECRET_RE.search(text)
