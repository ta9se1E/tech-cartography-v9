"""Phase27Q.1 claim batch import service tests."""

from __future__ import annotations

from pathlib import Path

import pytest

from tech_cartography.services.v8_claim_batch_import import (
  apply_claim_batch_import,
  validate_claim_batch_import,
)
from tech_cartography.services.v8_claim_input_loader import load_claims_input_csv
from tech_cartography.services.v8_sources_table import project_root_from_here

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "v8_claim_batch_import_fixture.csv"
CASE = "case_01_pan_graphitization"


def test_validate_fixture(tmp_path: Path) -> None:
  report = validate_claim_batch_import(
    case_id=CASE,
    input_path=FIXTURE,
    project_root=tmp_path,
  )
  assert report.valid_rows >= 1
  assert report.rejected_rows >= 2


def test_apply_creates_backup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  case_dir = tmp_path / "cases" / CASE
  case_dir.mkdir(parents=True)
  src_claims = project_root_from_here() / "cases" / CASE / "claims_input.csv"
  if src_claims.exists():
    (case_dir / "claims_input.csv").write_text(src_claims.read_text(encoding="utf-8"), encoding="utf-8")
  report = apply_claim_batch_import(
    case_id=CASE,
    input_path=FIXTURE,
    duplicate_mode="update",
    project_root=tmp_path,
  )
  assert report.valid_rows >= 1
  rows, _ = load_claims_input_csv(CASE, project_root=tmp_path)
  cn = next((r for r in rows if r.publication_number == "CN117987966A"), None)
  assert cn is not None
  assert cn.has_loaded_text()
  assert cn.claim_source_type == "manual"
