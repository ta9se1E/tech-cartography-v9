"""Tests for v8 demo readiness export (Phase 27M)."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.services.v8_demo_readiness import build_demo_readiness_report
from tech_cartography.services.v8_demo_readiness_export import export_demo_readiness
from tech_cartography.services.v8_sources_table import project_root_from_here


def test_export_demo_readiness_files(tmp_path: Path) -> None:
  root = project_root_from_here()
  report = build_demo_readiness_report(project_root=root)
  export_result = export_demo_readiness(report, project_root=tmp_path)
  assert Path(export_result.json_path).exists()
  assert Path(export_result.md_path).exists()
  assert Path(export_result.manifest_path).exists()
  assert Path(export_result.operator_checklist_path).exists()
  assert Path(export_result.cloud_checklist_path).exists()

  md = Path(export_result.md_path).read_text(encoding="utf-8")
  assert "artifact missing" in md.lower() or "not true zero" in md.lower()
  assert "smtp_password" not in md.lower()

  manifest = json.loads(Path(export_result.manifest_path).read_text(encoding="utf-8"))
  assert manifest["no_cloud_build"] is True
