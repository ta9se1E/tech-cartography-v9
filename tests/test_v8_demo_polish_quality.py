"""Quality tests for v8 demo polish (Phase 27L)."""

from __future__ import annotations

import shutil
from pathlib import Path

from tech_cartography.services.v8_demo_polish import build_demo_polish_report
from tech_cartography.services.v8_demo_polish_export import export_demo_polish, report_to_markdown
from tech_cartography.services.v8_sources_table import project_root_from_here

CASE_ID = "case_01_pan_graphitization"


def test_demo_narrative_not_empty(tmp_path: Path) -> None:
  root = project_root_from_here()
  case_dst = tmp_path / "cases" / CASE_ID
  case_dst.mkdir(parents=True)
  for name in ("claims_input.csv", "source_candidates.csv", "case_profile.yaml"):
    src = root / "cases" / CASE_ID / name
    if src.exists():
      shutil.copy(src, case_dst / name)
  report = build_demo_polish_report(case_id=CASE_ID, project_root=tmp_path)
  assert "1000件" in report.demo_narrative or "Top5" in report.demo_narrative
  assert "Evidence Map is not proof" in report.demo_narrative or "candidate" in report.demo_narrative


def test_export_safety_notices(tmp_path: Path) -> None:
  root = project_root_from_here()
  case_dst = tmp_path / "cases" / CASE_ID
  case_dst.mkdir(parents=True)
  for name in ("claims_input.csv", "source_candidates.csv", "case_profile.yaml"):
    src = root / "cases" / CASE_ID / name
    if src.exists():
      shutil.copy(src, case_dst / name)
  report = build_demo_polish_report(case_id=CASE_ID, project_root=tmp_path)
  md = report_to_markdown(report)
  assert "FTO" in md or "侵害" in md or "no legal" in md.lower()
  assert "Gap is not invalidity" in md or "未確認" in md
  export_demo_polish(report, project_root=tmp_path)
