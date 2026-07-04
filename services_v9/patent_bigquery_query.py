"""Patent BigQuery SQL preview and dry-run helpers for v9."""

from __future__ import annotations

import csv
import json
from datetime import date, datetime
from io import StringIO
from pathlib import Path
from typing import Any, Callable

from tech_cartography.retrieval.bigquery_env import bytes_to_gb, estimate_usd_from_bytes, resolve_project_id
from tech_cartography.services.v8_bigquery_safety import (
  BigQuerySafetyConfig,
  assert_dry_run_allowed,
  assert_execute_allowed,
)

from .persistence import ensure_v9_run_dirs
from .watch_profile_schema import migrate_watch_profile, normalize_publication_number, normalize_terms

PUBLICATIONS_TABLE = "`patents-public-data.patents.publications`"
FORBIDDEN_SQL_TOKENS = (
  "claims",
  "description",
  "claims_localized",
  "description_localized",
  "full_text",
)

ClientFactory = Callable[[str, str], Any]
JobConfigBuilder = Callable[[dict[str, Any], bool], Any]


def build_patent_bigquery_preview(
  search_plan: dict[str, Any],
  watch_profile: dict[str, Any],
  *,
  selected_query_id: str | None = None,
  time_range: str = "12m",
  max_results: int | None = None,
  config: BigQuerySafetyConfig | None = None,
) -> dict[str, Any]:
  cfg = config or BigQuerySafetyConfig.from_env()
  migrated_profile = migrate_watch_profile(watch_profile or {})
  patent_plan = dict(search_plan.get("plans", {}).get("patent", {}) or {})
  queries = list(patent_plan.get("queries", []) or [])
  if not queries:
    return {
      "request": {},
      "sql": "",
      "parameters": [],
      "validation_rows": [{"status": "error", "message": "特許検索計画にqueryがありません。"}],
      "query_options": [],
      "selected_query_id": "",
    }

  query_options = [str(query.get("query_id", "") or "") for query in queries if str(query.get("query_id", "") or "").strip()]
  resolved_query_id = selected_query_id if selected_query_id in query_options else query_options[0]
  selected_query = next(
    query for query in queries
    if str(query.get("query_id", "") or "") == resolved_query_id
  )

  date_from, date_to = _publication_window_from_time_range(time_range)
  configured_limit = int(patent_plan.get("limit", 0) or 0)
  resolved_limit = _normalize_positive_int(max_results, configured_limit if configured_limit > 0 else 500)

  countries = normalize_terms(list(migrated_profile.get("countries", [])))
  target_companies = normalize_terms(list(migrated_profile.get("target_companies", [])))
  seed_publications = [
    normalize_publication_number(value)
    for value in list(patent_plan.get("seed_publications", []) or [])
    if normalize_publication_number(str(value or ""))
  ]
  include_terms = normalize_terms(list(selected_query.get("terms", []) or []))
  exclude_terms = normalize_terms(list(patent_plan.get("exclude_terms", []) or []))

  request = {
    "query_id": resolved_query_id,
    "search_source": "patent",
    "strategy": str(selected_query.get("strategy", "") or "").strip(),
    "language": str(selected_query.get("language", "") or "").strip(),
    "query_text_preview": str(selected_query.get("query_text", "") or "").strip(),
    "theme_name": str(migrated_profile.get("theme_name", "") or "").strip(),
    "country_codes": countries,
    "publication_date_from": date_from,
    "publication_date_to": date_to,
    "include_terms": include_terms,
    "target_companies": target_companies,
    "seed_publications": seed_publications,
    "exclude_terms": exclude_terms,
    "max_results": resolved_limit,
    "maximum_bytes_billed": int(cfg.bigquery_max_bytes_billed or 0),
    "location": str(cfg.bigquery_location or "US").strip() or "US",
    "project_id": str(cfg.bigquery_project_id or "").strip(),
    "execute_enabled": False,
    "dry_run_only": True,
    "execution_guard_reason": "Phase v9-5B1 では BigQuery 本実行は禁止です。",
    "allow_query_execute_after_confirmation": False,
    "time_range": str(time_range or "12m"),
  }
  parameters = build_patent_query_parameters(request)
  sql = build_patent_bigquery_sql(request)
  validation_rows = validate_patent_bigquery_request(request, sql)
  return {
    "request": request,
    "sql": sql,
    "parameters": parameters,
    "validation_rows": validation_rows,
    "query_options": query_options,
    "selected_query_id": resolved_query_id,
  }


def build_patent_query_parameters(request: dict[str, Any]) -> list[dict[str, Any]]:
  return [
    {"name": "query_id", "parameter_type": "STRING", "value": str(request.get("query_id", "") or "")},
    {"name": "strategy", "parameter_type": "STRING", "value": str(request.get("strategy", "") or "")},
    {"name": "language", "parameter_type": "STRING", "value": str(request.get("language", "") or "")},
    {"name": "theme_name", "parameter_type": "STRING", "value": str(request.get("theme_name", "") or "")},
    {"name": "country_codes", "parameter_type": "ARRAY<STRING>", "value": list(request.get("country_codes", []) or [])},
    {"name": "publication_date_from", "parameter_type": "INT64", "value": int(request.get("publication_date_from", 0) or 0)},
    {"name": "publication_date_to", "parameter_type": "INT64", "value": int(request.get("publication_date_to", 0) or 0)},
    {"name": "include_terms", "parameter_type": "ARRAY<STRING>", "value": list(request.get("include_terms", []) or [])},
    {"name": "target_companies", "parameter_type": "ARRAY<STRING>", "value": list(request.get("target_companies", []) or [])},
    {"name": "seed_publications", "parameter_type": "ARRAY<STRING>", "value": list(request.get("seed_publications", []) or [])},
    {"name": "exclude_terms", "parameter_type": "ARRAY<STRING>", "value": list(request.get("exclude_terms", []) or [])},
    {"name": "max_results", "parameter_type": "INT64", "value": int(request.get("max_results", 0) or 0)},
  ]


def build_patent_bigquery_sql(request: dict[str, Any]) -> str:
  title_expr = _localized_text_expr("title_localized")
  abstract_expr = _localized_text_expr("abstract_localized")
  search_text_expr = f"LOWER(CONCAT(IFNULL({title_expr}, ''), ' ', IFNULL({abstract_expr}, '')))"

  sql = f"""
SELECT
  publication_number,
  application_number,
  family_id,
  country_code AS country,
  kind_code,
  publication_date,
  priority_date,
  {title_expr} AS title,
  {abstract_expr} AS abstract,
  {_assignees_expr()} AS assignee,
  {_inventors_expr()} AS inventor,
  {_cpc_codes_expr()} AS cpc_codes,
  CONCAT('https://patents.google.com/patent/', publication_number, '/en') AS source_url,
  @query_id AS query_id,
  @strategy AS query_strategy,
  @language AS query_language,
  @theme_name AS related_theme_name,
  IF(REPLACE(UPPER(publication_number), '-', '') IN UNNEST(@seed_publications), TRUE, FALSE) AS is_seed_publication,
  (
    SELECT COUNT(1)
    FROM UNNEST(@include_terms) AS term
    WHERE term IS NOT NULL
      AND term != ''
      AND (
        (LOWER(term) = 'pan' AND REGEXP_CONTAINS({search_text_expr}, r'\\bpan\\b'))
        OR (LOWER(term) != 'pan' AND CONTAINS_SUBSTR({search_text_expr}, LOWER(term)))
      )
  ) AS matched_keyword_count
FROM {PUBLICATIONS_TABLE}
WHERE
  (ARRAY_LENGTH(@country_codes) = 0 OR country_code IN UNNEST(@country_codes))
  AND (@publication_date_from = 0 OR publication_date >= @publication_date_from)
  AND (@publication_date_to = 0 OR publication_date <= @publication_date_to)
  AND (
    ARRAY_LENGTH(@include_terms) = 0
    OR EXISTS (
      SELECT 1
      FROM UNNEST(@include_terms) AS term
      WHERE term IS NOT NULL
        AND term != ''
        AND (
          (LOWER(term) = 'pan' AND REGEXP_CONTAINS({search_text_expr}, r'\\bpan\\b'))
          OR (LOWER(term) != 'pan' AND CONTAINS_SUBSTR({search_text_expr}, LOWER(term)))
        )
    )
    OR EXISTS (
      SELECT 1
      FROM UNNEST(@target_companies) AS company
      JOIN UNNEST(IFNULL(assignee_harmonized, [])) AS ah
      ON company IS NOT NULL
      WHERE company != ''
        AND LOWER(ah.name) LIKE CONCAT('%', LOWER(company), '%')
    )
    OR REPLACE(UPPER(publication_number), '-', '') IN UNNEST(@seed_publications)
  )
  AND NOT EXISTS (
    SELECT 1
    FROM UNNEST(@exclude_terms) AS term
    WHERE term IS NOT NULL
      AND term != ''
      AND CONTAINS_SUBSTR({search_text_expr}, LOWER(term))
  )
ORDER BY
  is_seed_publication DESC,
  matched_keyword_count DESC,
  publication_date DESC
LIMIT @max_results
""".strip()
  return sql


def validate_patent_bigquery_request(request: dict[str, Any], sql: str) -> list[dict[str, str]]:
  rows: list[dict[str, str]] = []
  if not str(request.get("query_id", "") or "").strip():
    rows.append({"status": "error", "message": "query_id が未設定です。"})
  if int(request.get("max_results", 0) or 0) <= 0:
    rows.append({"status": "error", "message": "max_results は 1 以上である必要があります。"})
  if int(request.get("maximum_bytes_billed", 0) or 0) <= 0:
    rows.append({"status": "warning", "message": "maximum_bytes_billed が未設定です。dry-run 実行は拒否されます。"})
  if request.get("execute_enabled") is not False:
    rows.append({"status": "error", "message": "Phase v9-5B1 では execute_enabled は False である必要があります。"})
  if request.get("allow_query_execute_after_confirmation") is not False:
    rows.append({"status": "error", "message": "Phase v9-5B1 ではユーザー確認後の本実行も許可しません。"})
  lowered = sql.lower()
  scrubbed = lowered.replace("candidate_information_only", "")
  for token in FORBIDDEN_SQL_TOKENS:
    if token in scrubbed:
      rows.append({"status": "error", "message": f"禁止フィールドを検出しました: {token}"})
  if "title_localized" not in sql or "abstract_localized" not in sql:
    rows.append({"status": "error", "message": "title / abstract 中心の bibliographic SQL になっていません。"})
  if "query(" in lowered or "create table" in lowered or "insert " in lowered or "update " in lowered or "delete " in lowered:
    rows.append({"status": "error", "message": "SQL に禁止操作が含まれています。"})
  if not rows:
    rows.append({"status": "ok", "message": "validation passed"})
  return rows


def run_patent_bigquery_dry_run(
  preview: dict[str, Any],
  *,
  client_factory: ClientFactory | None = None,
  job_config_builder: JobConfigBuilder | None = None,
  config: BigQuerySafetyConfig | None = None,
) -> dict[str, Any]:
  cfg = config or BigQuerySafetyConfig.from_env()
  request = dict(preview.get("request", {}) or {})
  sql = str(preview.get("sql", "") or "")
  parameters = list(preview.get("parameters", []) or [])
  validation_rows = list(preview.get("validation_rows", []) or [])

  if any(str(row.get("status", "")) == "error" for row in validation_rows):
    return {
      "dry_run_status": "validation_error",
      "estimated_bytes": 0,
      "estimated_gb": 0.0,
      "estimated_cost_usd": 0.0,
      "maximum_bytes_billed": int(request.get("maximum_bytes_billed", 0) or 0),
      "would_be_blocked_by_max_bytes": False,
      "query_validation": validation_rows,
      "execute_enabled": False,
      "execution_allowed": False,
      "error": "query validation error",
    }

  try:
    assert_dry_run_allowed(cfg)
  except PermissionError as exc:
    return {
      "dry_run_status": "rejected",
      "estimated_bytes": 0,
      "estimated_gb": 0.0,
      "estimated_cost_usd": 0.0,
      "maximum_bytes_billed": int(request.get("maximum_bytes_billed", 0) or 0),
      "would_be_blocked_by_max_bytes": False,
      "query_validation": validation_rows,
      "execute_enabled": False,
      "execution_allowed": False,
      "error": str(exc),
    }

  resolved_project = resolve_project_id(str(cfg.bigquery_project_id or "").strip() or None)
  project_id = str(resolved_project.get("project_id", "") or "").strip()
  if not project_id:
    return {
      "dry_run_status": "error",
      "estimated_bytes": 0,
      "estimated_gb": 0.0,
      "estimated_cost_usd": 0.0,
      "maximum_bytes_billed": int(request.get("maximum_bytes_billed", 0) or 0),
      "would_be_blocked_by_max_bytes": False,
      "query_validation": validation_rows,
      "execute_enabled": False,
      "execution_allowed": False,
      "error": str(resolved_project.get("error") or "project_id unresolved"),
    }

  try:
    client = (client_factory or _default_client_factory)(project_id, str(cfg.bigquery_location or "US"))
    job_config = (job_config_builder or _build_real_job_config)({"parameters": parameters, "maximum_bytes_billed": int(cfg.bigquery_max_bytes_billed or 0)}, True)
    job = client.query(sql, job_config=job_config)
    estimated_bytes = int(getattr(job, "total_bytes_processed", 0) or 0)
    maximum_bytes_billed = int(cfg.bigquery_max_bytes_billed or 0)
    blocked = maximum_bytes_billed > 0 and estimated_bytes > maximum_bytes_billed
    return {
      "dry_run_status": "ok",
      "estimated_bytes": estimated_bytes,
      "estimated_gb": bytes_to_gb(estimated_bytes),
      "estimated_cost_usd": estimate_usd_from_bytes(estimated_bytes),
      "maximum_bytes_billed": maximum_bytes_billed,
      "would_be_blocked_by_max_bytes": blocked,
      "query_validation": validation_rows,
      "execute_enabled": False,
      "execution_allowed": False,
      "project_id": project_id,
      "location": str(cfg.bigquery_location or "US"),
      "job_id": str(getattr(job, "job_id", "") or ""),
      "approved_for_execute": False,
      "error": None,
    }
  except Exception as exc:  # noqa: BLE001
    return {
      "dry_run_status": "error",
      "estimated_bytes": 0,
      "estimated_gb": 0.0,
      "estimated_cost_usd": 0.0,
      "maximum_bytes_billed": int(cfg.bigquery_max_bytes_billed or 0),
      "would_be_blocked_by_max_bytes": False,
      "query_validation": validation_rows,
      "execute_enabled": False,
      "execution_allowed": False,
      "error": str(exc),
    }


def save_patent_dry_run_artifacts(
  preview: dict[str, Any],
  dry_run_result: dict[str, Any],
  *,
  base_dir: Path | None = None,
) -> dict[str, Path]:
  dirs = ensure_v9_run_dirs(base_dir)
  runs_dir = dirs["root"] / "patent_query_runs"
  runs_dir.mkdir(parents=True, exist_ok=True)
  run_id = datetime.now().astimezone().strftime("%Y-%m-%d_%H%M%S")
  target_dir = runs_dir / run_id
  target_dir.mkdir(parents=True, exist_ok=True)

  sql_path = target_dir / "patent_query.sql"
  plan_path = target_dir / "patent_query_plan.json"
  dry_run_path = target_dir / "patent_dry_run.json"
  validation_path = target_dir / "patent_query_validation.csv"

  sql_path.write_text(str(preview.get("sql", "") or "") + "\n", encoding="utf-8")
  plan_path.write_text(json.dumps({
    "request": preview.get("request", {}),
    "parameters": preview.get("parameters", []),
  }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  dry_run_path.write_text(json.dumps(dry_run_result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  validation_path.write_text(build_patent_validation_csv(list(preview.get("validation_rows", []) or [])), encoding="utf-8")
  return {
    "run_dir": target_dir,
    "sql": sql_path,
    "plan_json": plan_path,
    "dry_run_json": dry_run_path,
    "validation_csv": validation_path,
  }


def execute_patent_bigquery_retrieval(
  preview: dict[str, Any],
  dry_run_result: dict[str, Any],
  *,
  approved: bool,
  client_factory: ClientFactory | None = None,
  job_config_builder: JobConfigBuilder | None = None,
  config: BigQuerySafetyConfig | None = None,
) -> dict[str, Any]:
  cfg = config or BigQuerySafetyConfig.from_env()
  request = dict(preview.get("request", {}) or {})
  sql = str(preview.get("sql", "") or "")
  parameters = list(preview.get("parameters", []) or [])
  validation_rows = list(preview.get("validation_rows", []) or [])

  retrieval_run_id = _build_retrieval_run_id(str(request.get("query_id", "") or "unknown"))
  if not approved:
    return _blocked_retrieval_result(
      retrieval_run_id,
      request,
      dry_run_result,
      validation_rows,
      "ユーザー承認前のため、本実行は許可されていません。",
      provider_status="not_approved",
    )
  if any(str(row.get("status", "")) == "error" for row in validation_rows):
    return _blocked_retrieval_result(
      retrieval_run_id,
      request,
      dry_run_result,
      validation_rows,
      "query validation error",
      provider_status="validation_error",
    )
  if str(dry_run_result.get("dry_run_status", "") or "") != "ok":
    return _blocked_retrieval_result(
      retrieval_run_id,
      request,
      dry_run_result,
      validation_rows,
      "dry-run 成功済みqueryのみ実行できます。",
      provider_status="dry_run_required",
    )
  if bool(dry_run_result.get("would_be_blocked_by_max_bytes", False)):
    return _blocked_retrieval_result(
      retrieval_run_id,
      request,
      dry_run_result,
      validation_rows,
      "費用上限を超過するため、本実行は拒否されました。",
      provider_status="blocked_by_max_bytes",
    )

  try:
    assert_execute_allowed(cfg)
  except PermissionError as exc:
    return _blocked_retrieval_result(
      retrieval_run_id,
      request,
      dry_run_result,
      validation_rows,
      str(exc),
      provider_status="execute_rejected",
    )

  resolved_project = resolve_project_id(str(cfg.bigquery_project_id or "").strip() or None)
  project_id = str(resolved_project.get("project_id", "") or "").strip()
  if not project_id:
    return _blocked_retrieval_result(
      retrieval_run_id,
      request,
      dry_run_result,
      validation_rows,
      str(resolved_project.get("error") or "project_id unresolved"),
      provider_status="error",
    )

  rows: list[dict[str, Any]] = []
  provider_status = "success"
  error_message: str | None = None
  job_id = ""
  try:
    client = (client_factory or _default_client_factory)(project_id, str(cfg.bigquery_location or "US"))
    job_config = (job_config_builder or _build_real_job_config)(
      {"parameters": parameters, "maximum_bytes_billed": int(cfg.bigquery_max_bytes_billed or 0)},
      False,
    )
    job = client.query(sql, job_config=job_config)
    job_id = str(getattr(job, "job_id", "") or "")
    iterator = job.result() if hasattr(job, "result") else []
    for raw_row in iterator:
      try:
        row = _row_to_dict(raw_row)
        rows.append(row)
      except Exception as exc:  # noqa: BLE001
        provider_status = "partial_success" if rows else "error"
        error_message = str(exc)
        break
  except Exception as exc:  # noqa: BLE001
    provider_status = "partial_success" if rows else "error"
    error_message = str(exc)

  normalized_rows = _normalize_patent_candidate_rows(
    rows,
    query_id=str(request.get("query_id", "") or ""),
    retrieval_run_id=retrieval_run_id,
    bigquery_job_id=job_id,
    provider_status=provider_status,
    retrieval_mode="real",
    record_stage="staged",
  )

  return {
    "retrieval_run_id": retrieval_run_id,
    "query_id": str(request.get("query_id", "") or ""),
    "provider_status": provider_status,
    "retrieval_mode": "real",
    "record_stage": "staged",
    "execution_allowed": provider_status in {"success", "partial_success"},
    "execute_enabled": True,
    "approved": True,
    "project_id": project_id,
    "location": str(cfg.bigquery_location or "US"),
    "bigquery_job_id": job_id,
    "maximum_bytes_billed": int(cfg.bigquery_max_bytes_billed or 0),
    "estimated_bytes_from_dry_run": int(dry_run_result.get("estimated_bytes", 0) or 0),
    "estimated_cost_usd_from_dry_run": float(dry_run_result.get("estimated_cost_usd", 0.0) or 0.0),
    "query_validation": validation_rows,
    "rows_retrieved": len(normalized_rows),
    "rows": normalized_rows,
    "error": error_message,
    "log": {
      "provider_status": provider_status,
      "query_id": str(request.get("query_id", "") or ""),
      "retrieval_run_id": retrieval_run_id,
      "bigquery_job_id": job_id,
      "rows_retrieved": len(normalized_rows),
      "error": error_message,
    },
  }


def save_patent_retrieval_artifacts(
  preview: dict[str, Any],
  dry_run_result: dict[str, Any],
  retrieval_result: dict[str, Any],
  *,
  base_dir: Path | None = None,
) -> dict[str, Path]:
  dirs = ensure_v9_run_dirs(base_dir)
  runs_dir = dirs["root"] / "patent_retrieval_runs"
  runs_dir.mkdir(parents=True, exist_ok=True)
  run_id = str(retrieval_result.get("retrieval_run_id", "") or "").strip() or datetime.now().astimezone().strftime("%Y-%m-%d_%H%M%S")
  target_dir = runs_dir / run_id
  target_dir.mkdir(parents=True, exist_ok=True)

  sql_path = target_dir / "patent_query.sql"
  plan_path = target_dir / "patent_query_plan.json"
  dry_run_path = target_dir / "patent_dry_run.json"
  validation_path = target_dir / "patent_query_validation.csv"
  staged_json_path = target_dir / "patent_candidates_staged.json"
  staged_csv_path = target_dir / "patent_candidates_staged.csv"
  log_path = target_dir / "patent_retrieval_log.json"

  sql_path.write_text(str(preview.get("sql", "") or "") + "\n", encoding="utf-8")
  plan_path.write_text(json.dumps({
    "request": preview.get("request", {}),
    "parameters": preview.get("parameters", []),
  }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  dry_run_path.write_text(json.dumps(dry_run_result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  validation_path.write_text(build_patent_validation_csv(list(preview.get("validation_rows", []) or [])), encoding="utf-8")
  staged_json_path.write_text(json.dumps({
    "retrieval_run_id": retrieval_result.get("retrieval_run_id", ""),
    "provider_status": retrieval_result.get("provider_status", ""),
    "rows": retrieval_result.get("rows", []),
  }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  staged_csv_path.write_text(build_patent_candidates_csv(list(retrieval_result.get("rows", []) or [])), encoding="utf-8")
  log_path.write_text(json.dumps({
    "retrieval_run_id": retrieval_result.get("retrieval_run_id", ""),
    "query_id": retrieval_result.get("query_id", ""),
    "provider_status": retrieval_result.get("provider_status", ""),
    "bigquery_job_id": retrieval_result.get("bigquery_job_id", ""),
    "rows_retrieved": retrieval_result.get("rows_retrieved", 0),
    "error": retrieval_result.get("error"),
    "log": retrieval_result.get("log", {}),
  }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  return {
    "run_dir": target_dir,
    "sql": sql_path,
    "plan_json": plan_path,
    "dry_run_json": dry_run_path,
    "validation_csv": validation_path,
    "staged_json": staged_json_path,
    "staged_csv": staged_csv_path,
    "retrieval_log_json": log_path,
  }


def build_patent_validation_csv(rows: list[dict[str, str]]) -> str:
  buffer = StringIO()
  writer = csv.DictWriter(buffer, fieldnames=["status", "message"])
  writer.writeheader()
  for row in rows:
    writer.writerow({
      "status": str(row.get("status", "") or ""),
      "message": str(row.get("message", "") or ""),
    })
  return buffer.getvalue()


def build_patent_candidates_csv(rows: list[dict[str, Any]]) -> str:
  fieldnames = [
    "publication_number",
    "family_id",
    "family_duplicate_candidate",
    "family_duplicate_group_size",
    "title",
    "abstract",
    "assignee",
    "inventor",
    "publication_date",
    "priority_date",
    "country",
    "cpc_codes",
    "source_url",
    "query_id",
    "retrieval_run_id",
    "bigquery_job_id",
    "provider_status",
    "record_stage",
    "retrieval_mode",
  ]
  buffer = StringIO()
  writer = csv.DictWriter(buffer, fieldnames=fieldnames)
  writer.writeheader()
  for row in rows:
    writer.writerow({key: row.get(key, "") for key in fieldnames})
  return buffer.getvalue()


def _publication_window_from_time_range(time_range: str) -> tuple[int, int]:
  today = date.today()
  end_value = int(today.strftime("%Y%m%d"))
  months = {
    "1m": 1,
    "3m": 3,
    "6m": 6,
    "12m": 12,
    "24m": 24,
  }.get(str(time_range or "12m"), 12)
  start_year = today.year
  start_month = today.month - months + 1
  while start_month <= 0:
    start_month += 12
    start_year -= 1
  start_value = int(f"{start_year:04d}{start_month:02d}01")
  return start_value, end_value


def _normalize_positive_int(value: Any, default: int) -> int:
  try:
    normalized = int(value)
  except (TypeError, ValueError):
    normalized = int(default)
  return max(normalized, 1)


def _build_retrieval_run_id(query_id: str) -> str:
  timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
  return f"patent_retrieval_{query_id}_{timestamp}"


def _row_to_dict(row: Any) -> dict[str, Any]:
  if isinstance(row, dict):
    return dict(row)
  if hasattr(row, "items"):
    return dict(row.items())
  return dict(row)


def _blocked_retrieval_result(
  retrieval_run_id: str,
  request: dict[str, Any],
  dry_run_result: dict[str, Any],
  validation_rows: list[dict[str, str]],
  error_message: str,
  *,
  provider_status: str,
) -> dict[str, Any]:
  return {
    "retrieval_run_id": retrieval_run_id,
    "query_id": str(request.get("query_id", "") or ""),
    "provider_status": provider_status,
    "retrieval_mode": "real",
    "record_stage": "staged",
    "execution_allowed": False,
    "execute_enabled": False,
    "approved": False,
    "project_id": str(request.get("project_id", "") or ""),
    "location": str(request.get("location", "") or ""),
    "bigquery_job_id": "",
    "maximum_bytes_billed": int(request.get("maximum_bytes_billed", 0) or 0),
    "estimated_bytes_from_dry_run": int(dry_run_result.get("estimated_bytes", 0) or 0),
    "estimated_cost_usd_from_dry_run": float(dry_run_result.get("estimated_cost_usd", 0.0) or 0.0),
    "query_validation": validation_rows,
    "rows_retrieved": 0,
    "rows": [],
    "error": error_message,
    "log": {
      "provider_status": provider_status,
      "query_id": str(request.get("query_id", "") or ""),
      "retrieval_run_id": retrieval_run_id,
      "bigquery_job_id": "",
      "rows_retrieved": 0,
      "error": error_message,
    },
  }


def _normalize_patent_candidate_rows(
  rows: list[dict[str, Any]],
  *,
  query_id: str,
  retrieval_run_id: str,
  bigquery_job_id: str,
  provider_status: str,
  retrieval_mode: str,
  record_stage: str,
) -> list[dict[str, Any]]:
  normalized_rows: list[dict[str, Any]] = []
  family_counts: dict[str, int] = {}
  for row in rows:
    family_key = str(row.get("family_id", "") or "").strip()
    if family_key:
      family_counts[family_key] = family_counts.get(family_key, 0) + 1

  for index, row in enumerate(rows, start=1):
    publication_number = normalize_publication_number(str(row.get("publication_number", "") or ""))
    family_id = str(row.get("family_id", "") or "").strip()
    normalized_rows.append(
      {
        "candidate_id": f"{retrieval_run_id}_{index:04d}",
        "publication_number": publication_number,
        "publication_number_original": str(row.get("publication_number", "") or "").strip(),
        "application_number": normalize_publication_number(str(row.get("application_number", "") or "")),
        "family_id": family_id,
        "family_duplicate_candidate": bool(family_id and family_counts.get(family_id, 0) > 1),
        "family_duplicate_group_size": int(family_counts.get(family_id, 0)),
        "title": str(row.get("title", "") or "").strip(),
        "abstract": str(row.get("abstract", "") or "").strip(),
        "assignee": str(row.get("assignee", "") or "").strip(),
        "inventor": str(row.get("inventor", row.get("inventors", "")) or "").strip(),
        "publication_date": str(row.get("publication_date", "") or "").strip(),
        "priority_date": str(row.get("priority_date", "") or "").strip(),
        "country": str(row.get("country", row.get("country_code", "")) or "").strip(),
        "cpc_codes": str(row.get("cpc_codes", row.get("cpc", "")) or "").strip(),
        "source_url": str(row.get("source_url", row.get("url", "")) or "").strip(),
        "query_id": query_id,
        "retrieval_run_id": retrieval_run_id,
        "bigquery_job_id": bigquery_job_id,
        "provider_status": provider_status,
        "retrieval_mode": retrieval_mode,
        "record_stage": record_stage,
        "data_source": "bigquery_patent",
      }
    )
  return normalized_rows


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


def _inventors_expr() -> str:
  return (
    "(SELECT STRING_AGG(DISTINCT inv.name, '; ' ORDER BY inv.name) "
    "FROM UNNEST(IFNULL(inventor, [])) AS inv "
    "WHERE inv.name IS NOT NULL AND inv.name != '')"
  )


def _cpc_codes_expr() -> str:
  return (
    "(SELECT STRING_AGG(DISTINCT item.code, '; ' ORDER BY item.code) "
    "FROM UNNEST(IFNULL(cpc, [])) AS item "
    "WHERE item.code IS NOT NULL AND item.code != '')"
  )


def _default_client_factory(project_id: str, location: str) -> Any:
  from google.cloud import bigquery

  return bigquery.Client(project=project_id, location=location)


def _build_real_job_config(payload: dict[str, Any], dry_run: bool) -> Any:
  from google.cloud import bigquery

  params = []
  for item in list(payload.get("parameters", []) or []):
    name = str(item.get("name", "") or "")
    parameter_type = str(item.get("parameter_type", "") or "")
    value = item.get("value")
    if parameter_type == "ARRAY<STRING>":
      params.append(bigquery.ArrayQueryParameter(name, "STRING", list(value or [])))
    elif parameter_type == "INT64":
      params.append(bigquery.ScalarQueryParameter(name, "INT64", int(value or 0)))
    else:
      params.append(bigquery.ScalarQueryParameter(name, "STRING", str(value or "")))

  return bigquery.QueryJobConfig(
    dry_run=dry_run,
    use_query_cache=False,
    query_parameters=params,
    maximum_bytes_billed=int(payload.get("maximum_bytes_billed", 0) or 0),
  )


__all__ = [
  "FORBIDDEN_SQL_TOKENS",
  "PUBLICATIONS_TABLE",
  "build_patent_candidates_csv",
  "build_patent_bigquery_preview",
  "build_patent_bigquery_sql",
  "build_patent_query_parameters",
  "build_patent_validation_csv",
  "execute_patent_bigquery_retrieval",
  "run_patent_bigquery_dry_run",
  "save_patent_dry_run_artifacts",
  "save_patent_retrieval_artifacts",
  "validate_patent_bigquery_request",
]
