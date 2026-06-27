"""Tests for v8 Fixed Point Observation service (Phase 27H)."""

from __future__ import annotations

from tech_cartography.services.v8_fixed_point_observation import build_observation_loop_report
from tech_cartography.services.v8_sources_repository import project_root_from_here

CASE_IDS = (
  "case_01_pan_graphitization",
  "case_02_sizing_interface",
  "case_03_pressure_vessel_filament_winding",
)


def test_build_observation_loop_all_cases() -> None:
  root = project_root_from_here()
  for case_id in CASE_IDS:
    report = build_observation_loop_report(case_id=case_id, project_root=root)
    assert report.watch_profile_update_proposals
    assert report.scheduler_followup_plan
    assert report.email_digest_plan
    assert report.no_email_send is True
    assert report.no_scheduler_start is True
    assert len(report.top_3_next_cycle_tasks) >= 1


def test_scheduler_dry_run_only() -> None:
  root = project_root_from_here()
  report = build_observation_loop_report(case_id="case_01_pan_graphitization", project_root=root)
  sched = report.scheduler_followup_plan
  assert sched is not None
  assert sched.schedule_mode == "dry_run_only"
  assert sched.no_scheduler_start is True
  assert sched.scheduler_enabled is False


def test_email_digest_preview_only() -> None:
  root = project_root_from_here()
  report = build_observation_loop_report(case_id="case_01_pan_graphitization", project_root=root)
  email = report.email_digest_plan
  assert email is not None
  assert email.digest_mode == "preview_only"
  assert email.no_email_send is True
  assert email.email_send_enabled is False


def test_claim_text_required_planned_step_incomplete_case() -> None:
  root = project_root_from_here()
  report = build_observation_loop_report(case_id="case_02_sizing_interface", project_root=root)
  sched = report.scheduler_followup_plan
  assert sched is not None
  assert sched.planned_steps[0] == "load_claim_text"
  assert report.loop_status == "blocked_by_claim_text_required"


def test_case1_full_manual_not_blocked_by_claim_text() -> None:
  root = project_root_from_here()
  report = build_observation_loop_report(case_id="case_01_pan_graphitization", project_root=root)
  assert report.loop_status != "blocked_by_claim_text_required"
  sched = report.scheduler_followup_plan
  assert sched is not None
  assert sched.planned_steps[0] != "load_claim_text"


def test_top_actions_in_cycle_tasks() -> None:
  root = project_root_from_here()
  report = build_observation_loop_report(case_id="case_02_sizing_interface", project_root=root)
  assert any("load_claim_text" in task for task in report.top_3_next_cycle_tasks)
