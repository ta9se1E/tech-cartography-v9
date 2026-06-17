"""Lightweight BigQuery probe for US fulltext availability before expensive retrieval."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Callable

from tech_cartography.retrieval.bigquery_env import bytes_to_gb, estimate_usd_from_bytes, resolve_project_id
from tech_cartography.retrieval.bigquery_fulltext_query_builder import PUBLICATIONS_TABLE, escape_sql_string
from tech_cartography.retrieval.publication_number_variants import (
  build_google_patents_url_variants,
  build_publication_number_variants,
  normalize_publication_number,
)

ClientFactory = Callable[[str], Any]

DEFAULT_MAX_PROBE_USD = 2.0
DEFAULT_MAX_PROBE_GB = 150.0
QUERY_STRATEGY = "bigquery_publications_availability"


@dataclass
class FulltextAvailabilityProbeResult:
  publication_number: str = ""
  variants_checked: list[str] = field(default_factory=list)
  matched_variant: str = ""
  table_name: str = PUBLICATIONS_TABLE
  has_publication_row: bool = False
  has_claims: bool = False
  has_description: bool = False
  claims_length_estimate: int = 0
  description_length_estimate: int = 0
  probe_status: str = ""
  internal_notes: list[str] = field(default_factory=list)
  user_status_japanese: str = ""
  next_action_japanese: str = ""
  google_patents_urls: list[str] = field(default_factory=list)
  scope: str = "claims_only"
  estimated_bytes: int = 0
  estimated_usd: float = 0.0
  executed: bool = False
  query_error: str = ""


def _claims_length_expr() -> str:
  return (
    "(SELECT COALESCE(SUM(LENGTH(loc.text)), 0) "
    "FROM UNNEST(claims_localized) AS loc "
    "WHERE loc.text IS NOT NULL AND loc.text != '')"
  )


def _description_length_expr() -> str:
  return (
    "(SELECT COALESCE(SUM(LENGTH(loc.text)), 0) "
    "FROM UNNEST(description_localized) AS loc "
    "WHERE loc.text IS NOT NULL AND loc.text != '')"
  )


def build_existence_probe_query(variants: list[str]) -> str:
  literals = ", ".join(escape_sql_string(v) for v in variants if v)
  return f"""
-- availability_probe: existence check (phase 1)
SELECT publication_number, country_code
FROM {PUBLICATIONS_TABLE}
WHERE publication_number IN ({literals})
  AND country_code = 'US'
LIMIT 20
""".strip()


def build_claims_length_probe_query(publication_number: str) -> str:
  literal = escape_sql_string(publication_number)
  return f"""
-- availability_probe: claims/description length (phase 2)
SELECT
  publication_number,
  country_code,
  {_claims_length_expr()} AS claims_length_estimate,
  {_description_length_expr()} AS description_length_estimate
FROM {PUBLICATIONS_TABLE}
WHERE publication_number = {literal}
  AND country_code = 'US'
LIMIT 1
""".strip()


def build_availability_probe_query(variants: list[str]) -> str:
  return build_existence_probe_query(variants)


def build_availability_probe_queries(
  publication_number: str,
  variants: list[str] | None = None,
  *,
  metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
  checked = variants or build_publication_number_variants(publication_number, metadata=metadata)
  if not checked:
    return []
  return [
    {
      "query_id": "availability_probe",
      "publication_number": publication_number,
      "variants": checked,
      "sql": build_availability_probe_query(checked),
      "table_name": PUBLICATIONS_TABLE,
    },
  ]


def _default_client_factory(project_id: str) -> Any:
  from google.cloud import bigquery

  return bigquery.Client(project=project_id)


def _dry_run_sql(
  sql: str,
  *,
  project_id: str | None,
  client_factory: ClientFactory | None,
  use_cache: bool,
) -> dict[str, Any]:
  resolved = resolve_project_id(project_id)
  pid = resolved.get("project_id", "")
  if not pid:
    return {"dry_run_status": "error", "estimated_usd": 0.0, "error": resolved.get("error")}
  factory = client_factory or _default_client_factory
  try:
    from google.cloud import bigquery

    client = factory(pid)
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=use_cache)
    job = client.query(sql, job_config=job_config)
    estimated_bytes = int(job.total_bytes_processed or 0)
    return {
      "dry_run_status": "ok",
      "estimated_bytes": estimated_bytes,
      "estimated_gb": bytes_to_gb(estimated_bytes),
      "estimated_usd": estimate_usd_from_bytes(estimated_bytes),
      "error": None,
    }
  except Exception as exc:  # noqa: BLE001
    return {"dry_run_status": "error", "estimated_usd": 0.0, "error": str(exc)}


def dry_run_availability_probe(
  publication_number: str,
  *,
  variants: list[str] | None = None,
  metadata: dict[str, Any] | None = None,
  project_id: str | None = None,
  client_factory: ClientFactory | None = None,
  use_cache: bool = True,
) -> dict[str, Any]:
  queries = build_availability_probe_queries(publication_number, variants, metadata=metadata)
  if not queries:
    return {
      "dry_run_status": "error",
      "estimated_bytes": 0,
      "estimated_usd": 0.0,
      "error": "No publication number variants to probe",
      "variants": [],
    }
  sql = queries[0]["sql"]
  resolved = resolve_project_id(project_id)
  pid = resolved.get("project_id", "")
  if not pid:
    return {
      "dry_run_status": "error",
      "estimated_bytes": 0,
      "estimated_usd": 0.0,
      "error": resolved.get("error"),
      "sql": sql,
      "variants": queries[0]["variants"],
    }
  factory = client_factory or _default_client_factory
  try:
    from google.cloud import bigquery

    client = factory(pid)
    job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=use_cache)
    job = client.query(sql, job_config=job_config)
    estimated_bytes = int(job.total_bytes_processed or 0)
    return {
      "dry_run_status": "ok",
      "estimated_bytes": estimated_bytes,
      "estimated_gb": bytes_to_gb(estimated_bytes),
      "estimated_usd": estimate_usd_from_bytes(estimated_bytes),
      "error": None,
      "sql": sql,
      "variants": queries[0]["variants"],
    }
  except Exception as exc:  # noqa: BLE001
    return {
      "dry_run_status": "error",
      "estimated_bytes": 0,
      "estimated_usd": 0.0,
      "error": str(exc),
      "sql": sql,
      "variants": queries[0]["variants"],
    }


def classify_probe_result(
  publication_number: str,
  rows: list[dict[str, Any]],
  *,
  variants_checked: list[str],
  scope: str = "claims_only",
  query_error: str = "",
  skipped_due_to_cost: bool = False,
) -> FulltextAvailabilityProbeResult:
  urls = build_google_patents_url_variants(publication_number)
  result = FulltextAvailabilityProbeResult(
    publication_number=publication_number,
    variants_checked=list(variants_checked),
    google_patents_urls=urls,
    scope=scope,
  )

  if skipped_due_to_cost:
    result.probe_status = "skipped_due_to_probe_cost"
    result.user_status_japanese = "診断クエリの推定コストが高いため、今回はprobeを実行しませんでした。"
    result.next_action_japanese = "手動でGoogle Patentsを確認するか、管理者に診断実行を依頼してください。"
    result.internal_notes.append("probe dry-run exceeded cost threshold")
    return result

  if query_error:
    result.probe_status = "query_error"
    result.query_error = query_error
    result.user_status_japanese = "BigQuery診断クエリでエラーが発生しました。"
    result.next_action_japanese = "番号形式とクエリ設定を確認してください。"
    result.internal_notes.append(query_error)
    return result

  if not rows:
    result.probe_status = "not_found_in_bigquery"
    result.has_publication_row = False
    result.user_status_japanese = (
      "BigQuery側では対象公報の行が見つかりませんでした。"
      "番号形式の不一致、またはpublic data未反映の可能性があります。"
    )
    result.next_action_japanese = (
      "Google Patents / PDF / 手動貼り付けルートで請求項を確認してください。"
    )
    result.internal_notes.extend(
      [
        "No rows matched any checked publication_number variant.",
        "Hypothesis: format mismatch, B2 grant without claims in BQ, or data lag vs Google Patents.",
      ],
    )
    return result

  best = max(
    rows,
    key=lambda r: int(r.get("claims_length_estimate") or 0) + int(r.get("description_length_estimate") or 0),
  )
  result.matched_variant = str(best.get("publication_number") or "")
  result.has_publication_row = True
  result.claims_length_estimate = int(best.get("claims_length_estimate") or 0)
  result.description_length_estimate = int(best.get("description_length_estimate") or 0)
  result.has_claims = result.claims_length_estimate > 0
  result.has_description = result.description_length_estimate > 0

  requested = str(scope or "claims_only").lower()
  if result.has_claims and requested in {"claims_only", "claims_and_description"}:
    result.probe_status = "found_claims"
    result.user_status_japanese = f"BigQueryで請求項テキストを確認できました（{result.matched_variant}）。"
    result.next_action_japanese = "この番号形式でfulltext取得に進めます。"
  elif result.has_description and requested == "description_only":
    result.probe_status = "found_description_only"
    result.user_status_japanese = "BigQueryで明細書テキストを確認できました。"
    result.next_action_japanese = "description_only取得に進めます。"
  elif result.has_description and not result.has_claims:
    result.probe_status = "found_description_only"
    result.user_status_japanese = (
      "BigQueryでは請求項は空ですが、明細書テキストは存在します。"
      "B2公報でA1側にclaimsがある可能性があります。"
    )
    result.next_action_japanese = "claims_onlyでは取得できないため、A1公開公報候補の確認またはmanual routeを検討してください。"
    result.internal_notes.append("Publication row exists but claims_length_estimate is 0")
  elif result.has_publication_row:
    result.probe_status = "found_metadata_only"
    result.user_status_japanese = (
      "BigQueryに公報行はありますが、claims/descriptionテキストが空です。"
    )
    result.next_action_japanese = "Google Patents / 手動貼り付けルートを推奨します。"
    result.internal_notes.append("Row found but localized text fields appear empty")
  else:
    result.probe_status = "publication_number_format_mismatch"
    result.user_status_japanese = "確認した番号形式ではBigQueryと一致しませんでした。"
    result.next_action_japanese = "番号形式を再確認し、metadata上のA1候補があれば確認してください。"

  if result.probe_status in {
    "not_found_in_bigquery",
    "found_metadata_only",
    "found_description_only",
    "publication_number_format_mismatch",
  } and requested == "claims_only" and not result.has_claims:
    result.probe_status = "manual_route_recommended"
    result.next_action_japanese = (
      "BigQuery fulltextでは請求項を取得できないため、Google Patents / 手動貼り付けルートへ回してください。"
    )

  return result


def execute_availability_probe(
  publication_number: str,
  *,
  scope: str = "claims_only",
  variants: list[str] | None = None,
  metadata: dict[str, Any] | None = None,
  project_id: str | None = None,
  client_factory: ClientFactory | None = None,
  use_cache: bool = True,
  execute: bool = True,
  max_probe_usd: float = DEFAULT_MAX_PROBE_USD,
  max_probe_gb: float = DEFAULT_MAX_PROBE_GB,
) -> FulltextAvailabilityProbeResult:
  dry = dry_run_availability_probe(
    publication_number,
    variants=variants,
    metadata=metadata,
    project_id=project_id,
    client_factory=client_factory,
    use_cache=use_cache,
  )
  checked = list(dry.get("variants") or [])
  est_usd = float(dry.get("estimated_usd") or 0)
  est_gb = float(dry.get("estimated_gb") or 0)
  if dry.get("dry_run_status") != "ok":
    return classify_probe_result(
      publication_number,
      [],
      variants_checked=checked,
      scope=scope,
      query_error=str(dry.get("error") or "dry-run failed"),
    )
  if est_usd > max_probe_usd or est_gb > max_probe_gb:
    result = classify_probe_result(
      publication_number,
      [],
      variants_checked=checked,
      scope=scope,
      skipped_due_to_cost=True,
    )
    result.estimated_bytes = int(dry.get("estimated_bytes") or 0)
    result.estimated_usd = est_usd
    return result

  if not execute:
    result = classify_probe_result(publication_number, [], variants_checked=checked, scope=scope)
    result.estimated_bytes = int(dry.get("estimated_bytes") or 0)
    result.estimated_usd = est_usd
    result.internal_notes.append("execute=False; probe classified without BigQuery execution")
    return result

  resolved = resolve_project_id(project_id)
  pid = resolved.get("project_id", "")
  if not pid:
    return classify_probe_result(
      publication_number,
      [],
      variants_checked=checked,
      scope=scope,
      query_error=str(resolved.get("error")),
    )

  sql = dry.get("sql") or ""
  factory = client_factory or _default_client_factory
  try:
    from google.cloud import bigquery

    client = factory(pid)
    job_config = bigquery.QueryJobConfig(dry_run=False, use_query_cache=use_cache)
    existence_rows = [dict(row.items()) for row in client.query(sql, job_config=job_config).result()]
    rows = existence_rows
    if existence_rows:
      best_pub = str(existence_rows[0].get("publication_number") or publication_number)
      claims_sql = build_claims_length_probe_query(best_pub)
      claims_dry = _dry_run_sql(
        claims_sql,
        project_id=project_id,
        client_factory=client_factory,
        use_cache=use_cache,
      )
      claims_est_usd = float(claims_dry.get("estimated_usd") or 0)
      if claims_dry.get("dry_run_status") == "ok" and claims_est_usd <= max_probe_usd:
        claims_job_config = bigquery.QueryJobConfig(dry_run=False, use_query_cache=use_cache)
        rows = [
          dict(row.items())
          for row in client.query(claims_sql, job_config=claims_job_config).result()
        ] or existence_rows
    result = classify_probe_result(publication_number, rows, variants_checked=checked, scope=scope)
    result.estimated_bytes = int(dry.get("estimated_bytes") or 0)
    result.estimated_usd = est_usd
    result.executed = True
    return result
  except Exception as exc:  # noqa: BLE001
    return classify_probe_result(
      publication_number,
      [],
      variants_checked=checked,
      scope=scope,
      query_error=str(exc),
    )


def probe_result_to_public_dict(result: FulltextAvailabilityProbeResult) -> dict[str, Any]:
  data = asdict(result)
  for key in ("estimated_usd", "estimated_bytes"):
    data.pop(key, None)
  return data


def save_availability_probe_result(
  result: FulltextAvailabilityProbeResult | dict[str, Any],
  output_dir: str | Path,
) -> dict[str, str]:
  from tech_cartography.reports.fulltext_availability_report import save_fulltext_availability_report

  row = result if isinstance(result, dict) else asdict(result)
  return save_fulltext_availability_report(row, output_dir)
