"""BigQuery SQL builder for US full text patent retrieval."""

from __future__ import annotations

import re
from typing import Any

PUBLICATIONS_TABLE = "`patents-public-data.patents.publications`"
US_PUB_PATTERN = re.compile(r"^US[\dA-Z\-]+$", re.IGNORECASE)


def escape_sql_string(value: str) -> str:
  return "'" + str(value).replace("'", "''") + "'"


def normalize_us_publication_number(publication_number: str) -> str:
  compact = re.sub(r"[\s\-]+", "", str(publication_number or "").upper())
  if compact.startswith("US"):
    return compact
  return compact


def _kind_suffix_variants(core: str) -> list[str]:
  """Generate common US publication number shapes from normalized core."""
  variants: list[str] = []
  if not core.startswith("US"):
    return variants
  body = core[2:]
  variants.append(core)
  variants.append(f"US-{body}")
  if len(body) > 2 and body[-2] in {"A1", "A2", "B1", "B2"}:
    kind = body[-2:]
    digits = body[:-2]
    variants.append(f"US{digits}{kind}")
    variants.append(f"US-{digits}{kind}")
    variants.append(f"US{digits}-{kind}")
  return variants


def build_publication_number_variants(publication_number: str) -> list[str]:
  normalized = normalize_us_publication_number(publication_number)
  if not normalized.startswith("US"):
    return []

  variants: list[str] = []
  variants.extend(_kind_suffix_variants(normalized))
  variants.extend(_kind_suffix_variants(normalized.replace("-", "")))

  deduped: list[str] = []
  seen: set[str] = set()
  for item in variants:
    key = item.upper()
    if key in seen:
      continue
    seen.add(key)
    deduped.append(item)
  return deduped


def validate_us_fulltext_request(publication_number: str, country: str | None = None) -> dict[str, Any]:
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
  variants = build_publication_number_variants(publication_number)
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
  return (
    f"(SELECT STRING_AGG(loc.text, '\\n' ORDER BY loc.language) "
    f"FROM UNNEST({field_name}) AS loc "
    "WHERE loc.text IS NOT NULL AND loc.text != '')"
  )


def build_us_fulltext_query(publication_number: str, *, country: str | None = None) -> str:
  """Build BigQuery SQL to fetch US full text fields for one publication."""
  validation = validate_us_fulltext_request(publication_number, country)
  if not validation["ok"]:
    raise ValueError(validation["error"])

  variants = validation["variants"]
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
