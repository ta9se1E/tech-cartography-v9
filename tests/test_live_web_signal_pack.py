"""Tests for live Web Signal pack service (Phase 25E)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tech_cartography.runtime.cloud_run_config import DISABLE_EXTERNAL_API_ENV
from tech_cartography.services.live_web_signal_pack import (
  REVIEW_STATUS,
  SAFETY_LABEL,
  SAFETY_NOTICE,
  build_live_web_signal_pack,
  infer_confidence_label,
  infer_live_signal_type,
  run_live_web_signal_pack,
  save_live_web_signal_pack,
  tavily_results_to_candidates,
)


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv(DISABLE_EXTERNAL_API_ENV, raising=False)
  monkeypatch.delenv("TAVILY_API_KEY", raising=False)


def test_tavily_results_convert_to_candidates() -> None:
  candidates = tavily_results_to_candidates(
    theme_name="Carbon Fiber",
    query="carbon fiber market",
    results=[
      {
        "title": "Toray press release on carbon fiber",
        "url": "https://www.toray.com/ir/news.html",
        "snippet": "company expansion",
        "score": 0.91,
        "fetched_at": "2026-06-18T12:00:00+00:00",
      },
    ],
  )
  assert len(candidates) == 1
  item = candidates[0]
  assert item["theme_name"] == "Carbon Fiber"
  assert item["signal_type"] == "company_signal"
  assert item["confidence_label"] == "high"
  assert item["review_status"] == REVIEW_STATUS
  assert item["safety_label"] == SAFETY_LABEL
  assert item["provider"] == "tavily"


def test_infer_live_signal_type_public_project() -> None:
  assert (
    infer_live_signal_type(
      title="NEDO grant program",
      snippet="national project funding",
      url="https://www.nedo.go.jp/project",
    )
    == "public_project_signal"
  )


def test_infer_confidence_label_medium() -> None:
  assert infer_confidence_label(0.6) == "medium"


def test_build_pack_has_safety_notice() -> None:
  pack = build_live_web_signal_pack(
    theme_name="Theme",
    query="query",
    candidates=[],
  )
  assert pack["safety_notice"] == SAFETY_NOTICE
  assert pack["next_actions"]


def test_save_pack_excludes_api_key(tmp_path: Path) -> None:
  pack = build_live_web_signal_pack(
    theme_name="Theme",
    query="query",
    candidates=tavily_results_to_candidates(
      theme_name="Theme",
      query="query",
      results=[{"title": "A", "url": "https://a.example", "snippet": "x", "score": 0.2, "fetched_at": "t"}],
    ),
  )
  saved = save_live_web_signal_pack(pack, tmp_path)
  json_text = Path(saved["json"]).read_text(encoding="utf-8")
  csv_text = Path(saved["csv"]).read_text(encoding="utf-8")
  assert "api_key" not in json_text.lower()
  assert "TAVILY_API_KEY" not in json_text
  assert "Web Signal candidate" in json_text
  assert "needs_human_review" in csv_text


def test_run_blocked_when_external_api_disabled(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "true")
  monkeypatch.setenv("TAVILY_API_KEY", "tvly-example-not-real")
  result = run_live_web_signal_pack(
    theme_name="Theme",
    query="query",
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    output_root=tmp_path,
  )
  assert result["ok"] is False
  assert result["error"] == "disabled_by_env"


def test_run_blocked_for_non_admin(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "false")
  monkeypatch.setenv("TAVILY_API_KEY", "tvly-example-not-real")
  result = run_live_web_signal_pack(
    theme_name="Theme",
    query="query",
    login_required=True,
    is_authenticated=True,
    auth_role="member",
    output_root=tmp_path,
  )
  assert result["ok"] is False
  assert result["error"] == "admin_required"


def test_run_success_with_mock_post(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "false")
  monkeypatch.setenv("TAVILY_API_KEY", "tvly-example-not-real")

  def _mock_post(**kwargs: object) -> dict:
    return {
      "results": [
        {"title": "Market outlook", "url": "https://example.com/market", "content": "demand forecast", "score": 0.7},
      ],
    }

  result = run_live_web_signal_pack(
    theme_name="Carbon Fiber",
    query="carbon fiber market",
    max_results=5,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    output_root=tmp_path,
    post_fn=_mock_post,
  )
  assert result["ok"] is True
  assert result["max_results"] == 3
  assert result["candidates"][0]["signal_type"] == "market_signal"
  payload = json.dumps(result)
  assert "tvly-example-not-real" not in payload
  assert Path(result["saved_paths"]["json"]).exists()
