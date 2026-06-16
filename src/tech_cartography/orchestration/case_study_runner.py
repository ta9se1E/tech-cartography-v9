"""One-command pipeline runner for Carbon Fiber Evidence Map v1."""

from __future__ import annotations

import json
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from tech_cartography.agents.business_view_agent import run_business_view_assessment
from tech_cartography.agents.synthesis_agent import run_synthesis_report
from tech_cartography.agents.technical_view_agent import run_technical_view_assessment
from tech_cartography.config import load_carbon_fiber_demo_profile
from tech_cartography.evidence.claim_paper_evidence_map import build_claim_paper_evidence_map
from tech_cartography.orchestration.latest_outputs import (
  build_artifact_index,
  save_artifact_index,
  write_latest_run_pointer,
)
from tech_cartography.orchestration.pipeline_config import PipelineConfig
from tech_cartography.orchestration.pipeline_manifest import (
  PipelineManifest,
  PipelineStageResult,
  create_manifest,
  save_manifest,
  update_stage_result,
)
from tech_cartography.orchestration.stage_resolver import (
  STAGE_NAMES,
  resolve_output_dir,
  resolve_required_inputs,
  resolve_stage_order,
  should_run_stage,
  validate_stage_inputs,
)
from tech_cartography.reports.business_assessment_export import save_business_view_outputs
from tech_cartography.reports.case_study_pipeline import run_case_study_pipeline, save_case_study_outputs
from tech_cartography.reports.claim_element_pipeline import run_claim_element_pipeline, save_claim_element_outputs
from tech_cartography.reports.evidence_map_export import save_claim_paper_evidence_map_outputs
from tech_cartography.reports.paper_evidence_pipeline import run_paper_evidence_pipeline, save_paper_evidence_outputs
from tech_cartography.reports.project_export import load_records_csv, save_records_csv
from tech_cartography.reports.synthesis_export import save_synthesis_outputs
from tech_cartography.reports.technical_assessment_export import save_technical_view_outputs
from tech_cartography.reports.web_signal_export import run_web_signal_mapping, save_web_signal_outputs
from tech_cartography.retrieval.bigquery_light_retriever import RetrievalConfig, run_multi_query_retrieval
from tech_cartography.retrieval.openalex_retriever import OpenAlexRetrievalConfig
from tech_cartography.retrieval.patent_fulltext_retriever import (
  FullTextRetrievalConfig,
  retrieve_fulltext_for_top_candidates,
  save_fulltext_collection_results,
)
from tech_cartography.reports.fulltext_evidence_report import (
  build_fulltext_evidence_summary,
  render_fulltext_evidence_markdown,
)
from tech_cartography.strategy.query_plan import QueryPlan
from tech_cartography.strategy.search_strategy_builder import build_search_strategy


def _now_iso() -> str:
  return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read_json(path: str | Path) -> Any:
  return json.loads(Path(path).read_text(encoding="utf-8"))


def _safe_mkdir(path: str | Path) -> str:
  Path(path).mkdir(parents=True, exist_ok=True)
  return str(path)


def run_search_strategy_stage(config: PipelineConfig, output_dir: str) -> dict[str, Any]:
  _safe_mkdir(output_dir)
  profile = load_carbon_fiber_demo_profile()
  strategy = build_search_strategy(profile)
  path = Path(output_dir) / "search_strategy.json"
  path.write_text(json.dumps(strategy, indent=2, ensure_ascii=False), encoding="utf-8")
  return {
    "strategy": strategy,
    "paths": {"search_strategy_json": str(path)},
    "summary": {"query_plans": len(strategy.get("query_plans", []))},
  }


def run_bigquery_light_stage(config: PipelineConfig, output_dir: str, previous_outputs: dict[str, Any]) -> dict[str, Any]:
  _safe_mkdir(output_dir)

  if config.use_existing_light_csv:
    # Caller wants to reuse a prior retrieval CSV without running BigQuery.
    return {
      "status": "cached",
      "paths": {"bigquery_light_results_dedup_csv": str(Path(config.use_existing_light_csv))},
      "summary": {"mode": "use_existing_light_csv"},
    }

  profile = load_carbon_fiber_demo_profile()
  strategy = build_search_strategy(profile)
  query_plans = [QueryPlan.from_dict(item) for item in strategy.get("query_plans", [])]

  config_obj = RetrievalConfig(
    project_id=None,
    dry_run=not config.execute_bigquery,
    execute=bool(config.execute_bigquery),
    maximum_bytes_billed_gb=config.maximum_bigquery_gb,
    max_results_per_intent=config.max_results_per_intent,
    max_results_total=config.max_results_total,
    output_dir=str(Path(output_dir)),
    use_cache=bool(config.use_cache),
  )
  result = run_multi_query_retrieval(query_plans, config_obj)
  # Retriever writes outputs under output_dir directly; the key file is bigquery_light_results_dedup.csv
  results_csv = Path(output_dir) / "bigquery_light_results_dedup.csv"
  paths = {"bigquery_light_results_dedup_csv": str(results_csv)} if results_csv.exists() else {}
  return {"status": result.get("status"), "paths": paths, "summary": result}


def run_clustering_ranking_stage(config: PipelineConfig, output_dir: str, previous_outputs: dict[str, Any]) -> dict[str, Any]:
  _safe_mkdir(output_dir)
  input_csv = previous_outputs.get("bigquery_light_results_dedup_csv") or config.use_existing_light_csv
  if not input_csv:
    raise FileNotFoundError("bigquery_light_results_dedup_csv is missing")
  records = load_records_csv(input_csv)
  result = run_case_study_pipeline(records, top_n=config.top_n, fulltext_top_n=config.fulltext_top_n)
  paths = save_case_study_outputs(result, output_dir)
  return {"status": "ok", "paths": paths, "summary": result.get("summary", {})}


def run_fulltext_collection_stage(config: PipelineConfig, output_dir: str, previous_outputs: dict[str, Any]) -> dict[str, Any]:
  _safe_mkdir(output_dir)
  candidates_csv = previous_outputs.get("top5_fulltext_candidates_csv") or config.use_existing_top5_csv
  if not candidates_csv:
    raise FileNotFoundError("top5_fulltext_candidates_csv is missing")
  candidates = load_records_csv(candidates_csv)
  cfg = FullTextRetrievalConfig(
    project_id=None,
    dry_run=not config.execute_fulltext,
    execute=bool(config.execute_fulltext),
    maximum_bytes_billed_gb=config.maximum_fulltext_gb,
    output_dir=str(Path(output_dir)),
    cache_dir="data/runtime/fulltext_cache",
    use_cache=bool(config.use_cache),
  )
  result = retrieve_fulltext_for_top_candidates(candidates, cfg)
  summary = build_fulltext_evidence_summary(result)
  markdown = render_fulltext_evidence_markdown(summary)
  paths = save_fulltext_collection_results(
    result.get("retrieved_records", []),
    cfg.output_dir,
    summary=result,
    manual_records=result.get("manual_required_records", []),
    markdown=markdown,
  )
  return {"status": result.get("status", "ok"), "paths": paths, "summary": summary}


def run_claim_element_stage(config: PipelineConfig, output_dir: str, previous_outputs: dict[str, Any]) -> dict[str, Any]:
  _safe_mkdir(output_dir)
  top20_csv = previous_outputs.get("top20_patents_csv")
  if not top20_csv:
    raise FileNotFoundError("top20_patents_csv is missing")
  records = load_records_csv(top20_csv)

  # Optionally enrich with fulltext if present.
  fulltext_json = previous_outputs.get("top5_fulltext_records_json")
  if fulltext_json and Path(fulltext_json).exists():
    fulltext_data = _read_json(fulltext_json)
    fulltext_records = (
      fulltext_data
      if isinstance(fulltext_data, list)
      else fulltext_data.get("retrieved_records", [])
    )
    ft_by_pub = {str(r.get("publication_number")): r for r in fulltext_records if isinstance(r, dict)}
    for record in records:
      pub = str(record.get("publication_number"))
      if pub in ft_by_pub:
        record.update(
          {
            "claims_text": ft_by_pub[pub].get("claims_text") or record.get("claims_text"),
            "description_text": ft_by_pub[pub].get("description_text") or record.get("description_text"),
            "claims_source": ft_by_pub[pub].get("claims_source") or record.get("claims_source"),
            "description_source": ft_by_pub[pub].get("description_source") or record.get("description_source"),
          },
        )

  result = run_claim_element_pipeline(records)
  paths = save_claim_element_outputs(result, output_dir)
  return {"status": "ok", "paths": paths, "summary": {"total_elements": len(result.get("elements", []))}}


def run_openalex_stage(config: PipelineConfig, output_dir: str, previous_outputs: dict[str, Any]) -> dict[str, Any]:
  _safe_mkdir(output_dir)
  query_csv = previous_outputs.get("paper_query_candidates_csv")
  elements_csv = previous_outputs.get("claim_elements_csv")
  if not query_csv or not elements_csv:
    raise FileNotFoundError("paper_query_candidates_csv / claim_elements_csv is missing")

  query_rows = load_records_csv(query_csv)
  claim_elements = load_records_csv(elements_csv)
  cfg = OpenAlexRetrievalConfig(
    execute=bool(config.execute_openalex),
    max_queries=int(config.openalex_max_queries),
    max_results_per_query=int(config.openalex_max_results_per_query),
    cache_dir="data/runtime/openalex_cache",
    use_cache=bool(config.use_cache),
    polite_email=None,
    output_dir=str(Path(output_dir)),
  )
  result = run_paper_evidence_pipeline(query_rows, claim_elements, cfg)
  paths = save_paper_evidence_outputs(result, output_dir)
  return {"status": "ok", "paths": paths, "summary": {"papers": len(result.get("papers_dedup", []))}}


def run_claim_paper_map_stage(config: PipelineConfig, output_dir: str, previous_outputs: dict[str, Any]) -> dict[str, Any]:
  _safe_mkdir(output_dir)
  claim_elements = load_records_csv(previous_outputs["claim_elements_csv"])
  paper_links = load_records_csv(previous_outputs["paper_evidence_links_csv"])
  paper_records = (
    load_records_csv(previous_outputs["paper_records_dedup_csv"])
    if previous_outputs.get("paper_records_dedup_csv") and Path(previous_outputs["paper_records_dedup_csv"]).exists()
    else []
  )
  source_quality = (
    load_records_csv(previous_outputs["source_quality_results_csv"])
    if previous_outputs.get("source_quality_results_csv") and Path(previous_outputs["source_quality_results_csv"]).exists()
    else []
  )
  result = build_claim_paper_evidence_map(
    claim_elements,
    paper_links,
    paper_records=paper_records,
    source_quality_results=source_quality,
  )
  paths = save_claim_paper_evidence_map_outputs(result, output_dir, top_n=30)
  return {"status": "ok", "paths": paths, "summary": {"total_patents": result.get("total_patents", 0)}}


def run_technical_view_stage(config: PipelineConfig, output_dir: str, previous_outputs: dict[str, Any]) -> dict[str, Any]:
  _safe_mkdir(output_dir)
  maps_path = previous_outputs.get("patent_evidence_maps_json")
  items_csv = previous_outputs.get("claim_paper_evidence_items_csv")
  gaps_csv = previous_outputs.get("evidence_gaps_csv")
  if not maps_path or not items_csv or not gaps_csv:
    raise FileNotFoundError("patent_evidence_maps_json / claim_paper_evidence_items_csv / evidence_gaps_csv is missing")

  maps_data = _read_json(maps_path)
  patent_maps = maps_data.get("patent_evidence_maps", []) if isinstance(maps_data, dict) else maps_data
  evidence_items = load_records_csv(items_csv)
  evidence_gaps = load_records_csv(gaps_csv)
  claim_elements = (
    load_records_csv(previous_outputs["claim_elements_csv"])
    if previous_outputs.get("claim_elements_csv") and Path(previous_outputs["claim_elements_csv"]).exists()
    else None
  )
  fulltext_records = None
  if previous_outputs.get("top5_fulltext_records_json") and Path(previous_outputs["top5_fulltext_records_json"]).exists():
    ft = _read_json(previous_outputs["top5_fulltext_records_json"])
    fulltext_records = ft if isinstance(ft, list) else ft.get("retrieved_records", [])

  result = run_technical_view_assessment(
    patent_maps,
    evidence_items,
    evidence_gaps,
    claim_elements=claim_elements,
    fulltext_records=fulltext_records,
  )
  paths = save_technical_view_outputs(result, output_dir)
  return {"status": "ok", "paths": paths, "summary": {"assessed": result.get("total_patents", 0)}}


def run_web_signal_stage(config: PipelineConfig, output_dir: str, previous_outputs: dict[str, Any]) -> dict[str, Any]:
  _safe_mkdir(output_dir)
  if not config.web_signal_file:
    raise FileNotFoundError("web_signal_file is not set")
  patents_csv = previous_outputs.get("top20_patents_csv")
  if not patents_csv:
    raise FileNotFoundError("top20_patents_csv is missing")

  from tech_cartography.ingestion.web_signal_loader import load_web_signal_file

  signals = load_web_signal_file(config.web_signal_file) if Path(config.web_signal_file).exists() else []
  patents = load_records_csv(patents_csv)
  result = run_web_signal_mapping(signals, patents)
  paths = save_web_signal_outputs(result, output_dir)
  return {"status": "ok", "paths": paths, "summary": {"links": len(result.get("links", []))}}


def run_business_view_stage(config: PipelineConfig, output_dir: str, previous_outputs: dict[str, Any]) -> dict[str, Any]:
  _safe_mkdir(output_dir)
  tech_json = previous_outputs.get("technical_assessments_json")
  tech_csv = previous_outputs.get("patent_technical_summary_csv")
  web_csv = previous_outputs.get("web_signal_patent_links_csv")
  if not tech_json or not tech_csv or not web_csv:
    raise FileNotFoundError("technical_assessments_json / patent_technical_summary_csv / web_signal_patent_links_csv is missing")

  technical_assessments = _read_json(tech_json)
  if not isinstance(technical_assessments, list):
    technical_assessments = []
  patent_technical_summary = load_records_csv(tech_csv)
  web_links = load_records_csv(web_csv)
  ranked_patents = (
    load_records_csv(previous_outputs["ranked_patents_csv"])
    if previous_outputs.get("ranked_patents_csv") and Path(previous_outputs["ranked_patents_csv"]).exists()
    else None
  )
  patent_evidence_maps = None
  if previous_outputs.get("patent_evidence_maps_json") and Path(previous_outputs["patent_evidence_maps_json"]).exists():
    maps = _read_json(previous_outputs["patent_evidence_maps_json"])
    patent_evidence_maps = maps if isinstance(maps, list) else maps.get("patent_evidence_maps", [])

  result = run_business_view_assessment(
    technical_assessments,
    patent_technical_summary,
    web_links,
    ranked_patents=ranked_patents,
    patent_evidence_maps=patent_evidence_maps,
  )
  paths = save_business_view_outputs(result, output_dir)
  return {"status": "ok", "paths": paths, "summary": {"assessed": result.get("total_patents", 0)}}


def run_synthesis_stage(config: PipelineConfig, output_dir: str, previous_outputs: dict[str, Any]) -> dict[str, Any]:
  _safe_mkdir(output_dir)
  cluster_summary = _read_json(previous_outputs["cluster_summary_json"]).get("clusters", [])
  top20 = load_records_csv(previous_outputs["top20_patents_csv"])
  top5 = load_records_csv(previous_outputs["top5_fulltext_candidates_csv"])
  technical_assessments = _read_json(previous_outputs["technical_assessments_json"])
  if not isinstance(technical_assessments, list):
    technical_assessments = []
  tech_summary = load_records_csv(previous_outputs["patent_technical_summary_csv"])
  business_assessments = _read_json(previous_outputs["business_assessments_json"])
  if not isinstance(business_assessments, list):
    business_assessments = []
  biz_summary = load_records_csv(previous_outputs["patent_business_summary_csv"])

  retrieval_summary = None
  if previous_outputs.get("retrieval_summary_json") and Path(previous_outputs["retrieval_summary_json"]).exists():
    retrieval_summary = _read_json(previous_outputs["retrieval_summary_json"])
  fulltext_summary = None
  if previous_outputs.get("fulltext_retrieval_summary_json") and Path(previous_outputs["fulltext_retrieval_summary_json"]).exists():
    fulltext_summary = _read_json(previous_outputs["fulltext_retrieval_summary_json"])
  claim_element_summary = None
  if previous_outputs.get("record_claim_element_summary_json") and Path(previous_outputs["record_claim_element_summary_json"]).exists():
    claim_element_summary = _read_json(previous_outputs["record_claim_element_summary_json"])
  claim_paper_summary = None
  if previous_outputs.get("claim_paper_evidence_map_summary_json") and Path(previous_outputs["claim_paper_evidence_map_summary_json"]).exists():
    claim_paper_summary = _read_json(previous_outputs["claim_paper_evidence_map_summary_json"])

  evidence_gaps = (
    load_records_csv(previous_outputs["evidence_gaps_csv"])
    if previous_outputs.get("evidence_gaps_csv") and Path(previous_outputs["evidence_gaps_csv"]).exists()
    else None
  )
  source_quality = (
    load_records_csv(previous_outputs["source_quality_results_csv"])
    if previous_outputs.get("source_quality_results_csv") and Path(previous_outputs["source_quality_results_csv"]).exists()
    else None
  )
  web_by_company = (
    load_records_csv(previous_outputs["web_signals_by_company_csv"])
    if previous_outputs.get("web_signals_by_company_csv") and Path(previous_outputs["web_signals_by_company_csv"]).exists()
    else None
  )
  web_by_cluster = (
    load_records_csv(previous_outputs["web_signals_by_cluster_csv"])
    if previous_outputs.get("web_signals_by_cluster_csv") and Path(previous_outputs["web_signals_by_cluster_csv"]).exists()
    else None
  )

  result = run_synthesis_report(
    cluster_summary,
    top20,
    top5,
    technical_assessments,
    tech_summary,
    business_assessments,
    biz_summary,
    retrieval_summary=retrieval_summary,
    fulltext_summary=fulltext_summary,
    claim_element_summary=claim_element_summary,
    claim_paper_summary=claim_paper_summary,
    evidence_gaps=evidence_gaps,
    source_quality_results=source_quality,
    web_signals_by_company=web_by_company,
    web_signals_by_cluster=web_by_cluster,
    theme=config.theme,
  )
  paths = save_synthesis_outputs(result, output_dir)
  return {"status": "ok", "paths": paths, "summary": {"report": paths.get("carbon_fiber_evidence_map_md")}}


STAGE_RUNNERS: dict[str, Callable[[PipelineConfig, str, dict[str, Any]], dict[str, Any]]] = {
  "search_strategy": lambda c, d, prev: run_search_strategy_stage(c, d),
  "bigquery_light_retrieval": lambda c, d, prev: run_bigquery_light_stage(c, d, prev),
  "technology_clustering_ranking": lambda c, d, prev: run_clustering_ranking_stage(c, d, prev),
  "top5_fulltext_collection": lambda c, d, prev: run_fulltext_collection_stage(c, d, prev),
  "claim_element_extraction": lambda c, d, prev: run_claim_element_stage(c, d, prev),
  "openalex_paper_evidence": lambda c, d, prev: run_openalex_stage(c, d, prev),
  "claim_paper_evidence_map": lambda c, d, prev: run_claim_paper_map_stage(c, d, prev),
  "technical_view_agent": lambda c, d, prev: run_technical_view_stage(c, d, prev),
  "web_signal_mapping": lambda c, d, prev: run_web_signal_stage(c, d, prev),
  "business_view_agent": lambda c, d, prev: run_business_view_stage(c, d, prev),
  "synthesis_report": lambda c, d, prev: run_synthesis_stage(c, d, prev),
}


def run_pipeline_stage(
  stage_id: str,
  config: PipelineConfig,
  manifest: PipelineManifest,
  known_outputs: dict[str, Any],
  *,
  blocked: bool,
) -> PipelineStageResult:
  stage_name = STAGE_NAMES.get(stage_id, stage_id)
  stage_output_dir = resolve_output_dir(stage_id, str(manifest.config.get("run_output_dir", "")))
  stage_inputs = resolve_required_inputs(stage_id, known_outputs, config)

  result = PipelineStageResult(stage_id=stage_id, stage_name=stage_name, status="pending")
  result.input_paths = stage_inputs
  result.started_at = _now_iso()

  if blocked:
    result.status = "blocked"
    result.skipped_reason = "blocked by previous failure"
    result.finished_at = _now_iso()
    return result

  if not should_run_stage(stage_id, config):
    result.status = "skipped"
    result.skipped_reason = "skip_stages/start_stage/stop_stage"
    result.finished_at = _now_iso()
    return result

  # External stages are safe-by-default: skip if execute flag is false AND no explicit existing input.
  if stage_id == "bigquery_light_retrieval" and not config.execute_bigquery and not config.use_existing_light_csv:
    result.status = "skipped"
    result.skipped_reason = "execute_bigquery is false (dry-run not executed); provide --execute-bigquery or --use-existing-light-csv"
    result.finished_at = _now_iso()
    return result
  if stage_id == "top5_fulltext_collection" and not config.execute_fulltext and not (known_outputs.get("top5_fulltext_candidates_csv") or config.use_existing_top5_csv):
    result.status = "skipped"
    result.skipped_reason = "execute_fulltext is false; provide --execute-fulltext or use cached/manual fulltext outputs"
    result.finished_at = _now_iso()
    return result
  if stage_id == "openalex_paper_evidence" and not config.execute_openalex and not config.use_cache:
    result.status = "skipped"
    result.skipped_reason = "execute_openalex is false and use_cache is false; enable cache or execute explicitly"
    result.finished_at = _now_iso()
    return result

  validation = validate_stage_inputs(stage_id, stage_inputs)
  if not validation.get("ok", True):
    result.status = "failed"
    result.errors.append(f"missing required inputs: {validation.get('missing')}")
    result.finished_at = _now_iso()
    return result

  result.status = "running"
  try:
    runner = STAGE_RUNNERS[stage_id]
    payload = runner(config, stage_output_dir, known_outputs)
    result.status = "success"
    result.output_paths = dict(payload.get("paths", {}) or {})
    result.summary = dict(payload.get("summary", {}) or {})
    if payload.get("status") and payload.get("status") not in {"ok", "success", "cached"}:
      result.warnings.append(f"stage returned status={payload.get('status')}")
  except Exception as exc:  # noqa: BLE001 (intentionally capturing stage error)
    result.status = "failed"
    result.errors.append(str(exc))
    result.errors.append(traceback.format_exc(limit=5))
  finally:
    result.finished_at = _now_iso()
  return result


def run_carbon_fiber_evidence_map_pipeline(config: PipelineConfig) -> dict[str, Any]:
  run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
  run_output_dir = str(Path(config.output_root) / run_id)
  _safe_mkdir(run_output_dir)

  manifest = create_manifest(config, run_id=run_id, run_output_dir=run_output_dir)
  manifest_dir = str(Path(run_output_dir))

  known_outputs: dict[str, Any] = {}
  blocked = False

  for stage_id in resolve_stage_order():
    stage_result = run_pipeline_stage(stage_id, config, manifest, known_outputs, blocked=blocked)
    manifest = update_stage_result(manifest, stage_result)

    # Update known outputs for later stages.
    if stage_result.status == "success":
      known_outputs.update(stage_result.output_paths)
    elif stage_result.status == "failed":
      blocked = True
      manifest.errors.append(f"stage failed: {stage_id}")

    # Persist manifest after every stage for recoverability.
    manifest_path = save_manifest(manifest, manifest_dir)
    manifest.config["manifest_path"] = manifest_path

  manifest.finished_at = _now_iso()
  manifest.status = "failed" if any(s.status == "failed" for s in manifest.stage_results) else "success"

  final_report = known_outputs.get("carbon_fiber_evidence_map_md")
  if final_report:
    manifest.final_outputs["final_report_md"] = final_report
  manifest.final_outputs["run_manifest_json"] = str(Path(manifest_dir) / "run_manifest.json")
  manifest.final_outputs["run_summary_md"] = str(Path(manifest_dir) / "run_summary.md")

  manifest_path = save_manifest(manifest, manifest_dir)
  manifest.config["manifest_path"] = manifest_path

  artifact_index = build_artifact_index(manifest)
  artifact_md_path = save_artifact_index(artifact_index, manifest_dir)
  manifest.final_outputs["artifact_index_md"] = artifact_md_path
  save_manifest(manifest, manifest_dir)

  latest_pointer = write_latest_run_pointer(run_id, manifest_path, config.output_root)
  manifest.final_outputs["latest_run_pointer_json"] = latest_pointer
  save_manifest(manifest, manifest_dir)

  return {
    "run_id": run_id,
    "manifest_path": manifest_path,
    "run_output_dir": run_output_dir,
    "final_report_path": final_report,
    "artifact_index_path": artifact_md_path,
    "stage_statuses": {s.stage_id: s.status for s in manifest.stage_results},
  }

