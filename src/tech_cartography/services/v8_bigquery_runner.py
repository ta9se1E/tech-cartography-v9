"""BigQuery admin runner (Phase 27Q.1)."""

from __future__ import annotations

import csv
import io
import hashlib
from pathlib import Path
from typing import Any, Protocol

from tech_cartography.runtime.v8_bigquery_schema import (
  VALID_RUN_MODES,
  BigQueryDryRunReport,
  BigQueryRunManifest,
)
from tech_cartography.runtime.v8_research_theme_schema import ResearchThemeProfile
from tech_cartography.services.v8_bigquery_export import export_bigquery_run_artifacts
from tech_cartography.services.v8_bigquery_query_builder import build_bigquery_query
from tech_cartography.services.v8_bigquery_safety import (
  BigQuerySafetyConfig,
  assert_dry_run_allowed,
  assert_execute_allowed,
)
from tech_cartography.services.v8_research_theme_defaults import load_research_theme_profile
from tech_cartography.services.v8_sources_table import project_root_from_here

LARGE_CANDIDATE_COLUMNS: tuple[str, ...] = (
  "publication_number",
  "application_number",
  "country_code",
  "kind_code",
  "family_id",
  "publication_date",
  "year",
  "title",
  "abstract",
  "assignee",
  "organization",
  "inventors",
  "url",
  "source_type",
  "heuristic_score",
  "notes",
)


class BigQueryClientProtocol(Protocol):
  def query(self, sql: str, *, job_config: Any = None) -> Any: ...


class FakeBigQueryJob:
  def __init__(self, *, total_bytes: int = 1024, rows: list[dict[str, Any]] | None = None) -> None:
    self.total_bytes_processed = total_bytes
    self.job_id = "fake-job"
    self._rows = rows or []

  def result(self) -> list[dict[str, Any]]:
    return self._rows


class FakeBigQueryClient:
  """Test double — no network, no credentials."""

  def __init__(self, *, total_bytes: int = 1024, rows: list[dict[str, Any]] | None = None) -> None:
    self.total_bytes = total_bytes
    self.rows = rows or []
    self.last_sql = ""
    self.last_dry_run = False

  def query(self, sql: str, *, job_config: Any = None) -> FakeBigQueryJob:
    self.last_sql = sql
    self.last_dry_run = bool(getattr(job_config, "dry_run", False))
    return FakeBigQueryJob(total_bytes=self.total_bytes, rows=self.rows)


def _run_id(case_id: str, mode: str) -> str:
  digest = hashlib.sha256(f"{case_id}|{mode}".encode()).hexdigest()[:10]
  return f"{case_id}:bq_run:{digest}"


def _results_to_large_candidate_csv(rows: list[dict[str, Any]]) -> str:
  buffer = io.StringIO()
  writer = csv.DictWriter(buffer, fieldnames=list(LARGE_CANDIDATE_COLUMNS), extrasaction="ignore")
  writer.writeheader()
  for row in rows:
    pub_date = str(row.get("publication_date") or "")
    year = pub_date[:4] if len(pub_date) >= 4 else ""
    writer.writerow({
      "publication_number": row.get("publication_number", ""),
      "application_number": row.get("application_number", ""),
      "country_code": row.get("country_code", ""),
      "kind_code": row.get("kind_code", ""),
      "family_id": row.get("family_id", ""),
      "publication_date": pub_date,
      "year": year,
      "title": row.get("title", ""),
      "abstract": row.get("abstract", ""),
      "assignee": row.get("assignee", ""),
      "organization": row.get("assignee", ""),
      "inventors": row.get("inventor", row.get("inventors", "")),
      "url": row.get("url", ""),
      "source_type": "patent",
      "heuristic_score": row.get("heuristic_score", ""),
      "notes": "bigquery candidate — metadata only; claim text not from BQ",
    })
  return buffer.getvalue()


def _rows_to_csv(rows: list[dict[str, Any]]) -> str:
  if not rows:
    return "publication_number,title\n"
  buffer = io.StringIO()
  writer = csv.DictWriter(buffer, fieldnames=list(rows[0].keys()))
  writer.writeheader()
  for row in rows:
    writer.writerow(row)
  return buffer.getvalue()


def run_bigquery_candidate_search(
  *,
  case_id: str,
  theme_profile: ResearchThemeProfile | None = None,
  mode: str = "generate_sql",
  project_root: Path | str | None = None,
  client: BigQueryClientProtocol | None = None,
  config: BigQuerySafetyConfig | None = None,
) -> BigQueryRunManifest:
  if mode not in VALID_RUN_MODES:
    raise ValueError(f"invalid mode: {mode}")

  root = Path(project_root or project_root_from_here())
  cfg = config or BigQuerySafetyConfig.from_env()
  profile = theme_profile or load_research_theme_profile(case_id, root)
  sql, query_config = build_bigquery_query(profile, config=cfg)

  if mode == "generate_sql":
    return export_bigquery_run_artifacts(
      case_id=case_id,
      sql=sql,
      query_config=query_config,
      mode=mode,
      project_root=root,
    )

  assert_dry_run_allowed(cfg)
  bq_client = client or _real_client(cfg)
  job_config = _job_config(cfg, dry_run=True)
  dry_job = bq_client.query(sql, job_config=job_config)
  dry_report = BigQueryDryRunReport(
    case_id=case_id,
    dry_run_ok=True,
    total_bytes_processed=int(getattr(dry_job, "total_bytes_processed", 0) or 0),
    maximum_bytes_billed=cfg.bigquery_max_bytes_billed,
    job_id=str(getattr(dry_job, "job_id", "")),
    location=cfg.bigquery_location,
  )

  if mode == "dry_run":
    return export_bigquery_run_artifacts(
      case_id=case_id,
      sql=sql,
      query_config=query_config,
      mode=mode,
      dry_run_report=dry_report,
      project_root=root,
    )

  assert_execute_allowed(cfg)
  exec_config = _job_config(cfg, dry_run=False)
  exec_job = bq_client.query(sql, job_config=exec_config)
  rows = [dict(r) for r in exec_job.result()]
  results_csv = _rows_to_csv(rows)
  lc_csv = _results_to_large_candidate_csv(rows)
  return export_bigquery_run_artifacts(
    case_id=case_id,
    sql=sql,
    query_config=query_config,
    mode=mode,
    dry_run_report=dry_report,
    results_csv_text=results_csv,
    large_candidate_csv_text=lc_csv,
    project_root=root,
  )


def _real_client(cfg: BigQuerySafetyConfig) -> BigQueryClientProtocol:
  try:
    from google.cloud import bigquery
  except ImportError as exc:
    raise ImportError("google-cloud-bigquery required for live BigQuery runs") from exc
  project = cfg.bigquery_project_id or None
  return bigquery.Client(project=project, location=cfg.bigquery_location)


def _job_config(cfg: BigQuerySafetyConfig, *, dry_run: bool) -> Any:
  from google.cloud import bigquery

  return bigquery.QueryJobConfig(
    dry_run=dry_run,
    use_query_cache=not dry_run,
    maximum_bytes_billed=cfg.bigquery_max_bytes_billed,
  )
