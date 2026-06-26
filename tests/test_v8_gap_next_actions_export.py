"""Tests for v8 Gap / Next Actions export (Phase 27G)."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.services.v8_gap_next_actions import build_gap_next_actions_report
from tech_cartography.services.v8_gap_next_actions_export import export_gap_next_actions
from tech_cartography.services.v8_sources_repository import project_root_from_here


def test_export_gap_next_actions_writes_artifacts(tmp_path: Path) -> None:
  root = project_root_from_here()
  report = build_gap_next_actions_report(case_id="case_01_pan_graphitization", project_root=root)
  result = export_gap_next_actions(report, project_root=tmp_path)

  assert Path(result.csv_path).exists()
  assert Path(result.md_path).exists()
  assert Path(result.manifest_path).exists()
  assert Path(result.watch_profile_proposal_path).exists()
  assert Path(result.digest_summary_path).exists()

  csv_text = Path(result.csv_path).read_text(encoding="utf-8")
  md_text = Path(result.md_path).read_text(encoding="utf-8")
  manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))

  assert "SMTP_PASSWORD" not in csv_text
  assert "TAVILY_API_KEY" not in md_text
  assert "FTO" in md_text
  assert "弱点" in md_text or "invalidity" in md_text.lower()
  assert manifest["gap_count"] == report.gap_count

  xlsx = Path(result.xlsx_path)
  if xlsx.exists():
    assert xlsx.stat().st_size > 0
