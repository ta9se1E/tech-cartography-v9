"""Tests for live digest preview UI wiring (Phase 25F)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tech_cartography.auth.basic_auth import REQUIRE_LOGIN_ENV
from tech_cartography.runtime.cloud_run_config import default_app_mode
from tech_cartography.ui.live_digest_preview_ui import should_show_live_digest_preview_ui


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv(REQUIRE_LOGIN_ENV, raising=False)
  monkeypatch.setenv("APP_DEFAULT_MODE", "demo")


def test_analyst_input_wires_digest_preview_ui() -> None:
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  assert "render_live_digest_preview_section" in text


def test_reports_tab_wires_digest_preview_section() -> None:
  text = Path("src/tech_cartography/ui/v7_easy_app.py").read_text(encoding="utf-8")
  assert "render_live_digest_preview_reports_section" in text


def test_digest_preview_ui_has_no_send_button() -> None:
  text = Path("src/tech_cartography/ui/live_digest_preview_ui.py").read_text(encoding="utf-8")
  assert "メール下書きを作成" in text
  assert "これは送信されません" in text
  assert "send_email" not in text
  assert "smtp" not in text.lower()
  assert "sendgrid" not in text.lower()
  assert "gmail" not in text.lower()


def test_demo_mode_hides_admin_digest_ui(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("APP_DEFAULT_MODE", "demo")
  monkeypatch.delenv(REQUIRE_LOGIN_ENV, raising=False)
  assert default_app_mode() == "demo"
  assert should_show_live_digest_preview_ui() is False


def test_reports_tab_demo_branch_skips_live_digest_preview() -> None:
  text = Path("src/tech_cartography/ui/v7_easy_app.py").read_text(encoding="utf-8")
  branch = text.split("if demo_artifacts is None:", 1)[1].split("if is_analyst_view()", 1)[0]
  assert "render_live_digest_preview_reports_section" in branch


def test_docs_cover_phase25f() -> None:
  text = Path("docs/phase25f_live_digest_mail_preview.md").read_text(encoding="utf-8")
  assert "Phase 25E" in text
  assert "outputs/live_digest_preview" in text
  assert "送信" in text
  assert "DISABLE_EMAIL_SEND" in text
