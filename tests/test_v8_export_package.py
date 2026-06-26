"""Tests for v8 export package (Phase 27C)."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.services.v8_export_package import build_export_package, records_to_csv_text
from tech_cartography.services.v8_sources_repository import load_sources_table, project_root_from_here


def test_build_export_package_writes_files(tmp_path: Path) -> None:
  root = project_root_from_here()
  table = load_sources_table("case_01_pan_graphitization", project_root=root)
  package = build_export_package(table, case_id="case_01_pan_graphitization", project_root=tmp_path)

  assert Path(package.sources_csv_path).exists()
  assert Path(package.sources_md_path).exists()
  assert Path(package.export_summary_path).exists()
  assert Path(package.manifest_path).exists()

  manifest = json.loads(Path(package.manifest_path).read_text(encoding="utf-8"))
  assert manifest["source_count"] == table.source_count
  assert "candidate_information_only_notice" in manifest
  assert "human_review_required_notice" in manifest
  assert "no_legal_judgement_notice" in manifest
  assert "fixed_point_observation_note" in manifest

  summary = Path(package.export_summary_path).read_text(encoding="utf-8")
  assert "FTO" in summary

  csv_text = records_to_csv_text(table.records)
  assert "SMTP_PASSWORD" not in csv_text
  assert "TAVILY_API_KEY" not in csv_text

  xlsx = Path(package.sources_xlsx_path)
  if xlsx.exists():
    assert xlsx.stat().st_size > 0
