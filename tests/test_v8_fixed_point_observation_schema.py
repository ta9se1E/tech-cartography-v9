"""Tests for v8 Fixed Point Observation schema (Phase 27H)."""

from __future__ import annotations

import json

from tech_cartography.runtime.v8_fixed_point_observation_schema import (
  OBSERVATION_LOOP_SAFETY_NOTICES,
  V8EmailDigestPlan,
  V8ObservationLoopExport,
  V8ObservationLoopReport,
  V8SchedulerFollowupPlan,
  V8WatchProfileUpdateProposal,
)


def test_observation_loop_report_json_serializable() -> None:
  report = V8ObservationLoopReport(
    report_id="case_01:obs:abc",
    case_id="case_01_pan_graphitization",
    publication_number="all",
    generated_at="2026-01-01T00:00:00Z",
    no_email_send=True,
    no_scheduler_start=True,
    no_legal_judgement=True,
  )
  payload = json.dumps(report.to_dict())
  data = json.loads(payload)
  assert data["no_email_send"] is True
  assert data["no_scheduler_start"] is True


def test_watch_proposal_from_dict() -> None:
  prop = V8WatchProfileUpdateProposal(
    proposal_id="p1",
    case_id="case_01_pan_graphitization",
    proposal_type="add_claim_loading_task",
    proposed_items=["claim 本文取得"],
    review_status="pending_human_review",
  )
  restored = V8WatchProfileUpdateProposal.from_dict(prop.to_dict())
  assert restored.proposal_type == "add_claim_loading_task"


def test_scheduler_plan_defaults() -> None:
  plan = V8SchedulerFollowupPlan(
    scheduler_plan_id="s1",
    case_id="case_01_pan_graphitization",
  )
  assert plan.schedule_mode == "dry_run_only"
  assert plan.no_scheduler_start is True
  assert plan.scheduler_enabled is False


def test_email_digest_plan_defaults() -> None:
  plan = V8EmailDigestPlan(
    digest_plan_id="d1",
    case_id="case_01_pan_graphitization",
  )
  assert plan.digest_mode == "preview_only"
  assert plan.no_email_send is True
  assert plan.email_send_enabled is False


def test_safety_notices() -> None:
  blob = " ".join(OBSERVATION_LOOP_SAFETY_NOTICES)
  assert "FTO" in blob
  assert "送信" in blob or "email" in blob.lower()


def test_export_dataclass() -> None:
  export = V8ObservationLoopExport(
    export_id="e1",
    case_id="case_01_pan_graphitization",
    publication_number="all",
    output_dir="/tmp/out",
    json_path="/tmp/out/fp.json",
    md_path="/tmp/out/fp.md",
    xlsx_path="/tmp/out/fp.xlsx",
    manifest_path="/tmp/out/manifest.json",
    watch_profile_proposal_path="/tmp/out/watch.md",
    scheduler_plan_path="/tmp/out/sched.md",
    email_digest_plan_path="/tmp/out/email.md",
    created_at="2026-01-01T00:00:00Z",
  )
  assert export.scheduler_plan_path.endswith("sched.md")
