"""Controlled manual external API operation config (Phase 25T)."""

from __future__ import annotations

import os

from tech_cartography.runtime.api_secret_config import is_secret_present
from tech_cartography.runtime.cloud_run_config import is_external_api_disabled

ENABLE_MANUAL_WEB_SIGNAL_COLLECTION_ENV = "ENABLE_MANUAL_WEB_SIGNAL_COLLECTION"
WEB_SIGNAL_COLLECTION_CONFIRMATION_ENV = "WEB_SIGNAL_COLLECTION_CONFIRMATION"
WEB_SIGNAL_MAX_QUERIES_ENV = "WEB_SIGNAL_MAX_QUERIES"
WEB_SIGNAL_MAX_RESULTS_PER_QUERY_ENV = "WEB_SIGNAL_MAX_RESULTS_PER_QUERY"
WEB_SIGNAL_ALLOWLIST_DOMAINS_ENV = "WEB_SIGNAL_ALLOWLIST_DOMAINS"
WEB_SIGNAL_BLOCKLIST_DOMAINS_ENV = "WEB_SIGNAL_BLOCKLIST_DOMAINS"
WEB_SIGNAL_REQUIRE_ACTIVE_WATCH_PROFILE_ENV = "WEB_SIGNAL_REQUIRE_ACTIVE_WATCH_PROFILE"

DEFAULT_COLLECTION_CONFIRMATION = "COLLECT WEB SIGNALS"
DEFAULT_MAX_QUERIES = 3
DEFAULT_MAX_RESULTS_PER_QUERY = 5
ABSOLUTE_MAX_QUERIES = 10
ABSOLUTE_MAX_RESULTS_PER_QUERY = 10


def _env(name: str) -> str:
  return str(os.environ.get(name, "") or "").strip()


def _truthy(raw: str) -> bool:
  return raw.strip().lower() in {"1", "true", "yes", "on"}


def is_manual_web_signal_collection_enabled() -> bool:
  return _truthy(_env(ENABLE_MANUAL_WEB_SIGNAL_COLLECTION_ENV))


def get_web_signal_collection_confirmation_text() -> str:
  return _env(WEB_SIGNAL_COLLECTION_CONFIRMATION_ENV) or DEFAULT_COLLECTION_CONFIRMATION


def get_web_signal_max_queries() -> int:
  raw = _env(WEB_SIGNAL_MAX_QUERIES_ENV) or str(DEFAULT_MAX_QUERIES)
  try:
    parsed = int(raw)
  except (TypeError, ValueError):
    parsed = DEFAULT_MAX_QUERIES
  return max(1, min(ABSOLUTE_MAX_QUERIES, parsed))


def get_web_signal_max_results_per_query() -> int:
  raw = _env(WEB_SIGNAL_MAX_RESULTS_PER_QUERY_ENV) or str(DEFAULT_MAX_RESULTS_PER_QUERY)
  try:
    parsed = int(raw)
  except (TypeError, ValueError):
    parsed = DEFAULT_MAX_RESULTS_PER_QUERY
  return max(1, min(ABSOLUTE_MAX_RESULTS_PER_QUERY, parsed))


def _parse_domain_list(raw: str) -> list[str]:
  if not raw:
    return []
  return [part.strip().lower() for part in raw.replace("\n", ",").split(",") if part.strip()]


def get_web_signal_allowlist_domains() -> list[str]:
  return _parse_domain_list(_env(WEB_SIGNAL_ALLOWLIST_DOMAINS_ENV))


def get_web_signal_blocklist_domains() -> list[str]:
  return _parse_domain_list(_env(WEB_SIGNAL_BLOCKLIST_DOMAINS_ENV))


def is_active_watch_profile_required() -> bool:
  raw = _env(WEB_SIGNAL_REQUIRE_ACTIVE_WATCH_PROFILE_ENV)
  if not raw:
    return True
  return _truthy(raw)


def is_tavily_secret_configured() -> bool:
  return is_secret_present("TAVILY_API_KEY")


def evaluate_manual_web_signal_collection(
  *,
  login_required: bool,
  is_authenticated: bool,
  auth_role: str,
  confirm_text: str,
  has_active_watch_profile: bool,
) -> tuple[bool, str | None, bool]:
  """Return (allowed, skipped_reason, confirmation_matched)."""
  expected = get_web_signal_collection_confirmation_text()
  confirmation_matched = str(confirm_text or "") == expected

  if is_external_api_disabled():
    return False, "external_api_disabled", confirmation_matched
  if not is_manual_web_signal_collection_enabled():
    return False, "manual_collection_disabled", confirmation_matched
  if login_required and not is_authenticated:
    return False, "login_required", confirmation_matched
  if login_required and str(auth_role or "member") != "admin":
    return False, "admin_required", confirmation_matched
  if not confirmation_matched:
    return False, "confirm_text_mismatch", confirmation_matched
  if is_active_watch_profile_required() and not has_active_watch_profile:
    return False, "active_watch_profile_required", confirmation_matched
  if not is_tavily_secret_configured():
    return False, "missing_tavily_key", confirmation_matched
  return True, None, confirmation_matched


def describe_external_api_collection_runtime() -> dict[str, object]:
  return {
    "disable_external_api": is_external_api_disabled(),
    "enable_manual_web_signal_collection": is_manual_web_signal_collection_enabled(),
    "web_signal_max_queries": get_web_signal_max_queries(),
    "web_signal_max_results_per_query": get_web_signal_max_results_per_query(),
    "require_active_watch_profile": is_active_watch_profile_required(),
    "tavily_secret_configured": is_tavily_secret_configured(),
    "collection_confirmation_text": get_web_signal_collection_confirmation_text(),
  }


def skipped_reason_message(reason: str | None) -> str:
  mapping = {
    "external_api_disabled": "外部API停止中（DISABLE_EXTERNAL_API=true）です。",
    "manual_collection_disabled": "手動収集は無効です（ENABLE_MANUAL_WEB_SIGNAL_COLLECTION=false）。",
    "login_required": "ログイン後に実行できます。",
    "admin_required": "管理者のみ実行できます。",
    "confirm_text_mismatch": "確認文が一致していません。",
    "active_watch_profile_required": "active Watch Profile が必要です。",
    "missing_tavily_key": "Tavily search key is not configured.",
    "no_queries": "Watch Profile に検索クエリがありません。",
  }
  return mapping.get(str(reason or ""), "Web Signal 収集を実行できません。")
