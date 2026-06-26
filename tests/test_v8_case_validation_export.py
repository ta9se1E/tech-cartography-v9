"""Tests for v8 case validation export (Phase 27I)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from tech_cartography.services.v8_case_validation_export import export_validation_pack
from tech_cartography.services.v8_case_validation_pack import build_three_case_validation_pack
from tech_cartography.services.v8_sources_table import project_root_from_here

_SECRET_RE = re.compile(
  r"(smtp_password|tavily_api_key|eyJhbGci)",
  re.IGNORECASE,
)


def test_export_validation_pack_writes_files(tmp_path: Path) -> None:
  root = project_root_from_here()
  pack = build_three_case_validation_pack(project_root=root, ensure_artifacts=False)
  result = export_validation_pack(pack, project_root=root)

  assert Path(result.json_path).exists()
  assert Path(result.md_path).exists()
  assert Path(result.manifest_path).exists()
  assert Path(result.demo_readiness_path).exists()
  assert Path(result.cloud_readiness_path).exists()
  for case_id, path in result.case_report_paths.items():
    assert Path(path).exists()
    assert case_id.startswith("case_")

  json_text = Path(result.json_path).read_text(encoding="utf-8")
  assert not _SECRET_RE.search(json_text)
  manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))
  assert manifest["overall_status"] == pack.overall_status
  assert "readiness_by_case" in manifest

  if not result.excel_warning:
    assert Path(result.xlsx_path).exists()
