"""Scheduler dry-run planning — no execution (Phase 25S)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tech_cartography.runtime.cloud_run_config import is_scheduler_disabled
from tech_cartography.runtime.live_artifact_paths import (
  check_directory_writable,
  get_live_scheduler_dry_run_dir,
)
from tech_cartography.runtime.user_context import evaluate_live_admin_access
from tech_cartography.services.live_run_history import (
  attach_user_run_metadata,
  generate_run_id,
  map_result_status,
  record_live_run,
)
from tech_cartography.services.live_web_signal_collector import find_latest_web_signal_collection_path
from tech_cartography.services.live_watch_profile_manager import (
  describe_watch_profile_status,
  get_active_watch_profile,
)

ACTION_TYPE = "live_scheduler_dry_run"

_SENSITIVE_PATTERN = re.compile(r"(smtp_password|api[_-]?key|authorization|oauth|jwt|secret)", re.IGNORECASE)


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _timestamp_slug(iso_ts: str) -> str:
  return iso_ts.replace(":", "").replace("-", "")


def _planned_steps(*, has_active_profile: bool, has_web_signal_collection: bool) -> list[str]:
  steps = [
    "verify_runtime_flags",
    "verify_active_watch_profile",
    "review_latest_web_signal_collection",
    "review_digest_preview_artifact",
    "review_next_cycle_search_plan",
    "human_approval_checkpoint",
  ]
  if not has_active_profile:
    steps.insert(1, "warning_no_active_watch_profile")
  if not has_web_signal_collection:
    steps.insert(2, "warning_no_web_signal_collection_artifact")
  return steps


def run_live_scheduler_dry_run(
  *,
  output_root: Path | str,
  login_required: bool,
  is_authenticated: bool,
  auth_role: str,
  user_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
  run_id = generate_run_id()
  started_at = _utc_now_iso()
  access_ok, access_error, _ = evaluate_live_admin_access(
    login_required=login_required,
    is_authenticated=is_authenticated,
    auth_role=auth_role,
    user_context=user_context,
  )
  if not access_ok:
    return {"ok": False, "error": access_error, "message": "管理者のみ dry-run を実行できます。"}

  active, active_path = get_active_watch_profile(output_root)
  collection_path = find_latest_web_signal_collection_path(output_root)
  profile_status = describe_watch_profile_status(output_root)
  warnings: list[str] = []
  if not active:
    warnings.append("active Watch Profile がありません。dry-run は計画のみで実行しません。")
  if not collection_path:
    warnings.append("最新 Web Signal collection artifact がありません。")
  if not is_scheduler_disabled():
    warnings.append("DISABLE_SCHEDULER=false です。本番 scheduler は起動しませんが env を確認してください。")

  payload = {
    "run_id": run_id,
    "action_type": ACTION_TYPE,
    "created_at": started_at,
    "scheduler_disabled": is_scheduler_disabled(),
    "active_watch_profile_path": active_path,
    "active_watch_profile_theme": (active or {}).get("theme_name"),
    "latest_web_signal_collection_path": str(collection_path) if collection_path else None,
    "planned_steps": _planned_steps(
      has_active_profile=bool(active),
      has_web_signal_collection=bool(collection_path),
    ),
    "warnings": warnings,
    "watch_profile_status": profile_status.get("watch_profile_status"),
    "safety_flags": {
      "no_external_api": True,
      "no_email_send": True,
      "no_scheduler_start": True,
      "human_approval_required": True,
    },
    "note": "Dry-run only — no scheduler start, no external API, no email send.",
  }
  payload = attach_user_run_metadata(payload, user_context=user_context, run_id=run_id)

  out_dir = get_live_scheduler_dry_run_dir(output_root)
  writable, message = check_directory_writable(out_dir)
  if not writable:
    return {"ok": False, "error": "save_failed", "message": message or str(out_dir)}

  slug = _timestamp_slug(started_at)
  json_path = out_dir / f"live_scheduler_dry_run_{slug}_{run_id}.json"
  md_path = out_dir / f"live_scheduler_dry_run_{slug}_{run_id}.md"
  serialized = json.dumps(payload, indent=2, ensure_ascii=False)
  if _SENSITIVE_PATTERN.search(serialized):
    return {"ok": False, "error": "sensitive_material", "message": "保存を拒否しました。"}
  json_path.write_text(serialized + "\n", encoding="utf-8")
  md_lines = [
    "# Scheduler Dry-Run Plan",
    "",
    f"- active_watch_profile_path: {active_path}",
    f"- latest_web_signal_collection_path: {collection_path}",
    f"- watch_profile_status: {profile_status.get('watch_profile_status')}",
    "",
    "## planned_steps",
  ]
  md_lines.extend(f"- {step}" for step in payload["planned_steps"])
  md_path.write_text("\n".join(md_lines) + "\n", encoding="utf-8")
  saved_paths = {"json": str(json_path), "markdown": str(md_path)}

  record_live_run(
    action_type=ACTION_TYPE,
    status="success",
    run_id=run_id,
    started_at=started_at,
    user_context=user_context,
    theme_name=(active or {}).get("theme_name"),
    input_summary=f"active_watch_profile_path={active_path or '(none)'}",
    output_artifact_paths=saved_paths,
    source_artifact_paths=[active_path] if active_path else [],
    project_root=output_root,
  )
  return {
    "ok": True,
    "payload": payload,
    "saved_paths": saved_paths,
    "warnings": warnings,
    "run_id": run_id,
  }
