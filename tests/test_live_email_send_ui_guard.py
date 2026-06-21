"""Tests for live email send UI guard wiring (Phase 25G)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tech_cartography.auth.basic_auth import REQUIRE_LOGIN_ENV
from tech_cartography.runtime.cloud_run_config import default_app_mode
from tech_cartography.ui.live_email_send_ui import should_show_live_email_send_ui


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv(REQUIRE_LOGIN_ENV, raising=False)
  monkeypatch.setenv("APP_DEFAULT_MODE", "demo")


def test_analyst_input_wires_email_send_ui() -> None:
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  assert "render_live_email_send_section" in text


def test_reports_digest_preview_wires_email_send_ui() -> None:
  text = Path("src/tech_cartography/ui/live_digest_preview_ui.py").read_text(encoding="utf-8")
  assert "render_live_email_send_section" in text


def test_email_send_ui_has_no_broadcast_or_smtp_password() -> None:
  text = Path("src/tech_cartography/ui/live_email_send_ui.py").read_text(encoding="utf-8")
  assert "CONFIRMATION_TEXT" in text
  assert "自分宛てに1通送信" in text
  assert "os.environ" not in text
  assert "sendgrid" not in text.lower()
  assert "gmail" not in text.lower()
  assert "cc/bcc" not in text.lower()


def test_demo_mode_hides_email_send_ui(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("APP_DEFAULT_MODE", "demo")
  assert default_app_mode() == "demo"
  assert should_show_live_email_send_ui() is False


def test_docs_cover_phase25g() -> None:
  text = Path("docs/phase25g_self_only_live_digest_email_send_test.md").read_text(encoding="utf-8")
  assert "Phase 25F" in text
  assert "self_only" in text
  assert "--update-env-vars" in text
  assert "outputs/live_email_send" in text
