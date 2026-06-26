"""Tests for v8 Claim Map export (Phase 27E)."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.services.v8_claim_map import build_claim_map
from tech_cartography.services.v8_claim_map_export import export_claim_map
from tech_cartography.services.v8_sources_repository import project_root_from_here


def test_export_claim_map_writes_artifacts(tmp_path: Path) -> None:
  root = project_root_from_here()
  claim_map = build_claim_map(case_id="case_01_pan_graphitization", project_root=root)
  result = export_claim_map(claim_map, project_root=tmp_path)

  assert Path(result.csv_path).exists()
  assert Path(result.md_path).exists()
  assert Path(result.manifest_path).exists()

  csv_text = Path(result.csv_path).read_text(encoding="utf-8")
  md_text = Path(result.md_path).read_text(encoding="utf-8")
  manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))

  assert "SMTP_PASSWORD" not in csv_text
  assert "TAVILY_API_KEY" not in md_text
  assert "FTO" in md_text
  assert manifest["claim_count"] == claim_map.claim_count

  xlsx = Path(result.xlsx_path)
  if xlsx.exists():
    assert xlsx.stat().st_size > 0
