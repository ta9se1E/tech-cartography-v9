"""Thin Cloud Run Job adapter for the existing v9 weekly scheduler."""

from __future__ import annotations

import os
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from .cloud_lock import acquire_cloud_weekly_lock, release_cloud_weekly_lock
from .cloud_runtime import get_persist_bucket_name, get_persist_root, is_cloud_runtime
from .cloud_weekly_settings import load_weekly_delivery_settings, resolve_allowed_recipients
from .email_delivery import load_email_delivery_config
from .persistence import load_watch_profile
from .retrieval_run_store import stable_payload_signature
from .weekly_run_config import default_weekly_run_config
from .weekly_scheduler import run_weekly_watch


def build_cloud_weekly_run_config(
  settings: Mapping[str, Any],
  *,
  persist_root: Path,
  environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
  env = environ if environ is not None else os.environ
  config = default_weekly_run_config()
  source_types = set(str(item or "").strip() for item in list(load_watch_profile(base_dir=persist_root).get("source_types", [])) if str(item or "").strip())
  config["enabled"] = bool(settings.get("enabled", False))
  config["watch_profile_path"] = str((persist_root / "watch_profile_current.json").resolve())
  config["execution"]["dry_run"] = _env_bool(env, "V9_CLOUD_JOB_DRY_RUN", True)
  config["execution"]["patent_enabled"] = "patent" in source_types and _env_bool(env, "V9_CLOUD_ENABLE_PATENT", False)
  config["execution"]["paper_enabled"] = "paper" in source_types
  config["execution"]["web_company_enabled"] = bool({"web", "company"} & source_types)
  config["email"]["mode"] = "self_only" if _env_bool(env, "V9_ENABLE_EMAIL_SEND", False) else "preview"
  config["email"]["self_send_enabled"] = _env_bool(env, "V9_ENABLE_EMAIL_SEND", False)
  config["schedule"]["timezone"] = str(settings.get("timezone", "Asia/Tokyo") or "Asia/Tokyo")
  config["schedule"]["day_of_week"] = str(settings.get("weekday", "MON") or "MON")
  config["schedule"]["hour"] = int(settings.get("hour", 9) or 9)
  config["schedule"]["minute"] = int(settings.get("minute", 0) or 0)
  polite_email = str(env.get("OPENALEX_POLITE_EMAIL", "") or "").strip()
  if polite_email:
    config["paper"]["polite_email"] = polite_email
  return config


def run_cloud_weekly_job(
  *,
  environ: Mapping[str, str] | None = None,
  provider_adapters: dict[str, Any] | None = None,
  output_root: Path | str | None = None,
  storage_client: Any | None = None,
) -> dict[str, Any]:
  env = dict(environ or os.environ)
  persist_root = Path(output_root) if output_root is not None else get_persist_root(env)
  settings = load_weekly_delivery_settings(base_dir=persist_root, environ=env, storage_client=storage_client)
  if not bool(settings.get("enabled", False)):
    return {
      "status": "skipped",
      "message": "weekly delivery is disabled",
      "settings": settings,
      "persist_root": str(persist_root),
      "external_api_called": False,
      "smtp_called": False,
    }

  recipient = str(settings.get("recipient_email", "") or "").strip().lower()
  allowed_recipients = set(resolve_allowed_recipients(env))
  if recipient and allowed_recipients and recipient not in allowed_recipients:
    return {
      "status": "blocked",
      "message": "recipient is not in allowlist",
      "settings": settings,
      "persist_root": str(persist_root),
      "external_api_called": False,
      "smtp_called": False,
    }

  email_config = load_email_delivery_config(env)
  send_enabled = _env_bool(env, "V9_ENABLE_EMAIL_SEND", False)
  if send_enabled:
    missing_fields = [
      field_name
      for field_name, value in (
        ("SMTP_HOST", email_config.smtp_host),
        ("SMTP_PORT", email_config.smtp_port),
        ("SMTP_USERNAME", email_config.smtp_username),
        ("SMTP_PASSWORD", email_config.smtp_password),
      )
      if not value
    ]
    if missing_fields:
      return {
        "status": "blocked",
        "message": "SMTP settings are incomplete",
        "missing_fields": missing_fields,
        "settings": settings,
        "persist_root": str(persist_root),
        "external_api_called": False,
        "smtp_called": False,
      }

  watch_profile_path = persist_root / "watch_profile_current.json"
  if not watch_profile_path.exists():
    return {
      "status": "blocked",
      "message": "watch_profile_current.json が存在しません。",
      "settings": settings,
      "persist_root": str(persist_root),
      "external_api_called": False,
      "smtp_called": False,
    }
  watch_profile = load_watch_profile(base_dir=persist_root)
  watch_profile_signature = stable_payload_signature(watch_profile)
  cloud_lock_info: dict[str, Any] | None = None
  config = build_cloud_weekly_run_config(settings, persist_root=persist_root, environ=env)
  config["_run_id"] = "cloud_weekly_job_" + datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")

  try:
    if is_cloud_runtime(env) and get_persist_bucket_name(env):
      cloud_lock_info = acquire_cloud_weekly_lock(
        watch_profile_signature,
        run_id=str(config.get("_run_id", "") or ""),
        bucket_name=get_persist_bucket_name(env),
        object_prefix="weekly_locks",
        storage_client=storage_client,
        stale_timeout_seconds=int(config.get("timeouts", {}).get("lock_stale_seconds", 21600) or 21600),
      )
      if not cloud_lock_info.get("acquired", False):
        return {
          "status": "blocked",
          "message": str(cloud_lock_info.get("message", "") or "cloud lock blocked"),
          "settings": settings,
          "persist_root": str(persist_root),
          "external_api_called": False,
          "smtp_called": False,
          "cloud_lock": cloud_lock_info,
        }

    if not send_enabled:
      config["_no_email"] = True
      config["email"]["mode"] = "preview"
      config["email"]["self_send_enabled"] = False

    result = run_weekly_watch(config, output_root=persist_root, provider_adapters=provider_adapters)
    return {
      **dict(result or {}),
      "settings": settings,
      "persist_root": str(persist_root),
      "cloud_lock": cloud_lock_info or {},
    }
  finally:
    if cloud_lock_info and cloud_lock_info.get("acquired", False):
      release_cloud_weekly_lock(cloud_lock_info, storage_client=storage_client)


def _env_bool(env: Mapping[str, str], name: str, default: bool) -> bool:
  value = str(env.get(name, "") or "").strip().lower()
  if value in {"1", "true", "yes", "on"}:
    return True
  if value in {"0", "false", "no", "off"}:
    return False
  return default


__all__ = [
  "build_cloud_weekly_run_config",
  "run_cloud_weekly_job",
]
