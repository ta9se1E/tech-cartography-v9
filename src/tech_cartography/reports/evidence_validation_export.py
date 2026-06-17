"""Export helpers for evidence validation outputs."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tech_cartography.reports.project_export import save_records_csv


def _element_rows(claim_result: dict[str, Any]) -> list[dict[str, Any]]:
  rows: list[dict[str, Any]] = []
  for element in claim_result.get("elements", []):
    row = element.to_dict() if hasattr(element, "to_dict") else dict(element)
    rows.append(row)
  return rows


def save_evidence_validation_outputs(result: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  readiness = result.get("fulltext_readiness") or {}
  claim_result = result.get("claim_element_result") or {}
  openalex = result.get("openalex_result") or {}
  paper_evidence = result.get("paper_evidence_result") or {}
  claim_map = result.get("claim_paper_map_result") or {}
  summary = result.get("evidence_validation_summary") or {}

  ready_csv_rows = [
    {
      "publication_number": row.get("publication_number"),
      "title": row.get("title"),
      "country": row.get("country"),
      "readiness_status": row.get("readiness_status"),
      "evidence_level": row.get("evidence_level"),
      "retrieval_status": row.get("retrieval_status"),
    }
    for row in readiness.get("ready_records", [])
  ]
  limited_csv_rows = [
    {
      "publication_number": row.get("publication_number"),
      "title": row.get("title"),
      "country": row.get("country"),
      "readiness_status": row.get("readiness_status"),
      "evidence_level": row.get("evidence_level"),
      "retrieval_status": row.get("retrieval_status"),
    }
    for row in readiness.get("limited_records", [])
  ]
  ready_for_claim_rows = ready_csv_rows + limited_csv_rows

  manual_rows = readiness.get("manual_required_records") or result.get("manual_candidates") or []
  element_rows = _element_rows(claim_result)
  query_rows = claim_result.get("paper_queries", [])
  claims_plan = result.get("claims_paper_query_plan") or {}
  claims_query_rows = claims_plan.get("queries", [])
  paper_links = paper_evidence.get("evidence_links", [])
  evidence_items = claim_map.get("evidence_items", [])

  paths: dict[str, str] = {
    "fulltext_readiness_json": str(out / "fulltext_readiness.json"),
    "ready_for_claim_extraction_csv": save_records_csv(
      ready_for_claim_rows,
      out / "ready_for_claim_extraction.csv",
    ),
    "manual_fulltext_watch_csv": save_records_csv(manual_rows, out / "manual_fulltext_watch.csv"),
    "claim_elements_csv": save_records_csv(element_rows, out / "claim_elements.csv"),
    "paper_query_candidates_csv": save_records_csv(query_rows, out / "paper_query_candidates.csv"),
    "openalex_query_plan_json": str(out / "openalex_query_plan.json"),
    "paper_evidence_links_csv": save_records_csv(paper_links, out / "paper_evidence_links.csv"),
    "claim_paper_evidence_items_csv": save_records_csv(evidence_items, out / "claim_paper_evidence_items.csv"),
    "evidence_validation_summary_json": str(out / "evidence_validation_summary.json"),
  }

  with Path(paths["fulltext_readiness_json"]).open("w", encoding="utf-8") as handle:
    json.dump(readiness, handle, indent=2, ensure_ascii=False, default=str)

  with Path(paths["openalex_query_plan_json"]).open("w", encoding="utf-8") as handle:
    json.dump(openalex.get("query_plan", []), handle, indent=2, ensure_ascii=False)

  export_summary = {
    **summary,
    "artifact_notes": {
      "claim_elements_csv": "empty" if not element_rows else f"{len(element_rows)} rows",
      "paper_query_candidates_csv": "empty" if not query_rows else f"{len(query_rows)} rows",
      "paper_evidence_links_csv": "empty" if not paper_links else f"{len(paper_links)} rows",
      "claim_paper_evidence_items_csv": "empty" if not evidence_items else f"{len(evidence_items)} rows",
      "openalex_mode": openalex.get("mode", "plan_only"),
    },
  }
  with Path(paths["evidence_validation_summary_json"]).open("w", encoding="utf-8") as handle:
    json.dump(export_summary, handle, indent=2, ensure_ascii=False, default=str)

  paths["output_dir"] = str(out)
  return paths
