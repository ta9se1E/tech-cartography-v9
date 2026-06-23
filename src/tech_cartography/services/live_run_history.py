"""Live user run history — operational execution records (Phase 25M, not audit logs)."""

from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tech_cartography.runtime.live_artifact_paths import (
  check_directory_writable,
  get_live_run_history_dir,
)
from tech_cartography.runtime.user_context import normalize_user_context, user_context_as_dict

SAFETY_LABEL = "User run history"
SECRET_REDACTION_STATUS = "secrets_redacted"

ACTION_TYPES: frozenset[str] = frozenset(
  {
    "live_web_signal_pack",
    "live_digest_preview",
    "self_only_email_send",
    "live_approved_member_email_send",
    "watch_expansion_proposal",
    "watch_profile_draft",
    "next_cycle_search_plan",
    "next_cycle_web_signal_pack",
    "live_operation_status",
    "live_beta_release_pack",
  },
)

_SENSITIVE_PATTERN = re.compile(
  r"(api[_-]?key\s*[:=]|authorization\s*:\s*bearer|smtp[_-]?password|login[_-]?password)",
  re.IGNORECASE,
)

_FORBIDDEN_ENV_NAMES: tuple[str, ...] = (
  "TECH_CARTOGRAPHY_LOGIN_PASSWORD",
  "SMTP_PASSWORD",
  "OPENAI_API_KEY",
  "GEMINI_API_KEY",
  "TAVILY_API_KEY",
)


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _timestamp_slug(iso_ts: str) -> str:
  return iso_ts.replace(":", "").replace("-", "")


USER_RUN_METADATA_KEYS: tuple[str, ...] = (
  "run_id",
  "created_by_user_id",
  "created_by_display_name",
  "created_by_role",
  "created_by_auth_provider",
)


def copy_user_run_metadata(target: dict[str, Any], source: dict[str, Any]) -> dict[str, Any]:
  for key in USER_RUN_METADATA_KEYS:
    if key in source:
      target[key] = source[key]
  return target


def generate_run_id() -> str:
  return f"run-{uuid.uuid4().hex[:12]}"


def sanitize_input_summary(text: str | None, *, max_len: int = 240) -> str | None:
  if not text:
    return None
  cleaned = re.sub(r"\s+", " ", str(text)).strip()
  if not cleaned:
    return None
  for env_name in _FORBIDDEN_ENV_NAMES:
    value = str(os.environ.get(env_name, "") or "").strip()
    if value and value in cleaned:
      cleaned = cleaned.replace(value, "[redacted]")
  if _SENSITIVE_PATTERN.search(cleaned):
    return "[redacted summary]"
  if len(cleaned) > max_len:
    return cleaned[: max_len - 3] + "..."
  return cleaned


def _assert_history_safe(serialized: str) -> None:
  if _SENSITIVE_PATTERN.search(serialized):
    raise ValueError("Refusing to save run history containing sensitive material")
  for env_name in _FORBIDDEN_ENV_NAMES:
    value = str(os.environ.get(env_name, "") or "").strip()
    if value and value in serialized:
      raise ValueError(f"Refusing to save run history leaking {env_name}")
    if env_name in serialized:
      raise ValueError(f"Refusing to save run history containing credential name {env_name}")


def attach_user_run_metadata(
  payload: dict[str, Any],
  *,
  user_context: dict[str, Any] | None,
  run_id: str,
) -> dict[str, Any]:
  ctx = user_context_as_dict(normalize_user_context(user_context))
  enriched = dict(payload)
  enriched["run_id"] = run_id
  enriched["created_by_user_id"] = ctx["user_id"]
  enriched["created_by_display_name"] = ctx["display_name"]
  enriched["created_by_role"] = ctx["role"]
  enriched["created_by_auth_provider"] = ctx["auth_provider"]
  return enriched


def sanitize_operation_metadata(metadata: dict[str, Any] | None) -> dict[str, Any] | None:
  if not metadata:
    return None
  allowed_keys = frozenset(
    {
      "post_send_recommended_action",
      "reset_required",
      "recipient_masked",
      "recipient_domain",
    },
  )
  safe: dict[str, Any] = {}
  for key, value in metadata.items():
    if key not in allowed_keys or value is None:
      continue
    text = str(value)
    if _SENSITIVE_PATTERN.search(text):
      continue
    safe[str(key)] = value
  return safe or None


def build_run_history_entry(
  *,
  run_id: str,
  action_type: str,
  started_at: str,
  finished_at: str,
  status: str,
  user_context: dict[str, Any] | None,
  theme_name: str | None = None,
  input_summary: str | None = None,
  output_artifact_paths: dict[str, str] | None = None,
  source_artifact_paths: list[str] | None = None,
  error_summary: str | None = None,
  operation_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
  if action_type not in ACTION_TYPES:
    raise ValueError(f"Unknown action_type: {action_type}")
  if status not in {"success", "failed", "blocked", "skipped"}:
    raise ValueError(f"Unknown status: {status}")

  ctx = user_context_as_dict(normalize_user_context(user_context))
  entry = {
    "run_id": run_id,
    "action_type": action_type,
    "started_at": started_at,
    "finished_at": finished_at,
    "status": status,
    "user_id": ctx["user_id"],
    "display_name": ctx["display_name"],
    "role": ctx["role"],
    "auth_provider": ctx["auth_provider"],
    "theme_name": (str(theme_name).strip() if theme_name else None) or None,
    "input_summary": sanitize_input_summary(input_summary),
    "output_artifact_paths": dict(output_artifact_paths or {}),
    "source_artifact_paths": list(source_artifact_paths or []),
    "error_summary": sanitize_input_summary(error_summary, max_len=400),
    "safety_label": SAFETY_LABEL,
    "secret_redaction_status": SECRET_REDACTION_STATUS,
  }
  safe_metadata = sanitize_operation_metadata(operation_metadata)
  if safe_metadata:
    entry["operation_metadata"] = safe_metadata
  serialized = json.dumps(entry, ensure_ascii=False)
  _assert_history_safe(serialized)
  return entry


def save_run_history_entry(
  entry: dict[str, Any],
  project_root: Path | str | None = None,
) -> dict[str, str]:
  out_dir = get_live_run_history_dir(project_root)
  writable, message = check_directory_writable(out_dir)
  if not writable:
    raise ValueError(message or f"Cannot write run history to {out_dir}")

  finished_at = str(entry.get("finished_at") or _utc_now_iso())
  slug = _timestamp_slug(finished_at)
  run_id = str(entry.get("run_id") or generate_run_id())
  json_path = out_dir / f"run_history_{slug}_{run_id}.json"
  md_path = out_dir / f"run_history_{slug}_{run_id}.md"

  json_text = json.dumps(entry, ensure_ascii=False, indent=2)
  _assert_history_safe(json_text)
  json_path.write_text(json_text + "\n", encoding="utf-8")
  md_path.write_text(render_run_history_markdown(entry), encoding="utf-8")
  return {"json": str(json_path), "markdown": str(md_path)}


def record_live_run(
  *,
  action_type: str,
  status: str,
  user_context: dict[str, Any] | None,
  run_id: str | None = None,
  started_at: str | None = None,
  finished_at: str | None = None,
  theme_name: str | None = None,
  input_summary: str | None = None,
  output_artifact_paths: dict[str, str] | None = None,
  source_artifact_paths: list[str] | None = None,
  error_summary: str | None = None,
  operation_metadata: dict[str, Any] | None = None,
  project_root: Path | str | None = None,
) -> tuple[dict[str, Any] | None, dict[str, str] | None, str | None]:
  run_id_value = run_id or generate_run_id()
  started = started_at or _utc_now_iso()
  finished = finished_at or _utc_now_iso()
  try:
    entry = build_run_history_entry(
      run_id=run_id_value,
      action_type=action_type,
      started_at=started,
      finished_at=finished,
      status=status,
      user_context=user_context,
      theme_name=theme_name,
      input_summary=input_summary,
      output_artifact_paths=output_artifact_paths,
      source_artifact_paths=source_artifact_paths,
      error_summary=error_summary,
      operation_metadata=operation_metadata,
    )
    saved_paths = save_run_history_entry(entry, project_root)
  except (OSError, ValueError) as exc:
    return None, None, str(exc)
  return entry, saved_paths, None


def render_run_history_markdown(entry: dict[str, Any]) -> str:
  lines = [
    "# User Run History",
    "",
    f"- run_id: {entry.get('run_id')}",
    f"- action_type: {entry.get('action_type')}",
    f"- status: {entry.get('status')}",
    f"- user_id: {entry.get('user_id')}",
    f"- display_name: {entry.get('display_name')}",
    f"- role: {entry.get('role')}",
    f"- started_at: {entry.get('started_at')}",
    f"- finished_at: {entry.get('finished_at')}",
    f"- theme_name: {entry.get('theme_name')}",
    "",
    "## input_summary",
    "",
    str(entry.get("input_summary") or "(none)"),
    "",
    "## output_artifact_paths",
    "",
  ]
  outputs = entry.get("output_artifact_paths") or {}
  if outputs:
    for key, path in outputs.items():
      lines.append(f"- {key}: {path}")
  else:
    lines.append("(none)")
  lines.extend(["", "## error_summary", "", str(entry.get("error_summary") or "(none)"), ""])
  op_meta = entry.get("operation_metadata") or {}
  if op_meta:
    lines.extend(["", "## operation_metadata", ""])
    for key, value in op_meta.items():
      lines.append(f"- {key}: {value}")
  lines.extend(["## safety_label", "", str(entry.get("safety_label") or SAFETY_LABEL), ""])
  return "\n".join(lines).strip() + "\n"


def _load_history_json(path: Path) -> dict[str, Any] | None:
  try:
    data = json.loads(path.read_text(encoding="utf-8"))
  except (OSError, json.JSONDecodeError):
    return None
  return data if isinstance(data, dict) else None


def list_run_history_entries(
  project_root: Path | str | None = None,
  *,
  limit: int = 20,
  user_id: str | None = None,
  action_type: str | None = None,
  status: str | None = None,
  viewer_user_context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
  out_dir = get_live_run_history_dir(project_root)
  if not out_dir.is_dir():
    return []

  viewer = normalize_user_context(viewer_user_context)
  entries: list[dict[str, Any]] = []
  files = sorted(out_dir.glob("run_history_*.json"), key=lambda path: path.stat().st_mtime, reverse=True)
  for path in files:
    entry = _load_history_json(path)
    if not entry:
      continue
    if not viewer.get("is_admin") and entry.get("user_id") != viewer.get("user_id"):
      continue
    if user_id and entry.get("user_id") != user_id:
      continue
    if action_type and entry.get("action_type") != action_type:
      continue
    if status and entry.get("status") != status:
      continue
    entries.append(entry)
    if len(entries) >= limit:
      break
  return entries


def summarize_run_history_for_console(
  project_root: Path | str | None,
  *,
  viewer_user_context: dict[str, Any] | None,
  limit: int = 20,
) -> dict[str, Any]:
  viewer = normalize_user_context(viewer_user_context)
  entries = list_run_history_entries(
    project_root,
    limit=limit,
    viewer_user_context=viewer,
  )
  latest_by_user = next((item for item in entries if item.get("user_id") == viewer.get("user_id")), None)
  latest_failed_or_blocked = next(
    (item for item in entries if item.get("status") in {"failed", "blocked"}),
    None,
  )
  return {
    "total_visible_count": len(entries),
    "latest_by_current_user": latest_by_user,
    "latest_failed_or_blocked": latest_failed_or_blocked,
    "recent_entries": entries[:5],
  }


def map_result_status(*, ok: bool | None, error: str | None = None, blocked: bool = False) -> str:
  if blocked or is_blocked_error(error):
    return "blocked"
  if ok:
    return "success"
  if error in {"empty_theme", "empty_query", "empty_selection"}:
    return "skipped"
  return "failed"


def is_blocked_error(error: str | None) -> bool:
  return str(error or "") in {
    "disabled_by_env",
    "missing_api_key",
    "missing_tavily_key",
    "login_required",
    "admin_required",
    "missing_smtp_config",
    "email_disabled",
    "approved_member_send_disabled",
    "approved_list_empty",
    "recipient_not_approved",
    "member_not_allowed",
    "invalid_recipient",
    "cc_bcc_not_allowed",
  }
