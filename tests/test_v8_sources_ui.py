"""Tests for v8 sources UI and table service (Phase 27B)."""

from __future__ import annotations

from pathlib import Path

import tech_cartography.services.v8_sources_table as sources_table
import tech_cartography.ui.v8_sources_ui as sources_ui


def test_v8_sources_ui_render_exists() -> None:
  assert callable(sources_ui.render_v8_sources_tab)


def test_load_source_candidates_from_cases() -> None:
  root = sources_table.project_root_from_here()
  rows = sources_table.load_source_candidates("case_01_pan_graphitization", project_root=root)
  assert len(rows) >= 3
  assert rows[0]["type"]
  assert "url" in rows[0]


def test_filter_patent_sources() -> None:
  root = sources_table.project_root_from_here()
  rows = sources_table.load_source_candidates("case_02_sizing_interface", project_root=root)
  patents = sources_table.filter_patent_sources(rows)
  assert patents
  assert all(r["type"].lower() == "patent" for r in patents)


def test_sources_csv_roundtrip() -> None:
  root = sources_table.project_root_from_here()
  rows = sources_table.load_source_candidates(project_root=root)
  csv_text = sources_table.sources_to_csv_text(rows)
  assert "publication_number" in csv_text
  assert "case_id" in csv_text
