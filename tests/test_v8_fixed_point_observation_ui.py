"""Tests for v8 fixed-point observation UI (Phase 27B)."""

from __future__ import annotations

from pathlib import Path

import tech_cartography.ui.v8_fixed_point_observation_ui as fpo_ui


def test_v8_fixed_point_observation_render_exists() -> None:
  assert callable(fpo_ui.render_v8_fixed_point_observation_tab)


def test_v8_fixed_point_mentions_email_and_scheduler() -> None:
  text = Path(fpo_ui.__file__).read_text(encoding="utf-8")
  assert "メール送信" in text
  assert "Scheduler" in text
  assert "Watch Profile" in text
  assert "Scope Feedback" in text
  assert "Run History" in text


def test_v8_fixed_point_no_smtp_password() -> None:
  text = Path(fpo_ui.__file__).read_text(encoding="utf-8")
  assert "SMTP_PASSWORD" not in text
  assert "TAVILY_API_KEY" not in text
