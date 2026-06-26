"""Tests for v8 demo polish service (Phase 27L)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tech_cartography.services.v8_demo_polish import build_demo_polish_report
from tech_cartography.services.v8_sources_table import project_root_from_here

CASE_ID = "case_01_pan_graphitization"


@pytest.fixture
def case_root(tmp_path: Path) -> Path:
  root = project_root_from_here()
  case_src = root / "cases" / CASE_ID
  case_dst = tmp_path / "cases" / CASE_ID
  case_dst.mkdir(parents=True)
  for name in ("claims_input.csv", "source_candidates.csv", "case_profile.yaml"):
    src = case_src / name
    if src.exists():
      shutil.copy(src, case_dst / name)
  return tmp_path


def test_build_demo_polish_report_does_not_crash(case_root: Path) -> None:
  report = build_demo_polish_report(case_id=CASE_ID, project_root=case_root)
  assert report.case_id == CASE_ID
  assert report.demo_narrative.strip()
  assert report.evidence_demo_status is not None
  assert report.gap_demo_status is not None


def test_claim_text_required_count_present(case_root: Path) -> None:
  report = build_demo_polish_report(case_id=CASE_ID, project_root=case_root)
  ev = report.evidence_demo_status
  assert ev is not None
  assert ev.claim_text_required_count >= 0


def test_manual_claim_count_present(case_root: Path) -> None:
  report = build_demo_polish_report(case_id=CASE_ID, project_root=case_root)
  ev = report.evidence_demo_status
  assert ev is not None
  assert ev.manual_claim_count >= 0


def test_story_cards_and_top_actions(case_root: Path) -> None:
  report = build_demo_polish_report(case_id=CASE_ID, project_root=case_root)
  assert len(report.story_cards) >= 5
  gap = report.gap_demo_status
  assert gap is not None
  assert gap.gap_count >= 0
  assert report.evidence_map_not_proof is True
  assert report.gap_is_not_invalidity is True
  assert report.no_email_send is True
  assert report.no_scheduler_start is True
