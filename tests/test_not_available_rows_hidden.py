"""Tests for hiding not-available claim link rows (Phase 24.5F)."""

from __future__ import annotations

import pandas as pd

from tech_cartography.ui.evidence_map_demo import (
  filter_claim_paper_link_rows,
  prepare_claim_paper_links_display_df,
)


def test_filter_claim_paper_link_rows_drops_not_available() -> None:
  df = pd.DataFrame(
    [
      {"claim_element": "not available", "claim_element_text": "text", "paper_title": "A"},
      {"claim_element": "el1", "claim_element_text": "not available", "paper_title": "B"},
      {"claim_element": "el2", "claim_element_text": "PAN fiber", "paper_title": "C"},
    ],
  )
  filtered = filter_claim_paper_link_rows(df)
  assert len(filtered) == 1
  assert filtered.iloc[0]["claim_element"] == "el2"


def test_filter_claim_paper_link_rows_empty_input() -> None:
  assert filter_claim_paper_link_rows(pd.DataFrame()).empty
  assert filter_claim_paper_link_rows(None).empty


def test_render_claim_paper_links_has_missing_guidance() -> None:
  text = open("src/tech_cartography/ui/evidence_map_demo.py", encoding="utf-8").read()
  fn = text.split("def render_claim_paper_links", 1)[1].split("def render_evidence_gaps_section", 1)[0]
  assert "filter_claim_paper_link_rows" in fn
  assert "CLAIM_ELEMENT_MISSING_GUIDANCE" in fn
  assert "developer_mode" in fn


def test_demo_evidence_tab_passes_developer_mode() -> None:
  text = open("src/tech_cartography/ui/v7_easy_app.py", encoding="utf-8").read()
  evidence = text.split("def _tab_evidence", 1)[1].split("def _tab_market", 1)[0]
  assert "render_demo_evidence_tab(demo_artifacts, developer_mode=" in evidence
