"""Global web discovery search plan helpers for v9."""

from __future__ import annotations

from typing import Any

from .global_web_plan_schema import (
  DEFAULT_GLOBAL_WEB_COUNTRY_CODES,
  DEFAULT_GLOBAL_WEB_INTENTS,
  GLOBAL_WEB_PLAN_SCHEMA_VERSION,
  load_global_web_country_profiles,
)
from .watch_profile_schema import migrate_watch_profile, normalize_terms

_INTENT_PRIORITY = {
  "research_development": "high",
  "investment_production": "high",
  "product_commercialization": "high",
  "partnership_project": "medium",
  "regulation_standard": "medium",
  "organization_recruitment": "low",
}

_INTENT_RESULT_BUCKET = {
  "research_development": "web",
  "investment_production": "company",
  "partnership_project": "company",
  "product_commercialization": "company",
  "organization_recruitment": "company",
  "regulation_standard": "web",
}

_INTENT_ACTIVITY_TERMS_EN = {
  "research_development": "research development",
  "investment_production": "investment production",
  "partnership_project": "partnership project",
  "product_commercialization": "product commercialization",
  "organization_recruitment": "organization recruitment",
  "regulation_standard": "regulation standard",
}


def build_global_web_search_plan(
  profile: dict[str, Any],
  web_limit: int,
  company_limit: int,
  country_profiles: list[dict[str, Any]] | None = None,
  options: dict[str, Any] | None = None,
) -> dict[str, Any]:
  migrated = migrate_watch_profile(profile or {})
  normalized_options = _normalize_global_web_options(options)
  profiles = _apply_country_settings(
    list(country_profiles or load_global_web_country_profiles()),
    normalized_options["country_settings"],
  )
  keywords = migrated["keywords"]

  english_core_terms = normalize_terms(
    keywords["core_en"][:3]
    + keywords["material_process_en"][:2]
    + keywords["application_en"][:2]
  )
  japanese_core_terms = normalize_terms(
    [str(migrated.get("theme_name", "") or "").strip()]
    + keywords["core_ja"][:3]
    + keywords["material_process_ja"][:2]
    + keywords["application_ja"][:2]
  )
  target_companies = normalize_terms(list(migrated.get("target_companies", [])))[:5]
  exclude_terms = normalize_terms(keywords["exclude_en"] + keywords["exclude_ja"])

  queries: list[dict[str, Any]] = []
  seen_dedupe_keys: dict[str, str] = {}
  query_index = 0

  for country in profiles:
    for intent in DEFAULT_GLOBAL_WEB_INTENTS:
      query_index += 1
      priority = _INTENT_PRIORITY[intent]
      result_bucket = _INTENT_RESULT_BUCKET[intent]
      query_local, query_english_fallback, local_mode, fallback_mode, generated_from = _build_country_queries(
        migrated,
        country,
        intent,
        english_core_terms,
        japanese_core_terms,
        target_companies[0] if target_companies else "",
      )
      dedupe_key = _build_dedupe_key(country["country_region_code"], intent, result_bucket, query_local, query_english_fallback)
      duplicate_of = seen_dedupe_keys.get(dedupe_key)
      if duplicate_of is None:
        seen_dedupe_keys[dedupe_key] = f"gw_q{query_index:03d}"

      country_enabled = bool(country.get("enabled", True))
      intent_enabled = bool(normalized_options["intent_settings"].get(intent, True))
      max_results = _planned_max_results(result_bucket, priority, normalized_options["max_results"])
      enabled = country_enabled and intent_enabled and priority == "high" and duplicate_of is None
      queries.append(
        {
          "query_id": f"gw_q{query_index:03d}",
          "country_region_code": country["country_region_code"],
          "web_intent": intent,
          "result_bucket": result_bucket,
          "priority": priority,
          "enabled": enabled,
          "origin": "generated",
          "query_local": query_local,
          "query_english_fallback": query_english_fallback,
          "local_query_generation_mode": local_mode,
          "fallback_execution_mode": fallback_mode,
          "provider_primary": country["provider_primary"],
          "provider_fallback": country["provider_fallback"] if country["english_fallback_enabled"] else "",
          "verification_provider": country["verification_provider"],
          "search_depth": "discovery",
          "max_results": max_results,
          "time_range": normalized_options["time_range"],
          "generated_from": generated_from,
          "exclude_terms": list(exclude_terms),
          "dedupe_key": dedupe_key,
          "duplicate_of": duplicate_of,
        }
      )

  plan = {
    "schema_version": GLOBAL_WEB_PLAN_SCHEMA_VERSION,
    "theme_name": str(migrated.get("theme_name", "") or "").strip(),
    "theme_description": str(migrated.get("theme_description", "") or "").strip(),
    "execution_enabled": False,
    "web_limit": _normalize_non_negative_limit(web_limit),
    "company_limit": _normalize_non_negative_limit(company_limit),
    "time_range": normalized_options["time_range"],
    "countries": profiles,
    "intents": list(DEFAULT_GLOBAL_WEB_INTENTS),
    "queries": queries,
    "exclude_terms": exclude_terms,
    "target_companies": target_companies,
    "provider_routing": _build_provider_routing_summary(profiles),
    "notes": [
      "Global Web 計画は Web 100件 + 企業100件の予算内で管理します。",
      "初回は high priority の discovery query のみ enabled=True とし、English fallback は結果不足時のみ実行予定です。",
      "翻訳APIや実検索APIは呼び出しません。",
    ],
  }
  plan["country_coverage"] = build_global_web_country_coverage(plan)
  plan["discovery_query_count"] = len(queries)
  plan["enabled_query_count"] = sum(1 for query in queries if query.get("enabled"))
  plan["verification_planned_count"] = sum(
    _normalize_non_negative_limit(query.get("max_results"))
    for query in queries
    if query.get("enabled")
  )
  plan["translation_planned_count"] = sum(
    1
    for query in queries
    if str(query.get("local_query_generation_mode", "") or "") == "translation_pending"
  )
  return plan


def validate_global_web_search_plan(plan: dict[str, Any]) -> list[str]:
  errors: list[str] = []
  if not isinstance(plan, dict):
    return ["Global Web検索計画の形式が不正です。"]

  if str(plan.get("schema_version", "") or "").strip() != GLOBAL_WEB_PLAN_SCHEMA_VERSION:
    errors.append("Global Web検索計画の schema_version が不正です。")
  if plan.get("execution_enabled") is not False:
    errors.append("Global Web検索計画の execution_enabled は False である必要があります。")

  web_limit = plan.get("web_limit")
  company_limit = plan.get("company_limit")
  if not isinstance(web_limit, int) or web_limit < 0:
    errors.append("Global Web検索計画の web_limit が不正です。")
    web_limit = 0
  if not isinstance(company_limit, int) or company_limit < 0:
    errors.append("Global Web検索計画の company_limit が不正です。")
    company_limit = 0

  countries = plan.get("countries")
  if not isinstance(countries, list):
    errors.append("Global Web検索計画の countries が list ではありません。")
    countries = []
  else:
    country_codes = {str(item.get("country_region_code", "") or "").strip() for item in countries if isinstance(item, dict)}
    missing = set(DEFAULT_GLOBAL_WEB_COUNTRY_CODES) - country_codes
    if missing:
      errors.append("Global Web対象国・地域が不足しています: " + ", ".join(sorted(missing)))

  queries = plan.get("queries")
  if not isinstance(queries, list):
    errors.append("Global Web検索計画の queries が list ではありません。")
    return errors

  seen_ids: set[str] = set()
  enabled_high_count = 0
  enabled_web_results = 0
  enabled_company_results = 0
  for query in queries:
    if not isinstance(query, dict):
      errors.append("Global Web検索クエリ形式が不正です。")
      continue
    query_id = str(query.get("query_id", "") or "").strip()
    if not query_id:
      errors.append("Global Web検索クエリに query_id がありません。")
    elif query_id in seen_ids:
      errors.append(f"{query_id} が重複しています。")
    else:
      seen_ids.add(query_id)

    for field in (
      "country_region_code",
      "web_intent",
      "result_bucket",
      "priority",
      "query_local",
      "local_query_generation_mode",
      "provider_primary",
      "verification_provider",
      "search_depth",
      "dedupe_key",
    ):
      if not str(query.get(field, "") or "").strip():
        errors.append(f"{query_id or 'unknown'} の {field} が空です。")

    if query.get("enabled") and query.get("priority") != "high":
      errors.append(f"{query_id or 'unknown'} は high 以外で enabled になっています。")

    if query.get("enabled"):
      enabled_high_count += 1
      if query.get("result_bucket") == "web":
        enabled_web_results += _normalize_non_negative_limit(query.get("max_results"))
      elif query.get("result_bucket") == "company":
        enabled_company_results += _normalize_non_negative_limit(query.get("max_results"))

  if enabled_high_count < 25 or enabled_high_count > 35:
    errors.append("Global Web検索計画の初期 enabled query 数が想定範囲外です。")
  if enabled_web_results > web_limit:
    errors.append("Global Web検索計画の enabled web 件数が web_limit を超えています。")
  if enabled_company_results > company_limit:
    errors.append("Global Web検索計画の enabled company 件数が company_limit を超えています。")

  return errors


def summarize_global_web_search_plan_ja(plan: dict[str, Any]) -> str:
  coverage = build_global_web_country_coverage(plan)
  query_count = len(plan.get("queries", []) or [])
  enabled_count = sum(1 for query in plan.get("queries", []) or [] if query.get("enabled"))
  lines = [
    "Global Web検索計画",
    "",
    f"- 対象国・地域: {len(coverage)}",
    f"- 生成クエリ数: {query_count}",
    f"- 初期有効クエリ数: {enabled_count}",
    f"- Web予算: {int(plan.get('web_limit', 0) or 0)}件",
    f"- 企業予算: {int(plan.get('company_limit', 0) or 0)}件",
    "- 初回は high priority discovery query のみ有効です。",
    "- English fallback は結果不足時のみ実行予定です。",
  ]
  return "\n".join(lines)


def build_global_web_country_coverage(plan: dict[str, Any]) -> list[dict[str, Any]]:
  countries = plan.get("countries", []) if isinstance(plan, dict) else []
  queries = plan.get("queries", []) if isinstance(plan, dict) else []
  coverage_rows: list[dict[str, Any]] = []
  for country in countries:
    if not isinstance(country, dict):
      continue
    code = str(country.get("country_region_code", "") or "").strip()
    country_queries = [query for query in queries if str(query.get("country_region_code", "") or "").strip() == code]
    enabled_queries = [query for query in country_queries if query.get("enabled")]
    coverage_rows.append(
      {
        "country_region_code": code,
        "country_region_name_ja": str(country.get("country_region_name_ja", "") or "").strip(),
        "priority": int(country.get("priority", 0) or 0),
        "enabled": bool(country.get("enabled", True)),
        "primary_language": str(country.get("primary_language", "") or "").strip(),
        "locale": str(country.get("locale", "") or "").strip(),
        "query_count": len(country_queries),
        "enabled_query_count": len(enabled_queries),
        "web_query_count": sum(1 for query in country_queries if query.get("result_bucket") == "web"),
        "company_query_count": sum(1 for query in country_queries if query.get("result_bucket") == "company"),
        "preferred_domains": list(country.get("preferred_domains", [])),
        "excluded_domains": list(country.get("excluded_domains", [])),
        "official_source_priority": bool(country.get("official_source_priority", False)),
      }
    )
  return coverage_rows


def build_global_web_plan_validation_rows(plan: dict[str, Any]) -> list[dict[str, str]]:
  errors = validate_global_web_search_plan(plan)
  if not errors:
    return [{"status": "ok", "message": "validation passed"}]
  return [
    {"status": "error", "message": error}
    for error in errors
  ]


def _build_country_queries(
  profile: dict[str, Any],
  country: dict[str, Any],
  intent: str,
  english_core_terms: list[str],
  japanese_core_terms: list[str],
  target_company_anchor: str,
) -> tuple[str, str, str, str, list[str]]:
  theme_name = str(profile.get("theme_name", "") or "").strip()
  primary_language = str(country.get("primary_language", "") or "").strip().lower()
  local_activity_term = str(country.get("local_activity_terms", {}).get(intent, "") or "").strip()
  english_activity_term = _INTENT_ACTIVITY_TERMS_EN[intent]
  company_anchor = target_company_anchor.strip() if _INTENT_RESULT_BUCKET[intent] == "company" else ""

  if primary_language == "ja":
    local_terms = _select_terms_for_intent(intent, japanese_core_terms or english_core_terms, theme_name, company_anchor)
    query_local = _build_space_query(local_terms + [local_activity_term])
    query_english_fallback = _build_space_query(_select_terms_for_intent(intent, english_core_terms, "", company_anchor) + [english_activity_term])
    return query_local, query_english_fallback, "native_ja", "result_shortage_only", [
      "theme_name",
      "keywords.core_ja",
      "keywords.material_process_ja",
      "keywords.application_ja",
      *(
        ["target_companies"]
        if company_anchor
        else []
      ),
      f"local_activity_terms.{intent}",
    ]

  if primary_language == "en":
    local_terms = _select_terms_for_intent(
      intent,
      english_core_terms,
      theme_name if _contains_ascii_letter(theme_name) else "",
      company_anchor,
    )
    query_local = _build_space_query(local_terms + [local_activity_term or english_activity_term])
    return query_local, "", "native_en", "not_applicable", [
      "theme_name",
      "keywords.core_en",
      "keywords.material_process_en",
      "keywords.application_en",
      *(
        ["target_companies"]
        if company_anchor
        else []
      ),
      f"local_activity_terms.{intent}",
    ]

  local_terms = _select_terms_for_intent(
    intent,
    english_core_terms,
    theme_name if _contains_ascii_letter(theme_name) else "",
    company_anchor,
  )
  query_local = _build_space_query(local_terms + [local_activity_term])
  query_english_fallback = _build_space_query(local_terms + [english_activity_term])
  return query_local, query_english_fallback, "translation_pending", "result_shortage_only", [
    "keywords.core_en",
    "keywords.material_process_en",
    "keywords.application_en",
    *(
      ["target_companies"]
      if company_anchor
      else []
    ),
    f"local_activity_terms.{intent}",
  ]


def _select_terms_for_intent(intent: str, base_terms: list[str], anchor: str, company_anchor: str) -> list[str]:
  terms = []
  if anchor.strip():
    terms.append(anchor.strip())
  if company_anchor.strip():
    terms.append(company_anchor.strip())
  if intent in {"research_development", "regulation_standard"}:
    terms.extend(base_terms[:3])
  elif intent in {"investment_production", "product_commercialization"}:
    terms.extend(base_terms[:2] + base_terms[3:4])
  elif intent == "partnership_project":
    terms.extend(base_terms[:2] + base_terms[4:5])
  else:
    terms.extend(base_terms[:2])
  return normalize_terms(terms)[:4]


def _build_space_query(terms: list[str]) -> str:
  cleaned = normalize_terms([str(term or "").strip() for term in terms])
  return " ".join(cleaned)


def _build_dedupe_key(
  country_code: str,
  intent: str,
  result_bucket: str,
  query_local: str,
  query_english_fallback: str,
) -> str:
  return "|".join(
    [
      str(country_code or "").strip().upper(),
      str(intent or "").strip(),
      str(result_bucket or "").strip(),
      str(query_local or "").strip().lower(),
      str(query_english_fallback or "").strip().lower(),
    ]
  )


def _contains_ascii_letter(value: str) -> bool:
  return any("A" <= char <= "Z" or "a" <= char <= "z" for char in str(value or ""))


def _normalize_non_negative_limit(value: Any) -> int:
  if isinstance(value, bool):
    return 0
  try:
    normalized = int(value)
  except (TypeError, ValueError):
    return 0
  return max(normalized, 0)


def _planned_max_results(result_bucket: str, priority: str, max_results_settings: dict[str, int] | None = None) -> int:
  settings = max_results_settings or {}
  setting_key = f"{result_bucket}_{priority}"
  configured = _normalize_non_negative_limit(settings.get(setting_key))
  if configured > 0:
    return configured
  if result_bucket == "web":
    if priority == "high":
      return 10
    if priority == "medium":
      return 4
    return 2
  if priority == "high":
    return 5
  if priority == "medium":
    return 4
  return 2


def _normalize_global_web_options(options: dict[str, Any] | None) -> dict[str, Any]:
  payload = dict(options or {})
  intent_settings_raw = payload.get("intent_settings", {})
  country_settings_raw = payload.get("country_settings", {})
  max_results_raw = payload.get("max_results", {})
  intent_settings = {
    intent: bool(intent_settings_raw.get(intent, True))
    for intent in DEFAULT_GLOBAL_WEB_INTENTS
  } if isinstance(intent_settings_raw, dict) else {
    intent: True for intent in DEFAULT_GLOBAL_WEB_INTENTS
  }
  max_results = {
    "web_high": _positive_or_default(max_results_raw, "web_high", 10),
    "web_medium": _positive_or_default(max_results_raw, "web_medium", 4),
    "web_low": _positive_or_default(max_results_raw, "web_low", 2),
    "company_high": _positive_or_default(max_results_raw, "company_high", 5),
    "company_medium": _positive_or_default(max_results_raw, "company_medium", 4),
    "company_low": _positive_or_default(max_results_raw, "company_low", 2),
  } if isinstance(max_results_raw, dict) else {
    "web_high": 10,
    "web_medium": 4,
    "web_low": 2,
    "company_high": 5,
    "company_medium": 4,
    "company_low": 2,
  }
  country_settings = country_settings_raw if isinstance(country_settings_raw, dict) else {}
  return {
    "time_range": str(payload.get("time_range", "12m") or "12m").strip() or "12m",
    "intent_settings": intent_settings,
    "country_settings": country_settings,
    "max_results": max_results,
  }


def _apply_country_settings(
  profiles: list[dict[str, Any]],
  country_settings: dict[str, Any],
) -> list[dict[str, Any]]:
  updated_profiles: list[dict[str, Any]] = []
  for profile in profiles:
    code = str(profile.get("country_region_code", "") or "").strip().upper()
    overrides = country_settings.get(code, {})
    if not isinstance(overrides, dict):
      overrides = {}
    updated = dict(profile)
    updated["enabled"] = bool(overrides.get("enabled", True))
    updated["priority"] = _positive_or_default(overrides, "priority", int(profile.get("priority", 0) or 0))
    updated["official_source_priority"] = bool(overrides.get("official_source_priority", profile.get("official_source_priority", False)))
    updated["english_fallback_enabled"] = bool(
      overrides.get("english_fallback_enabled", profile.get("english_fallback_enabled", False))
    )
    updated_profiles.append(updated)
  updated_profiles.sort(key=lambda item: (int(item.get("priority", 0) or 0), str(item.get("country_region_code", "") or "")))
  return updated_profiles


def _build_provider_routing_summary(profiles: list[dict[str, Any]]) -> list[dict[str, str]]:
  rows: list[dict[str, str]] = []
  for country in profiles:
    rows.append(
      {
        "country_region_code": str(country.get("country_region_code", "") or "").strip(),
        "provider_primary": str(country.get("provider_primary", "") or "").strip(),
        "provider_fallback": str(country.get("provider_fallback", "") or "").strip(),
        "verification_provider": str(country.get("verification_provider", "") or "").strip(),
      }
    )
  return rows


def _positive_or_default(values: dict[str, Any], key: str, default: int) -> int:
  normalized = _normalize_non_negative_limit(values.get(key))
  return normalized if normalized > 0 else default


__all__ = [
  "build_global_web_country_coverage",
  "build_global_web_plan_validation_rows",
  "build_global_web_search_plan",
  "summarize_global_web_search_plan_ja",
  "validate_global_web_search_plan",
]
