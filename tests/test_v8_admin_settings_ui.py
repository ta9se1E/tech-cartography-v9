"""Tests for v8 admin settings UI isolation (Phase 27B)."""

from __future__ import annotations

from pathlib import Path

import tech_cartography.ui.v8_admin_settings_ui as admin_ui


def test_v8_admin_settings_render_exists() -> None:
  assert callable(admin_ui.render_v8_admin_settings_tab)


def test_v8_admin_settings_has_operation_sections() -> None:
  text = Path(admin_ui.__file__).read_text(encoding="utf-8")
  for token in (
    "render_live_operation_console_section",
    "render_live_scheduler_dry_run_section",
    "render_run_history_section",
    "IAP",
    "secret",
  ):
    assert token in text


def test_v8_admin_settings_no_raw_secrets_display() -> None:
  text = Path(admin_ui.__file__).read_text(encoding="utf-8")
  assert "SMTP_PASSWORD" not in text
  assert "TAVILY_API_KEY" not in text
