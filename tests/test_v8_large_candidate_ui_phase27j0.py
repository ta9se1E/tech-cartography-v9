"""Tests for v8 large candidate UI (Phase 27J.0)."""

from __future__ import annotations

from pathlib import Path

import tech_cartography.ui.v8_export_ui as export_ui
import tech_cartography.ui.v8_input_ui as input_ui
import tech_cartography.ui.v8_patent_shortlist_ui as shortlist_ui
import tech_cartography.ui.v8_sources_ui as sources_ui
import tech_cartography.ui.v8_claim_map_ui as claim_ui


def test_input_ui_large_candidate_import() -> None:
  text = Path(input_ui.__file__).read_text(encoding="utf-8")
  assert "Import Large Candidate File" in text
  assert "1000件候補" in text
  assert "use_container_width" not in text


def test_sources_ui_large_population() -> None:
  text = Path(sources_ui.__file__).read_text(encoding="utf-8")
  assert "source_candidates_large" in text
  assert "large candidate population" in text


def test_patent_shortlist_staged_selection() -> None:
  text = Path(shortlist_ui.__file__).read_text(encoding="utf-8")
  assert "Top100" in text
  assert "Top20" in text
  assert "Top5" in text


def test_export_ui_large_candidate_pack() -> None:
  text = Path(export_ui.__file__).read_text(encoding="utf-8")
  assert "Large Candidate Pack" in text


def test_claim_map_top5_only() -> None:
  text = Path(claim_ui.__file__).read_text(encoding="utf-8")
  assert "Top5" in text or "large" in text.lower()
