"""Tests for external API guard (Phase 25C)."""

from __future__ import annotations

import json

import pytest

from tech_cartography.runtime.api_secret_config import get_api_secret_status
from tech_cartography.runtime.cloud_run_config import DISABLE_EXTERNAL_API_ENV
from tech_cartography.runtime.external_api_guard import (
  check_service_external_api,
  external_api_ui_messages,
  get_external_api_guard_status,
  resolve_allow_external_api,
)
from tech_cartography.runtime.cloud_run_config import default_app_mode, is_external_api_disabled


@pytest.fixture(autouse=True)
def _clear_guard_env(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv(DISABLE_EXTERNAL_API_ENV, raising=False)
  monkeypatch.delenv("TAVILY_API_KEY", raising=False)
  monkeypatch.delenv("GOOGLE_API_KEY", raising=False)
  monkeypatch.setenv("APP_DEFAULT_MODE", "demo")


def test_guard_status_has_no_secret_values(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("TAVILY_API_KEY", "tvly-example-not-real")
  status = get_external_api_guard_status()
  payload = json.dumps(status)
  assert "tvly-example-not-real" not in payload
  assert "disabled_by_env" in status


def test_check_tavily_blocked_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "true")
  monkeypatch.setenv("TAVILY_API_KEY", "tvly-example-not-real")
  allowed, missing, reason = check_service_external_api("tavily")
  assert allowed is False
  assert reason == "disabled_by_env"
  assert missing == ["TAVILY_API_KEY"]


def test_check_tavily_blocked_when_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "false")
  allowed, missing, reason = check_service_external_api("tavily")
  assert allowed is False
  assert reason == "missing_keys"
  assert missing == ["TAVILY_API_KEY"]


def test_check_openalex_allowed_without_keys_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "false")
  allowed, missing, reason = check_service_external_api("openalex")
  assert allowed is True
  assert missing == []
  assert reason is None


def test_ui_messages_show_disabled_and_missing(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "true")
  messages = external_api_ui_messages()
  assert any("外部API無効化中" in message for message in messages)


def test_ui_messages_show_missing_keys_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "false")
  messages = external_api_ui_messages()
  assert any("TAVILY_API_KEY" in message for message in messages)


def test_resolve_allow_external_api_respects_disable_flag(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "true")
  allowed, reasons = resolve_allow_external_api(
    allow_checkbox=True,
    run_tavily=True,
  )
  assert allowed is False
  assert "disabled_by_env" in reasons


def test_resolve_allow_external_api_respects_missing_keys(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "false")
  allowed, reasons = resolve_allow_external_api(
    allow_checkbox=True,
    run_tavily=True,
  )
  assert allowed is False
  assert "missing_keys" in reasons
  assert "TAVILY_API_KEY" in reasons


def test_demo_mode_unaffected_by_secret_status(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("APP_DEFAULT_MODE", "demo")
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "true")
  assert default_app_mode() == "demo"
  assert is_external_api_disabled() is True
  status = get_api_secret_status()
  assert "secrets" in status
