"""Tests for v8 Evidence Map UI phase 27F."""

from __future__ import annotations

from pathlib import Path

import tech_cartography.ui.v8_evidence_map_ui as evidence_map_ui


def test_v8_evidence_map_ui_phase27f_controls() -> None:
  text = Path(evidence_map_ui.__file__).read_text(encoding="utf-8")
  assert "Generate / Refresh Evidence Map" in text
  assert "width=\"stretch\"" in text
  assert "use_container_width" not in text
  assert "supporting evidence candidate" in text
  assert "not proof" in text.lower() or "証明" in text
  assert "claim text required" in text.lower() or "claim_text_required" in text
  assert "All cases" in text
  assert "gap_next_actions" in text or "Gap / Next Actions" in text


def test_v8_evidence_map_ui_importable() -> None:
  assert callable(evidence_map_ui.render_v8_evidence_map_tab)
