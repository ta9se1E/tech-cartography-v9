"""Tests for next cycle Tavily runner (Phase 25J)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tech_cartography.runtime.cloud_run_config import DISABLE_EXTERNAL_API_ENV
from tech_cartography.runtime.live_artifact_paths import LIVE_OUTPUTS_ROOT_ENV
from tech_cartography.services.live_next_cycle_tavily_runner import (
  MAX_SELECTED_QUERIES,
  REVIEW_STATUS,
  SAFETY_LABEL,
  clamp_selected_queries,
  run_next_cycle_tavily_searches,
  save_next_cycle_web_signal_pack,
)
from tech_cartography.services.live_tavily_search import clamp_max_results


@pytest.fixture(autouse=True)
def _clear_env(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv(DISABLE_EXTERNAL_API_ENV, raising=False)
  monkeypatch.delenv("TAVILY_API_KEY", raising=False)


def test_clamp_selected_queries_max_three() -> None:
  rows = [{"query_id": str(i), "query": f"query {i}"} for i in range(10)]
  selected = clamp_selected_queries(rows)
  assert len(selected) == MAX_SELECTED_QUERIES


def test_max_results_per_query_clamped_to_three() -> None:
  assert clamp_max_results(99) == 3
  assert clamp_max_results(1) == 1


def test_disabled_external_api_blocks_tavily(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "true")
  monkeypatch.setenv("TAVILY_API_KEY", "dummy-key")
  called = {"count": 0}

  def _post(**kwargs: object) -> dict:
    called["count"] += 1
    return {"results": []}

  result = run_next_cycle_tavily_searches(
    selected_query_candidates=[{"query_id": "q1", "query": "carbon fiber PAN"}],
    max_results_per_query=2,
    output_root=Path("."),
    theme_name="Theme",
    source_plan_path=None,
    source_watch_profile_draft_path=None,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    post_fn=_post,
  )
  assert result["ok"] is False
  assert result["error"] == "disabled_by_env"
  assert called["count"] == 0


def test_missing_api_key_blocks_tavily(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv("TAVILY_API_KEY", raising=False)
  called = {"count": 0}

  def _post(**kwargs: object) -> dict:
    called["count"] += 1
    return {"results": []}

  result = run_next_cycle_tavily_searches(
    selected_query_candidates=[{"query_id": "q1", "query": "carbon fiber PAN"}],
    max_results_per_query=2,
    output_root=Path("."),
    theme_name="Theme",
    source_plan_path=None,
    source_watch_profile_draft_path=None,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    post_fn=_post,
  )
  assert result["ok"] is False
  assert result["error"] == "missing_keys"
  assert called["count"] == 0


def test_mock_tavily_saves_next_cycle_pack(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  live_root = tmp_path / "live_root"
  monkeypatch.setenv(LIVE_OUTPUTS_ROOT_ENV, str(live_root))
  monkeypatch.setenv("TAVILY_API_KEY", "test-key")

  def _post(**kwargs: object) -> dict:
    return {
      "results": [
        {
          "title": "Toray carbon fiber update",
          "url": "https://example.com/news",
          "content": "precursor recycling project",
          "score": 0.8,
        },
      ],
    }

  result = run_next_cycle_tavily_searches(
    selected_query_candidates=[
      {"query_id": "q1", "query": "Toray carbon fiber"},
      {"query_id": "q2", "query": "NEDO grant CFRP"},
    ],
    max_results_per_query=2,
    output_root=tmp_path / "project",
    theme_name="Carbon Fiber",
    source_plan_path="/tmp/plan.json",
    source_watch_profile_draft_path="/tmp/draft.json",
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    post_fn=_post,
  )
  assert result["ok"] is True
  assert result["saved_paths"]["json"]
  assert str(live_root / "live_next_cycle_web_signals") in result["saved_paths"]["json"]
  pack = result["pack"]
  assert pack["source_type"] == "next_cycle_web_signal_pack"
  candidate = pack["candidates"][0]
  assert candidate["review_status"] == REVIEW_STATUS
  assert candidate["safety_label"] == SAFETY_LABEL
  serialized = json.dumps(pack)
  assert "test-key" not in serialized
  assert "SMTP_PASSWORD" not in serialized


def test_save_pack_directly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  live_root = tmp_path / "live_root"
  monkeypatch.setenv(LIVE_OUTPUTS_ROOT_ENV, str(live_root))
  pack = {
    "theme_name": "Theme",
    "source_type": "next_cycle_web_signal_pack",
    "fetched_at": "2026-06-18T12:00:00+00:00",
    "provider": "tavily",
    "candidates": [],
    "safety_notice": "safe",
  }
  saved = save_next_cycle_web_signal_pack(pack, tmp_path)
  assert str(live_root / "live_next_cycle_web_signals") in saved["json"]
