"""v8 Fixed Point Observation export (Phase 27H)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tech_cartography.runtime.live_artifact_paths import get_live_outputs_root
from tech_cartography.runtime.v8_fixed_point_observation_schema import (
  OBSERVATION_LOOP_NEXT_PHASES,
  OBSERVATION_LOOP_SAFETY_NOTICES,
  V8ObservationLoopReport,
  V8ObservationLoopExport,
)

V8_FIXED_POINT_OBSERVATION_SUBDIR = "v8_fixed_point_observation"
LOCAL_V8_FIXED_POINT_OBSERVATION_SUBDIR = "local_v8_fixed_point_observation"

_SENSITIVE_RE = re.compile(
  r"(smtp_password|tavily_api_key|api[_-]?key\s*[:=]|authorization|oauth|jwt|eyJhbGci)",
  re.IGNORECASE,
)


def get_v8_fixed_point_observation_dir(project_root: Path | str | None = None) -> Path:
  root = get_live_outputs_root(project_root)
  if root.name == "outputs" or not str(root).endswith("live"):
    return root / LOCAL_V8_FIXED_POINT_OBSERVATION_SUBDIR
  return root / V8_FIXED_POINT_OBSERVATION_SUBDIR


def find_latest_fixed_point_observation_dir(
  case_id: str | None = None,
  project_root: Path | str | None = None,
) -> Path | None:
  base = get_v8_fixed_point_observation_dir(project_root)
  if not base.is_dir():
    return None
  if case_id:
    dirs = sorted(
      (p for p in base.iterdir() if p.is_dir() and p.name.startswith(f"{case_id}_")),
      key=lambda p: p.stat().st_mtime,
      reverse=True,
    )
    return dirs[0] if dirs else None
  dirs = sorted((p for p in base.iterdir() if p.is_dir()), key=lambda p: p.stat().st_mtime, reverse=True)
  return dirs[0] if dirs else None


def _assert_no_secrets(text: str) -> None:
  if _SENSITIVE_RE.search(text):
    raise ValueError("export content must not contain secret-like strings")


def _watch_proposals_markdown(report: V8ObservationLoopReport) -> str:
  lines = [f"# Watch Profile Update Proposal — {report.case_id}", ""]
  for prop in report.watch_profile_update_proposals:
    lines.append(f"## {prop.proposal_type}")
    lines.append(f"- reason: {prop.reason}")
    lines.append(f"- priority: {prop.priority_label}")
    lines.append(f"- review_status: {prop.review_status}")
    for item in prop.proposed_items:
      lines.append(f"  - {item}")
    lines.append("")
  lines.append("※ 人手承認後に Watch Profile へ反映。本 Phase では自動更新しません。")
  return "\n".join(lines)


def _scheduler_plan_markdown(report: V8ObservationLoopReport) -> str:
  plan = report.scheduler_followup_plan
  if not plan:
    return "# Scheduler Follow-up Plan\n\n(none)"
  lines = [
    f"# Scheduler Follow-up Plan — {report.case_id}",
    "",
    f"- schedule_mode: {plan.schedule_mode}",
    f"- scheduler_enabled: {plan.scheduler_enabled}",
    f"- no_scheduler_start: {plan.no_scheduler_start}",
    f"- planned_cycle_label: {plan.planned_cycle_label}",
    "",
    "## Planned steps",
  ]
  for step in plan.planned_steps:
    lines.append(f"- {step}")
  if plan.blocked_steps:
    lines.extend(["", "## Blocked steps"])
    for step in plan.blocked_steps:
      lines.append(f"- {step}")
  if plan.required_human_inputs:
    lines.extend(["", "## Required human inputs"])
    for inp in plan.required_human_inputs:
      lines.append(f"- {inp}")
  lines.extend(["", f"hint: {plan.scheduler_followup_hint}"])
  return "\n".join(lines)


def _email_digest_plan_markdown(report: V8ObservationLoopReport) -> str:
  plan = report.email_digest_plan
  if not plan:
    return "# Email Digest Plan\n\n(none)"
  lines = [
    f"# Email Digest Plan — {report.case_id}",
    "",
    f"- digest_mode: {plan.digest_mode}",
    f"- email_send_enabled: {plan.email_send_enabled}",
    f"- no_email_send: {plan.no_email_send}",
    f"- subject_draft: {plan.subject_draft}",
    "",
    "## Digest summary",
    plan.digest_summary,
    "",
    f"hint: {plan.email_digest_hint}",
  ]
  return "\n".join(lines)


def observation_loop_to_markdown(report: V8ObservationLoopReport) -> str:
  lines = [
    f"# Fixed Point Observation Loop — {report.case_id}",
    "",
    f"- publication_number: {report.publication_number}",
    f"- generated_at: {report.generated_at}",
    f"- loop_status: {report.loop_status}",
    f"- no_email_send: {report.no_email_send}",
    f"- no_scheduler_start: {report.no_scheduler_start}",
    "",
    "## Safety",
  ]
  for notice in OBSERVATION_LOOP_SAFETY_NOTICES:
    lines.append(f"- {notice}")
  lines.extend([
    "",
    "## Current state",
    report.current_state_summary,
    "",
    "## What changed or needs change",
    report.what_changed_or_needs_change,
    "",
    "## Top 3 Next Cycle Tasks",
  ])
  for task in report.top_3_next_cycle_tasks:
    lines.append(f"- {task}")
  lines.extend([
    "",
    "## Watch Profile Update Proposal",
    _watch_proposals_markdown(report),
    "",
    "## Scheduler Follow-up Plan",
    _scheduler_plan_markdown(report),
    "",
    "## Email Digest Plan",
    _email_digest_plan_markdown(report),
    "",
    "## Artifact Trace",
  ])
  for trace in report.artifact_trace:
    lines.append(f"- {trace}")
  for path in report.source_artifact_paths:
    lines.append(f"- source: {path}")
  lines.extend(["", "## Next phases", *[f"- {p}" for p in OBSERVATION_LOOP_NEXT_PHASES]])
  if report.warnings:
    lines.extend(["", "## Warnings", *[f"- {w}" for w in report.warnings]])
  text = "\n".join(lines)
  _assert_no_secrets(text)
  return text


def write_excel_observation_loop(report: V8ObservationLoopReport, path: Path) -> str:
  try:
    import pandas as pd

    path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(path, engine="openpyxl") as writer:
      pd.DataFrame([{
        "report_id": report.report_id,
        "case_id": report.case_id,
        "loop_status": report.loop_status,
        "current_state_summary": report.current_state_summary,
        "no_email_send": report.no_email_send,
        "no_scheduler_start": report.no_scheduler_start,
      }]).to_excel(writer, sheet_name="Observation Loop", index=False)

      prop_rows = [p.to_dict() for p in report.watch_profile_update_proposals]
      for row in prop_rows:
        for col in ("proposed_items", "source_gap_ids", "source_action_ids", "affected_claim_axes", "caution_flags"):
          row[col] = "; ".join(row.get(col) or [])
      pd.DataFrame(prop_rows or [{"proposal_type": "(none)"}]).to_excel(
        writer, sheet_name="Watch Profile Proposal", index=False,
      )

      if report.scheduler_followup_plan:
        sched = report.scheduler_followup_plan.to_dict()
        for col in ("planned_steps", "blocked_steps", "required_human_inputs", "caution_flags"):
          sched[col] = "; ".join(sched.get(col) or [])
        pd.DataFrame([sched]).to_excel(writer, sheet_name="Scheduler Plan", index=False)
      else:
        pd.DataFrame([{"schedule_mode": "(none)"}]).to_excel(writer, sheet_name="Scheduler Plan", index=False)

      if report.email_digest_plan:
        pd.DataFrame([report.email_digest_plan.to_dict()]).to_excel(
          writer, sheet_name="Email Digest Plan", index=False,
        )
      else:
        pd.DataFrame([{"digest_mode": "(none)"}]).to_excel(writer, sheet_name="Email Digest Plan", index=False)

      pd.DataFrame({"trace": report.artifact_trace or ["(none)"]}).to_excel(
        writer, sheet_name="Artifact Trace", index=False,
      )
      pd.DataFrame({"warning": report.warnings or ["(none)"]}).to_excel(
        writer, sheet_name="Warnings", index=False,
      )
    return ""
  except Exception as exc:
    return f"Excel export skipped: {exc}"


def export_observation_loop(
  report: V8ObservationLoopReport,
  *,
  project_root: Path | str | None = None,
) -> V8ObservationLoopExport:
  root = Path(project_root) if project_root else Path.cwd()
  slug = report.generated_at.replace(":", "").replace("-", "").replace("+00:00", "Z")
  pub_slug = report.publication_number.replace("/", "_") or "all"
  output_dir = get_v8_fixed_point_observation_dir(root) / f"{report.case_id}_{pub_slug}_{slug}"
  output_dir.mkdir(parents=True, exist_ok=True)

  json_path = output_dir / "fixed_point_observation.json"
  md_path = output_dir / "fixed_point_observation.md"
  xlsx_path = output_dir / "fixed_point_observation.xlsx"
  manifest_path = output_dir / "fixed_point_observation_manifest.json"
  watch_path = output_dir / "watch_profile_update_proposal.md"
  scheduler_path = output_dir / "scheduler_followup_plan.md"
  email_path = output_dir / "email_digest_plan.md"

  watch_md = _watch_proposals_markdown(report)
  scheduler_md = _scheduler_plan_markdown(report)
  email_md = _email_digest_plan_markdown(report)

  json_path.write_text(json.dumps(report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
  md_path.write_text(observation_loop_to_markdown(report), encoding="utf-8")
  watch_path.write_text(watch_md, encoding="utf-8")
  scheduler_path.write_text(scheduler_md, encoding="utf-8")
  email_path.write_text(email_md, encoding="utf-8")
  excel_warning = write_excel_observation_loop(report, xlsx_path)

  manifest: dict[str, Any] = {
    "export_id": report.report_id,
    "case_id": report.case_id,
    "publication_number": report.publication_number,
    "generated_at": report.generated_at,
    "loop_status": report.loop_status,
    "no_email_send": report.no_email_send,
    "no_scheduler_start": report.no_scheduler_start,
    "watch_profile_proposal_count": len(report.watch_profile_update_proposals),
    "source_artifact_paths": report.source_artifact_paths,
    "safety_notices": list(OBSERVATION_LOOP_SAFETY_NOTICES),
    "next_phase_connections": list(OBSERVATION_LOOP_NEXT_PHASES),
    "files": {
      "fixed_point_observation_json": str(json_path),
      "fixed_point_observation_md": str(md_path),
      "fixed_point_observation_xlsx": str(xlsx_path),
      "watch_profile_update_proposal_md": str(watch_path),
      "scheduler_followup_plan_md": str(scheduler_path),
      "email_digest_plan_md": str(email_path),
    },
    "excel_warning": excel_warning,
  }
  manifest_text = json.dumps(manifest, ensure_ascii=False, indent=2)
  _assert_no_secrets(manifest_text)
  manifest_path.write_text(manifest_text, encoding="utf-8")

  report.export_paths = [
    str(json_path), str(md_path), str(manifest_path),
    str(watch_path), str(scheduler_path), str(email_path),
  ]

  return V8ObservationLoopExport(
    export_id=report.report_id,
    case_id=report.case_id,
    publication_number=report.publication_number,
    output_dir=str(output_dir),
    json_path=str(json_path),
    md_path=str(md_path),
    xlsx_path=str(xlsx_path),
    manifest_path=str(manifest_path),
    watch_profile_proposal_path=str(watch_path),
    scheduler_plan_path=str(scheduler_path),
    email_digest_plan_path=str(email_path),
    created_at=report.generated_at,
    excel_warning=excel_warning,
  )
