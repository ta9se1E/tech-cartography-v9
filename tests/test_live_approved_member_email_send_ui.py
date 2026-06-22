"""Tests for approved member email send UI wiring (Phase 25Q)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tech_cartography.auth.basic_auth import REQUIRE_LOGIN_ENV
from tech_cartography.ui.live_approved_member_email_send_ui import should_show_live_approved_member_email_send_ui


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv(REQUIRE_LOGIN_ENV, raising=False)
  monkeypatch.setenv("APP_DEFAULT_MODE", "analyst")


def test_analyst_input_wires_approved_member_send_ui() -> None:
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  assert "render_live_approved_member_email_send_section" in text


def test_digest_preview_wires_approved_member_send_ui() -> None:
  text = Path("src/tech_cartography/ui/live_digest_preview_ui.py").read_text(encoding="utf-8")
  assert "render_live_approved_member_email_send_section" in text


def test_ui_uses_selectbox_not_freeform_recipient() -> None:
  text = Path("src/tech_cartography/ui/live_approved_member_email_send_ui.py").read_text(encoding="utf-8")
  assert "st.selectbox" in text
  assert "承認済みメンバーへDigestを送信" in text
  assert "get_confirmation_text" in text
  assert "os.environ" not in text


def test_ui_requires_login(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(REQUIRE_LOGIN_ENV, "false")
  assert should_show_live_approved_member_email_send_ui() is False
