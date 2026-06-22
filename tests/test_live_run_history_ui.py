"""Tests for live run history UI wiring (Phase 25M)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tech_cartography.auth.basic_auth import REQUIRE_LOGIN_ENV
from tech_cartography.runtime.cloud_run_config import default_app_mode
from tech_cartography.ui.live_run_history_ui import should_show_run_history_ui


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv(REQUIRE_LOGIN_ENV, raising=False)
  monkeypatch.setenv("APP_DEFAULT_MODE", "demo")


def test_reports_tab_wires_run_history_ui() -> None:
  text = Path("src/tech_cartography/ui/v7_easy_app.py").read_text(encoding="utf-8")
  assert "render_run_history_section" in text


def test_settings_tab_wires_run_history_ui() -> None:
  text = Path("src/tech_cartography/ui/user_settings_view.py").read_text(encoding="utf-8")
  assert "render_run_history_section" in text


def test_input_tab_wires_run_history_ui() -> None:
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  assert "render_run_history_section" in text


def test_run_history_ui_text_has_no_secrets() -> None:
  text = Path("src/tech_cartography/ui/live_run_history_ui.py").read_text(encoding="utf-8")
  assert "Run History（実行履歴）" in text
  assert "監査ログではなく" in text
  assert "SMTP_PASSWORD" not in text
  assert "TECH_CARTOGRAPHY_LOGIN_PASSWORD" not in text


def test_demo_mode_hides_run_history_ui(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("APP_DEFAULT_MODE", "demo")
  assert default_app_mode() == "demo"
  assert should_show_run_history_ui() is False


def test_docs_cover_phase25m() -> None:
  text = Path("docs/phase25m_user_run_context_and_execution_history.md").read_text(encoding="utf-8")
  assert "監査ログではありません" in text or "監査ログではない" in text
  assert "live_run_history" in text
