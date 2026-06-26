"""Tests for v8 Gap / Next Actions UI phase 27G."""

from __future__ import annotations

from pathlib import Path

import tech_cartography.ui.v8_gap_next_actions_ui as gap_ui


def test_v8_gap_next_actions_ui_phase27g_controls() -> None:
  text = Path(gap_ui.__file__).read_text(encoding="utf-8")
  assert "Generate / Refresh Gap" in text
  assert "width=\"stretch\"" in text
  assert "use_container_width" not in text
  assert "弱点" in text or "invalidity" in text.lower()
  assert "FTO" in text
  assert "All cases" in text
  assert "fixed_point_observation" in text or "定点観測" in text
  assert "watch_profile_update_proposal" in text.lower() or "Watch Profile" in text
  assert "digest_summary" in text.lower() or "Digest summary" in text


def test_v8_gap_next_actions_ui_importable() -> None:
  assert callable(gap_ui.render_v8_gap_next_actions_tab)
