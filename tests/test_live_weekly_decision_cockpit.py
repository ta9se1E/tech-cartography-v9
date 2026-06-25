"""Weekly Decision Cockpit service tests (Phase 25W)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from tech_cartography.runtime.live_artifact_paths import ensure_live_artifact_dirs, get_live_watch_profiles_active_dir
from tech_cartography.services.live_evidence_gap_builder import (
  build_evidence_gap_payload,
  save_evidence_gap_artifact,
)
from tech_cartography.services.live_weekly_decision_cockpit import (
  build_weekly_decision_cockpit_payload,
  run_live_weekly_decision_cockpit_build,
  save_weekly_decision_cockpit,
)


def _active_profile(tmp_path: Path) -> None:
  ensure_live_artifact_dirs(tmp_path)
  path = get_live_watch_profiles_active_dir(tmp_path) / "watch_profile_active_test.json"
  path.write_text(
    json.dumps({"theme_name": "Carbon Fiber Intelligence", "search_queries": ["PAN"]}),
    encoding="utf-8",
  )


def test_payload_without_artifacts(tmp_path: Path) -> None:
  ensure_live_artifact_dirs(tmp_path)
  payload = build_weekly_decision_cockpit_payload(tmp_path)
  assert payload["theme_name"]
  assert payload["readiness_level"] == "no_active_profile"
  assert payload["safety_flags"]["candidate_information_only"] is True


def test_payload_with_profile_and_gap(tmp_path: Path) -> None:
  _active_profile(tmp_path)
  gap_payload = build_evidence_gap_payload(tmp_path)
  gap_payload["run_id"] = "run-gap"
  gap_payload["timestamp"] = "2026-06-24T12:00:00+00:00"
  save_evidence_gap_artifact(gap_payload, tmp_path)
  payload = build_weekly_decision_cockpit_payload(tmp_path)
  assert payload["theme_name"] == "Carbon Fiber Intelligence"
  assert payload["top_evidence_gaps"]
  assert payload["readiness_level"] in {"evidence_gap_ready", "data_collected", "no_active_profile"}


def test_save_json_md(tmp_path: Path) -> None:
  _active_profile(tmp_path)
  payload = build_weekly_decision_cockpit_payload(tmp_path)
  payload["run_id"] = "run-cockpit"
  saved = save_weekly_decision_cockpit(payload, tmp_path)
  assert Path(saved["json"]).exists()
  assert Path(saved["markdown"]).exists()
  assert "TAVILY_API_KEY" not in Path(saved["json"]).read_text(encoding="utf-8")


def test_no_external_api(tmp_path: Path) -> None:
  _active_profile(tmp_path)
  with patch("tech_cartography.services.live_web_signal_collector.collect_live_web_signals") as mock:
    build_weekly_decision_cockpit_payload(tmp_path)
  mock.assert_not_called()


def test_run_build_admin(tmp_path: Path) -> None:
  _active_profile(tmp_path)
  result = run_live_weekly_decision_cockpit_build(
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
    user_context={"user_id": "admin", "role": "admin", "is_admin": True, "auth_provider": "google_iap"},
  )
  assert result["ok"] is True
