"""Claim element extraction pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tech_cartography.domain.claim_element import ClaimElement
from tech_cartography.evidence.claim_element_extractor import extract_claim_elements_for_records
from tech_cartography.evidence.description_support_mapper import map_description_support
from tech_cartography.evidence.paper_query_builder import (
  build_paper_queries_for_record,
  prioritize_paper_queries,
)
from tech_cartography.reports.claim_element_report import (
  build_claim_element_summary,
  render_claim_element_markdown,
  save_claim_element_report,
)
from tech_cartography.reports.project_export import build_output_directory, save_records_csv


def run_claim_element_pipeline(records: list[dict[str, Any]]) -> dict[str, Any]:
  extraction = extract_claim_elements_for_records(records)
  record_results: list[dict[str, Any]] = []
  all_elements: list[ClaimElement] = []
  record_lookup = {str(record.get("publication_number")): record for record in records}

  for record_result in extraction["record_results"]:
    publication_number = str(record_result["publication_number"])
    source_record = record_lookup.get(publication_number, {})
    supported_elements = map_description_support(source_record, record_result["elements"])
    enriched = dict(record_result)
    enriched["elements"] = supported_elements
    record_results.append(enriched)
    all_elements.extend(supported_elements)

  paper_queries: list[dict[str, Any]] = []
  for record_result in record_results:
    paper_queries.extend(build_paper_queries_for_record(record_result))
  paper_queries = prioritize_paper_queries(paper_queries, top_n=50)

  return {
    "total_records": extraction["total_records"],
    "records_with_claims": extraction["records_with_claims"],
    "record_results": record_results,
    "elements": all_elements,
    "paper_queries": paper_queries,
  }


def save_claim_element_outputs(result: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  element_rows = [
    {
      "publication_number": element.publication_number,
      "title": next(
        (record.get("title") for record in result["record_results"] if record["publication_number"] == element.publication_number),
        "",
      ),
      "assignee": next(
        (record.get("assignee") for record in result["record_results"] if record["publication_number"] == element.publication_number),
        "",
      ),
      **element.to_dict(),
    }
    for element in result["elements"]
  ]
  summary = build_claim_element_summary(result)
  markdown = render_claim_element_markdown(summary)
  paths = {
    "claim_elements_json": str(out / "claim_elements.json"),
    "claim_elements_csv": save_records_csv(element_rows, out / "claim_elements.csv"),
    "record_claim_element_summary_json": str(out / "record_claim_element_summary.json"),
    "paper_query_candidates_csv": save_records_csv(
      result.get("paper_queries", []),
      out / "paper_query_candidates.csv",
    ),
    "claim_element_report_md": save_claim_element_report(markdown, out),
  }
  with Path(paths["claim_elements_json"]).open("w", encoding="utf-8") as handle:
    json.dump([element.to_dict() for element in result["elements"]], handle, indent=2, ensure_ascii=False)
  with Path(paths["record_claim_element_summary_json"]).open("w", encoding="utf-8") as handle:
    json.dump(
      {
        "summary": summary,
        "record_results": [
          {
            **record,
            "elements": [
              element.to_dict() if isinstance(element, ClaimElement) else element
              for element in record.get("elements", [])
            ],
          }
          for record in result["record_results"]
        ],
      },
      handle,
      indent=2,
      ensure_ascii=False,
    )
  paths["output_dir"] = str(out)
  return paths
