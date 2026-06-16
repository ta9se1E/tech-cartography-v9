"""BigQuery SQL builder for US full text patent retrieval."""

from __future__ import annotations

import re

PUBLICATIONS_TABLE = "`patents-public-data.patents.publications`"


def escape_sql_string(value: str) -> str:
  return "'" + str(value).replace("'", "''") + "'"


def normalize_us_publication_number(publication_number: str) -> str:
  compact = re.sub(r"[\s\-]+", "", str(publication_number or "").upper())
  if compact.startswith("US"):
    return compact
  return compact


def build_publication_number_variants(publication_number: str) -> list[str]:
  normalized = normalize_us_publication_number(publication_number)
  variants = [normalized]
  if normalized.startswith("US") and "-" not in normalized:
    variants.append(f"US-{normalized[2:]}")
  compact_no_prefix = normalized[2:] if normalized.startswith("US") else normalized
  if compact_no_prefix:
    variants.append(f"US-{compact_no_prefix}")
  deduped: list[str] = []
  seen: set[str] = set()
  for item in variants:
    key = item.upper()
    if key in seen:
      continue
    seen.add(key)
    deduped.append(item)
  return deduped


def is_us_publication(publication_number: str | None, country: str | None = None) -> bool:
  if country and str(country).strip().upper() == "US":
    return True
  normalized = normalize_us_publication_number(publication_number or "")
  return normalized.startswith("US")


def _localized_text_expr(field_name: str) -> str:
  return (
    f"(SELECT STRING_AGG(loc.text, '\\n' ORDER BY loc.language) "
    f"FROM UNNEST({field_name}) AS loc "
    "WHERE loc.text IS NOT NULL AND loc.text != '')"
  )


def build_us_fulltext_query(publication_number: str) -> str:
  """Build BigQuery SQL to fetch US full text fields for one publication."""
  variants = build_publication_number_variants(publication_number)
  literals = ", ".join(escape_sql_string(item) for item in variants)
  title_expr = _localized_text_expr("title_localized")
  abstract_expr = _localized_text_expr("abstract_localized")
  claims_expr = _localized_text_expr("claims_localized")
  description_expr = _localized_text_expr("description_localized")
  assignee_expr = (
    "(SELECT STRING_AGG(DISTINCT ah.name, '; ' ORDER BY ah.name) "
    "FROM UNNEST(IFNULL(assignee_harmonized, [])) AS ah "
    "WHERE ah.name IS NOT NULL AND ah.name != '')"
  )

  return f"""
SELECT
  publication_number,
  publication_date,
  country_code,
  {title_expr} AS title,
  {abstract_expr} AS abstract,
  {claims_expr} AS claims,
  {description_expr} AS description,
  {assignee_expr} AS assignee
FROM {PUBLICATIONS_TABLE}
WHERE publication_number IN ({literals})
  AND country_code = 'US'
LIMIT 1
""".strip()
