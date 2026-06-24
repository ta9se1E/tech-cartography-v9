"""Live evidence gap builder tests (Phase 25V)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tech_cartography.runtime.live_artifact_paths import ensure_live_artifact_dirs, get_live_watch_profiles_active_dir
from tech_cartography.services.live_evidence_gap_builder import (
  build_evidence_gap_payload,
  run_live_evidence_gap_build,
  save_evidence_gap_artifact,
)
from tech_cartography.services.live_run_history import list_run_history_entries


def _write_active_profile(tmp_path: Path, profile: dict) -> None:
  ensure_live_artifact_dirs(tmp_path)
  active_dir = get_live_watch_profiles_active_dir(tmp_path)
  path = active_dir / "watch_profile_active_test.json"
  path.write_text(json.dumps(profile), encoding="utf-8")


@pytest.fixture
def active_profile() -> dict:
  return {
    "profile_id": "wp-test",
    "theme_name": "Carbon Fiber Intelligence",
    "search_keywords": ["carbon fiber"],
    "search_queries": ["PAN precursor carbon fiber"],
    "status": "active",
  }


def test_build_without_web_signal_artifact(tmp_path: Path, active_profile: dict) -> None:
  _write_active_profile(tmp_path, active_profile)
  payload = build_evidence_gap_payload(tmp_path)
  assert payload["evidence_gaps"]
  assert payload["next_verification_actions"]
  assert payload["what_not_to_conclude"]
  assert payload["safety_flags"]["candidate_information_only"] is True


def test_skipped_without_active_profile(tmp_path: Path) -> None:
  ensure_live_artifact_dirs(tmp_path)
  payload = build_evidence_gap_payload(tmp_path)
  assert payload["status"] == "skipped"
  assert payload["warnings"]


def test_save_json_and_md(tmp_path: Path, active_profile: dict) -> None:
  _write_active_profile(tmp_path, active_profile)
  payload = build_evidence_gap_payload(tmp_path)
  payload["run_id"] = "run-test"
  payload["timestamp"] = "2026-06-24T12:00:00+00:00"
  saved = save_evidence_gap_artifact(payload, tmp_path)
  assert Path(saved["json"]).exists()
  assert Path(saved["markdown"]).exists()
  text = Path(saved["json"]).read_text(encoding="utf-8")
  assert "TAVILY_API_KEY" not in text


def test_run_records_history(tmp_path: Path, active_profile: dict) -> None:
  _write_active_profile(tmp_path, active_profile)
  result = run_live_evidence_gap_build(
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context={"user_id": "admin", "role": "admin", "auth_provider": "streamlit_basic", "is_admin": True},
  )
  assert result["ok"] is True
  entries = list_run_history_entries(
    tmp_path,
    action_type="live_evidence_gap_build",
    viewer_user_context={"user_id": "admin", "role": "admin", "is_admin": True},
  )
  assert entries
  assert entries[0]["status"] == "success"


def test_no_external_api(tmp_path: Path, active_profile: dict) -> None:
  _write_active_profile(tmp_path, active_profile)
  with patch("tech_cartography.services.live_web_signal_collector.collect_live_web_signals") as mock:
    build_evidence_gap_payload(tmp_path)
  mock.assert_not_called()
