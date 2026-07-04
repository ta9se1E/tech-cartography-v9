"""Thin Cloud Run Job adapter for the existing v9 weekly scheduler."""

from __future__ import annotations

import os
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

from .cloud_lock import acquire_cloud_weekly_lock, release_cloud_weekly_lock
from .cloud_runtime import get_persist_bucket_name, get_persist_root, is_cloud_runtime
from .cloud_weekly_settings import load_weekly_delivery_settings, resolve_allowed_recipients
from .email_delivery import load_email_delivery_config
from .persistence import load_watch_profile
from .retrieval_run_store import stable_payload_signature
from .web_company_retrieval import build_global_web_retrieval_preview, execute_global_web_retrieval
from .weekly_run_config import default_weekly_run_config
from .weekly_scheduler import run_web_company_provider_for_weekly, run_weekly_watch

STRICT_BOOL_VALUES = {
  "true": True,
  "1": True,
  "yes": True,
  "false": False,
  "0": False,
  "no": False,
}
QUERY_ID_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9_]{1,63}$")
ALLOWED_PAPER_TIME_RANGES = {"all", "12m", "6m", "3m"}


def build_cloud_weekly_run_config(
  settings: Mapping[str, Any],
  *,
  persist_root: Path,
  environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
  env = dict(environ or os.environ)
  config = default_weekly_run_config()
  source_types = set(str(item or "").strip() for item in list(load_watch_profile(base_dir=persist_root).get("source_types", [])) if str(item or "").strip())
  controls = resolve_cloud_job_controls(env)
  config["enabled"] = bool(settings.get("enabled", False))
  config["watch_profile_path"] = str((persist_root / "watch_profile_current.json").resolve())
  config["execution"]["dry_run"] = bool(controls["dry_run"])
  config["execution"]["patent_enabled"] = bool("patent" in source_types and controls["patent_enabled"])
  config["execution"]["paper_enabled"] = _resolve_source_enabled(
    "paper" in source_types,
    controls["paper_enabled"],
  )
  config["execution"]["web_company_enabled"] = _resolve_source_enabled(
    bool({"web", "company"} & source_types),
    controls["web_company_enabled"],
  )
  send_enabled = _env_bool(env, "V9_ENABLE_EMAIL_SEND", False)
  config["email"]["mode"] = "self_only" if send_enabled else "preview"
  config["email"]["self_send_enabled"] = send_enabled
  config["schedule"]["timezone"] = str(settings.get("timezone", "Asia/Tokyo") or "Asia/Tokyo")
  config["schedule"]["day_of_week"] = str(settings.get("weekday", "MON") or "MON")
  config["schedule"]["hour"] = int(settings.get("hour", 9) or 9)
  config["schedule"]["minute"] = int(settings.get("minute", 0) or 0)
  if controls["paper_approved_query_ids"]:
    config["paper"]["approved_query_ids"] = list(controls["paper_approved_query_ids"])
  if controls["web_approved_query_ids"]:
    config["web_company"]["approved_query_ids"] = list(controls["web_approved_query_ids"])
  if controls["paper_max_results"] is not None:
    config["limits"]["paper_max_results"] = int(controls["paper_max_results"])
  if controls["web_max_results"] is not None:
    config["limits"]["web_max_results"] = int(controls["web_max_results"])
  if controls["web_verification_limit"] is not None:
    config["web_company"]["verification_limit"] = int(controls["web_verification_limit"])
  if controls["paper_time_range"] is not None:
    config["paper"]["time_range"] = str(controls["paper_time_range"])
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
  try:
    controls = resolve_cloud_job_controls(env)
    config = build_cloud_weekly_run_config(settings, persist_root=persist_root, environ=env)
  except RuntimeError as exc:
    return {
      "status": "blocked",
      "message": str(exc),
      "settings": settings,
      "persist_root": str(persist_root),
      "external_api_called": False,
      "smtp_called": False,
    }
  config["_run_id"] = "cloud_weekly_job_" + datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
  effective_provider_adapters = _build_cloud_provider_adapters(
    controls=controls,
    provider_adapters=provider_adapters,
  )

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

    result = run_weekly_watch(config, output_root=persist_root, provider_adapters=effective_provider_adapters)
    return {
      **dict(result or {}),
      "settings": settings,
      "persist_root": str(persist_root),
      "cloud_lock": cloud_lock_info or {},
      "cloud_job_summary": summarize_cloud_weekly_job_config(config, controls=controls),
    }
  finally:
    if cloud_lock_info and cloud_lock_info.get("acquired", False):
      release_cloud_weekly_lock(cloud_lock_info, storage_client=storage_client)


def resolve_cloud_job_controls(environ: Mapping[str, str] | None = None) -> dict[str, Any]:
  env = dict(environ or os.environ)
  errors: list[str] = []
  controls = {
    "dry_run": _parse_strict_bool(env, "V9_CLOUD_JOB_DRY_RUN", default=True, errors=errors),
    "patent_enabled": _parse_strict_bool(env, "V9_CLOUD_ENABLE_PATENT", default=False, errors=errors),
    "paper_enabled": _parse_optional_strict_bool(env, "V9_CLOUD_ENABLE_PAPER", errors=errors),
    "web_company_enabled": _parse_optional_strict_bool(env, "V9_CLOUD_ENABLE_WEB_COMPANY", errors=errors),
    "paper_approved_query_ids": _parse_query_ids(env, "V9_CLOUD_PAPER_APPROVED_QUERY_IDS", errors=errors),
    "web_approved_query_ids": _parse_query_ids(env, "V9_CLOUD_WEB_APPROVED_QUERY_IDS", errors=errors),
    "paper_max_results": _parse_limited_int(env, "V9_CLOUD_PAPER_MAX_RESULTS", minimum=1, maximum=5, errors=errors),
    "web_max_results": _parse_limited_int(env, "V9_CLOUD_WEB_MAX_RESULTS", minimum=1, maximum=2, errors=errors),
    "web_verification_limit": _parse_limited_int(env, "V9_CLOUD_WEB_VERIFICATION_LIMIT", minimum=0, maximum=1, errors=errors),
    "paper_time_range": _parse_time_range(env, "V9_CLOUD_PAPER_TIME_RANGE", errors=errors),
    "web_english_fallback": _parse_strict_bool(env, "V9_CLOUD_WEB_ENGLISH_FALLBACK", default=False, errors=errors),
    "google_grounding": _parse_strict_bool(env, "V9_CLOUD_GOOGLE_GROUNDING", default=False, errors=errors),
  }
  if errors:
    raise RuntimeError("cloud job env validation failed: " + "; ".join(errors))
  return controls


def summarize_cloud_weekly_job_config(
  config: Mapping[str, Any],
  *,
  controls: Mapping[str, Any] | None = None,
  environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
  resolved_controls = dict(controls or resolve_cloud_job_controls(environ))
  execution = dict(config.get("execution", {}) or {})
  limits = dict(config.get("limits", {}) or {})
  paper = dict(config.get("paper", {}) or {})
  web_company = dict(config.get("web_company", {}) or {})
  email = dict(config.get("email", {}) or {})
  return {
    "dry_run": bool(execution.get("dry_run", True)),
    "providers": {
      "patent_enabled": bool(execution.get("patent_enabled", False)),
      "paper_enabled": bool(execution.get("paper_enabled", False)),
      "web_company_enabled": bool(execution.get("web_company_enabled", False)),
    },
    "paper_approved_query_ids": list(paper.get("approved_query_ids", []) or []),
    "web_approved_query_ids": list(web_company.get("approved_query_ids", []) or []),
    "paper_max_results": int(limits.get("paper_max_results", 0) or 0),
    "web_max_results": int(limits.get("web_max_results", 0) or 0),
    "web_verification_limit": int(web_company.get("verification_limit", 0) or 0),
    "paper_time_range": str(paper.get("time_range", "") or ""),
    "web_english_fallback": bool(resolved_controls.get("web_english_fallback", False)),
    "google_grounding": bool(resolved_controls.get("google_grounding", False)),
    "email_send_enabled": bool(email.get("self_send_enabled", False)),
    "email_mode": str(email.get("mode", "") or ""),
  }


def _env_bool(env: Mapping[str, str], name: str, default: bool) -> bool:
  value = str(env.get(name, "") or "").strip().lower()
  if value in {"1", "true", "yes", "on"}:
    return True
  if value in {"0", "false", "no", "off"}:
    return False
  return default


def _resolve_source_enabled(source_enabled: bool, env_override: bool | None) -> bool:
  if env_override is None:
    return bool(source_enabled)
  return bool(source_enabled and env_override)


def _parse_strict_bool(
  env: Mapping[str, str],
  name: str,
  *,
  default: bool,
  errors: list[str],
) -> bool:
  raw = str(env.get(name, "") or "").strip().lower()
  if not raw:
    return default
  if raw not in STRICT_BOOL_VALUES:
    errors.append(f"{name} must be one of true,false,1,0,yes,no")
    return default
  return STRICT_BOOL_VALUES[raw]


def _parse_optional_strict_bool(
  env: Mapping[str, str],
  name: str,
  *,
  errors: list[str],
) -> bool | None:
  raw = str(env.get(name, "") or "").strip().lower()
  if not raw:
    return None
  if raw not in STRICT_BOOL_VALUES:
    errors.append(f"{name} must be one of true,false,1,0,yes,no")
    return None
  return STRICT_BOOL_VALUES[raw]


def _parse_query_ids(
  env: Mapping[str, str],
  name: str,
  *,
  errors: list[str],
) -> list[str]:
  raw = str(env.get(name, "") or "")
  if not raw.strip():
    return []
  cleaned: list[str] = []
  seen: set[str] = set()
  for part in re.split(r"[,\n;]+", raw):
    value = str(part or "").strip()
    if not value:
      continue
    if not QUERY_ID_PATTERN.fullmatch(value):
      errors.append(f"{name} has invalid query id: {value}")
      continue
    if value in seen:
      continue
    seen.add(value)
    cleaned.append(value)
  return cleaned


def _parse_limited_int(
  env: Mapping[str, str],
  name: str,
  *,
  minimum: int,
  maximum: int,
  errors: list[str],
) -> int | None:
  raw = str(env.get(name, "") or "").strip()
  if not raw:
    return None
  try:
    value = int(raw)
  except ValueError:
    errors.append(f"{name} must be an integer")
    return None
  if not (minimum <= value <= maximum):
    errors.append(f"{name} must be between {minimum} and {maximum}")
    return None
  return value


def _parse_time_range(
  env: Mapping[str, str],
  name: str,
  *,
  errors: list[str],
) -> str | None:
  raw = str(env.get(name, "") or "").strip().lower()
  if not raw:
    return None
  if raw not in ALLOWED_PAPER_TIME_RANGES:
    errors.append(f"{name} must be one of {', '.join(sorted(ALLOWED_PAPER_TIME_RANGES))}")
    return None
  return raw


def _build_cloud_provider_adapters(
  *,
  controls: Mapping[str, Any],
  provider_adapters: dict[str, Any] | None,
) -> dict[str, Any]:
  adapters = dict(provider_adapters or {})
  if "web_company" not in adapters:
    adapters["web_company"] = _build_web_company_adapter(controls)
  return adapters


def _build_web_company_adapter(controls: Mapping[str, Any]):
  def _adapter(*, search_plan: dict[str, Any], watch_profile: dict[str, Any], config: dict[str, Any], output_root: Path, weekly_run_id: str) -> dict[str, Any]:
    def _preview_builder(preview_search_plan: dict[str, Any], *, max_query_count: int | None = None, verification_limit: int = 30, summary_top_n: int = 10) -> dict[str, Any]:
      effective_plan = deepcopy(preview_search_plan)
      for country in list(effective_plan.get("global_web_plan", {}).get("countries", []) or []):
        if isinstance(country, dict):
          country["english_fallback_enabled"] = bool(controls.get("web_english_fallback", False))
      return build_global_web_retrieval_preview(
        effective_plan,
        max_query_count=max_query_count,
        verification_limit=verification_limit,
        summary_top_n=summary_top_n,
      )

    def _execute_runner(preview: dict[str, Any]) -> dict[str, Any]:
      return execute_global_web_retrieval(
        preview,
        allow_google_grounding=bool(controls.get("google_grounding", False)),
      )

    return run_web_company_provider_for_weekly(
      search_plan=search_plan,
      watch_profile=watch_profile,
      config=config,
      output_root=output_root,
      weekly_run_id=weekly_run_id,
      preview_builder=_preview_builder,
      execute_runner=_execute_runner,
    )

  return _adapter


__all__ = [
  "build_cloud_weekly_run_config",
  "resolve_cloud_job_controls",
  "run_cloud_weekly_job",
  "summarize_cloud_weekly_job_config",
]
