"""BigQuery SQL builder for lightweight patent metadata retrieval."""

from __future__ import annotations

import re

from tech_cartography.strategy.query_plan import QueryPlan

PUBLICATIONS_TABLE = "`patents-public-data.patents.publications`"

FORBIDDEN_FIELDS = (
  "claims",
  "description",
  "claims_localized",
  "description_localized",
  "full_text",
)


def escape_sql_string(value: str) -> str:
  return "'" + str(value).replace("'", "''") + "'"


def _localized_text_expr(field_name: str) -> str:
  return (
    f"(SELECT loc.text FROM UNNEST({field_name}) AS loc "
    "WHERE loc.text IS NOT NULL AND loc.text != '' "
    "ORDER BY CASE WHEN loc.language = 'en' THEN 0 ELSE 1 END, loc.language "
    "LIMIT 1)"
  )


def _assignees_expr() -> str:
  return (
    "(SELECT STRING_AGG(DISTINCT ah.name, '; ' ORDER BY ah.name) "
    "FROM UNNEST(IFNULL(assignee_harmonized, [])) AS ah "
    "WHERE ah.name IS NOT NULL AND ah.name != '')"
  )


def _cpc_codes_expr() -> str:
  return (
    "(SELECT STRING_AGG(DISTINCT cpc.code, '; ' ORDER BY cpc.code) "
    "FROM UNNEST(IFNULL(cpc, [])) AS cpc "
    "WHERE cpc.code IS NOT NULL AND cpc.code != '')"
  )


def _ipc_codes_expr() -> str:
  return (
    "(SELECT STRING_AGG(DISTINCT ipc.code, '; ' ORDER BY ipc.code) "
    "FROM UNNEST(IFNULL(ipc, [])) AS ipc "
    "WHERE ipc.code IS NOT NULL AND ipc.code != '')"
  )


def _term_match_condition(search_text_expr: str, term: str) -> str:
  normalized = term.strip().lower()
  if not normalized:
    return "FALSE"
  if normalized == "pan":
    return f"REGEXP_CONTAINS(LOWER({search_text_expr}), r'\\\\bpan\\\\b')"
  escaped = normalized.replace("'", "''")
  return f"LOWER({search_text_expr}) LIKE '%{escaped}%'"


def terms_to_like_conditions(terms: list[str], fields: list[str]) -> str:
  cleaned = [term.strip() for term in terms if term and term.strip()]
  if not cleaned:
    return "TRUE"
  field_exprs = [f"IFNULL({field}, '')" for field in fields]
  search_text_expr = f"CONCAT({', '.join(field_exprs)})"
  conditions = [_term_match_condition(search_text_expr, term) for term in cleaned]
  return "(\n    " + "\n    OR ".join(conditions) + "\n  )"


def companies_to_assignee_conditions(companies: list[str]) -> str:
  cleaned = [company.strip() for company in companies if company and company.strip()]
  if not cleaned:
    return "TRUE"
  conditions = []
  for company in cleaned:
    escaped = company.lower().replace("'", "''")
    conditions.append(
      "EXISTS ("
      "SELECT 1 "
      "FROM UNNEST(IFNULL(assignee_harmonized, [])) AS ah "
      f"WHERE LOWER(ah.name) LIKE '%{escaped}%'"
      ")",
    )
  return "(\n    " + "\n    OR ".join(conditions) + "\n  )"


def build_where_clause(query_plan: QueryPlan) -> str:
  title_expr = _localized_text_expr("title_localized")
  abstract_expr = _localized_text_expr("abstract_localized")
  search_fields = [title_expr, abstract_expr]

  include_terms = list(dict.fromkeys(
    [*query_plan.must_have_terms, *query_plan.should_have_terms],
  ))
  clauses: list[str] = []

  if query_plan.target_countries:
    country_literals = ", ".join(
      escape_sql_string(country.upper()) for country in query_plan.target_countries
    )
    clauses.append(f"country_code IN ({country_literals})")

  if query_plan.year_min is not None:
    clauses.append(f"publication_date >= {query_plan.year_min}0101")
  if query_plan.year_max is not None:
    clauses.append(f"publication_date <= {query_plan.year_max}1231")

  if query_plan.intent_id == "company_watch" and query_plan.target_companies:
    clauses.append(companies_to_assignee_conditions(query_plan.target_companies))

  include_clause = terms_to_like_conditions(include_terms, search_fields)
  if include_terms:
    clauses.append(include_clause)

  if query_plan.exclude_terms:
    exclude_clause = (
      f"NOT {terms_to_like_conditions(query_plan.exclude_terms, search_fields)}"
    )
    clauses.append(exclude_clause)

  if not clauses:
    return "TRUE"
  return "\n  AND ".join(clauses)


def build_lightweight_patent_query(query_plan: QueryPlan, limit: int = 500) -> str:
  """Build lightweight BigQuery SQL for metadata-only patent retrieval."""
  title_expr = _localized_text_expr("title_localized")
  abstract_expr = _localized_text_expr("abstract_localized")
  where_clause = build_where_clause(query_plan)
  resolved_limit = max(1, int(limit))

  sql = f"""
SELECT
  publication_number,
  publication_date,
  {title_expr} AS title,
  {abstract_expr} AS abstract,
  {_assignees_expr()} AS assignee,
  country_code AS country,
  CONCAT('https://patents.google.com/patent/', publication_number) AS url,
  {_cpc_codes_expr()} AS cpc_codes,
  {_ipc_codes_expr()} AS ipc_codes,
  {escape_sql_string(query_plan.intent_id)} AS search_intent,
  {escape_sql_string(query_plan.intent_id)} AS query_plan_id,
  {escape_sql_string(query_plan.query_hint)} AS query_hint,
  'bigquery_lightweight' AS source_type,
  'metadata_only' AS evidence_level,
  'not_fetched' AS claims_source,
  'not_fetched' AS description_source
FROM {PUBLICATIONS_TABLE}
WHERE {where_clause}
ORDER BY publication_date DESC
LIMIT {resolved_limit}
""".strip()

  lowered = sql.lower()
  scrubbed = lowered
  for safe_literal in ("claims_source", "description_source", "not_fetched"):
    scrubbed = scrubbed.replace(safe_literal, "")
  for forbidden in FORBIDDEN_FIELDS:
    if forbidden in scrubbed:
      raise ValueError(f"Forbidden field in SQL: {forbidden}")

  return sql


def infer_matched_terms(record: dict, query_plan: QueryPlan) -> list[str]:
  """Infer matched terms from title/abstract against query plan terms."""
  text = " ".join(
    str(record.get(field, "") or "") for field in ("title", "abstract")
  ).lower()
  candidates = list(
    dict.fromkeys([*query_plan.must_have_terms, *query_plan.should_have_terms]),
  )
  matched: list[str] = []
  for term in candidates:
    normalized = term.strip().lower()
    if not normalized:
      continue
    if normalized == "pan":
      if re.search(r"\bpan\b", text):
        matched.append(term)
      continue
    if normalized in text:
      matched.append(term)
  return matched
