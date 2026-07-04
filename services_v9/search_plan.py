"""Unified search plan helpers for the lightweight v9 signal watch app."""

from __future__ import annotations

from typing import Any

from .watch_profile_schema import migrate_watch_profile, normalize_terms

DEFAULT_TOTAL_LIMIT = 1000

DEFAULT_SOURCE_LIMITS = {
  "patent": 500,
  "paper": 300,
  "web": 100,
  "company": 100,
}

_PLAN_SCHEMA_VERSION = "v9.5a1"
_SOURCE_ORDER = ("patent", "paper", "web", "company")
_MAX_TOTAL_LIMIT = 5000
_MAX_QUERY_TERMS = 6
_PATENT_MAX_QUERIES = 12
_PAPER_MAX_QUERIES = 12
_WEB_MAX_QUERIES = 10
_COMPANY_MAX_QUERIES = 10


def normalize_total_limit(value: Any) -> int:
  if isinstance(value, bool):
    return DEFAULT_TOTAL_LIMIT
  try:
    normalized = int(value)
  except (TypeError, ValueError):
    return DEFAULT_TOTAL_LIMIT
  if normalized <= 0:
    return DEFAULT_TOTAL_LIMIT
  return min(max(normalized, 1), _MAX_TOTAL_LIMIT)


def normalize_source_limits(
  total_limit: int,
  source_limits: dict[str, Any] | None = None,
) -> dict[str, int]:
  normalized_total = normalize_total_limit(total_limit)
  weights = _normalize_source_limit_weights(source_limits)
  if sum(weights.values()) <= 0:
    weights = dict(DEFAULT_SOURCE_LIMITS)

  weight_total = sum(weights.values())
  scaled = {
    source: int(normalized_total * weights[source] / weight_total)
    for source in _SOURCE_ORDER
  }
  diff = normalized_total - sum(scaled.values())
  scaled["patent"] += diff
  return {source: int(max(scaled[source], 0)) for source in _SOURCE_ORDER}


def batch_terms(
  terms: list[str],
  batch_size: int = 6,
  max_batches: int = 8,
) -> list[list[str]]:
  if max_batches <= 0:
    return []
  size = max(int(batch_size), 1)
  cleaned = normalize_terms([str(term or "").strip() for term in list(terms)])
  if not cleaned:
    return []

  batches: list[list[str]] = []
  for start in range(0, len(cleaned), size):
    if len(batches) >= max_batches:
      break
    batch = cleaned[start:start + size]
    if batch:
      batches.append(batch)
  return batches


def build_patent_search_plan(
  profile: dict[str, Any],
  limit: int,
) -> dict[str, Any]:
  migrated = _migrated_profile(profile)
  keywords = migrated["keywords"]
  theme_name = str(migrated.get("theme_name", "") or "").strip()
  exclude_terms = normalize_terms(keywords["exclude_en"] + keywords["exclude_ja"])
  seed_publications = normalize_terms(
    list(migrated.get("seed_publications", []))
    + list(migrated.get("candidate_publications", []))
  )

  query_specs: list[dict[str, Any]] = []
  _add_focus_query_specs(query_specs, theme_name, keywords["core_en"], "en", "theme_core", max_terms_after_theme=5, max_batches=2)
  _add_focus_query_specs(query_specs, theme_name, keywords["core_ja"], "ja", "theme_core", max_terms_after_theme=5, max_batches=2)
  _add_pair_query_specs(query_specs, keywords["core_en"], keywords["material_process_en"], "en", "core_material_process", max_pairs=2)
  _add_pair_query_specs(query_specs, keywords["core_ja"], keywords["material_process_ja"], "ja", "core_material_process", max_pairs=2)
  _add_pair_query_specs(query_specs, keywords["core_en"], keywords["application_en"], "en", "core_application", max_pairs=2)
  _add_pair_query_specs(query_specs, keywords["core_ja"], keywords["application_ja"], "ja", "core_application", max_pairs=2)
  _add_language_focus_query(query_specs, keywords["core_en"] + keywords["material_process_en"], "en", "english_focus")
  _add_language_focus_query(query_specs, keywords["core_ja"] + keywords["material_process_ja"], "ja", "japanese_focus")

  return {
    "enabled": True,
    "limit": _normalize_non_negative_limit(limit),
    "queries": _finalize_queries("patent", query_specs, _PATENT_MAX_QUERIES),
    "seed_publications": seed_publications,
    "exclude_terms": exclude_terms,
    "notes": [
      "検索実行は未実装です。BigQuery SQL はまだ生成しません。",
      "Seed公報と候補公報は検索文字列へ直接展開せず、別フィールドへ保持します。",
    ],
  }


def build_paper_search_plan(
  profile: dict[str, Any],
  limit: int,
) -> dict[str, Any]:
  migrated = _migrated_profile(profile)
  keywords = migrated["keywords"]
  theme_name = str(migrated.get("theme_name", "") or "").strip()
  exclude_terms = normalize_terms(keywords["exclude_en"] + keywords["exclude_ja"])

  query_specs: list[dict[str, Any]] = []
  _add_pair_query_specs(query_specs, keywords["core_en"], keywords["material_process_en"], "en", "core_material_process", max_pairs=2)
  _add_pair_query_specs(query_specs, keywords["core_ja"], keywords["material_process_ja"], "ja", "core_material_process", max_pairs=2)
  _add_pair_query_specs(query_specs, keywords["core_en"], keywords["application_en"], "en", "core_application", max_pairs=2)
  _add_pair_query_specs(query_specs, keywords["core_ja"], keywords["application_ja"], "ja", "core_application", max_pairs=2)
  _add_terms_query(
    query_specs,
    "en",
    "defect_property_relationship",
    _compose_terms(theme_name, keywords["core_en"][:2] + keywords["application_en"][:2] + ["defect-property relationship"]),
  )
  _add_terms_query(
    query_specs,
    "en",
    "process_property_relationship",
    _compose_terms(theme_name, keywords["material_process_en"][:2] + keywords["application_en"][:2] + ["process-property relationship"]),
  )
  _add_terms_query(
    query_specs,
    "ja",
    "defect_property_relationship",
    _compose_terms(theme_name, keywords["core_ja"][:2] + keywords["application_ja"][:2] + ["欠陥 特性 関係"]),
  )
  _add_terms_query(
    query_specs,
    "ja",
    "process_property_relationship",
    _compose_terms(theme_name, keywords["material_process_ja"][:2] + keywords["application_ja"][:2] + ["工程 特性 関係"]),
  )
  _add_language_focus_query(query_specs, keywords["core_en"] + keywords["application_en"], "en", "english_focus")
  _add_language_focus_query(query_specs, keywords["core_ja"] + keywords["application_ja"], "ja", "japanese_focus")

  return {
    "enabled": True,
    "limit": _normalize_non_negative_limit(limit),
    "queries": _finalize_queries("paper", query_specs, _PAPER_MAX_QUERIES),
    "exclude_terms": exclude_terms,
    "notes": [
      "OpenAlex staged retrieval を明示実行できます。ページ表示だけでは検索しません。",
      "Seed公報番号は論文検索クエリへ直接挿入しません。",
    ],
  }


def build_web_search_plan(
  profile: dict[str, Any],
  limit: int,
) -> dict[str, Any]:
  migrated = _migrated_profile(profile)
  keywords = migrated["keywords"]
  theme_name = str(migrated.get("theme_name", "") or "").strip()
  target_companies = normalize_terms(list(migrated.get("target_companies", [])))
  exclude_terms = normalize_terms(keywords["exclude_en"] + keywords["exclude_ja"])

  query_specs: list[dict[str, Any]] = []
  english_base = normalize_terms(keywords["core_en"][:2] + keywords["material_process_en"][:2] + keywords["application_en"][:1])
  japanese_base = normalize_terms(keywords["core_ja"][:2] + keywords["material_process_ja"][:2] + keywords["application_ja"][:1])

  for strategy_term, strategy in (
    ("news", "technology_news"),
    ("product announcement", "product_announcement"),
    ("press release", "press_release"),
    ("technical blog", "technical_blog"),
  ):
    _add_terms_query(query_specs, "en", strategy, _compose_terms(theme_name, english_base[:3] + [strategy_term]))

  for strategy_term, strategy in (
    ("技術ニュース", "technology_news"),
    ("製品発表", "product_announcement"),
    ("プレスリリース", "press_release"),
    ("技術ブログ", "technical_blog"),
  ):
    _add_terms_query(query_specs, "ja", strategy, _compose_terms(theme_name, japanese_base[:3] + [strategy_term]))

  for company in target_companies[:2]:
    _add_terms_query(query_specs, "mixed", "capital_investment", _compose_terms(company, [theme_name or _first_term(english_base + japanese_base), "設備投資"]))
    _add_terms_query(query_specs, "mixed", "joint_research", _compose_terms(company, [theme_name or _first_term(english_base + japanese_base), "共同研究"]))

  return {
    "enabled": True,
    "limit": _normalize_non_negative_limit(limit),
    "queries": _finalize_queries("web", query_specs, _WEB_MAX_QUERIES),
    "exclude_terms": exclude_terms,
    "notes": [
      "検索実行は未実装です。Web API 固有構文や日付フィルタはまだ付与しません。",
      "ニュース、製品発表、プレスリリース、技術ブログ、設備投資、共同研究の観点で分割します。",
    ],
  }


def build_company_search_plan(
  profile: dict[str, Any],
  limit: int,
) -> dict[str, Any]:
  migrated = _migrated_profile(profile)
  keywords = migrated["keywords"]
  theme_name = str(migrated.get("theme_name", "") or "").strip()
  target_companies = normalize_terms(list(migrated.get("target_companies", [])))[:5]
  exclude_terms = normalize_terms(keywords["exclude_en"] + keywords["exclude_ja"])
  material_or_application = normalize_terms(
    keywords["material_process_en"][:2]
    + keywords["material_process_ja"][:2]
    + keywords["application_en"][:1]
    + keywords["application_ja"][:1]
  )

  query_specs: list[dict[str, Any]] = []
  if target_companies:
    for company in target_companies:
      _add_terms_query(
        query_specs,
        "mixed",
        "company_theme",
        _compose_terms(company, [theme_name or _first_term(material_or_application)] + material_or_application[:2]),
      )
    for company in target_companies:
      _add_terms_query(query_specs, "mixed", "company_press_release", _compose_terms(company, ["プレスリリース"]))
  else:
    generic_anchor = theme_name or _first_term(material_or_application) or "関連企業探索"
    _add_terms_query(query_specs, "ja", "related_company_discovery", _compose_terms(generic_anchor, ["関連企業探索"]))
    _add_terms_query(query_specs, "ja", "capital_investment", _compose_terms(generic_anchor, material_or_application[:2] + ["設備投資"]))
    _add_terms_query(query_specs, "ja", "joint_research", _compose_terms(generic_anchor, material_or_application[:2] + ["共同研究"]))
    _add_terms_query(query_specs, "ja", "product", _compose_terms(generic_anchor, material_or_application[:2] + ["製品"]))
    _add_terms_query(query_specs, "ja", "press_release", _compose_terms(generic_anchor, ["プレスリリース"]))

  notes = ["検索実行は未実装です。企業情報検索は preview 計画のみです。"]
  if not target_companies:
    notes.append("注目企業が未設定のため、テーマ起点の関連企業探索クエリを生成しました。")

  return {
    "enabled": True,
    "limit": _normalize_non_negative_limit(limit),
    "queries": _finalize_queries("company", query_specs, _COMPANY_MAX_QUERIES),
    "target_companies": target_companies,
    "exclude_terms": exclude_terms,
    "notes": notes,
  }


def build_unified_search_plan(
  profile: dict[str, Any],
  total_limit: int = DEFAULT_TOTAL_LIMIT,
  source_limits: dict[str, Any] | None = None,
  global_web_options: dict[str, Any] | None = None,
) -> dict[str, Any]:
  from .global_web_plan import build_global_web_search_plan

  migrated = _migrated_profile(profile)
  normalized_total = normalize_total_limit(total_limit)
  normalized_limits = normalize_source_limits(normalized_total, source_limits)

  plan = {
    "schema_version": _PLAN_SCHEMA_VERSION,
    "theme_name": str(migrated.get("theme_name", "") or "").strip(),
    "theme_description": str(migrated.get("theme_description", "") or "").strip(),
    "execution_enabled": False,
    "total_limit": normalized_total,
    "source_limits": normalized_limits,
    "plans": {
      "patent": build_patent_search_plan(migrated, normalized_limits["patent"]),
      "paper": build_paper_search_plan(migrated, normalized_limits["paper"]),
      "web": build_web_search_plan(migrated, normalized_limits["web"]),
      "company": build_company_search_plan(migrated, normalized_limits["company"]),
    },
    "global_web_plan": build_global_web_search_plan(
      migrated,
      web_limit=normalized_limits["web"],
      company_limit=normalized_limits["company"],
      options=global_web_options,
    ),
  }
  return plan


def validate_search_plan(plan: dict[str, Any]) -> list[str]:
  errors: list[str] = []
  if not isinstance(plan, dict):
    return ["検索計画の形式が不正です。"]

  if not str(plan.get("schema_version", "") or "").strip():
    errors.append("schema_version が設定されていません。")
  if plan.get("execution_enabled") is not False:
    errors.append("execution_enabled は False である必要があります。")

  total_limit = plan.get("total_limit")
  if isinstance(total_limit, bool) or not isinstance(total_limit, int) or not (1 <= total_limit <= _MAX_TOTAL_LIMIT):
    errors.append("total_limit は 1 以上 5000 以下の整数である必要があります。")

  source_limits = plan.get("source_limits")
  if not isinstance(source_limits, dict):
    errors.append("source_limits の形式が不正です。")
    source_limits = {}

  source_limit_sum = 0
  for source in _SOURCE_ORDER:
    value = source_limits.get(source)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
      errors.append(f"{source} の件数上限が不正です。")
      continue
    source_limit_sum += value

  if isinstance(total_limit, int) and source_limit_sum != total_limit:
    errors.append("情報源別件数の合計が全体件数と一致しません。")

  plans = plan.get("plans")
  if not isinstance(plans, dict):
    errors.append("plans の形式が不正です。")
    plans = {}

  seen_query_ids: set[str] = set()
  for source in _SOURCE_ORDER:
    source_plan = plans.get(source)
    if not isinstance(source_plan, dict):
      errors.append(f"{source} の検索計画が存在しません。")
      continue

    source_limit = source_plan.get("limit")
    if isinstance(source_limit, bool) or not isinstance(source_limit, int) or source_limit < 0:
      errors.append(f"{source} の limit が不正です。")
    elif isinstance(total_limit, int) and source_limit > total_limit:
      errors.append(f"{source} の limit が total_limit を超えています。")

    queries = source_plan.get("queries")
    if not isinstance(queries, list):
      errors.append(f"{source} の queries は list である必要があります。")
      continue

    for query in queries:
      if not isinstance(query, dict):
        errors.append(f"{source} の query 形式が不正です。")
        continue
      query_id = str(query.get("query_id", "") or "").strip()
      if not query_id:
        errors.append(f"{source} に query_id が空のクエリがあります。")
      elif query_id in seen_query_ids:
        errors.append(f"{query_id} が重複しています。")
      else:
        seen_query_ids.add(query_id)

      query_text = str(query.get("query_text", "") or "").strip()
      if not query_text:
        errors.append(f"{query_id or source} の検索文字列が空です。")

  global_web_plan = plan.get("global_web_plan")
  if isinstance(global_web_plan, dict):
    from .global_web_plan import validate_global_web_search_plan

    errors.extend(validate_global_web_search_plan(global_web_plan))

  return errors


def summarize_search_plan_ja(plan: dict[str, Any]) -> str:
  plans = plan.get("plans", {}) if isinstance(plan, dict) else {}
  patent_plan = plans.get("patent", {}) if isinstance(plans, dict) else {}
  paper_plan = plans.get("paper", {}) if isinstance(plans, dict) else {}
  web_plan = plans.get("web", {}) if isinstance(plans, dict) else {}
  company_plan = plans.get("company", {}) if isinstance(plans, dict) else {}
  global_web_plan = plan.get("global_web_plan", {}) if isinstance(plan, dict) else {}
  seed_count = len(patent_plan.get("seed_publications", []) or [])
  global_web_query_count = len(global_web_plan.get("queries", []) or []) if isinstance(global_web_plan, dict) else 0

  lines = [
    "統合検索計画",
    "",
    f"- 最大取得件数: {int(plan.get('total_limit', DEFAULT_TOTAL_LIMIT) or DEFAULT_TOTAL_LIMIT)}件",
    f"- 特許: 最大{int(patent_plan.get('limit', 0) or 0)}件 / {len(patent_plan.get('queries', []) or [])}クエリ",
    f"- 論文: 最大{int(paper_plan.get('limit', 0) or 0)}件 / {len(paper_plan.get('queries', []) or [])}クエリ",
    f"- Web情報: 最大{int(web_plan.get('limit', 0) or 0)}件 / {len(web_plan.get('queries', []) or [])}クエリ",
    f"- 企業情報: 最大{int(company_plan.get('limit', 0) or 0)}件 / {len(company_plan.get('queries', []) or [])}クエリ",
    f"- Global Web: {global_web_query_count}計画",
    f"- Seed公報: {seed_count}件",
    f"- 外部検索実行: {'ON' if plan.get('execution_enabled') else 'OFF'}",
    "",
    "この計画は検索実行前のPreviewです。",
  ]
  return "\n".join(lines)


def _normalize_source_limit_weights(source_limits: dict[str, Any] | None) -> dict[str, int]:
  if not isinstance(source_limits, dict):
    return dict(DEFAULT_SOURCE_LIMITS)
  return {
    source: _normalize_non_negative_limit(source_limits.get(source))
    for source in _SOURCE_ORDER
  }


def _normalize_non_negative_limit(value: Any) -> int:
  if isinstance(value, bool):
    return 0
  try:
    normalized = int(value)
  except (TypeError, ValueError):
    return 0
  return max(normalized, 0)


def _migrated_profile(profile: dict[str, Any]) -> dict[str, Any]:
  return migrate_watch_profile(profile or {})


def _contains_ascii_letter(value: str) -> bool:
  return any("A" <= char <= "Z" or "a" <= char <= "z" for char in str(value or ""))


def _first_term(terms: list[str]) -> str:
  for term in terms:
    if str(term or "").strip():
      return str(term).strip()
  return ""


def _compose_terms(anchor: str, terms: list[str]) -> list[str]:
  composed = []
  if str(anchor or "").strip():
    composed.append(str(anchor).strip())
  composed.extend(str(term or "").strip() for term in terms)
  return normalize_terms(composed)[:_MAX_QUERY_TERMS]


def _build_query_text(terms: list[str]) -> str:
  cleaned_terms = []
  for term in terms:
    value = str(term or "").strip()
    if not value:
      continue
    safe_value = value.replace('"', "'")
    cleaned_terms.append(f"\"{safe_value}\"")
  return " AND ".join(cleaned_terms)


def _add_terms_query(
  query_specs: list[dict[str, Any]],
  language: str,
  strategy: str,
  terms: list[str],
) -> None:
  cleaned_terms = normalize_terms(list(terms))[:_MAX_QUERY_TERMS]
  if not cleaned_terms:
    return
  query_specs.append(
    {
      "language": language,
      "strategy": strategy,
      "terms": cleaned_terms,
    }
  )


def _add_focus_query_specs(
  query_specs: list[dict[str, Any]],
  theme_name: str,
  terms: list[str],
  language: str,
  strategy: str,
  *,
  max_terms_after_theme: int,
  max_batches: int,
) -> None:
  for batch in batch_terms(terms, batch_size=max_terms_after_theme, max_batches=max_batches):
    _add_terms_query(query_specs, language, strategy, _compose_terms(theme_name, batch))


def _add_pair_query_specs(
  query_specs: list[dict[str, Any]],
  first_terms: list[str],
  second_terms: list[str],
  language: str,
  strategy: str,
  *,
  max_pairs: int,
) -> None:
  first_batches = batch_terms(first_terms, batch_size=3, max_batches=max_pairs)
  second_batches = batch_terms(second_terms, batch_size=3, max_batches=max_pairs)
  for index in range(min(len(first_batches), len(second_batches), max_pairs)):
    _add_terms_query(query_specs, language, strategy, first_batches[index] + second_batches[index])


def _add_language_focus_query(
  query_specs: list[dict[str, Any]],
  terms: list[str],
  language: str,
  strategy: str,
) -> None:
  batches = batch_terms(terms, batch_size=_MAX_QUERY_TERMS, max_batches=1)
  if batches:
    _add_terms_query(query_specs, language, strategy, batches[0])


def _finalize_queries(
  source: str,
  query_specs: list[dict[str, Any]],
  max_queries: int,
) -> list[dict[str, Any]]:
  queries: list[dict[str, Any]] = []
  seen_query_texts: set[str] = set()
  for spec in query_specs:
    terms = normalize_terms(list(spec.get("terms", [])))[:_MAX_QUERY_TERMS]
    query_text = _build_query_text(terms)
    if not query_text or query_text in seen_query_texts:
      continue
    seen_query_texts.add(query_text)
    queries.append(
      {
        "language": str(spec.get("language", "") or ""),
        "strategy": str(spec.get("strategy", "") or ""),
        "terms": terms,
        "query_text": query_text,
      }
    )
    if len(queries) >= max_queries:
      break

  finalized: list[dict[str, Any]] = []
  for index, query in enumerate(queries, start=1):
    finalized.append(
      {
        "query_id": f"{source}_q{index:02d}",
        "origin": "generated",
        **query,
      }
    )
  return finalized


__all__ = [
  "DEFAULT_SOURCE_LIMITS",
  "DEFAULT_TOTAL_LIMIT",
  "batch_terms",
  "build_company_search_plan",
  "build_paper_search_plan",
  "build_patent_search_plan",
  "build_unified_search_plan",
  "build_web_search_plan",
  "normalize_source_limits",
  "normalize_total_limit",
  "summarize_search_plan_ja",
  "validate_search_plan",
]
