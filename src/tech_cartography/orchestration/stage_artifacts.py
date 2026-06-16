"""Standard artifact keys and output normalization for pipeline stages."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tech_cartography.orchestration.pipeline_config import PipelineConfig
from tech_cartography.orchestration.pipeline_manifest import PipelineManifest
from tech_cartography.orchestration.stage_resolver import resolve_stage_order
from tech_cartography.reports.project_export import load_records_csv

CLUSTERING_REQUIRED_COLUMNS = ["publication_number"]

PRIMARY_ARTIFACT_KEYS = [
  "bigquery_light_dedup_csv",
  "ranked_patents_csv",
  "top20_patents_csv",
  "top5_fulltext_candidates_csv",
  "strategic_watch_candidates_csv",
  "country_watch_summary_csv",
  "company_watch_summary_csv",
  "fulltext_plan_json",
  "top5_fulltext_records_json",
  "manual_fulltext_checklist_md",
  "fulltext_evidence_report_md",
  "fulltext_readiness_json",
  "ready_for_claim_extraction_csv",
  "manual_fulltext_watch_csv",
  "evidence_validation_summary_json",
  "evidence_validation_report_md",
  "final_report_md",
]

PATH_ALIASES: dict[str, str] = {
  "bigquery_light_results_dedup_csv": "bigquery_light_dedup_csv",
  "bigquery_light_results_raw_csv": "bigquery_light_raw_csv",
  "output_csv_path": "bigquery_light_dedup_csv",
  "output_raw_csv_path": "bigquery_light_raw_csv",
  "output_summary_path": "retrieval_summary_json",
  "report_markdown": "carbon_fiber_case_study_report_md",
  "carbon_fiber_evidence_map_md": "carbon_fiber_evidence_map_v1_md",
}


def normalize_stage_outputs(
  stage_id: str,
  paths: dict[str, Any],
  result: dict[str, Any] | None = None,
) -> dict[str, str]:
  combined: dict[str, Any] = dict(paths or {})
  if result:
    for key in ("output_csv_path", "output_raw_csv_path", "output_summary_path"):
      if result.get(key):
        combined[key] = result[key]

  normalized: dict[str, str] = {}
  for key, value in combined.items():
    if not value or key == "output_dir":
      continue
    std_key = PATH_ALIASES.get(key, key)
    normalized[std_key] = str(value)

  if stage_id == "search_strategy" and normalized.get("search_strategy_json"):
    normalized.setdefault("query_plans_json", normalized["search_strategy_json"])

  if stage_id == "synthesis_report":
    report = normalized.get("carbon_fiber_evidence_map_v1_md") or normalized.get("carbon_fiber_evidence_map_md")
    if report:
      normalized["carbon_fiber_evidence_map_v1_md"] = report
      normalized["final_report_md"] = report

  return normalized


def validate_clustering_csv(path: str | Path) -> dict[str, Any]:
  csv_path = Path(path)
  if not csv_path.exists():
    return {"ok": False, "reason": "missing", "path": str(csv_path)}
  records = load_records_csv(csv_path)
  if not records:
    return {"ok": False, "reason": "empty", "path": str(csv_path), "record_count": 0}
  missing_columns = [col for col in CLUSTERING_REQUIRED_COLUMNS if col not in records[0]]
  if missing_columns:
    return {
      "ok": False,
      "reason": "missing_columns",
      "path": str(csv_path),
      "missing_columns": missing_columns,
      "record_count": len(records),
    }
  return {"ok": True, "path": str(csv_path), "record_count": len(records)}


def get_stage_skip_reason(stage_id: str, config: PipelineConfig) -> str | None:
  if stage_id in (config.skip_stages or []):
    return "skip_stage"
  order = resolve_stage_order()
  if stage_id not in order:
    return "unknown_stage"
  if config.stop_stage and config.stop_stage in order:
    if order.index(stage_id) > order.index(config.stop_stage):
      return "skipped_stop_stage_after"
  if config.start_stage and config.start_stage in order:
    if order.index(stage_id) < order.index(config.start_stage):
      return "skipped_before_start_stage"
  return None


def classify_missing_input_block(
  stage_id: str,
  config: PipelineConfig,
  manifest: PipelineManifest,
  known_outputs: dict[str, Any],
  missing_keys: list[str],
) -> str | None:
  if stage_id != "technology_clustering_ranking":
    return None
  if "bigquery_light_dedup_csv" not in missing_keys:
    return None

  bq_stage = next((s for s in manifest.stage_results if s.stage_id == "bigquery_light_retrieval"), None)
  if config.use_existing_light_csv:
    return None
  if bq_stage and bq_stage.status == "skipped":
    return "BigQuery light retrieval was skipped and no existing light CSV was provided."
  if bq_stage and bq_stage.status == "success" and not known_outputs.get("bigquery_light_dedup_csv"):
    return "BigQuery light retrieval succeeded but bigquery_light_dedup_csv was not produced."
  if not config.execute_bigquery and not config.use_existing_light_csv:
    return "BigQuery light retrieval was skipped and no existing light CSV was provided."
  return "missing bigquery_light_dedup_csv"


def build_next_recommended_commands(manifest: PipelineManifest, config: PipelineConfig) -> list[str]:
  commands: list[str] = []
  config_path = "configs/carbon_fiber_pipeline.yaml"
  bq_stage = next((s for s in manifest.stage_results if s.stage_id == "bigquery_light_retrieval"), None)
  clustering = next((s for s in manifest.stage_results if s.stage_id == "technology_clustering_ranking"), None)

  if bq_stage and bq_stage.status == "skipped" and clustering and clustering.status == "blocked":
    commands.append(
      f"python scripts/run_carbon_fiber_evidence_map.py --config {config_path} "
      f"--execute-bigquery --stop-stage technology_clustering_ranking",
    )
    commands.append(
      f"python scripts/run_carbon_fiber_evidence_map.py --config {config_path} "
      f"--use-existing-light-csv <path/to/bigquery_light_results_dedup.csv> "
      f"--start-stage technology_clustering_ranking",
    )

  if clustering and clustering.status == "failed":
    commands.append(
      f"python scripts/run_carbon_fiber_evidence_map.py --config {config_path} "
      f"--use-existing-light-csv <path/to/bigquery_light_results_dedup.csv> "
      f"--start-stage technology_clustering_ranking",
    )

  if config.stop_stage and not commands:
    commands.append(
      f"python scripts/run_carbon_fiber_evidence_map.py --config {config_path} "
      f"--start-stage <next_stage>",
    )

  return commands


def collect_primary_artifacts(known_outputs: dict[str, Any], final_outputs: dict[str, Any]) -> dict[str, str]:
  merged = {**known_outputs, **final_outputs}
  index: dict[str, str] = {}
  for key in PRIMARY_ARTIFACT_KEYS:
    value = merged.get(key)
    index[key] = str(value) if value and Path(str(value)).exists() else "missing"
  return index
