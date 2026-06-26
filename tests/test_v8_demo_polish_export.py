"""Tests for v8 demo polish export (Phase 27L)."""

from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest

from tech_cartography.services.v8_demo_polish import build_demo_polish_report
from tech_cartography.services.v8_demo_polish_export import export_demo_polish
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


def test_export_demo_polish_files(case_root: Path) -> None:
  report = build_demo_polish_report(case_id=CASE_ID, project_root=case_root)
  export_result = export_demo_polish(report, project_root=case_root)
  assert Path(export_result.json_path).exists()
  assert Path(export_result.md_path).exists()
  assert Path(export_result.manifest_path).exists()
  assert Path(export_result.story_cards_csv_path).exists()
  assert Path(export_result.narrative_path).exists()
  assert Path(export_result.caveats_path).exists()

  md_text = Path(export_result.md_path).read_text(encoding="utf-8")
  assert "Evidence Map is not proof" in md_text or "supporting evidence candidate" in md_text
  assert "Gap" in md_text

  manifest = json.loads(Path(export_result.manifest_path).read_text(encoding="utf-8"))
  assert manifest["case_id"] == CASE_ID
  assert "smtp_password" not in md_text.lower()
  assert "tavily_api_key" not in md_text.lower()
