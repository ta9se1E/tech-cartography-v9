"""Tests for v8 manual claim injection service (Phase 27J)."""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

import pytest

from tech_cartography.services.v8_claim_input_loader import claims_input_path
from tech_cartography.services.v8_manual_claim_injection import (
  inject_manual_claim,
  list_claims_needing_text,
  validate_claim_text,
)
from tech_cartography.services.v8_sources_table import project_root_from_here

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "v8_manual_claim_fixture.txt"
CASE_ID = "case_01_pan_graphitization"
PUB = "US5176959"


@pytest.fixture
def isolated_case_root(tmp_path: Path) -> Path:
  root = project_root_from_here()
  case_src = root / "cases" / CASE_ID
  case_dst = tmp_path / "cases" / CASE_ID
  case_dst.mkdir(parents=True)
  for name in ("claims_input.csv", "source_candidates.csv", "case_profile.yaml"):
    src = case_src / name
    if src.exists():
      shutil.copy(src, case_dst / name)
  return tmp_path


def test_reject_empty_claim() -> None:
  status, text, _ = validate_claim_text("")
  assert status == "rejected_empty"
  assert text == ""


def test_reject_placeholder_claim() -> None:
  status, _, _ = validate_claim_text("claim text not loaded")
  assert status == "rejected_placeholder"


def test_reject_too_short_claim() -> None:
  status, _, _ = validate_claim_text("short claim")
  assert status == "rejected_too_short"


def test_fixture_claim_is_valid() -> None:
  claim_text = FIXTURE_PATH.read_text(encoding="utf-8").strip()
  assert "test fixture only, not real patent claim" in claim_text
  status, normalized, _ = validate_claim_text(claim_text)
  assert status == "manual_input"
  assert len(normalized) >= 20


def test_inject_saves_to_claims_csv_with_backup(isolated_case_root: Path) -> None:
  claim_text = FIXTURE_PATH.read_text(encoding="utf-8").strip()
  csv_path = claims_input_path(CASE_ID, isolated_case_root)
  assert csv_path.exists()

  result = inject_manual_claim(
    case_id=CASE_ID,
    publication_number=PUB,
    claim_no="1",
    claim_text=claim_text,
    claim_source_type="google_patents_user_copy",
    project_root=isolated_case_root,
  )
  assert result.saved_to_claims_input_csv is True
  assert result.claim_text_status == "manual_input"
  assert any("backup created" in w for w in result.warnings)

  with csv_path.open(encoding="utf-8", newline="") as handle:
    rows = list(csv.DictReader(handle))
  loaded = [r for r in rows if r["publication_number"] == PUB and r["claim_text"].strip()]
  assert len(loaded) == 1
  assert "user provided claim text" in loaded[0]["notes"]
  assert loaded[0]["claim_source_type"] == "google_patents_user_copy"


def test_list_claims_needing_text(isolated_case_root: Path) -> None:
  needing = list_claims_needing_text(CASE_ID, project_root=isolated_case_root)
  assert len(needing) >= 1
  assert all(n["publication_number"] for n in needing)
