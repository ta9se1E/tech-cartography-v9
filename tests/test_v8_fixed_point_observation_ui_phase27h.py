"""Tests for v8 Fixed Point Observation UI phase 27H."""

from __future__ import annotations

from pathlib import Path

import tech_cartography.ui.v8_fixed_point_observation_ui as fp_ui


def test_v8_fixed_point_observation_ui_phase27h_controls() -> None:
  text = Path(fp_ui.__file__).read_text(encoding="utf-8")
  assert "Generate / Refresh Fixed Point Observation" in text
  assert "width=\"stretch\"" in text
  assert "use_container_width" not in text
  assert "FTO" in text
  assert "All cases" in text
  assert "no_email_send" in text or "送信しない" in text
  assert "no_scheduler_start" in text or "起動しない" in text
  assert "Watch Profile" in text
  assert "Scheduler Follow-up" in text or "scheduler_followup" in text
  assert "Email Digest" in text or "email_digest" in text
  assert "gap_next_actions" in text or "Gap / Next Actions" in text
  assert "export" in text.lower()


def test_v8_fixed_point_observation_ui_importable() -> None:
  assert callable(fp_ui.render_v8_fixed_point_observation_tab)
