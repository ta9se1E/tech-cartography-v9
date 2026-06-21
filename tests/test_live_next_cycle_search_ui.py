"""Tests for next cycle search UI wiring (Phase 25J)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tech_cartography.auth.basic_auth import REQUIRE_LOGIN_ENV
from tech_cartography.runtime.cloud_run_config import default_app_mode
from tech_cartography.ui.live_next_cycle_search_ui import should_show_live_next_cycle_search_ui


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv(REQUIRE_LOGIN_ENV, raising=False)
  monkeypatch.setenv("APP_DEFAULT_MODE", "demo")


def test_analyst_input_wires_next_cycle_search_ui() -> None:
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  assert "render_live_next_cycle_search_section" in text


def test_reports_tab_wires_next_cycle_pack_section() -> None:
  text = Path("src/tech_cartography/ui/v7_easy_app.py").read_text(encoding="utf-8")
  assert "render_live_next_cycle_search_reports_section" in text


def test_next_cycle_ui_is_admin_only_without_secrets() -> None:
  text = Path("src/tech_cartography/ui/live_next_cycle_search_ui.py").read_text(encoding="utf-8")
  assert "Next Cycle Search（承認済みWatch Profileから検索）" in text
  assert "次回検索クエリ候補を作成" in text
  assert "選択したクエリでTavily検索" in text
  assert "os.environ" not in text
  assert "SMTP_PASSWORD" not in text
  assert "scheduler" in text.lower()


def test_demo_mode_hides_next_cycle_ui(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("APP_DEFAULT_MODE", "demo")
  assert default_app_mode() == "demo"
  assert should_show_live_next_cycle_search_ui() is False


def test_docs_cover_phase25j() -> None:
  text = Path("docs/phase25j_watch_profile_driven_next_cycle_search.md").read_text(encoding="utf-8")
  assert "Phase 25I" in text
  assert "pending_human_selection" in text
  assert "DISABLE_EXTERNAL_API" in text
  assert "next_cycle_web_signal_pack" in text
