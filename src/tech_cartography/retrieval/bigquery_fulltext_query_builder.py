"""BigQuery SQL builder for US full text patent retrieval."""

from __future__ import annotations

import re
from typing import Any

from tech_cartography.retrieval.publication_number_variants import (
  build_publication_number_variants as _build_variants,
  normalize_publication_number as normalize_us_publication_number,
)

PUBLICATIONS_TABLE = "`patents-public-data.patents.publications`"
US_PUB_PATTERN = re.compile(r"^US[\dA-Z\-]+$", re.IGNORECASE)

VALID_FULLTEXT_SCOPES = frozenset(
  {"claims_only", "description_only", "claims_and_description"},
)


def escape_sql_string(value: str) -> str:
  return "'" + str(value).replace("'", "''") + "'"


def validate_fulltext_scope(scope: str) -> str:
  normalized = str(scope or "").strip().lower()
  if normalized not in VALID_FULLTEXT_SCOPES:
    raise ValueError(
      f"Invalid fulltext scope '{scope}'. "
      f"Expected one of: {', '.join(sorted(VALID_FULLTEXT_SCOPES))}",
    )
  return normalized


def build_publication_number_variants(
  publication_number: str,
  *,
  metadata: dict[str, Any] | None = None,
) -> list[str]:
  return _build_variants(publication_number, metadata=metadata)


def validate_us_fulltext_request(
  publication_number: str,
  country: str | None = None,
  *,
  metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
  if country and str(country).strip().upper() not in {"", "US"}:
    return {
      "ok": False,
      "error": f"Non-US country ({country}) is not eligible for BigQuery fulltext SQL",
      "variants": [],
    }
  normalized = normalize_us_publication_number(publication_number)
  if not normalized.startswith("US"):
    return {
      "ok": False,
      "error": f"Publication number '{publication_number}' is not a US publication",
      "variants": [],
    }
  variants = build_publication_number_variants(publication_number, metadata=metadata)
  if not variants:
    return {
      "ok": False,
      "error": f"Could not build publication number variants for '{publication_number}'",
      "variants": [],
    }
  return {"ok": True, "error": None, "variants": variants}


def is_us_publication(publication_number: str | None, country: str | None = None) -> bool:
  if country and str(country).strip().upper() == "US":
    return True
  normalized = normalize_us_publication_number(publication_number or "")
  return normalized.startswith("US")


def _localized_text_expr(field_name: str) -> str:
  """Aggregate all localized segments without language filter (avoid dropping claims)."""
  return (
    f"(SELECT STRING_AGG(loc.text, '\\n' ORDER BY loc.language) "
    f"FROM UNNEST({field_name}) AS loc "
    "WHERE loc.text IS NOT NULL AND TRIM(loc.text) != '')"
  )


def _where_clause(literals: str) -> str:
  return f"""
WHERE publication_number IN ({literals})
  AND country_code = 'US'
LIMIT 1
""".strip()


def build_us_claims_query(
  publication_number: str,
  *,
  country: str | None = None,
  metadata: dict[str, Any] | None = None,
) -> str:
  validation = validate_us_fulltext_request(publication_number, country, metadata=metadata)
  if not validation["ok"]:
    raise ValueError(validation["error"])
  literals = ", ".join(escape_sql_string(item) for item in validation["variants"])
  claims_expr = _localized_text_expr("claims_localized")
  assignee_expr = (
    "(SELECT STRING_AGG(DISTINCT ah.name, '; ' ORDER BY ah.name) "
    "FROM UNNEST(IFNULL(assignee_harmonized, [])) AS ah "
    "WHERE ah.name IS NOT NULL AND ah.name != '')"
  )
  return f"""
-- scope: claims_only
SELECT
  publication_number,
  publication_date,
  country_code,
  {assignee_expr} AS assignee,
  {claims_expr} AS claims
FROM {PUBLICATIONS_TABLE}
{_where_clause(literals)}
""".strip()


def build_us_description_query(
  publication_number: str,
  *,
  country: str | None = None,
  metadata: dict[str, Any] | None = None,
) -> str:
  validation = validate_us_fulltext_request(publication_number, country, metadata=metadata)
  if not validation["ok"]:
    raise ValueError(validation["error"])
  literals = ", ".join(escape_sql_string(item) for item in validation["variants"])
  description_expr = _localized_text_expr("description_localized")
  assignee_expr = (
    "(SELECT STRING_AGG(DISTINCT ah.name, '; ' ORDER BY ah.name) "
    "FROM UNNEST(IFNULL(assignee_harmonized, [])) AS ah "
    "WHERE ah.name IS NOT NULL AND ah.name != '')"
  )
  return f"""
-- scope: description_only
SELECT
  publication_number,
  publication_date,
  country_code,
  {assignee_expr} AS assignee,
  {description_expr} AS description
FROM {PUBLICATIONS_TABLE}
{_where_clause(literals)}
""".strip()


def build_us_claims_and_description_query(
  publication_number: str,
  *,
  country: str | None = None,
  metadata: dict[str, Any] | None = None,
) -> str:
  validation = validate_us_fulltext_request(publication_number, country, metadata=metadata)
  if not validation["ok"]:
    raise ValueError(validation["error"])
  literals = ", ".join(escape_sql_string(item) for item in validation["variants"])
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
-- scope: claims_and_description
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
{_where_clause(literals)}
""".strip()


def build_us_fulltext_query(
  publication_number: str,
  scope: str = "claims_only",
  *,
  country: str | None = None,
  metadata: dict[str, Any] | None = None,
) -> str:
  """Build BigQuery SQL to fetch US full text fields for one publication."""
  normalized_scope = validate_fulltext_scope(scope)
  if normalized_scope == "claims_only":
    return build_us_claims_query(publication_number, country=country, metadata=metadata)
  if normalized_scope == "description_only":
    return build_us_description_query(publication_number, country=country, metadata=metadata)
  return build_us_claims_and_description_query(publication_number, country=country, metadata=metadata)
