"""BigQuery SQL builder for Google Patents Public Dataset (Phase 27Q.1)."""

from __future__ import annotations

import json
import re
from typing import Any

from tech_cartography.runtime.v8_bigquery_schema import BIGQUERY_SAFETY_NOTICES
from tech_cartography.runtime.v8_research_theme_schema import (
  ResearchThemeProfile,
  normalize_publication_number,
)
from tech_cartography.services.v8_bigquery_safety import BigQuerySafetyConfig, clamp_limit

PUBLICATIONS_TABLE = "`patents-public-data.patents.publications`"

_STRING_ESCAPE_RE = re.compile(r"([\\'])")

SCORE_CORE = 3
SCORE_MATERIAL = 2
SCORE_APPLICATION = 1
SCORE_SEED = 10
SCORE_EXCLUDE = -10


def _escape_sql_string(value: str) -> str:
  return _STRING_ESCAPE_RE.sub(r"\\\1", value.replace("\n", " ").replace("\r", " "))


def _keyword_match_expr(keyword: str, *, title_weight: float = 1.5) -> str:
  kw = _escape_sql_string(keyword.lower())
  return (
    f"(IF(REGEXP_CONTAINS(LOWER(COALESCE(title_localized[SAFE_OFFSET(0)].text, '')), r'{kw}'), "
    f"{title_weight}, 0) + "
    f"IF(REGEXP_CONTAINS(LOWER(COALESCE(abstract_localized[SAFE_OFFSET(0)].text, '')), r'{kw}'), 1, 0))"
  )


def _build_keyword_score_terms(keywords: list[str], weight: int) -> list[str]:
  terms: list[str] = []
  for kw in keywords:
    kw_clean = kw.strip()
    if not kw_clean:
      continue
    terms.append(f"({_keyword_match_expr(kw_clean)}) * {weight}")
  return terms


def build_bigquery_query(
  profile: ResearchThemeProfile,
  *,
  limit: int | None = None,
  config: BigQuerySafetyConfig | None = None,
) -> tuple[str, dict[str, Any]]:
  """Return (sql, query_config_dict). Uses escaped literals — no user string concatenation in SQL body."""
  cfg = config or BigQuerySafetyConfig.from_env()
  row_limit = clamp_limit(limit or profile.max_results, cfg)
  seeds = [normalize_publication_number(s) for s in profile.seed_publication_numbers]

  score_parts: list[str] = []
  score_parts.extend(_build_keyword_score_terms(profile.core_keywords, SCORE_CORE))
  score_parts.extend(_build_keyword_score_terms(profile.material_process_keywords, SCORE_MATERIAL))
  score_parts.extend(_build_keyword_score_terms(profile.application_keywords, SCORE_APPLICATION))

  exclude_parts: list[str] = []
  for kw in profile.exclude_keywords:
    kw_clean = kw.strip()
    if not kw_clean:
      continue
    exclude_parts.append(
      f"IF(REGEXP_CONTAINS(LOWER(CONCAT(COALESCE(title_localized[SAFE_OFFSET(0)].text,''), ' ', "
      f"COALESCE(abstract_localized[SAFE_OFFSET(0)].text,''))), r'{_escape_sql_string(kw_clean.lower())}'), "
      f"{SCORE_EXCLUDE}, 0)"
    )

  seed_match = ""
  seed_cte = ""
  if seeds:
    seed_literals = ", ".join(f"'{_escape_sql_string(s)}'" for s in seeds)
    seed_cte = f"""
seed_pubs AS (
  SELECT pub FROM UNNEST([{seed_literals}]) AS pub
),
"""
    seed_match = (
      "IF(REPLACE(UPPER(publication_number), '-', '') IN (SELECT pub FROM seed_pubs), "
      f"{SCORE_SEED}, 0)"
    )

  score_expr = " + ".join([seed_match] + score_parts + exclude_parts) if (seed_match or score_parts or exclude_parts) else "0"

  where_clauses: list[str] = ["publication_number IS NOT NULL"]

  if profile.countries:
    country_literals = ", ".join(f"'{_escape_sql_string(c.upper())}'" for c in profile.countries)
    where_clauses.append(f"country_code IN ({country_literals})")

  if profile.publication_year_from is not None:
    where_clauses.append(f"SAFE_CAST(SUBSTR(CAST(publication_date AS STRING), 1, 4) AS INT64) >= {int(profile.publication_year_from)}")

  if profile.publication_year_to is not None:
    where_clauses.append(f"SAFE_CAST(SUBSTR(CAST(publication_date AS STRING), 1, 4) AS INT64) <= {int(profile.publication_year_to)}")

  keyword_or: list[str] = []
  all_keywords = profile.core_keywords + profile.material_process_keywords + profile.application_keywords
  for kw in all_keywords:
    kw_clean = kw.strip()
    if not kw_clean:
      continue
    esc = _escape_sql_string(kw_clean.lower())
    keyword_or.append(
      f"REGEXP_CONTAINS(LOWER(CONCAT(COALESCE(title_localized[SAFE_OFFSET(0)].text,''), ' ', "
      f"COALESCE(abstract_localized[SAFE_OFFSET(0)].text,''))), r'{esc}')"
    )

  mode = profile.search_mode
  if mode == "seed_only" and seeds:
    seed_or = " OR ".join(
      f"REPLACE(UPPER(publication_number), '-', '') = '{_escape_sql_string(s)}'" for s in seeds
    )
    where_clauses.append(f"({seed_or})")
  elif mode == "keyword_only":
    if keyword_or:
      where_clauses.append(f"({' OR '.join(keyword_or)})")
  else:
    parts: list[str] = []
    if keyword_or:
      parts.append(f"({' OR '.join(keyword_or)})")
    if seeds:
      seed_or = " OR ".join(
        f"REPLACE(UPPER(publication_number), '-', '') = '{_escape_sql_string(s)}'" for s in seeds
      )
      parts.append(f"({seed_or})")
    if parts:
      where_clauses.append(f"({' OR '.join(parts)})")

  for kw in profile.exclude_keywords:
    kw_clean = kw.strip()
    if not kw_clean:
      continue
    esc = _escape_sql_string(kw_clean.lower())
    where_clauses.append(
      f"NOT REGEXP_CONTAINS(LOWER(CONCAT(COALESCE(title_localized[SAFE_OFFSET(0)].text,''), ' ', "
      f"COALESCE(abstract_localized[SAFE_OFFSET(0)].text,''))), r'{esc}')"
    )

  where_sql = " AND ".join(where_clauses)

  sql = f"""-- Phase27Q.1 generated query — candidate metadata only (no JP/CN claims)
-- {BIGQUERY_SAFETY_NOTICES[0]}
WITH
{seed_cte}base AS (
  SELECT
    publication_number,
    application_number,
    country_code,
    kind_code,
    family_id,
    publication_date,
    COALESCE(title_localized[SAFE_OFFSET(0)].text, '') AS title,
    COALESCE(abstract_localized[SAFE_OFFSET(0)].text, '') AS abstract,
    COALESCE(assignee[SAFE_OFFSET(0)].name, '') AS assignee,
    ARRAY_TO_STRING(ARRAY(SELECT i.name FROM UNNEST(inventor) AS i LIMIT 5), '; ') AS inventor,
    ARRAY_TO_STRING(ARRAY(SELECT c.code FROM UNNEST(cpc) AS c LIMIT 8), '; ') AS cpc,
    CONCAT('https://patents.google.com/patent/', publication_number, '/en') AS url,
    'patent' AS source_type,
    'candidate_information_only' AS source_status,
    TRUE AS candidate_information_only,
    TRUE AS human_review_required,
    '{_escape_sql_string(profile.theme_name)}' AS related_case_theme,
    ({score_expr}) AS heuristic_score
  FROM {PUBLICATIONS_TABLE}
  WHERE {where_sql}
),
scored AS (
  SELECT
    *,
    'heuristic draft — reading priority score only' AS match_reason,
    '' AS matched_keywords
  FROM base
  WHERE heuristic_score > 0 OR publication_number IS NOT NULL
)
SELECT
  publication_number,
  application_number,
  country_code,
  kind_code,
  family_id,
  publication_date,
  title,
  abstract,
  assignee,
  inventor,
  cpc,
  url,
  source_type,
  source_status,
  candidate_information_only,
  human_review_required,
  related_case_theme,
  matched_keywords,
  match_reason,
  heuristic_score
FROM scored
ORDER BY heuristic_score DESC, publication_date DESC
LIMIT {row_limit}
"""

  query_config = {
    "case_id": profile.case_id,
    "theme_name": profile.theme_name,
    "search_mode": profile.search_mode,
    "limit": row_limit,
    "countries": profile.countries,
    "publication_year_from": profile.publication_year_from,
    "publication_year_to": profile.publication_year_to,
    "seed_publication_numbers": seeds,
    "core_keyword_count": len(profile.core_keywords),
    "material_keyword_count": len(profile.material_process_keywords),
    "application_keyword_count": len(profile.application_keywords),
    "exclude_keyword_count": len(profile.exclude_keywords),
    "safety_notices": list(BIGQUERY_SAFETY_NOTICES[:3]),
    "no_claims_for_jp_cn": True,
  }
  return sql, query_config
