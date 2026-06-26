"""Tests for v8 manual claim refresh export (Phase 27J)."""

from __future__ import annotations

import json
import re
import shutil
from pathlib import Path

import pytest

from tech_cartography.services.v8_manual_claim_injection import inject_manual_claim
from tech_cartography.services.v8_manual_claim_refresh import refresh_after_manual_claim
from tech_cartography.services.v8_manual_claim_refresh_export import export_manual_claim_refresh
from tech_cartography.services.v8_sources_table import project_root_from_here

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "v8_manual_claim_fixture.txt"
CASE_ID = "case_01_pan_graphitization"
PUB = "US5176959"
SECRET_RE = re.compile(r"(smtp_password|tavily_api_key|eyJhbGci)", re.IGNORECASE)


@pytest.fixture
def injected_case_root(tmp_path: Path) -> Path:
  root = project_root_from_here()
  case_dst = tmp_path / "cases" / CASE_ID
  case_dst.mkdir(parents=True)
  for name in ("claims_input.csv", "source_candidates.csv", "case_profile.yaml"):
    src = root / "cases" / CASE_ID / name
    if src.exists():
      shutil.copy(src, case_dst / name)
  inject_manual_claim(
    case_id=CASE_ID,
    publication_number=PUB,
    claim_no="1",
    claim_text=FIXTURE_PATH.read_text(encoding="utf-8").strip(),
    project_root=tmp_path,
  )
  return tmp_path


def test_export_manual_claim_refresh_pack(injected_case_root: Path) -> None:
  report = refresh_after_manual_claim(
    case_id=CASE_ID,
    publication_number=PUB,
    project_root=injected_case_root,
  )
  export_result = export_manual_claim_refresh(report, project_root=injected_case_root)

  assert Path(export_result.json_path).exists()
  assert Path(export_result.md_path).exists()
  assert Path(export_result.manifest_path).exists()
  assert Path(export_result.artifact_trace_path).exists()

  json_text = Path(export_result.json_path).read_text(encoding="utf-8")
  assert not SECRET_RE.search(json_text)
  manifest = json.loads(Path(export_result.manifest_path).read_text(encoding="utf-8"))
  assert manifest["case_id"] == CASE_ID
  assert "FTO" in Path(export_result.md_path).read_text(encoding="utf-8") or "法的" in json_text
