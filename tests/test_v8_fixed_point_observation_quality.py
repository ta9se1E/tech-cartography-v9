"""Quality tests for v8 Fixed Point Observation (Phase 27H)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.runtime.v8_fixed_point_observation_schema import OBSERVATION_LOOP_SAFETY_NOTICES
from tech_cartography.services.v8_fixed_point_observation import build_observation_loop_report
from tech_cartography.services.v8_fixed_point_observation_export import (
  export_observation_loop,
  observation_loop_to_markdown,
)
from tech_cartography.services.v8_sources_repository import project_root_from_here

CASE_IDS = (
  "case_01_pan_graphitization",
  "case_02_sizing_interface",
  "case_03_pressure_vessel_filament_winding",
)


def test_three_cases_observation_loop() -> None:
  root = project_root_from_here()
  for case_id in CASE_IDS:
    report = build_observation_loop_report(case_id=case_id, project_root=root)
    assert report.human_review_required is True
    assert report.candidate_information_only is True
    assert report.no_legal_judgement is True
    assert len(report.top_3_next_cycle_tasks) <= 3


def test_markdown_safety_notices() -> None:
  root = project_root_from_here()
  report = build_observation_loop_report(case_id="case_01_pan_graphitization", project_root=root)
  md = observation_loop_to_markdown(report)
  assert "FTO" in md or "侵害" in md
  assert "送信" in md or "no_email_send" in md


def test_no_secrets_in_export(tmp_path: Path) -> None:
  root = project_root_from_here()
  report = build_observation_loop_report(case_id="case_03_pressure_vessel_filament_winding", project_root=root)
  result = export_observation_loop(report, project_root=tmp_path)
  json_text = Path(result.json_path).read_text(encoding="utf-8")
  assert "eyJhbGci" not in json_text
  assert "smtp_password" not in json_text.lower()


def test_mail_scheduler_not_removed() -> None:
  fp_ui = Path("src/tech_cartography/ui/v8_fixed_point_observation_ui.py").read_text(encoding="utf-8")
  admin_ui = Path("src/tech_cartography/ui/v8_admin_settings_ui.py").read_text(encoding="utf-8")
  assert "メール送信" in fp_ui
  assert "Scheduler" in fp_ui
  assert "メール送信" in admin_ui or "Email" in admin_ui


def test_watch_profile_not_auto_updated() -> None:
  blob = " ".join(OBSERVATION_LOOP_SAFETY_NOTICES)
  assert "自動反映" in blob or "人手" in blob
