"""Tests for v8 Fixed Point Observation export (Phase 27H)."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.services.v8_fixed_point_observation import build_observation_loop_report
from tech_cartography.services.v8_fixed_point_observation_export import export_observation_loop
from tech_cartography.services.v8_sources_repository import project_root_from_here


def test_export_observation_loop_writes_artifacts(tmp_path: Path) -> None:
  root = project_root_from_here()
  report = build_observation_loop_report(case_id="case_01_pan_graphitization", project_root=root)
  result = export_observation_loop(report, project_root=tmp_path)

  assert Path(result.json_path).exists()
  assert Path(result.md_path).exists()
  assert Path(result.manifest_path).exists()
  assert Path(result.watch_profile_proposal_path).exists()
  assert Path(result.scheduler_plan_path).exists()
  assert Path(result.email_digest_plan_path).exists()

  md_text = Path(result.md_path).read_text(encoding="utf-8")
  manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))

  assert "SMTP_PASSWORD" not in md_text
  assert "TAVILY_API_KEY" not in md_text
  assert "FTO" in md_text
  assert manifest["no_email_send"] is True
  assert manifest["no_scheduler_start"] is True

  xlsx = Path(result.xlsx_path)
  if xlsx.exists():
    assert xlsx.stat().st_size > 0
