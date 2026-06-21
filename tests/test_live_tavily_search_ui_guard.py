"""Tests for live Tavily search UI guard wiring (Phase 25D)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tech_cartography.auth.basic_auth import REQUIRE_LOGIN_ENV
from tech_cartography.runtime.cloud_run_config import DISABLE_EXTERNAL_API_ENV, default_app_mode
from tech_cartography.runtime.external_api_guard import check_live_tavily_smoke_allowed
from tech_cartography.ui.live_tavily_search_ui import should_show_live_tavily_smoke_test


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv(REQUIRE_LOGIN_ENV, raising=False)
  monkeypatch.delenv(DISABLE_EXTERNAL_API_ENV, raising=False)
  monkeypatch.delenv("TAVILY_API_KEY", raising=False)
  monkeypatch.setenv("APP_DEFAULT_MODE", "demo")


def test_check_live_tavily_smoke_allowed_admin_only(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "false")
  monkeypatch.setenv("TAVILY_API_KEY", "tvly-example-not-real")

  allowed, reason = check_live_tavily_smoke_allowed(
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
  )
  assert allowed is True
  assert reason is None

  allowed_member, reason_member = check_live_tavily_smoke_allowed(
    login_required=True,
    is_authenticated=True,
    auth_role="member",
  )
  assert allowed_member is False
  assert reason_member == "admin_required"


def test_check_live_tavily_smoke_requires_login(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "false")
  monkeypatch.setenv("TAVILY_API_KEY", "tvly-example-not-real")
  allowed, reason = check_live_tavily_smoke_allowed(
    login_required=True,
    is_authenticated=False,
    auth_role="admin",
  )
  assert allowed is False
  assert reason == "login_required"


def test_analyst_input_tab_wires_smoke_test_ui() -> None:
  text = Path("src/tech_cartography/ui/theme_validation_ui.py").read_text(encoding="utf-8")
  assert "render_live_tavily_smoke_test_section" in text


def test_live_tavily_ui_module_has_admin_notice() -> None:
  text = Path("src/tech_cartography/ui/live_tavily_search_ui.py").read_text(encoding="utf-8")
  assert "Live Web Search Smoke Test" in text
  assert "Tavilyで1回検索" in text
  assert "APIキー本体は表示しません" in text
  assert "os.environ" not in text


def test_demo_mode_unaffected(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("APP_DEFAULT_MODE", "demo")
  monkeypatch.delenv(REQUIRE_LOGIN_ENV, raising=False)
  assert default_app_mode() == "demo"
  assert should_show_live_tavily_smoke_test() is False


def test_docs_cover_phase25d() -> None:
  text = Path("docs/phase25d_live_tavily_web_search_smoke_test.md").read_text(encoding="utf-8")
  assert "DISABLE_EXTERNAL_API" in text
  assert "outputs/live_search" in text
  assert "Web Signal candidate" in text
