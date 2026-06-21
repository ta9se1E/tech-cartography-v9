"""Tests for API secret config (Phase 25C)."""

from __future__ import annotations

import json

import pytest

from tech_cartography.runtime.api_secret_config import (
  KNOWN_API_SECRETS,
  can_use_external_api,
  get_api_secret_status,
  is_external_api_enabled,
  is_secret_present,
)
from tech_cartography.runtime.cloud_run_config import DISABLE_EXTERNAL_API_ENV


@pytest.fixture(autouse=True)
def _clear_api_env(monkeypatch: pytest.MonkeyPatch) -> None:
  for name in KNOWN_API_SECRETS:
    monkeypatch.delenv(name, raising=False)
  monkeypatch.delenv(DISABLE_EXTERNAL_API_ENV, raising=False)


def test_missing_secret_is_not_present() -> None:
  assert is_secret_present("OPENAI_API_KEY") is False


def test_configured_secret_is_present(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("OPENAI_API_KEY", "sk-example-not-real")
  assert is_secret_present("OPENAI_API_KEY") is True


@pytest.mark.parametrize(
  "value",
  ["", "dummy", "placeholder", "<secret-manager-only>", "  placeholder  "],
)
def test_placeholder_values_are_missing(monkeypatch: pytest.MonkeyPatch, value: str) -> None:
  monkeypatch.setenv("TAVILY_API_KEY", value)
  assert is_secret_present("TAVILY_API_KEY") is False


def test_get_api_secret_status_never_returns_values(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("GEMINI_API_KEY", "gemini-secret-value")
  status = get_api_secret_status()
  payload = json.dumps(status)
  assert "gemini-secret-value" not in payload
  assert status["secrets"]["GEMINI_API_KEY"] == "configured"
  assert "GEMINI_API_KEY" not in status["missing_keys"]


def test_get_api_secret_status_lists_missing_keys() -> None:
  status = get_api_secret_status()
  assert set(status["missing_keys"]) == set(KNOWN_API_SECRETS)
  assert status["external_api_execution"] == "enabled"


def test_disable_external_api_marks_execution_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "true")
  status = get_api_secret_status()
  assert status["external_api_execution"] == "disabled"
  assert is_external_api_enabled() is False


def test_can_use_external_api_blocked_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "true")
  monkeypatch.setenv("TAVILY_API_KEY", "tvly-example-not-real")
  allowed, missing = can_use_external_api(["TAVILY_API_KEY"])
  assert allowed is False
  assert missing == ["TAVILY_API_KEY"]


def test_can_use_external_api_blocked_when_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "false")
  allowed, missing = can_use_external_api(["TAVILY_API_KEY"])
  assert allowed is False
  assert missing == ["TAVILY_API_KEY"]


def test_can_use_external_api_allowed_with_keys(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "false")
  monkeypatch.setenv("TAVILY_API_KEY", "tvly-example-not-real")
  allowed, missing = can_use_external_api(["TAVILY_API_KEY"])
  assert allowed is True
  assert missing == []


def test_admin_status_module_does_not_expose_secret_values() -> None:
  text = (
    __import__("pathlib").Path("src/tech_cartography/ui/api_secret_status_ui.py").read_text(encoding="utf-8")
  )
  assert "os.environ" not in text
  assert "getenv" not in text
  assert "APIキー本体は表示しません" in text
