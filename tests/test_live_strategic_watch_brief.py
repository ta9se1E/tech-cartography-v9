"""Strategic Watch Brief tests (Phase 25V)."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.runtime.live_artifact_paths import ensure_live_artifact_dirs, get_live_watch_profiles_active_dir
from tech_cartography.services.live_strategic_watch_brief import (
  build_strategic_watch_brief_payload,
  run_live_strategic_watch_brief_build,
  save_strategic_watch_brief,
)
from tech_cartography.services.live_run_history import list_run_history_entries


def _write_active_profile(tmp_path: Path) -> None:
  ensure_live_artifact_dirs(tmp_path)
  path = get_live_watch_profiles_active_dir(tmp_path) / "watch_profile_active_test.json"
  path.write_text(
    json.dumps({"theme_name": "Carbon Fiber Intelligence", "search_queries": ["PAN"]}),
    encoding="utf-8",
  )


def test_build_strategic_brief(tmp_path: Path) -> None:
  _write_active_profile(tmp_path)
  payload = build_strategic_watch_brief_payload(tmp_path)
  assert payload["weekly_conclusion_candidates"]
  assert payload["what_not_to_conclude"]
  assert len(payload.get("recommended_next_human_actions") or []) <= 3
  assert payload["safety_flags"]["legal_judgement"] is False


def test_save_brief_artifacts(tmp_path: Path) -> None:
  _write_active_profile(tmp_path)
  payload = build_strategic_watch_brief_payload(tmp_path)
  payload["run_id"] = "run-brief"
  payload["timestamp"] = "2026-06-24T12:00:00+00:00"
  saved = save_strategic_watch_brief(payload, tmp_path)
  assert Path(saved["json"]).exists()
  assert Path(saved["markdown"]).exists()
  assert "候補" in Path(saved["markdown"]).read_text(encoding="utf-8")


def test_run_records_brief_history(tmp_path: Path) -> None:
  _write_active_profile(tmp_path)
  result = run_live_strategic_watch_brief_build(
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context={"user_id": "admin", "role": "admin", "auth_provider": "streamlit_basic", "is_admin": True},
  )
  assert result["ok"] is True
  entries = list_run_history_entries(
    tmp_path,
    action_type="live_strategic_watch_brief_build",
    viewer_user_context={"user_id": "admin", "role": "admin", "is_admin": True},
  )
  assert entries
