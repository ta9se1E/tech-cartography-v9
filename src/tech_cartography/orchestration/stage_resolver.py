"""Resolve pipeline stage order and inputs/outputs."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tech_cartography.orchestration.pipeline_config import PipelineConfig


STAGE_ORDER = [
  "search_strategy",
  "bigquery_light_retrieval",
  "technology_clustering_ranking",
  "top5_fulltext_collection",
  "evidence_validation",
  "claim_element_extraction",
  "openalex_paper_evidence",
  "claim_paper_evidence_map",
  "technical_view_agent",
  "web_signal_mapping",
  "business_view_agent",
  "synthesis_report",
]


STAGE_NAMES = {
  "search_strategy": "Search Strategy Builder",
  "bigquery_light_retrieval": "BigQuery Light Multi-Query Retrieval",
  "technology_clustering_ranking": "Technology Clustering / Patent Ranking",
  "top5_fulltext_collection": "Top5 Full Text Evidence Collection",
  "evidence_validation": "Evidence Validation (Fulltext Readiness + Claim×Paper Plan)",
  "claim_element_extraction": "Claim Element Extraction",
  "openalex_paper_evidence": "OpenAlex Paper Evidence Search",
  "claim_paper_evidence_map": "Patent Claim × Paper Evidence Map",
  "technical_view_agent": "Technical View Agent",
  "web_signal_mapping": "Web / Company Signal Mapping",
  "business_view_agent": "Business View Agent",
  "synthesis_report": "Synthesis Report",
}


def resolve_stage_order() -> list[str]:
  return list(STAGE_ORDER)


def _is_within_range(stage_id: str, config: PipelineConfig) -> bool:
  order = resolve_stage_order()
  if stage_id not in order:
    return False
  start_idx = order.index(config.start_stage) if config.start_stage in order else 0
  stop_idx = order.index(config.stop_stage) if config.stop_stage in order else len(order) - 1
  idx = order.index(stage_id)
  return start_idx <= idx <= stop_idx


def should_run_stage(stage_id: str, config: PipelineConfig) -> bool:
  if stage_id in (config.skip_stages or []):
    return False
  if config.start_stage or config.stop_stage:
    return _is_within_range(stage_id, config)
  return True


def resolve_output_dir(stage_id: str, run_output_dir: str) -> str:
  return str(Path(run_output_dir) / "stages" / stage_id)


def find_latest_output(pattern: str) -> str | None:
  # Safety: only look under outputs/
  root = Path("outputs")
  if not root.exists():
    return None
  matches = sorted(root.glob(f"**/{pattern}"))
  if not matches:
    return None
  return str(matches[-1])


def resolve_required_inputs(
  stage_id: str,
  known_outputs: dict[str, Any],
  config: PipelineConfig,
) -> dict[str, Any]:
  out: dict[str, Any] = {}

  if stage_id == "search_strategy":
    out["profile_path"] = config.profile_path
    out["theme"] = config.theme
    return out

  if stage_id == "bigquery_light_retrieval":
    out["execute"] = config.execute_bigquery
    out["maximum_gb"] = config.maximum_bigquery_gb
    out["max_results_total"] = config.max_results_total
    out["max_results_per_intent"] = config.max_results_per_intent
    out["use_existing_light_csv"] = config.use_existing_light_csv
    return out

  if stage_id == "technology_clustering_ranking":
    out["bigquery_light_dedup_csv"] = (
      config.use_existing_light_csv
      or known_outputs.get("bigquery_light_dedup_csv")
      or known_outputs.get("bigquery_light_results_dedup_csv")
      or find_latest_output("bigquery_light_results_dedup.csv")
    )
    out["top_n"] = config.top_n
    out["fulltext_top_n"] = config.fulltext_top_n
    return out

  if stage_id == "top5_fulltext_collection":
    out["top5_candidates_csv"] = (
      known_outputs.get("top5_fulltext_candidates_csv")
      or config.use_existing_top5_csv
      or find_latest_output("top5_fulltext_candidates.csv")
    )
    out["strategic_watch_candidates_csv"] = (
      known_outputs.get("strategic_watch_candidates_csv")
      or find_latest_output("strategic_watch_candidates.csv")
    )
    out["country_watch_summary_csv"] = known_outputs.get("country_watch_summary_csv") or find_latest_output(
      "country_watch_summary.csv",
    )
    out["company_watch_summary_csv"] = known_outputs.get("company_watch_summary_csv") or find_latest_output(
      "company_watch_summary.csv",
    )
    out["execute"] = config.execute_fulltext
    out["maximum_gb"] = config.maximum_fulltext_gb
    out["use_cache"] = config.use_cache
    return out

  if stage_id == "evidence_validation":
    out["top5_fulltext_records_json"] = (
      known_outputs.get("top5_fulltext_records_json") or find_latest_output("top5_fulltext_records.json")
    )
    out["strategic_watch_manual_fulltext_required_csv"] = (
      known_outputs.get("strategic_watch_manual_fulltext_required_csv")
      or find_latest_output("strategic_watch_manual_fulltext_required.csv")
    )
    out["execute_openalex"] = config.execute_openalex
    out["max_queries"] = config.openalex_max_queries
    out["max_results_per_query"] = config.openalex_max_results_per_query
    out["use_cache"] = config.use_cache
    return out

  if stage_id == "claim_element_extraction":
    out["top20_patents_csv"] = known_outputs.get("top20_patents_csv") or find_latest_output("top20_patents.csv")
    out["top5_fulltext_records_json"] = (
      known_outputs.get("top5_fulltext_records_json") or find_latest_output("top5_fulltext_records.json")
    )
    return out

  if stage_id == "openalex_paper_evidence":
    out["paper_query_candidates_csv"] = known_outputs.get("paper_query_candidates_csv") or find_latest_output(
      "paper_query_candidates.csv",
    )
    out["paper_query_candidates_from_claims_csv"] = (
      known_outputs.get("paper_query_candidates_from_claims_csv")
      or find_latest_output("paper_query_candidates_from_claims.csv")
    )
    out["claim_elements_csv"] = known_outputs.get("claim_elements_csv") or find_latest_output("claim_elements.csv")
    out["claim_elements_from_manual_fulltext_csv"] = (
      known_outputs.get("claim_elements_from_manual_fulltext_csv")
      or find_latest_output("claim_elements_from_manual_fulltext.csv")
    )
    out["execute"] = config.execute_openalex
    out["max_queries"] = config.openalex_max_queries
    out["max_results_per_query"] = config.openalex_max_results_per_query
    out["use_cache"] = config.use_cache
    return out

  if stage_id == "claim_paper_evidence_map":
    out["claim_elements_csv"] = known_outputs.get("claim_elements_csv") or find_latest_output("claim_elements.csv")
    out["paper_evidence_links_csv"] = known_outputs.get("paper_evidence_links_csv") or find_latest_output(
      "paper_evidence_links.csv",
    )
    out["paper_records_dedup_csv"] = known_outputs.get("paper_records_dedup_csv") or find_latest_output(
      "paper_records_dedup.csv",
    )
    out["source_quality_results_csv"] = known_outputs.get("source_quality_results_csv") or find_latest_output(
      "source_quality_results.csv",
    )
    return out

  if stage_id == "technical_view_agent":
    out["patent_evidence_maps_json"] = known_outputs.get("patent_evidence_maps_json") or find_latest_output(
      "patent_evidence_maps.json",
    )
    out["claim_paper_evidence_items_csv"] = known_outputs.get("claim_paper_evidence_items_csv") or find_latest_output(
      "claim_paper_evidence_items.csv",
    )
    out["evidence_gaps_csv"] = known_outputs.get("evidence_gaps_csv") or find_latest_output("evidence_gaps.csv")
    out["claim_elements_csv"] = known_outputs.get("claim_elements_csv") or find_latest_output("claim_elements.csv")
    out["top5_fulltext_records_json"] = known_outputs.get("top5_fulltext_records_json") or find_latest_output(
      "top5_fulltext_records.json",
    )
    return out

  if stage_id == "web_signal_mapping":
    out["web_signal_file"] = config.web_signal_file
    out["patents_csv"] = known_outputs.get("top20_patents_csv") or find_latest_output("top20_patents.csv")
    return out

  if stage_id == "business_view_agent":
    out["technical_assessments_json"] = known_outputs.get("technical_assessments_json") or find_latest_output(
      "technical_assessments.json",
    )
    out["patent_technical_summary_csv"] = known_outputs.get("patent_technical_summary_csv") or find_latest_output(
      "patent_technical_summary.csv",
    )
    out["web_signal_patent_links_csv"] = known_outputs.get("web_signal_patent_links_csv") or find_latest_output(
      "web_signal_patent_links.csv",
    )
    out["ranked_patents_csv"] = known_outputs.get("ranked_patents_csv") or find_latest_output("ranked_patents.csv")
    out["patent_evidence_maps_json"] = known_outputs.get("patent_evidence_maps_json") or find_latest_output(
      "patent_evidence_maps.json",
    )
    return out

  if stage_id == "synthesis_report":
    out["cluster_summary_json"] = known_outputs.get("cluster_summary_json") or find_latest_output("cluster_summary.json")
    out["top20_patents_csv"] = known_outputs.get("top20_patents_csv") or find_latest_output("top20_patents.csv")
    out["top5_fulltext_candidates_csv"] = known_outputs.get("top5_fulltext_candidates_csv") or find_latest_output(
      "top5_fulltext_candidates.csv",
    )
    out["technical_assessments_json"] = known_outputs.get("technical_assessments_json") or find_latest_output(
      "technical_assessments.json",
    )
    out["patent_technical_summary_csv"] = known_outputs.get("patent_technical_summary_csv") or find_latest_output(
      "patent_technical_summary.csv",
    )
    out["business_assessments_json"] = known_outputs.get("business_assessments_json") or find_latest_output(
      "business_assessments.json",
    )
    out["patent_business_summary_csv"] = known_outputs.get("patent_business_summary_csv") or find_latest_output(
      "patent_business_summary.csv",
    )
    out["claim_paper_evidence_map_summary_json"] = known_outputs.get("claim_paper_evidence_map_summary_json") or find_latest_output(
      "claim_paper_evidence_map_summary.json",
    )
    out["evidence_gaps_csv"] = known_outputs.get("evidence_gaps_csv") or find_latest_output("evidence_gaps.csv")
    out["source_quality_results_csv"] = known_outputs.get("source_quality_results_csv") or find_latest_output(
      "source_quality_results.csv",
    )
    out["web_signals_by_company_csv"] = known_outputs.get("web_signals_by_company_csv") or find_latest_output(
      "web_signals_by_company.csv",
    )
    out["web_signals_by_cluster_csv"] = known_outputs.get("web_signals_by_cluster_csv") or find_latest_output(
      "web_signals_by_cluster.csv",
    )
    out["theme"] = config.theme
    return out

  return out


def validate_stage_inputs(stage_id: str, input_paths: dict[str, Any]) -> dict[str, Any]:
  required: list[str] = []
  if stage_id == "technology_clustering_ranking":
    required = ["bigquery_light_dedup_csv"]
  elif stage_id == "top5_fulltext_collection":
    required = ["top5_candidates_csv"]
  elif stage_id == "evidence_validation":
    required = ["top5_fulltext_records_json"]
  elif stage_id == "claim_element_extraction":
    required = ["top20_patents_csv"]
  elif stage_id == "openalex_paper_evidence":
    required = ["claim_elements_csv"]
  elif stage_id == "claim_paper_evidence_map":
    required = ["claim_elements_csv", "paper_evidence_links_csv"]
  elif stage_id == "technical_view_agent":
    required = ["patent_evidence_maps_json", "claim_paper_evidence_items_csv", "evidence_gaps_csv"]
  elif stage_id == "web_signal_mapping":
    required = ["web_signal_file", "patents_csv"]
  elif stage_id == "business_view_agent":
    required = ["technical_assessments_json", "patent_technical_summary_csv", "web_signal_patent_links_csv"]
  elif stage_id == "synthesis_report":
    required = [
      "cluster_summary_json",
      "top20_patents_csv",
      "top5_fulltext_candidates_csv",
      "technical_assessments_json",
      "patent_technical_summary_csv",
      "business_assessments_json",
      "patent_business_summary_csv",
    ]

  missing: list[str] = []
  for key in required:
    path = input_paths.get(key)
    if key == "claim_elements_csv" and stage_id == "openalex_paper_evidence":
      alt = input_paths.get("claim_elements_from_manual_fulltext_csv")
      if alt and Path(str(alt)).exists():
        continue
    if not path or not Path(str(path)).exists():
      missing.append(key)

  if stage_id == "openalex_paper_evidence":
    claims_q = input_paths.get("paper_query_candidates_from_claims_csv")
    regular_q = input_paths.get("paper_query_candidates_csv")
    if not (
      (claims_q and Path(str(claims_q)).exists())
      or (regular_q and Path(str(regular_q)).exists())
    ):
      missing.append("paper_query_candidates_csv")

  return {
    "ok": not missing,
    "missing": missing,
  }

