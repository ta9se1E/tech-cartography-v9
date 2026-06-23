"""Live artifact storage paths — local outputs fallback or LIVE_OUTPUTS_ROOT (Phase 25H)."""

from __future__ import annotations

import os
import uuid
from pathlib import Path
from typing import Any

LIVE_OUTPUTS_ROOT_ENV = "LIVE_OUTPUTS_ROOT"

LIVE_WEB_SIGNALS_SUBDIR = "live_web_signals"
LIVE_DIGEST_PREVIEW_SUBDIR = "live_digest_preview"
LIVE_EMAIL_SEND_SUBDIR = "live_email_send"
LIVE_APPROVED_MEMBER_SEND_SUBDIR = "live_approved_member_send"
LIVE_WATCH_EXPANSION_SUBDIR = "live_watch_expansion"
LIVE_WATCH_PROFILES_SUBDIR = "live_watch_profiles"
LIVE_WATCH_PROFILES_DRAFTS_SUBDIR = "drafts"
LIVE_WATCH_PROFILES_ACTIVE_SUBDIR = "active"
LIVE_WATCH_PROFILES_ARCHIVE_SUBDIR = "archive"
LIVE_SCHEDULER_DRY_RUN_SUBDIR = "live_scheduler_dry_run"
LIVE_NEXT_CYCLE_SEARCH_SUBDIR = "live_next_cycle_search"
LIVE_NEXT_CYCLE_WEB_SIGNALS_SUBDIR = "live_next_cycle_web_signals"
LIVE_OPERATION_STATUS_SUBDIR = "live_operation_status"
LIVE_RELEASE_PACK_SUBDIR = "live_release_pack"
LIVE_RUN_HISTORY_SUBDIR = "live_run_history"

LOCAL_OUTPUTS_DIRNAME = "outputs"


def _env_live_outputs_root() -> str:
  return str(os.environ.get(LIVE_OUTPUTS_ROOT_ENV, "") or "").strip()


def using_live_outputs_root_env() -> bool:
  return bool(_env_live_outputs_root())


def _safe_resolve_path(raw: str, *, project_root: Path | None = None) -> Path:
  candidate = Path(raw).expanduser()
  if not candidate.is_absolute():
    base = project_root if project_root is not None else Path.cwd()
    candidate = base / candidate
  if ".." in Path(raw).parts:
    raise ValueError("LIVE_OUTPUTS_ROOT must not contain path traversal segments")
  resolved = candidate.resolve()
  if resolved == Path("/"):
    raise ValueError("LIVE_OUTPUTS_ROOT resolves to an unsafe path")
  return resolved


def get_live_outputs_root(project_root: Path | str | None = None) -> Path:
  """Return active live outputs root (env override or project outputs/)."""
  raw = _env_live_outputs_root()
  base = Path(project_root).resolve() if project_root is not None else None
  if raw:
    return _safe_resolve_path(raw, project_root=base)
  if base is not None:
    return base / LOCAL_OUTPUTS_DIRNAME
  return Path(LOCAL_OUTPUTS_DIRNAME).resolve()


def get_live_web_signals_dir(project_root: Path | str | None = None) -> Path:
  return get_live_outputs_root(project_root) / LIVE_WEB_SIGNALS_SUBDIR


def get_live_digest_preview_dir(project_root: Path | str | None = None) -> Path:
  return get_live_outputs_root(project_root) / LIVE_DIGEST_PREVIEW_SUBDIR


def get_live_email_send_dir(project_root: Path | str | None = None) -> Path:
  return get_live_outputs_root(project_root) / LIVE_EMAIL_SEND_SUBDIR


def get_live_approved_member_send_dir(project_root: Path | str | None = None) -> Path:
  return get_live_outputs_root(project_root) / LIVE_APPROVED_MEMBER_SEND_SUBDIR


def get_live_watch_expansion_dir(project_root: Path | str | None = None) -> Path:
  return get_live_outputs_root(project_root) / LIVE_WATCH_EXPANSION_SUBDIR


def get_live_watch_profiles_dir(project_root: Path | str | None = None) -> Path:
  return get_live_outputs_root(project_root) / LIVE_WATCH_PROFILES_SUBDIR


def get_live_watch_profiles_drafts_dir(project_root: Path | str | None = None) -> Path:
  return get_live_watch_profiles_dir(project_root) / LIVE_WATCH_PROFILES_DRAFTS_SUBDIR


def get_live_watch_profiles_active_dir(project_root: Path | str | None = None) -> Path:
  return get_live_watch_profiles_dir(project_root) / LIVE_WATCH_PROFILES_ACTIVE_SUBDIR


def get_live_watch_profiles_archive_dir(project_root: Path | str | None = None) -> Path:
  return get_live_watch_profiles_dir(project_root) / LIVE_WATCH_PROFILES_ARCHIVE_SUBDIR


def get_live_scheduler_dry_run_dir(project_root: Path | str | None = None) -> Path:
  return get_live_outputs_root(project_root) / LIVE_SCHEDULER_DRY_RUN_SUBDIR


def get_live_next_cycle_search_dir(project_root: Path | str | None = None) -> Path:
  return get_live_outputs_root(project_root) / LIVE_NEXT_CYCLE_SEARCH_SUBDIR


def get_live_next_cycle_web_signals_dir(project_root: Path | str | None = None) -> Path:
  return get_live_outputs_root(project_root) / LIVE_NEXT_CYCLE_WEB_SIGNALS_SUBDIR


def get_live_operation_status_dir(project_root: Path | str | None = None) -> Path:
  return get_live_outputs_root(project_root) / LIVE_OPERATION_STATUS_SUBDIR


def get_live_release_pack_dir(project_root: Path | str | None = None) -> Path:
  return get_live_outputs_root(project_root) / LIVE_RELEASE_PACK_SUBDIR


def get_live_run_history_dir(project_root: Path | str | None = None) -> Path:
  return get_live_outputs_root(project_root) / LIVE_RUN_HISTORY_SUBDIR


def _count_json_artifacts(directory: Path, pattern: str) -> int:
  if not directory.exists():
    return 0
  return sum(1 for _ in directory.glob(pattern))


def check_directory_writable(directory: Path) -> tuple[bool, str | None]:
  try:
    directory.mkdir(parents=True, exist_ok=True)
    probe = directory / f".write_probe_{uuid.uuid4().hex[:8]}"
    probe.write_text("ok", encoding="utf-8")
    probe.unlink(missing_ok=True)
    return True, None
  except OSError as exc:
    return False, f"{directory} is not writable ({type(exc).__name__})"


def ensure_live_artifact_dirs(project_root: Path | str | None = None) -> tuple[bool, str | None]:
  """Create live artifact dirs when possible. Returns (ok, error_message)."""
  for directory in (
    get_live_web_signals_dir(project_root),
    get_live_digest_preview_dir(project_root),
    get_live_email_send_dir(project_root),
    get_live_approved_member_send_dir(project_root),
    get_live_watch_expansion_dir(project_root),
    get_live_watch_profiles_dir(project_root),
    get_live_watch_profiles_drafts_dir(project_root),
    get_live_watch_profiles_active_dir(project_root),
    get_live_watch_profiles_archive_dir(project_root),
    get_live_scheduler_dry_run_dir(project_root),
    get_live_next_cycle_search_dir(project_root),
    get_live_next_cycle_web_signals_dir(project_root),
    get_live_operation_status_dir(project_root),
    get_live_release_pack_dir(project_root),
    get_live_run_history_dir(project_root),
  ):
    ok, message = check_directory_writable(directory)
    if not ok:
      return False, message or f"Cannot prepare directory: {directory}"
  return True, None


def describe_live_artifact_storage(project_root: Path | str | None = None) -> dict[str, Any]:
  """Admin-safe storage summary — no secrets."""
  root = get_live_outputs_root(project_root)
  web_dir = get_live_web_signals_dir(project_root)
  digest_dir = get_live_digest_preview_dir(project_root)
  email_dir = get_live_email_send_dir(project_root)
  approved_member_send_dir = get_live_approved_member_send_dir(project_root)
  expansion_dir = get_live_watch_expansion_dir(project_root)
  profiles_dir = get_live_watch_profiles_dir(project_root)
  next_cycle_search_dir = get_live_next_cycle_search_dir(project_root)
  next_cycle_web_signals_dir = get_live_next_cycle_web_signals_dir(project_root)
  operation_status_dir = get_live_operation_status_dir(project_root)
  release_pack_dir = get_live_release_pack_dir(project_root)
  run_history_dir = get_live_run_history_dir(project_root)

  root_ok, root_message = check_directory_writable(root)
  web_ok, web_message = check_directory_writable(web_dir)
  digest_ok, digest_message = check_directory_writable(digest_dir)
  email_ok, email_message = check_directory_writable(email_dir)
  approved_member_send_ok, approved_member_send_message = check_directory_writable(approved_member_send_dir)
  expansion_ok, expansion_message = check_directory_writable(expansion_dir)
  profiles_ok, profiles_message = check_directory_writable(profiles_dir)
  next_cycle_search_ok, next_cycle_search_message = check_directory_writable(next_cycle_search_dir)
  next_cycle_web_ok, next_cycle_web_message = check_directory_writable(next_cycle_web_signals_dir)
  operation_status_ok, operation_status_message = check_directory_writable(operation_status_dir)
  release_pack_ok, release_pack_message = check_directory_writable(release_pack_dir)
  run_history_ok, run_history_message = check_directory_writable(run_history_dir)

  env_value = _env_live_outputs_root()
  return {
    "live_outputs_root_env": env_value or "(unset — local outputs fallback)",
    "using_env_override": using_live_outputs_root_env(),
    "active_storage_root": str(root),
    "web_signal_dir": str(web_dir),
    "digest_preview_dir": str(digest_dir),
    "email_send_log_dir": str(email_dir),
    "approved_member_send_log_dir": str(approved_member_send_dir),
    "watch_expansion_dir": str(expansion_dir),
    "watch_profiles_dir": str(profiles_dir),
    "next_cycle_search_dir": str(next_cycle_search_dir),
    "next_cycle_web_signals_dir": str(next_cycle_web_signals_dir),
    "operation_status_dir": str(operation_status_dir),
    "release_pack_dir": str(release_pack_dir),
    "run_history_dir": str(run_history_dir),
    "writable": {
      "active_storage_root": root_ok,
      "web_signal_dir": web_ok,
      "digest_preview_dir": digest_ok,
      "email_send_log_dir": email_ok,
      "approved_member_send_log_dir": approved_member_send_ok,
      "watch_expansion_dir": expansion_ok,
      "watch_profiles_dir": profiles_ok,
      "next_cycle_search_dir": next_cycle_search_ok,
      "next_cycle_web_signals_dir": next_cycle_web_ok,
      "operation_status_dir": operation_status_ok,
      "release_pack_dir": release_pack_ok,
      "run_history_dir": run_history_ok,
    },
    "writable_messages": {
      "active_storage_root": root_message,
      "web_signal_dir": web_message,
      "digest_preview_dir": digest_message,
      "email_send_log_dir": email_message,
      "approved_member_send_log_dir": approved_member_send_message,
      "watch_expansion_dir": expansion_message,
      "watch_profiles_dir": profiles_message,
      "next_cycle_search_dir": next_cycle_search_message,
      "next_cycle_web_signals_dir": next_cycle_web_message,
      "operation_status_dir": operation_status_message,
      "release_pack_dir": release_pack_message,
      "run_history_dir": run_history_message,
    },
    "artifact_counts": {
      "web_signal_packs": _count_json_artifacts(web_dir, "live_web_signal_pack_*.json"),
      "digest_previews": _count_json_artifacts(digest_dir, "live_digest_preview_*.json"),
      "email_send_logs": _count_json_artifacts(email_dir, "live_email_send_*.json"),
      "approved_member_send_logs": _count_json_artifacts(
        approved_member_send_dir,
        "live_approved_member_send_*.json",
      ),
      "watch_expansion_proposals": _count_json_artifacts(
        expansion_dir,
        "live_watch_expansion_proposals_*.json",
      ),
      "watch_profile_drafts": _count_json_artifacts(profiles_dir, "watch_profile_draft_*.json"),
      "next_cycle_search_plans": _count_json_artifacts(
        next_cycle_search_dir,
        "next_cycle_search_plan_*.json",
      ),
      "next_cycle_web_signal_packs": _count_json_artifacts(
        next_cycle_web_signals_dir,
        "next_cycle_web_signal_pack_*.json",
      ),
      "operation_status_snapshots": _count_json_artifacts(
        operation_status_dir,
        "live_operation_status_*.json",
      ),
      "live_release_packs": _count_json_artifacts(
        release_pack_dir,
        "live_beta_release_pack_*.json",
      ),
      "live_run_history_entries": _count_json_artifacts(
        run_history_dir,
        "run_history_*.json",
      ),
    },
  }
