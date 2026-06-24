"""Tests for live web signal collector (Phase 25T)."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import pytest

from tech_cartography.runtime.cloud_run_config import DISABLE_EXTERNAL_API_ENV
from tech_cartography.runtime.external_api_operation_config import (
  ENABLE_MANUAL_WEB_SIGNAL_COLLECTION_ENV,
  get_web_signal_collection_confirmation_text,
)
from tech_cartography.runtime.live_artifact_paths import ensure_live_artifact_dirs
from tech_cartography.runtime.watch_profile_management_config import ENABLE_WATCH_PROFILE_MANAGEMENT_ENV
from tech_cartography.services.live_run_history import list_run_history_entries
from tech_cartography.services.live_watch_profile_manager import (
  create_watch_profile_draft,
  get_latest_watch_profile_draft,
  promote_draft_to_active,
)
from tech_cartography.runtime.watch_profile_management_config import get_activation_confirmation_text
from tech_cartography.services.live_web_signal_collector import ACTION_TYPE, collect_live_web_signals

ADMIN_CTX = {"user_id": "admin@example.com", "role": "admin", "is_admin": True}


def _mock_tavily(**kwargs: Any) -> dict[str, Any]:
  query = kwargs["payload"]["query"]
  return {
    "results": [
      {
        "title": f"Candidate {query}",
        "url": "https://example.com/news",
        "content": "snippet text",
      },
    ],
  }


@pytest.fixture
def collection_env(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(ENABLE_MANUAL_WEB_SIGNAL_COLLECTION_ENV, "true")
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "false")
  monkeypatch.setenv("TAVILY_API_KEY", "test-key-value")
  monkeypatch.setenv(ENABLE_WATCH_PROFILE_MANAGEMENT_ENV, "true")


def _seed_active_profile(tmp_path: Path) -> None:
  ensure_live_artifact_dirs(tmp_path)
  create_watch_profile_draft(
    profile_input={
      "theme_name": "Carbon Fiber Intelligence",
      "search_queries": ["PAN precursor CFRP", "carbon fiber recycling"],
      "search_keywords": ["Toray"],
    },
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context=ADMIN_CTX,
  )
  _, draft_path = get_latest_watch_profile_draft(tmp_path)
  promote_draft_to_active(
    draft_path=draft_path,
    confirm_text=get_activation_confirmation_text(),
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context=ADMIN_CTX,
  )


def test_skipped_when_external_api_disabled(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(ENABLE_MANUAL_WEB_SIGNAL_COLLECTION_ENV, "true")
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "true")
  _seed_active_profile(tmp_path)
  result = collect_live_web_signals(
    output_root=tmp_path,
    confirm_text=get_web_signal_collection_confirmation_text(),
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context=ADMIN_CTX,
  )
  assert result["status"] == "skipped"
  assert Path(result["saved_paths"]["json"]).is_file()


def test_skipped_on_confirmation_mismatch(tmp_path: Path, collection_env: None) -> None:
  _seed_active_profile(tmp_path)
  result = collect_live_web_signals(
    output_root=tmp_path,
    confirm_text="WRONG",
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context=ADMIN_CTX,
  )
  assert result["status"] == "skipped"
  assert result["skipped_reason"] == "confirm_text_mismatch"


def test_skipped_without_active_profile(tmp_path: Path, collection_env: None) -> None:
  ensure_live_artifact_dirs(tmp_path)
  result = collect_live_web_signals(
    output_root=tmp_path,
    confirm_text=get_web_signal_collection_confirmation_text(),
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context=ADMIN_CTX,
  )
  assert result["status"] == "skipped"
  assert result["skipped_reason"] == "active_watch_profile_required"


def test_member_cannot_collect(tmp_path: Path, collection_env: None) -> None:
  _seed_active_profile(tmp_path)
  result = collect_live_web_signals(
    output_root=tmp_path,
    confirm_text=get_web_signal_collection_confirmation_text(),
    login_required=True,
    is_authenticated=True,
    auth_role="member",
    user_context={"user_id": "member@example.com", "role": "member"},
  )
  assert result["status"] == "skipped"
  assert result["skipped_reason"] == "admin_required"


def test_success_saves_candidate_signals(tmp_path: Path, collection_env: None) -> None:
  _seed_active_profile(tmp_path)
  result = collect_live_web_signals(
    output_root=tmp_path,
    confirm_text=get_web_signal_collection_confirmation_text(),
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context=ADMIN_CTX,
    post_fn=_mock_tavily,
  )
  assert result["ok"] is True
  assert result["status"] == "success"
  payload = json.loads(Path(result["saved_paths"]["json"]).read_text(encoding="utf-8"))
  assert payload["web_signals"]
  assert payload["web_signals"][0]["confidence_label"] == "candidate"
  assert payload["safety_flags"]["candidate_information_only"] is True
  raw = Path(result["saved_paths"]["json"]).read_text(encoding="utf-8")
  assert "TAVILY_API_KEY" not in raw
  assert os.environ.get("TAVILY_API_KEY", "") not in raw


def test_max_queries_respected(tmp_path: Path, collection_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("WEB_SIGNAL_MAX_QUERIES", "1")
  _seed_active_profile(tmp_path)
  result = collect_live_web_signals(
    output_root=tmp_path,
    confirm_text=get_web_signal_collection_confirmation_text(),
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context=ADMIN_CTX,
    post_fn=_mock_tavily,
  )
  payload = result["payload"]
  assert len(payload.get("queries_used") or []) <= 1


def test_max_results_per_query_respected(tmp_path: Path, collection_env: None, monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("WEB_SIGNAL_MAX_RESULTS_PER_QUERY", "1")
  _seed_active_profile(tmp_path)
  call_count = {"n": 0}

  def _counting_tavily(**kwargs: Any) -> dict[str, Any]:
    call_count["n"] += 1
    return {
      "results": [
        {"title": "A", "url": "https://example.com/a", "content": "a"},
        {"title": "B", "url": "https://example.com/b", "content": "b"},
      ],
    }

  result = collect_live_web_signals(
    output_root=tmp_path,
    confirm_text=get_web_signal_collection_confirmation_text(),
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context=ADMIN_CTX,
    post_fn=_counting_tavily,
  )
  payload = result["payload"]
  for signal in payload.get("web_signals") or []:
    pass
  per_query = {}
  for signal in payload.get("web_signals") or []:
    q = signal.get("query")
    per_query[q] = per_query.get(q, 0) + 1
  assert all(count <= 1 for count in per_query.values())


def test_run_history_records_collection(tmp_path: Path, collection_env: None) -> None:
  _seed_active_profile(tmp_path)
  collect_live_web_signals(
    output_root=tmp_path,
    confirm_text=get_web_signal_collection_confirmation_text(),
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context=ADMIN_CTX,
    post_fn=_mock_tavily,
  )
  entries = list_run_history_entries(tmp_path, viewer_user_context=ADMIN_CTX)
  assert any(e.get("action_type") == ACTION_TYPE for e in entries)
