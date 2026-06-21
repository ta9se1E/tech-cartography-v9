"""Tests for live operation console UI wiring (Phase 25K)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tech_cartography.auth.basic_auth import REQUIRE_LOGIN_ENV
from tech_cartography.runtime.cloud_run_config import default_app_mode
from tech_cartography.ui.live_operation_console_ui import should_show_live_operation_console_ui


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv(REQUIRE_LOGIN_ENV, raising=False)
  monkeypatch.setenv("APP_DEFAULT_MODE", "demo")


def test_analyst_input_wires_operation_console() -> None:
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  assert "render_live_operation_console_section" in text


def test_reports_tab_wires_operation_console() -> None:
  text = Path("src/tech_cartography/ui/v7_easy_app.py").read_text(encoding="utf-8")
  assert "render_live_operation_console_section" in text


def test_console_ui_is_admin_only_without_secrets() -> None:
  text = Path("src/tech_cartography/ui/live_operation_console_ui.py").read_text(encoding="utf-8")
  assert "Live Operation Console（手動週次運用）" in text
  assert "next recommended action" in text
  assert "状態を更新して保存" in text
  assert "build_and_save_operation_cycle_status" in text
  assert "os.environ" not in text
  assert "SMTP_PASSWORD" not in text
  assert "一括実行" not in text


def test_demo_mode_hides_console(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("APP_DEFAULT_MODE", "demo")
  assert default_app_mode() == "demo"
  assert should_show_live_operation_console_ui() is False


def test_docs_cover_phase25k() -> None:
  text = Path("docs/phase25k_manual_weekly_operation_console.md").read_text(encoding="utf-8")
  assert "Phase 25J" in text
  assert "scheduler" in text
  assert "live_operation_status" in text
