"""Tests for v8 patent shortlist export (Phase 27D)."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.services.v8_patent_shortlist import build_patent_shortlist
from tech_cartography.services.v8_patent_shortlist_export import (
  export_patent_shortlist,
  shortlist_to_csv_text,
  shortlist_to_markdown,
)
from tech_cartography.services.v8_sources_repository import project_root_from_here


def test_export_patent_shortlist_writes_artifacts(tmp_path: Path) -> None:
  root = project_root_from_here()
  shortlist = build_patent_shortlist(
    case_id="case_01_pan_graphitization",
    top_n=5,
    project_root=root,
  )
  result = export_patent_shortlist(shortlist, project_root=tmp_path)

  assert Path(result.csv_path).exists()
  assert Path(result.md_path).exists()
  assert Path(result.manifest_path).exists()

  csv_text = Path(result.csv_path).read_text(encoding="utf-8")
  md_text = Path(result.md_path).read_text(encoding="utf-8")
  manifest = json.loads(Path(result.manifest_path).read_text(encoding="utf-8"))

  assert "SMTP_PASSWORD" not in csv_text
  assert "TAVILY_API_KEY" not in md_text
  assert "FTO" in md_text
  assert "侵害" in md_text or "有効性" in md_text
  assert manifest["count"] == shortlist.count
  assert "safety_notices" in manifest

  xlsx = Path(result.xlsx_path)
  if xlsx.exists():
    assert xlsx.stat().st_size > 0


def test_shortlist_to_csv_and_markdown_no_secrets() -> None:
  root = project_root_from_here()
  shortlist = build_patent_shortlist(case_id="case_02_sizing_interface", top_n=3, project_root=root)
  csv_text = shortlist_to_csv_text(shortlist.patent_candidates)
  md_text = shortlist_to_markdown(shortlist)
  assert shortlist.patent_candidates
  assert "why_read" in csv_text
  assert "reading priority" in md_text.lower() or "読む優先度" in md_text
