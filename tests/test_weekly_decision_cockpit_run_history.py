"""Run History integration for Weekly Decision Cockpit (Phase 25W)."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.runtime.live_artifact_paths import ensure_live_artifact_dirs, get_live_watch_profiles_active_dir
from tech_cartography.services.live_run_history import list_run_history_entries
from tech_cartography.services.live_weekly_decision_cockpit import run_live_weekly_decision_cockpit_build


def test_run_history_records_cockpit_build(tmp_path: Path) -> None:
  ensure_live_artifact_dirs(tmp_path)
  path = get_live_watch_profiles_active_dir(tmp_path) / "watch_profile_active_test.json"
  path.write_text(json.dumps({"theme_name": "Theme"}), encoding="utf-8")
  run_live_weekly_decision_cockpit_build(
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context={"user_id": "admin@example.com", "role": "admin", "is_admin": True, "auth_provider": "google_iap"},
  )
  entries = list_run_history_entries(
    tmp_path,
    action_type="live_weekly_decision_cockpit_build",
    viewer_user_context={"user_id": "admin@example.com", "role": "admin", "is_admin": True},
  )
  assert entries
  latest = entries[0]
  assert latest["status"] == "success"
  assert latest.get("output_artifact_paths", {}).get("json")
  meta = latest.get("operation_metadata") or {}
  assert meta.get("candidate_information_only") is True
  assert meta.get("legal_judgement") is False
