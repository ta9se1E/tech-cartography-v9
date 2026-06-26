"""Tests for v8 Claim Map UI phase 27E."""

from __future__ import annotations

from pathlib import Path

import tech_cartography.ui.v8_claim_map_ui as claim_map_ui


def test_v8_claim_map_ui_phase27e_controls() -> None:
  text = Path(claim_map_ui.__file__).read_text(encoding="utf-8")
  assert "Generate / Refresh Claim Map" in text
  assert "width=\"stretch\"" in text
  assert "use_container_width" not in text
  assert "claim text not loaded" in text
  assert "FTO" in text
  assert "evidence_map" in text or "Evidence Map" in text
  assert "claims_input.csv" in text
  assert "All cases" in text


def test_v8_claim_map_ui_importable() -> None:
  assert callable(claim_map_ui.render_v8_claim_map_tab)
