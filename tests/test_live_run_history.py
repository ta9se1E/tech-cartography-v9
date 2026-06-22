"""Tests for live run history service (Phase 25M)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tech_cartography.runtime.live_artifact_paths import LIVE_OUTPUTS_ROOT_ENV, get_live_run_history_dir
from tech_cartography.services.live_run_history import (
  attach_user_run_metadata,
  generate_run_id,
  list_run_history_entries,
  record_live_run,
  sanitize_input_summary,
)


@pytest.fixture(autouse=True)
def _clear_secrets(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv("TECH_CARTOGRAPHY_LOGIN_PASSWORD", raising=False)
  monkeypatch.delenv("SMTP_PASSWORD", raising=False)
  monkeypatch.delenv("TAVILY_API_KEY", raising=False)


def test_generate_run_id() -> None:
  run_id = generate_run_id()
  assert run_id.startswith("run-")


def test_record_success_under_live_outputs_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  live_root = tmp_path / "live_outputs"
  monkeypatch.setenv(LIVE_OUTPUTS_ROOT_ENV, str(live_root))
  user = {"user_id": "admin", "display_name": "admin", "role": "admin", "auth_provider": "streamlit_basic", "is_admin": True}
  entry, saved, error = record_live_run(
    action_type="live_web_signal_pack",
    status="success",
    run_id=generate_run_id(),
    user_context=user,
    theme_name="Theme",
    input_summary="query=test",
    output_artifact_paths={"json": str(live_root / "pack.json")},
    project_root=tmp_path,
  )
  assert error is None
  assert saved is not None
  assert Path(saved["json"]).exists()
  assert entry is not None
  assert entry["user_id"] == "admin"


def test_record_blocked_status(tmp_path: Path) -> None:
  user = {"user_id": "admin", "display_name": "admin", "role": "admin", "auth_provider": "streamlit_basic", "is_admin": True}
  entry, _, error = record_live_run(
    action_type="live_web_signal_pack",
    status="blocked",
    run_id=generate_run_id(),
    user_context=user,
    error_summary="disabled_by_env",
    project_root=tmp_path,
  )
  assert error is None
  assert entry is not None
  assert entry["status"] == "blocked"


def test_no_secrets_in_saved_history(
  tmp_path: Path,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  monkeypatch.setenv("TECH_CARTOGRAPHY_LOGIN_PASSWORD", "super-secret-login")
  monkeypatch.setenv("SMTP_PASSWORD", "super-secret-smtp")
  monkeypatch.setenv("TAVILY_API_KEY", "tvly-secret")
  user = {"user_id": "admin", "display_name": "admin", "role": "admin", "auth_provider": "streamlit_basic", "is_admin": True}
  _, saved, error = record_live_run(
    action_type="live_digest_preview",
    status="success",
    run_id=generate_run_id(),
    user_context=user,
    input_summary="preview only",
    project_root=tmp_path,
  )
  assert error is None
  blob = Path(saved["json"]).read_text(encoding="utf-8")
  assert "super-secret-login" not in blob
  assert "super-secret-smtp" not in blob
  assert "tvly-secret" not in blob
  assert "TECH_CARTOGRAPHY_LOGIN_PASSWORD" not in blob


def test_admin_sees_all_member_sees_own_only(tmp_path: Path) -> None:
  admin = {"user_id": "admin", "display_name": "admin", "role": "admin", "auth_provider": "streamlit_basic", "is_admin": True}
  member = {"user_id": "member01", "display_name": "m1", "role": "member", "auth_provider": "streamlit_basic", "is_admin": False}
  record_live_run(action_type="live_web_signal_pack", status="success", run_id=generate_run_id(), user_context=admin, project_root=tmp_path)
  record_live_run(action_type="live_digest_preview", status="success", run_id=generate_run_id(), user_context=member, project_root=tmp_path)
  admin_entries = list_run_history_entries(tmp_path, limit=20, viewer_user_context=admin)
  member_entries = list_run_history_entries(tmp_path, limit=20, viewer_user_context=member)
  assert len(admin_entries) >= 2
  assert len(member_entries) == 1
  assert member_entries[0]["user_id"] == "member01"


def test_attach_user_run_metadata() -> None:
  payload = attach_user_run_metadata(
    {"theme_name": "T"},
    user_context={"user_id": "admin", "display_name": "admin", "role": "admin", "auth_provider": "streamlit_basic"},
    run_id="run-abc",
  )
  assert payload["run_id"] == "run-abc"
  assert payload["created_by_user_id"] == "admin"


def test_sanitize_redacts_env_value(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv("TAVILY_API_KEY", "leaked-key-value")
  summary = sanitize_input_summary("query with leaked-key-value inside")
  assert summary is not None
  assert "leaked-key-value" not in summary
