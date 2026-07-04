"""Weekly scheduler config helpers for v9."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from .persistence import PROJECT_ROOT

WEEKLY_RUN_CONFIG_SCHEMA_VERSION = "v9.6b"
VALID_EMAIL_MODES = {"preview", "self_only"}
VALID_WEEKDAYS = {"MON", "TUE", "WED", "THU", "FRI", "SAT", "SUN"}
DEFAULT_WATCH_PROFILE_PATH = "data/demo/v9_demo_watch_profile.json"


def default_weekly_run_config() -> dict[str, Any]:
  return {
    "schema_version": WEEKLY_RUN_CONFIG_SCHEMA_VERSION,
    "enabled": False,
    "watch_profile_path": DEFAULT_WATCH_PROFILE_PATH,
    "execution": {
      "dry_run": True,
      "patent_enabled": False,
      "paper_enabled": False,
      "web_company_enabled": False,
      "stage_retry_limit": 0,
    },
    "limits": {
      "patent_max_results": 500,
      "paper_max_results": 300,
      "web_max_results": 100,
      "company_max_results": 100,
    },
    "patent": {
      "approved_query_ids": [],
      "maximum_bytes_billed": 0,
      "time_range": "12m",
    },
    "paper": {
      "approved_query_ids": [],
      "time_range": "12m",
      "per_page": 25,
      "retry_limit": 2,
      "polite_email": "",
    },
    "web_company": {
      "approved_query_ids": [],
      "max_query_count": 30,
      "verification_limit": 30,
      "summary_top_n": 10,
    },
    "email": {
      "mode": "preview",
      "self_send_enabled": False,
    },
    "schedule": {
      "timezone": "Asia/Tokyo",
      "day_of_week": "MON",
      "hour": 8,
      "minute": 0,
    },
    "timeouts": {
      "patent_seconds": 1200,
      "paper_seconds": 1200,
      "web_company_seconds": 1200,
      "email_seconds": 120,
      "lock_stale_seconds": 21600,
    },
  }


def load_weekly_run_config(path: Path | str) -> dict[str, Any]:
  resolved = resolve_project_path(path)
  try:
    raw = json.loads(resolved.read_text(encoding="utf-8"))
  except FileNotFoundError as exc:
    raise RuntimeError(f"weekly run config が見つかりません: {resolved}") from exc
  except json.JSONDecodeError as exc:
    raise RuntimeError(f"weekly run config の JSON 読み込みに失敗しました: {resolved} ({exc})") from exc
  except OSError as exc:
    raise RuntimeError(f"weekly run config を読み込めませんでした: {resolved} ({exc})") from exc
  if not isinstance(raw, dict):
    raise RuntimeError("weekly run config の形式が不正です。")
  merged = _deep_merge(default_weekly_run_config(), raw)
  merged["_config_path"] = str(resolved)
  return merged


def validate_weekly_run_config(config: dict[str, Any]) -> dict[str, Any]:
  merged = _deep_merge(default_weekly_run_config(), dict(config or {}))
  errors: list[str] = []
  warnings: list[str] = []

  if str(merged.get("schema_version", "") or "").strip() != WEEKLY_RUN_CONFIG_SCHEMA_VERSION:
    warnings.append(f"schema_version が `{WEEKLY_RUN_CONFIG_SCHEMA_VERSION}` ではありません。")

  merged["enabled"] = bool(merged.get("enabled", False))
  merged["watch_profile_path"] = str(merged.get("watch_profile_path", DEFAULT_WATCH_PROFILE_PATH) or "").strip()
  if not merged["watch_profile_path"]:
    errors.append("watch_profile_path が未設定です。")

  execution = dict(merged.get("execution", {}) or {})
  execution["dry_run"] = bool(execution.get("dry_run", True))
  execution["patent_enabled"] = bool(execution.get("patent_enabled", False))
  execution["paper_enabled"] = bool(execution.get("paper_enabled", False))
  execution["web_company_enabled"] = bool(execution.get("web_company_enabled", False))
  execution["stage_retry_limit"] = min(max(_safe_int(execution.get("stage_retry_limit", 0), 0), 0), 1)
  merged["execution"] = execution

  limits = dict(merged.get("limits", {}) or {})
  limits["patent_max_results"] = max(_safe_int(limits.get("patent_max_results", 500), 500), 0)
  limits["paper_max_results"] = max(_safe_int(limits.get("paper_max_results", 300), 300), 0)
  limits["web_max_results"] = max(_safe_int(limits.get("web_max_results", 100), 100), 0)
  limits["company_max_results"] = max(_safe_int(limits.get("company_max_results", 100), 100), 0)
  merged["limits"] = limits

  patent = dict(merged.get("patent", {}) or {})
  patent["approved_query_ids"] = _normalize_string_list(patent.get("approved_query_ids", []))
  patent["maximum_bytes_billed"] = max(_safe_int(patent.get("maximum_bytes_billed", 0), 0), 0)
  patent["time_range"] = str(patent.get("time_range", "12m") or "12m").strip() or "12m"
  merged["patent"] = patent

  paper = dict(merged.get("paper", {}) or {})
  paper["approved_query_ids"] = _normalize_string_list(paper.get("approved_query_ids", []))
  paper["time_range"] = str(paper.get("time_range", "12m") or "12m").strip().lower() or "12m"
  paper["per_page"] = max(_safe_int(paper.get("per_page", 25), 25), 1)
  paper["retry_limit"] = min(max(_safe_int(paper.get("retry_limit", 2), 2), 0), 5)
  paper["polite_email"] = str(paper.get("polite_email", "") or "").strip()
  merged["paper"] = paper

  web_company = dict(merged.get("web_company", {}) or {})
  web_company["approved_query_ids"] = _normalize_string_list(web_company.get("approved_query_ids", []))
  web_company["max_query_count"] = max(_safe_int(web_company.get("max_query_count", 30), 30), 1)
  web_company["verification_limit"] = max(_safe_int(web_company.get("verification_limit", 30), 30), 1)
  web_company["summary_top_n"] = max(_safe_int(web_company.get("summary_top_n", 10), 10), 1)
  merged["web_company"] = web_company

  email = dict(merged.get("email", {}) or {})
  email["mode"] = str(email.get("mode", "preview") or "preview").strip().lower()
  email["self_send_enabled"] = bool(email.get("self_send_enabled", False))
  merged["email"] = email
  if email["mode"] not in VALID_EMAIL_MODES:
    errors.append("email.mode は `preview` または `self_only` である必要があります。")
  if email["self_send_enabled"] and email["mode"] != "self_only":
    errors.append("email.self_send_enabled=true の場合は email.mode=self_only が必要です。")

  schedule = dict(merged.get("schedule", {}) or {})
  schedule["timezone"] = str(schedule.get("timezone", "Asia/Tokyo") or "Asia/Tokyo").strip() or "Asia/Tokyo"
  schedule["day_of_week"] = str(schedule.get("day_of_week", "MON") or "MON").strip().upper()
  schedule["hour"] = _safe_int(schedule.get("hour", 8), 8)
  schedule["minute"] = _safe_int(schedule.get("minute", 0), 0)
  merged["schedule"] = schedule
  if schedule["day_of_week"] not in VALID_WEEKDAYS:
    errors.append("schedule.day_of_week が不正です。")
  if not (0 <= schedule["hour"] <= 23):
    errors.append("schedule.hour は 0-23 の範囲である必要があります。")
  if not (0 <= schedule["minute"] <= 59):
    errors.append("schedule.minute は 0-59 の範囲である必要があります。")

  timeouts = dict(merged.get("timeouts", {}) or {})
  timeouts["patent_seconds"] = max(_safe_int(timeouts.get("patent_seconds", 1200), 1200), 1)
  timeouts["paper_seconds"] = max(_safe_int(timeouts.get("paper_seconds", 1200), 1200), 1)
  timeouts["web_company_seconds"] = max(_safe_int(timeouts.get("web_company_seconds", 1200), 1200), 1)
  timeouts["email_seconds"] = max(_safe_int(timeouts.get("email_seconds", 120), 120), 1)
  raw_lock_stale_seconds = _safe_int(timeouts.get("lock_stale_seconds", 21600), 21600)
  if raw_lock_stale_seconds <= 0:
    errors.append("timeouts.lock_stale_seconds は 1 以上の整数である必要があります。")
    timeouts["lock_stale_seconds"] = 21600
  elif raw_lock_stale_seconds < 60:
    errors.append("timeouts.lock_stale_seconds は 60 秒以上である必要があります。")
    timeouts["lock_stale_seconds"] = raw_lock_stale_seconds
  else:
    timeouts["lock_stale_seconds"] = raw_lock_stale_seconds
  merged["timeouts"] = timeouts

  if not execution["dry_run"] and execution["patent_enabled"]:
    if not patent["approved_query_ids"]:
      errors.append("patent_enabled=true で dry_run=false の場合は approved_query_ids が必要です。")
    if patent["maximum_bytes_billed"] <= 0:
      errors.append("patent_enabled=true で dry_run=false の場合は maximum_bytes_billed が必要です。")
  if not execution["dry_run"] and execution["paper_enabled"] and not paper["approved_query_ids"]:
    errors.append("paper_enabled=true で dry_run=false の場合は approved_query_ids が必要です。")
  if not execution["dry_run"] and execution["web_company_enabled"] and not web_company["approved_query_ids"]:
    errors.append("web_company_enabled=true で dry_run=false の場合は approved_query_ids が必要です。")

  if execution["dry_run"]:
    warnings.append("dry_run=true のため、外部API実行とメール送信は行いません。")
  if not merged["enabled"]:
    warnings.append("enabled=false のため、Scheduler実行は blocked になります。")

  return {
    "status": "ok" if not errors else "blocked",
    "errors": errors,
    "warnings": warnings,
    "normalized_config": merged,
  }


def sanitize_weekly_run_config(config: dict[str, Any]) -> dict[str, Any]:
  sanitized = deepcopy(dict(config or {}))
  sanitized.pop("_config_path", None)
  return sanitized


def resolve_project_path(path: Path | str) -> Path:
  requested = Path(str(path or "").strip())
  if not str(requested):
    raise RuntimeError("path が未設定です。")
  if requested.is_absolute():
    return requested.resolve()
  resolved = (PROJECT_ROOT / requested).resolve()
  if PROJECT_ROOT.resolve() not in {resolved, *resolved.parents}:
    raise RuntimeError(f"許可範囲外の相対 path です: {path}")
  return resolved


def _deep_merge(base: dict[str, Any], override: dict[str, Any]) -> dict[str, Any]:
  merged = deepcopy(base)
  for key, value in dict(override or {}).items():
    if isinstance(value, dict) and isinstance(merged.get(key), dict):
      merged[key] = _deep_merge(dict(merged.get(key, {}) or {}), value)
    else:
      merged[key] = deepcopy(value)
  return merged


def _normalize_string_list(values: Any) -> list[str]:
  return [
    str(item or "").strip()
    for item in list(values or [])
    if str(item or "").strip()
  ]


def _safe_int(value: Any, default: int) -> int:
  try:
    return int(value)
  except (TypeError, ValueError):
    return default


__all__ = [
  "DEFAULT_WATCH_PROFILE_PATH",
  "VALID_EMAIL_MODES",
  "VALID_WEEKDAYS",
  "WEEKLY_RUN_CONFIG_SCHEMA_VERSION",
  "default_weekly_run_config",
  "load_weekly_run_config",
  "resolve_project_path",
  "sanitize_weekly_run_config",
  "validate_weekly_run_config",
]
