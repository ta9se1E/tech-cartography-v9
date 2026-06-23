"""Live Watch Profile management service (Phase 25S)."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tech_cartography.runtime.live_artifact_paths import (
  check_directory_writable,
  get_live_watch_profiles_active_dir,
  get_live_watch_profiles_archive_dir,
  get_live_watch_profiles_drafts_dir,
)
from tech_cartography.runtime.watch_profile_management_config import (
  get_activation_confirmation_text,
  get_archive_confirmation_text,
  get_rollback_confirmation_text,
  is_watch_profile_management_enabled,
)
from tech_cartography.runtime.watch_profile_schema import (
  PROFILE_STATUS_ACTIVE,
  PROFILE_STATUS_ARCHIVED,
  PROFILE_STATUS_DRAFT,
  diff_watch_profiles,
  empty_watch_profile_template,
  normalize_watch_profile,
  summarize_watch_profile,
  validate_watch_profile_draft,
  validate_watch_profile_for_activation,
)
from tech_cartography.runtime.user_context import evaluate_live_admin_access, user_context_as_dict
from tech_cartography.services.live_run_history import (
  attach_user_run_metadata,
  generate_run_id,
  map_result_status,
  record_live_run,
)

ACTION_DRAFT_SAVE = "live_watch_profile_draft_save"
ACTION_ACTIVATE = "live_watch_profile_activate"
ACTION_ARCHIVE = "live_watch_profile_archive"
ACTION_ROLLBACK = "live_watch_profile_rollback"

SAFETY_NOTICE = (
  "Watch Profile stores human-approved monitoring scope only. "
  "No external API execution, email send, or scheduler start occurs here."
)

_SENSITIVE_PATTERN = re.compile(
  r"(smtp_password|api[_-]?key|authorization|oauth|jwt|secret)",
  re.IGNORECASE,
)


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _timestamp_slug(iso_ts: str) -> str:
  return iso_ts.replace(":", "").replace("-", "")


def _safety_flags(*, confirmation_matched: bool = False) -> dict[str, bool]:
  return {
    "no_external_api": True,
    "no_email_send": True,
    "no_scheduler_start": True,
    "human_approval_required": True,
    "confirmation_matched": confirmation_matched,
  }


def _assert_safe_serialized(serialized: str) -> None:
  if _SENSITIVE_PATTERN.search(serialized):
    raise ValueError("Refusing to save watch profile containing sensitive material")


def _latest_json(directory: Path, pattern: str) -> Path | None:
  if not directory.is_dir():
    return None
  files = sorted(directory.glob(pattern), key=lambda p: p.stat().st_mtime if p.exists() else 0, reverse=True)
  return files[0] if files else None


def _load_json(path: Path) -> dict[str, Any] | None:
  try:
    data = json.loads(path.read_text(encoding="utf-8"))
  except (OSError, json.JSONDecodeError):
    return None
  return data if isinstance(data, dict) else None


def _render_markdown(profile: dict[str, Any]) -> str:
  summary = summarize_watch_profile(profile)
  lines = ["# Watch Profile", ""]
  for key, value in summary.items():
    lines.append(f"- {key}: {value}")
  lines.extend(["", "## notes", "", str(profile.get("notes") or "(none)"), ""])
  return "\n".join(lines).strip() + "\n"


def _save_profile(
  profile: dict[str, Any],
  *,
  output_root: Path | str,
  status: str,
  run_id: str,
) -> dict[str, str]:
  if status == PROFILE_STATUS_DRAFT:
    out_dir = get_live_watch_profiles_drafts_dir(output_root)
    prefix = "watch_profile_draft"
  elif status == PROFILE_STATUS_ACTIVE:
    out_dir = get_live_watch_profiles_active_dir(output_root)
    prefix = "watch_profile_active"
  else:
    out_dir = get_live_watch_profiles_archive_dir(output_root)
    prefix = "watch_profile_archive"

  writable, message = check_directory_writable(out_dir)
  if not writable:
    raise ValueError(message or f"Cannot write watch profile to {out_dir}")

  slug = _timestamp_slug(str(profile.get("created_at") or _utc_now_iso()))
  json_path = out_dir / f"{prefix}_{slug}_{run_id}.json"
  md_path = out_dir / f"{prefix}_{slug}_{run_id}.md"
  serialized = json.dumps(profile, indent=2, ensure_ascii=False)
  _assert_safe_serialized(serialized)
  json_path.write_text(serialized + "\n", encoding="utf-8")
  md_path.write_text(_render_markdown(profile), encoding="utf-8")
  return {"json": str(json_path), "markdown": str(md_path)}


def load_watch_profile(path: Path | str) -> dict[str, Any] | None:
  return _load_json(Path(path))


def list_watch_profile_drafts(project_root: Path | str) -> list[dict[str, Any]]:
  drafts_dir = get_live_watch_profiles_drafts_dir(project_root)
  if not drafts_dir.is_dir():
    return []
  items: list[dict[str, Any]] = []
  for path in sorted(drafts_dir.glob("watch_profile_draft_*.json"), reverse=True):
    data = _load_json(path)
    if data:
      data["_artifact_path"] = str(path)
      items.append(data)
  return items


def get_latest_watch_profile_draft(project_root: Path | str) -> tuple[dict[str, Any] | None, str | None]:
  path = _latest_json(get_live_watch_profiles_drafts_dir(project_root), "watch_profile_draft_*.json")
  if path is None:
    return None, None
  data = _load_json(path)
  return data, str(path)


def get_active_watch_profile(project_root: Path | str) -> tuple[dict[str, Any] | None, str | None]:
  path = _latest_json(get_live_watch_profiles_active_dir(project_root), "watch_profile_active_*.json")
  if path is None:
    return None, None
  data = _load_json(path)
  return data, str(path)


def _record(
  *,
  action_type: str,
  ok: bool,
  error: str | None,
  run_id: str,
  started_at: str,
  user_context: dict[str, Any] | None,
  profile: dict[str, Any] | None,
  output_root: Path | str,
  saved_paths: dict[str, str] | None = None,
  source_paths: list[str] | None = None,
  confirmation_matched: bool = False,
) -> None:
  prof = profile or {}
  record_live_run(
    action_type=action_type,
    status=map_result_status(ok=ok, error=error),
    run_id=run_id,
    started_at=started_at,
    user_context=user_context,
    theme_name=str(prof.get("theme_name") or "") or None,
    input_summary=(
      f"profile_id={prof.get('profile_id')} status={prof.get('status')} "
      f"confirmation_matched={confirmation_matched}"
    ),
    output_artifact_paths=saved_paths or {},
    source_artifact_paths=source_paths or [],
    error_summary=None if ok else str(error or ""),
    operation_metadata={
      "profile_id": prof.get("profile_id"),
      "version": prof.get("version"),
      "status": prof.get("status"),
      "confirmation_matched": confirmation_matched,
      "no_external_api": True,
      "no_email_send": True,
      "no_scheduler_start": True,
      "human_approval_required": True,
    },
    project_root=output_root,
  )


def _admin_gate(
  *,
  login_required: bool,
  is_authenticated: bool,
  auth_role: str,
  user_context: dict[str, Any] | None,
  management_required: bool,
) -> tuple[bool, str | None]:
  if management_required and not is_watch_profile_management_enabled():
    return False, "management_disabled"
  access_ok, access_error, _ = evaluate_live_admin_access(
    login_required=login_required,
    is_authenticated=is_authenticated,
    auth_role=auth_role,
    user_context=user_context,
  )
  if not access_ok:
    return False, access_error or "admin_required"
  return True, None


def create_watch_profile_draft(
  *,
  profile_input: dict[str, Any],
  output_root: Path | str,
  login_required: bool,
  is_authenticated: bool,
  auth_role: str,
  user_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
  run_id = generate_run_id()
  started_at = _utc_now_iso()
  allowed, block = _admin_gate(
    login_required=login_required,
    is_authenticated=is_authenticated,
    auth_role=auth_role,
    user_context=user_context,
    management_required=True,
  )
  if not allowed:
    _record(
      action_type=ACTION_DRAFT_SAVE,
      ok=False,
      error=block,
      run_id=run_id,
      started_at=started_at,
      user_context=user_context,
      profile=None,
      output_root=output_root,
    )
    return {"ok": False, "error": block, "message": _block_message(block)}

  profile = normalize_watch_profile(profile_input)
  profile["status"] = PROFILE_STATUS_DRAFT
  profile["created_at"] = started_at
  ctx = user_context_as_dict(user_context or {})
  profile["created_by"] = ctx.get("user_id") or ""
  valid, errors = validate_watch_profile_draft(profile)
  if not valid:
    _record(
      action_type=ACTION_DRAFT_SAVE,
      ok=False,
      error="validation_failed",
      run_id=run_id,
      started_at=started_at,
      user_context=user_context,
      profile=profile,
      output_root=output_root,
    )
    return {"ok": False, "error": "validation_failed", "validation_errors": errors}

  profile = attach_user_run_metadata(profile, user_context=user_context, run_id=run_id)
  profile["safety_notice"] = SAFETY_NOTICE
  profile["safety_flags"] = _safety_flags()
  try:
    saved_paths = _save_profile(profile, output_root=output_root, status=PROFILE_STATUS_DRAFT, run_id=run_id)
  except (OSError, ValueError) as exc:
    _record(
      action_type=ACTION_DRAFT_SAVE,
      ok=False,
      error="save_failed",
      run_id=run_id,
      started_at=started_at,
      user_context=user_context,
      profile=profile,
      output_root=output_root,
    )
    return {"ok": False, "error": "save_failed", "message": str(exc)}

  _record(
    action_type=ACTION_DRAFT_SAVE,
    ok=True,
    error=None,
    run_id=run_id,
    started_at=started_at,
    user_context=user_context,
    profile=profile,
    output_root=output_root,
    saved_paths=saved_paths,
  )
  return {"ok": True, "profile": profile, "saved_paths": saved_paths, "run_id": run_id}


def promote_draft_to_active(
  *,
  draft_path: str | Path,
  confirm_text: str,
  output_root: Path | str,
  login_required: bool,
  is_authenticated: bool,
  auth_role: str,
  user_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
  run_id = generate_run_id()
  started_at = _utc_now_iso()
  expected = get_activation_confirmation_text()
  confirmation_matched = str(confirm_text or "") == expected
  allowed, block = _admin_gate(
    login_required=login_required,
    is_authenticated=is_authenticated,
    auth_role=auth_role,
    user_context=user_context,
    management_required=True,
  )
  if not allowed:
    return {"ok": False, "error": block, "message": _block_message(block)}
  if not confirmation_matched:
    return {"ok": False, "error": "confirm_text_mismatch", "message": _block_message("confirm_text_mismatch")}

  draft = load_watch_profile(draft_path)
  if not draft:
    return {"ok": False, "error": "missing_draft", "message": "draft が見つかりません。"}

  valid, errors = validate_watch_profile_for_activation(draft)
  if not valid:
    return {"ok": False, "error": "validation_failed", "validation_errors": errors}

  active_profile, active_path = get_active_watch_profile(output_root)
  archived_paths: dict[str, str] | None = None
  if active_profile and active_path:
    archived = dict(active_profile)
    archived["status"] = PROFILE_STATUS_ARCHIVED
    archived["archived_at"] = started_at
    archived_paths = _save_profile(
      archived,
      output_root=output_root,
      status=PROFILE_STATUS_ARCHIVED,
      run_id=generate_run_id(),
    )

  activated = normalize_watch_profile(draft)
  activated["status"] = PROFILE_STATUS_ACTIVE
  activated["approved_at"] = started_at
  ctx = user_context_as_dict(user_context or {})
  activated["approved_by"] = ctx.get("user_id") or ""
  if active_profile:
    activated["previous_profile_id"] = active_profile.get("profile_id")
  activated["version"] = int(activated.get("version") or 1) + 1
  activated = attach_user_run_metadata(activated, user_context=user_context, run_id=run_id)
  activated["safety_flags"] = _safety_flags(confirmation_matched=True)

  try:
    saved_paths = _save_profile(activated, output_root=output_root, status=PROFILE_STATUS_ACTIVE, run_id=run_id)
  except (OSError, ValueError) as exc:
    return {"ok": False, "error": "save_failed", "message": str(exc)}

  _record(
    action_type=ACTION_ACTIVATE,
    ok=True,
    error=None,
    run_id=run_id,
    started_at=started_at,
    user_context=user_context,
    profile=activated,
    output_root=output_root,
    saved_paths=saved_paths,
    source_paths=[str(draft_path)],
    confirmation_matched=True,
  )
  return {
    "ok": True,
    "profile": activated,
    "saved_paths": saved_paths,
    "archived_previous": archived_paths,
    "run_id": run_id,
  }


def archive_active_watch_profile(
  *,
  confirm_text: str,
  output_root: Path | str,
  login_required: bool,
  is_authenticated: bool,
  auth_role: str,
  user_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
  run_id = generate_run_id()
  started_at = _utc_now_iso()
  expected = get_archive_confirmation_text()
  confirmation_matched = str(confirm_text or "") == expected
  allowed, block = _admin_gate(
    login_required=login_required,
    is_authenticated=is_authenticated,
    auth_role=auth_role,
    user_context=user_context,
    management_required=True,
  )
  if not allowed:
    return {"ok": False, "error": block, "message": _block_message(block)}
  if not confirmation_matched:
    return {"ok": False, "error": "confirm_text_mismatch", "message": _block_message("confirm_text_mismatch")}

  active, active_path = get_active_watch_profile(output_root)
  if not active or not active_path:
    return {"ok": False, "error": "no_active_profile", "message": "active Watch Profile がありません。"}

  archived = dict(active)
  archived["status"] = PROFILE_STATUS_ARCHIVED
  archived["archived_at"] = started_at
  try:
    saved_paths = _save_profile(archived, output_root=output_root, status=PROFILE_STATUS_ARCHIVED, run_id=run_id)
  except (OSError, ValueError) as exc:
    return {"ok": False, "error": "save_failed", "message": str(exc)}

  _record(
    action_type=ACTION_ARCHIVE,
    ok=True,
    error=None,
    run_id=run_id,
    started_at=started_at,
    user_context=user_context,
    profile=archived,
    output_root=output_root,
    saved_paths=saved_paths,
    source_paths=[active_path],
    confirmation_matched=True,
  )
  return {"ok": True, "profile": archived, "saved_paths": saved_paths, "run_id": run_id}


def rollback_to_previous_watch_profile(
  *,
  confirm_text: str,
  output_root: Path | str,
  login_required: bool,
  is_authenticated: bool,
  auth_role: str,
  user_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
  run_id = generate_run_id()
  started_at = _utc_now_iso()
  expected = get_rollback_confirmation_text()
  confirmation_matched = str(confirm_text or "") == expected
  allowed, block = _admin_gate(
    login_required=login_required,
    is_authenticated=is_authenticated,
    auth_role=auth_role,
    user_context=user_context,
    management_required=True,
  )
  if not allowed:
    return {"ok": False, "error": block, "message": _block_message(block)}
  if not confirmation_matched:
    return {"ok": False, "error": "confirm_text_mismatch", "message": _block_message("confirm_text_mismatch")}

  active, active_path = get_active_watch_profile(output_root)
  if not active:
    return {"ok": False, "error": "no_active_profile", "message": "active Watch Profile がありません。"}

  previous_id = str(active.get("previous_profile_id") or "").strip()
  if not previous_id:
    return {"ok": False, "error": "no_previous_profile", "message": "rollback 対象の previous profile がありません。"}

  archive_dir = get_live_watch_profiles_archive_dir(output_root)
  candidate: dict[str, Any] | None = None
  candidate_path: str | None = None
  for path in sorted(archive_dir.glob("watch_profile_archive_*.json"), reverse=True):
    data = _load_json(path)
    if data and str(data.get("profile_id")) == previous_id:
      candidate = data
      candidate_path = str(path)
      break
  if not candidate:
    return {"ok": False, "error": "previous_not_found", "message": "archive 内に previous profile が見つかりません。"}

  archived_current = dict(active)
  archived_current["status"] = PROFILE_STATUS_ARCHIVED
  archived_current["archived_at"] = started_at
  try:
    _save_profile(archived_current, output_root=output_root, status=PROFILE_STATUS_ARCHIVED, run_id=generate_run_id())
  except (OSError, ValueError) as exc:
    return {"ok": False, "error": "save_failed", "message": str(exc)}

  restored = normalize_watch_profile(candidate)
  restored["status"] = PROFILE_STATUS_ACTIVE
  restored["approved_at"] = started_at
  ctx = user_context_as_dict(user_context or {})
  restored["approved_by"] = ctx.get("user_id") or ""
  restored["previous_profile_id"] = active.get("profile_id")
  try:
    saved_paths = _save_profile(restored, output_root=output_root, status=PROFILE_STATUS_ACTIVE, run_id=run_id)
  except (OSError, ValueError) as exc:
    return {"ok": False, "error": "save_failed", "message": str(exc)}

  _record(
    action_type=ACTION_ROLLBACK,
    ok=True,
    error=None,
    run_id=run_id,
    started_at=started_at,
    user_context=user_context,
    profile=restored,
    output_root=output_root,
    saved_paths=saved_paths,
    source_paths=[candidate_path] if candidate_path else [],
    confirmation_matched=True,
  )
  return {"ok": True, "profile": restored, "saved_paths": saved_paths, "run_id": run_id}


def import_next_cycle_plan_to_draft(
  *,
  plan: dict[str, Any],
  plan_path: str,
  output_root: Path | str,
  login_required: bool,
  is_authenticated: bool,
  auth_role: str,
  user_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
  queries = [str(q).strip() for q in (plan.get("query_candidates") or []) if str(q).strip()]
  draft_input = empty_watch_profile_template(theme_name=str(plan.get("theme_name") or ""))
  draft_input["search_queries"] = queries
  draft_input["search_keywords"] = queries[:5]
  draft_input["notes"] = f"Imported from next cycle plan: {plan_path}"
  draft_input["source_artifact_paths"] = [plan_path]
  return create_watch_profile_draft(
    profile_input=draft_input,
    output_root=output_root,
    login_required=login_required,
    is_authenticated=is_authenticated,
    auth_role=auth_role,
    user_context=user_context,
  )


def describe_watch_profile_status(project_root: Path | str) -> dict[str, Any]:
  active, active_path = get_active_watch_profile(project_root)
  draft, draft_path = get_latest_watch_profile_draft(project_root)
  if active:
    status = "active_profile_ready"
    next_action = "Digest Preview / Scheduler dry-run で active profile を参照できます。"
  elif draft:
    status = "draft_waiting_approval"
    next_action = "admin が内容を確認し、確認文付きで active 化してください。"
  else:
    status = "no_active_profile"
    next_action = "Watch Profile draft を作成してください。"
  misconfigured = bool(draft and not (draft.get("search_keywords") or draft.get("search_queries")))
  if misconfigured:
    status = "profile_misconfigured"
    next_action = "search_keywords または search_queries を設定してください。"
  return {
    "watch_profile_status": status,
    "active_watch_profile_exists": bool(active),
    "active_watch_profile_path": active_path,
    "active_watch_profile_theme": (active or {}).get("theme_name"),
    "latest_draft_exists": bool(draft),
    "latest_draft_path": draft_path,
    "latest_draft_theme": (draft or {}).get("theme_name"),
    "next_recommended_action": next_action,
    "management_enabled": is_watch_profile_management_enabled(),
  }


def _block_message(code: str | None) -> str:
  mapping = {
    "management_disabled": "Watch Profile 管理は無効です（ENABLE_WATCH_PROFILE_MANAGEMENT=false）。",
    "admin_required": "admin権限が必要です。",
    "login_required": "ログイン後に実行できます。",
    "confirm_text_mismatch": "確認文が一致していません。",
  }
  return mapping.get(str(code or ""), "操作できません。")
