"""Evidence validation pipeline: fulltext readiness through claim-paper mapping."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tech_cartography.evidence.claim_paper_evidence_map import build_claim_paper_evidence_map
from tech_cartography.reports.claim_element_pipeline import run_claim_element_pipeline
from tech_cartography.reports.evidence_validation_export import save_evidence_validation_outputs
from tech_cartography.reports.evidence_validation_report import (
  build_evidence_validation_summary,
  render_evidence_validation_markdown,
  save_evidence_validation_report,
)
from tech_cartography.reports.paper_evidence_pipeline import run_paper_evidence_pipeline
from tech_cartography.retrieval.openalex_retriever import OpenAlexRetrievalConfig
from tech_cartography.validation.fulltext_readiness import assess_fulltext_readiness


def _empty_claim_element_result() -> dict[str, Any]:
  return {
    "total_records": 0,
    "records_with_claims": 0,
    "record_results": [],
    "elements": [],
    "paper_queries": [],
  }


def _resolve_pipeline_status(
  readiness: dict[str, Any],
  claim_element_result: dict[str, Any],
  errors: list[str],
) -> str:
  if errors:
    return "failed"
  ready = int(readiness.get("ready_count", 0))
  limited = int(readiness.get("limited_count", 0))
  if ready == 0 and limited == 0:
    return "limited_no_fulltext"
  if claim_element_result.get("elements"):
    return "success"
  return "partial_success"


def run_evidence_validation(
  fulltext_records: list[dict[str, Any]],
  manual_candidates: list[dict[str, Any]] | None = None,
  execute_openalex: bool = False,
  openalex_max_queries: int = 20,
  openalex_max_results_per_query: int = 10,
  use_cache: bool = True,
  output_dir: str | None = None,
) -> dict[str, Any]:
  warnings: list[str] = []
  errors: list[str] = []

  readiness = assess_fulltext_readiness(fulltext_records, manual_candidates)
  extraction_records = list(readiness.get("ready_records", [])) + list(readiness.get("limited_records", []))

  if extraction_records:
    claim_element_result = run_claim_element_pipeline(extraction_records)
  else:
    claim_element_result = _empty_claim_element_result()
    warnings.append("No ready or limited fulltext records; claim element extraction skipped.")

  query_rows = [
    row if isinstance(row, dict) else row
    for row in claim_element_result.get("paper_queries", [])
  ]
  element_rows = [
    element.to_dict() if hasattr(element, "to_dict") else element
    for element in claim_element_result.get("elements", [])
  ]

  openalex_cfg = OpenAlexRetrievalConfig(
    execute=bool(execute_openalex),
    max_queries=int(openalex_max_queries),
    max_results_per_query=int(openalex_max_results_per_query),
    cache_dir="data/runtime/openalex_cache",
    use_cache=bool(use_cache),
    output_dir=str(output_dir or "outputs/evidence_validation"),
  )

  if query_rows:
    paper_evidence_result = run_paper_evidence_pipeline(query_rows, element_rows, openalex_cfg)
    openalex_result = {
      "mode": paper_evidence_result.get("mode", "plan_only" if not execute_openalex else "execute"),
      "status": paper_evidence_result.get("status", "ok"),
      "total_query_candidates": paper_evidence_result.get("total_query_candidates", len(query_rows)),
      "executed_queries": paper_evidence_result.get("executed_queries", 0),
      "cache_hits": paper_evidence_result.get("cache_hits", 0),
      "cache_misses": paper_evidence_result.get("cache_misses", 0),
      "query_plan": paper_evidence_result.get("query_plan", []),
      "papers_dedup": paper_evidence_result.get("papers_dedup", []),
      "warnings": paper_evidence_result.get("warnings", []),
      "errors": paper_evidence_result.get("errors", []),
    }
    paper_links = paper_evidence_result.get("evidence_links", [])
    source_quality = paper_evidence_result.get("source_quality_results", [])
    paper_records = paper_evidence_result.get("papers_dedup", [])
  else:
    openalex_result = {
      "mode": "plan_only" if not execute_openalex else "execute",
      "status": "ok",
      "total_query_candidates": 0,
      "executed_queries": 0,
      "cache_hits": 0,
      "cache_misses": 0,
      "query_plan": [],
      "papers_dedup": [],
      "warnings": ["No paper query candidates generated."],
      "errors": [],
    }
    paper_evidence_result = {
      "evidence_links": [],
      "papers_dedup": [],
      "source_quality_results": [],
    }
    paper_links = []
    source_quality = []
    paper_records = []
    warnings.append("No paper query candidates; OpenAlex plan is empty.")

  if element_rows:
    claim_paper_map_result = build_claim_paper_evidence_map(
      element_rows,
      paper_links,
      paper_records=paper_records,
      source_quality_results=source_quality,
    )
  else:
    claim_paper_map_result = {
      "evidence_items": [],
      "patent_evidence_maps": [],
      "evidence_gaps": [],
      "top_evidence_items": [],
      "warnings": ["No claim elements available for claim-paper mapping."],
      "errors": [],
    }

  status = _resolve_pipeline_status(readiness, claim_element_result, errors)

  result = {
    "status": status,
    "fulltext_readiness": readiness,
    "claim_element_result": claim_element_result,
    "paper_query_result": {
      "total_queries": len(query_rows),
      "queries": query_rows,
    },
    "openalex_result": openalex_result,
    "paper_evidence_result": paper_evidence_result,
    "claim_paper_map_result": claim_paper_map_result,
    "manual_candidates": list(manual_candidates or []),
    "warnings": warnings,
    "errors": errors,
    "output_paths": {},
  }

  result["evidence_validation_summary"] = build_evidence_validation_summary(result)
  if output_dir:
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    paths = save_evidence_validation_outputs(result, out)
    markdown = render_evidence_validation_markdown(result["evidence_validation_summary"])
    paths["evidence_validation_report_md"] = save_evidence_validation_report(markdown, out)
    result["output_paths"] = paths

  return result
