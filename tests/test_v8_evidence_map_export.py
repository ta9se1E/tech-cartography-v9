"""Tests for v8 Evidence Map export (Phase 27F)."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.services.v8_evidence_map import build_evidence_map
from tech_cartography.services.v8_evidence_map_export import export_evidence_map
from tech_cartography.services.v8_sources_repository import project_root_from_here


def test_export_evidence_map_writes_artifacts(tmp_path: Path) -> None:
  root = project_root_from_here()
  emap = build_evidence_map(case_id="case_01_pan_graphitization", project_root=root)
  result = export_evidence_map(emap, project_root=tmp_path)

  assert Path(result.csv_path).exists()
  assert Path(result.md_path).exists()
  assert Path(result.manifest_path).exists()

  csv_text = Path(result.csv_path).read_text(encoding="utf-8")
  md_text = Path(result.md_path).read_text(encoding="utf-8")
  manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))

  assert "SMTP_PASSWORD" not in csv_text
  assert "TAVILY_API_KEY" not in md_text
  assert "FTO" in md_text
  assert "not proof" in md_text.lower() or "証明" in md_text
  assert manifest["link_count"] == emap.link_count

  xlsx = Path(result.xlsx_path)
  if xlsx.exists():
    assert xlsx.stat().st_size > 0
