"""Tests for email operation status UI (Phase 25Q.2)."""

from __future__ import annotations

from pathlib import Path


def test_email_operation_status_ui_exists() -> None:
  text = Path("src/tech_cartography/ui/email_operation_status_ui.py").read_text(encoding="utf-8")
  assert "render_email_operation_status_panel" in text
  assert "safe_off" in text or "SAFETY_LEVEL_SAFE_OFF" in text
  assert "build_post_send_reset_command" in text
  assert "os.environ" not in text
  assert "SMTP_PASSWORD" not in text


def test_wired_into_approved_member_send_ui() -> None:
  text = Path("src/tech_cartography/ui/live_approved_member_email_send_ui.py").read_text(encoding="utf-8")
  assert "render_email_operation_status_compact" in text


def test_wired_into_operation_console() -> None:
  text = Path("src/tech_cartography/ui/live_operation_console_ui.py").read_text(encoding="utf-8")
  assert "render_email_operation_status_panel" in text


def test_wired_into_auth_status() -> None:
  text = Path("src/tech_cartography/ui/auth_status_ui.py").read_text(encoding="utf-8")
  assert "render_email_operation_status_panel" in text
