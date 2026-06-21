"""Tests for live Tavily search service (Phase 25D)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tech_cartography.runtime.cloud_run_config import DISABLE_EXTERNAL_API_ENV
from tech_cartography.services.live_tavily_search import (
  build_live_search_save_payload,
  clamp_max_results,
  normalize_tavily_search_response,
  run_live_tavily_search_smoke,
  save_live_tavily_search_result,
  scrub_sensitive_payload,
)


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv(DISABLE_EXTERNAL_API_ENV, raising=False)
  monkeypatch.delenv("TAVILY_API_KEY", raising=False)


def test_clamp_max_results_limits_to_three() -> None:
  assert clamp_max_results(10) == 3
  assert clamp_max_results(0) == 1
  assert clamp_max_results("2") == 2


def test_normalize_tavily_response_maps_fields() -> None:
  fetched_at = "2026-06-18T12:00:00+00:00"
  rows = normalize_tavily_search_response(
    {
      "results": [
        {
          "title": "Example",
          "url": "https://example.com",
          "content": "snippet text",
          "score": 0.9,
        },
      ],
    },
    query="carbon fiber",
    fetched_at=fetched_at,
  )
  assert rows[0]["title"] == "Example"
  assert rows[0]["snippet"] == "snippet text"
  assert rows[0]["provider"] == "tavily"
  assert rows[0]["query"] == "carbon fiber"


def test_run_blocked_when_external_api_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "true")
  monkeypatch.setenv("TAVILY_API_KEY", "tvly-example-not-real")
  result = run_live_tavily_search_smoke(
    "carbon fiber",
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
  )
  assert result["ok"] is False
  assert result["error"] == "disabled_by_env"
  assert "tvly-example-not-real" not in json.dumps(result)


def test_run_blocked_when_key_missing(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "false")
  result = run_live_tavily_search_smoke(
    "carbon fiber",
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
  )
  assert result["ok"] is False
  assert result["error"] == "missing_keys"


def test_run_blocked_for_non_admin(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "false")
  monkeypatch.setenv("TAVILY_API_KEY", "tvly-example-not-real")
  result = run_live_tavily_search_smoke(
    "carbon fiber",
    login_required=True,
    is_authenticated=True,
    auth_role="member",
  )
  assert result["ok"] is False
  assert result["error"] == "admin_required"


def test_run_blocked_when_not_logged_in(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "false")
  monkeypatch.setenv("TAVILY_API_KEY", "tvly-example-not-real")
  result = run_live_tavily_search_smoke(
    "carbon fiber",
    login_required=True,
    is_authenticated=False,
    auth_role="member",
  )
  assert result["ok"] is False
  assert result["error"] == "login_required"


def test_run_success_with_mock_post(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "false")
  monkeypatch.setenv("TAVILY_API_KEY", "tvly-example-not-real")

  def _mock_post(**kwargs: object) -> dict:
    assert kwargs["api_key"] == "tvly-example-not-real"
    return {
      "results": [
        {"title": "Hit", "url": "https://example.com", "content": "body", "score": 0.5},
      ],
    }

  result = run_live_tavily_search_smoke(
    "carbon fiber",
    max_results=5,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    post_fn=_mock_post,
  )
  assert result["ok"] is True
  assert len(result["results"]) == 1
  assert result["max_results"] == 3
  payload = json.dumps(result)
  assert "tvly-example-not-real" not in payload


def test_run_api_error_does_not_raise(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "false")
  monkeypatch.setenv("TAVILY_API_KEY", "tvly-example-not-real")

  def _mock_post(**kwargs: object) -> dict:
    return {"error": "http_error", "detail": "tvly-example-not-real leaked"}

  result = run_live_tavily_search_smoke(
    "carbon fiber",
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    post_fn=_mock_post,
  )
  assert result["ok"] is False
  assert "tvly-example-not-real" not in json.dumps(result)


def test_save_payload_excludes_api_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "false")
  monkeypatch.setenv("TAVILY_API_KEY", "tvly-example-not-real")

  result = run_live_tavily_search_smoke(
    "carbon fiber",
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    post_fn=lambda **kwargs: {
      "results": [{"title": "A", "url": "https://a.example", "content": "x", "score": 1}],
    },
  )
  saved = save_live_tavily_search_result(result, tmp_path)
  json_text = Path(saved["json"]).read_text(encoding="utf-8")
  md_text = Path(saved["markdown"]).read_text(encoding="utf-8")
  assert "tvly-example-not-real" not in json_text
  assert "tvly-example-not-real" not in md_text
  assert "api_key" not in json_text.lower()


def test_scrub_sensitive_payload() -> None:
  cleaned = scrub_sensitive_payload({"api_key": "secret", "results": [{"title": "ok"}]})
  assert cleaned["api_key"] == "[redacted]"
  assert cleaned["results"][0]["title"] == "ok"


def test_build_save_payload_has_safety_notice() -> None:
  payload = build_live_search_save_payload({"query": "q", "results": [], "safety_notice": "notice"})
  assert payload["safety_notice"] == "notice"
