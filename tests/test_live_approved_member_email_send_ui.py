"""Tests for approved member email send UI wiring (Phase 25Q)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tech_cartography.auth.basic_auth import REQUIRE_LOGIN_ENV
from tech_cartography.ui.live_approved_member_email_send_ui import (
  should_show_live_approved_member_email_send_ui,
)
from tech_cartography.ui.live_email_send_ui import should_show_live_email_send_ui


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv(REQUIRE_LOGIN_ENV, raising=False)
  monkeypatch.setenv("APP_DEFAULT_MODE", "analyst")


def test_analyst_input_wires_approved_member_send_ui() -> None:
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  assert "render_live_approved_member_email_send_section" in text
  assert text.index("render_live_approved_member_email_send_section") < text.index(
    "render_live_email_send_section",
  )


def test_digest_preview_wires_approved_member_before_self_only() -> None:
  text = Path("src/tech_cartography/ui/live_digest_preview_ui.py").read_text(encoding="utf-8")
  assert "render_live_approved_member_email_send_section" in text
  assert text.index("render_live_approved_member_email_send_section") < text.index(
    "render_live_email_send_section",
  )


def test_ui_uses_selectbox_and_approved_sender() -> None:
  text = Path("src/tech_cartography/ui/live_approved_member_email_send_ui.py").read_text(encoding="utf-8")
  assert "st.selectbox" in text
  assert "send_live_digest_email_to_approved_member" in text
  assert "send_live_digest_email_self_only" not in text
  assert "live_approved_member_email_send" in text
  assert "承認済みメンバーへDigestを送信" in text
  assert "is_app_authenticated" in text
  assert "os.environ" not in text


def test_self_only_hidden_in_iap_mode(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(REQUIRE_LOGIN_ENV, "true")
  monkeypatch.setenv("AUTH_PROVIDER_MODE", "iap")
  from tech_cartography.ui import live_email_send_ui as email_ui

  monkeypatch.setattr(email_ui, "is_login_required", lambda: True)
  monkeypatch.setattr(email_ui, "can_use_admin_features", lambda: True)
  monkeypatch.setattr(email_ui, "is_iap_authenticated", lambda: True)
  assert should_show_live_email_send_ui() is False
