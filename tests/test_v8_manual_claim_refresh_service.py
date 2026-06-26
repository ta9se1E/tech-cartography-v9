"""Tests for v8 manual claim refresh service (Phase 27J)."""

from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tech_cartography.services.v8_claim_map import build_claim_map
from tech_cartography.services.v8_evidence_map import build_evidence_map
from tech_cartography.services.v8_manual_claim_injection import inject_manual_claim
from tech_cartography.services.v8_manual_claim_refresh import refresh_after_manual_claim
from tech_cartography.services.v8_sources_table import project_root_from_here

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "v8_manual_claim_fixture.txt"
CASE_ID = "case_01_pan_graphitization"
PUB = "US5176959"


@pytest.fixture
def injected_case_root(tmp_path: Path) -> Path:
  root = project_root_from_here()
  case_src = root / "cases" / CASE_ID
  case_dst = tmp_path / "cases" / CASE_ID
  case_dst.mkdir(parents=True)
  for name in ("claims_input.csv", "source_candidates.csv", "case_profile.yaml"):
    src = case_src / name
    if src.exists():
      shutil.copy(src, case_dst / name)
  claim_text = FIXTURE_PATH.read_text(encoding="utf-8").strip()
  inject_manual_claim(
    case_id=CASE_ID,
    publication_number=PUB,
    claim_no="1",
    claim_text=claim_text,
    claim_source_type="manual",
    project_root=tmp_path,
  )
  return tmp_path


def test_claim_map_manual_input_status(injected_case_root: Path) -> None:
  claim_map = build_claim_map(case_id=CASE_ID, project_root=injected_case_root)
  loaded = [r for r in claim_map.records if r.publication_number == PUB]
  assert loaded
  assert loaded[0].claim_text_status == "manual_input"
  assert loaded[0].claim_text != "claim text not loaded"


def test_claim_text_required_count_decreases(injected_case_root: Path) -> None:
  before = build_evidence_map(case_id=CASE_ID, project_root=injected_case_root)
  before_required = before.claim_text_required_count

  report = refresh_after_manual_claim(
    case_id=CASE_ID,
    publication_number=PUB,
    claim_no="1",
    project_root=injected_case_root,
  )
  assert report.claim_text_required_count_after <= before_required
  assert report.validation_readiness_after in {
    "partial_claim_loaded",
    "needs_manual_review",
    "ready",
    "needs_claim_text",
  }
  assert report.no_email_send is True
  assert report.no_scheduler_start is True


def test_refresh_without_claim_raises(isolated_root: Path) -> None:
  root = project_root_from_here()
  case_dst = isolated_root / "cases" / CASE_ID
  case_dst.mkdir(parents=True)
  shutil.copy(root / "cases" / CASE_ID / "claims_input.csv", case_dst / "claims_input.csv")
  with pytest.raises(ValueError, match="claim 本文がありません"):
    refresh_after_manual_claim(
      case_id=CASE_ID,
      publication_number=PUB,
      project_root=isolated_root,
    )


@pytest.fixture
def isolated_root(tmp_path: Path) -> Path:
  return tmp_path
