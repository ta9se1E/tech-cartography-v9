"""Schema helpers for the v9 global web search plan."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
COUNTRY_PROFILES_PATH = PROJECT_ROOT / "config" / "v9_global_web_country_profiles.json"

GLOBAL_WEB_PLAN_SCHEMA_VERSION = "v9.5a1-global-web"
DEFAULT_GLOBAL_WEB_COUNTRY_CODES = (
  "JP",
  "US",
  "CN",
  "DE",
  "KR",
  "TW",
  "GB",
  "FR",
  "IN",
  "NL",
)
DEFAULT_GLOBAL_WEB_INTENTS = (
  "research_development",
  "investment_production",
  "partnership_project",
  "product_commercialization",
  "organization_recruitment",
  "regulation_standard",
)


def load_global_web_country_profiles() -> list[dict[str, Any]]:
  payload = json.loads(COUNTRY_PROFILES_PATH.read_text(encoding="utf-8"))
  if not isinstance(payload, list):
    raise RuntimeError("Global Web country profile config must be a list.")
  profiles = [_normalize_country_profile(item) for item in payload if isinstance(item, dict)]
  profiles.sort(key=lambda item: (int(item["priority"]), str(item["country_region_code"])))
  return profiles


def build_country_profile_map() -> dict[str, dict[str, Any]]:
  return {
    str(profile["country_region_code"]): profile
    for profile in load_global_web_country_profiles()
  }


def validate_country_profiles(profiles: list[dict[str, Any]]) -> list[str]:
  errors: list[str] = []
  seen_codes: set[str] = set()
  for profile in profiles:
    code = str(profile.get("country_region_code", "") or "").strip()
    if not code:
      errors.append("country_region_code が空の国設定があります。")
      continue
    if code in seen_codes:
      errors.append(f"{code} の国設定が重複しています。")
    seen_codes.add(code)
    for field in (
      "country_region_name_ja",
      "primary_language",
      "fallback_language",
      "locale",
      "provider_primary",
      "provider_fallback",
      "verification_provider",
    ):
      if not str(profile.get(field, "") or "").strip():
        errors.append(f"{code} の {field} が未設定です。")
    if not isinstance(profile.get("priority"), int) or int(profile["priority"]) <= 0:
      errors.append(f"{code} の priority が不正です。")
    for list_field in ("preferred_domains", "excluded_domains"):
      if not isinstance(profile.get(list_field), list):
        errors.append(f"{code} の {list_field} は list である必要があります。")
    local_terms = profile.get("local_activity_terms")
    if not isinstance(local_terms, dict):
      errors.append(f"{code} の local_activity_terms は dict である必要があります。")
    else:
      for intent in DEFAULT_GLOBAL_WEB_INTENTS:
        if not str(local_terms.get(intent, "") or "").strip():
          errors.append(f"{code} の {intent} 用 local_activity_terms が未設定です。")
  expected_codes = set(DEFAULT_GLOBAL_WEB_COUNTRY_CODES)
  missing = expected_codes - seen_codes
  if missing:
    errors.append("対象国・地域設定が不足しています: " + ", ".join(sorted(missing)))
  return errors


def _normalize_country_profile(profile: dict[str, Any]) -> dict[str, Any]:
  local_terms_raw = profile.get("local_activity_terms", {})
  local_terms = {}
  if isinstance(local_terms_raw, dict):
    for intent in DEFAULT_GLOBAL_WEB_INTENTS:
      local_terms[intent] = str(local_terms_raw.get(intent, "") or "").strip()

  return {
    "country_region_code": str(profile.get("country_region_code", "") or "").strip().upper(),
    "country_region_name_ja": str(profile.get("country_region_name_ja", "") or "").strip(),
    "primary_language": str(profile.get("primary_language", "") or "").strip().lower(),
    "fallback_language": str(profile.get("fallback_language", "") or "").strip().lower(),
    "locale": str(profile.get("locale", "") or "").strip(),
    "priority": int(profile.get("priority", 0) or 0),
    "preferred_domains": [str(item or "").strip() for item in list(profile.get("preferred_domains", [])) if str(item or "").strip()],
    "excluded_domains": [str(item or "").strip() for item in list(profile.get("excluded_domains", [])) if str(item or "").strip()],
    "local_activity_terms": local_terms,
    "english_fallback_enabled": bool(profile.get("english_fallback_enabled", False)),
    "official_source_priority": bool(profile.get("official_source_priority", False)),
    "provider_primary": str(profile.get("provider_primary", "") or "").strip(),
    "provider_fallback": str(profile.get("provider_fallback", "") or "").strip(),
    "verification_provider": str(profile.get("verification_provider", "") or "").strip(),
  }


__all__ = [
  "COUNTRY_PROFILES_PATH",
  "DEFAULT_GLOBAL_WEB_COUNTRY_CODES",
  "DEFAULT_GLOBAL_WEB_INTENTS",
  "GLOBAL_WEB_PLAN_SCHEMA_VERSION",
  "build_country_profile_map",
  "load_global_web_country_profiles",
  "validate_country_profiles",
]
