"""BigQuery run export helpers (Phase 27Q.1)."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.runtime.v8_bigquery_schema import BigQueryDryRunReport, BigQueryRunManifest
from tech_cartography.runtime.v8_sources_schema import utc_now_iso
from tech_cartography.services.v8_sources_table import project_root_from_here

LOCAL_BIGQUERY_RUNS = "local_v8_bigquery_runs"


def get_bigquery_runs_dir(project_root: Path | str | None = None) -> Path:
  root = Path(project_root or project_root_from_here())
  return root / "outputs" / LOCAL_BIGQUERY_RUNS


def export_bigquery_run_artifacts(
  *,
  case_id: str,
  sql: str,
  query_config: dict,
  mode: str,
  dry_run_report: BigQueryDryRunReport | None = None,
  results_csv_text: str = "",
  large_candidate_csv_text: str = "",
  project_root: Path | str | None = None,
) -> BigQueryRunManifest:
  root = Path(project_root or project_root_from_here())
  stamp = utc_now_iso().replace(":", "").replace("-", "").replace("+00:00", "Z")
  output_dir = get_bigquery_runs_dir(root) / case_id / stamp
  output_dir.mkdir(parents=True, exist_ok=True)

  sql_path = output_dir / "generated_query.sql"
  sql_path.write_text(sql, encoding="utf-8")

  config_path = output_dir / "query_config.json"
  config_path.write_text(json.dumps(query_config, ensure_ascii=False, indent=2), encoding="utf-8")

  summary_path = output_dir / "query_summary.md"
  summary_path.write_text(
    "\n".join([
      f"# BigQuery Query Summary — {case_id}",
      "",
      f"- mode: {mode}",
      f"- theme: {query_config.get('theme_name', '—')}",
      f"- search_mode: {query_config.get('search_mode', '—')}",
      f"- limit: {query_config.get('limit', '—')}",
      f"- seed_count: {len(query_config.get('seed_publication_numbers') or [])}",
      "",
      "JP/CN claim/description は取得しません — candidate metadata only.",
      "",
    ]),
    encoding="utf-8",
  )

  dry_run_path = ""
  if dry_run_report:
    dry_run_path = str(output_dir / "dry_run_report.json")
    Path(dry_run_path).write_text(json.dumps(dry_run_report.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
    md = output_dir / "dry_run_report.md"
    md.write_text(
      "\n".join([
        f"# Dry Run — {case_id}",
        "",
        f"- ok: {dry_run_report.dry_run_ok}",
        f"- total_bytes_processed: {dry_run_report.total_bytes_processed}",
        f"- maximum_bytes_billed: {dry_run_report.maximum_bytes_billed}",
        "",
      ]),
      encoding="utf-8",
    )

  results_path = ""
  lc_path = ""
  row_count = 0
  if results_csv_text:
    results_path = str(output_dir / "bigquery_results_raw.csv")
    Path(results_path).write_text(results_csv_text, encoding="utf-8")
    row_count = max(0, results_csv_text.count("\n") - 1)
  if large_candidate_csv_text:
    lc_path = str(output_dir / "source_candidates_large.csv")
    Path(lc_path).write_text(large_candidate_csv_text, encoding="utf-8")

  manifest = BigQueryRunManifest(
    run_id=f"{case_id}:bq:{stamp}",
    case_id=case_id,
    mode=mode,
    output_dir=str(output_dir),
    sql_path=str(sql_path),
    config_path=str(config_path),
    dry_run_path=dry_run_path,
    results_csv_path=results_path,
    large_candidate_csv_path=lc_path,
    row_count=row_count,
  )
  manifest_path = output_dir / "query_manifest.json"
  manifest_path.write_text(json.dumps(manifest.to_dict(), ensure_ascii=False, indent=2), encoding="utf-8")
  return manifest
