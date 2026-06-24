"""Digest Preview references web signal collection without auto API (Phase 25T)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tech_cartography.runtime.cloud_run_config import DISABLE_EXTERNAL_API_ENV
from tech_cartography.runtime.external_api_operation_config import ENABLE_MANUAL_WEB_SIGNAL_COLLECTION_ENV
from tech_cartography.runtime.live_artifact_paths import ensure_live_artifact_dirs
from tech_cartography.runtime.watch_profile_management_config import ENABLE_WATCH_PROFILE_MANAGEMENT_ENV
from tech_cartography.services.live_digest_preview import build_save_payload
from tech_cartography.services.live_watch_profile_manager import (
  create_watch_profile_draft,
  get_latest_watch_profile_draft,
  promote_draft_to_active,
)
from tech_cartography.runtime.watch_profile_management_config import get_activation_confirmation_text
from tech_cartography.services.live_web_signal_collector import collect_live_web_signals
from tech_cartography.runtime.external_api_operation_config import get_web_signal_collection_confirmation_text

ADMIN_CTX = {"user_id": "admin@example.com", "role": "admin", "is_admin": True}


def test_digest_preview_payload_includes_collection_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(ENABLE_MANUAL_WEB_SIGNAL_COLLECTION_ENV, "true")
  monkeypatch.setenv(DISABLE_EXTERNAL_API_ENV, "false")
  monkeypatch.setenv("TAVILY_API_KEY", "test-key-value")
  monkeypatch.setenv(ENABLE_WATCH_PROFILE_MANAGEMENT_ENV, "true")
  ensure_live_artifact_dirs(tmp_path)
  create_watch_profile_draft(
    profile_input={"theme_name": "Theme", "search_queries": ["query one"]},
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

  def _mock_tavily(**kwargs):
    return {"results": [{"title": "T", "url": "https://example.com/a", "content": "s"}]}

  collect_live_web_signals(
    output_root=tmp_path,
    confirm_text=get_web_signal_collection_confirmation_text(),
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context=ADMIN_CTX,
    post_fn=_mock_tavily,
  )
  payload = build_save_payload({"theme_name": "Theme"}, output_root=tmp_path)
  assert payload.get("latest_web_signal_collection_path")


def test_digest_preview_source_does_not_auto_collect() -> None:
  text = Path(__file__).resolve().parents[1].joinpath(
    "src/tech_cartography/services/live_digest_preview.py",
  ).read_text(encoding="utf-8")
  assert "collect_live_web_signals" not in text
