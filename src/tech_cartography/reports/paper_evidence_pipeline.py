"""OpenAlex paper evidence pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tech_cartography.evidence.paper_evidence_mapper import map_papers_to_claim_elements
from tech_cartography.evidence.source_quality_agent import evaluate_paper_source_quality
from tech_cartography.reports.paper_evidence_report import (
  build_paper_evidence_summary,
  render_paper_evidence_markdown,
  save_paper_evidence_report,
)
from tech_cartography.reports.project_export import save_records_csv
from tech_cartography.retrieval.openalex_retriever import (
  OpenAlexRetrievalConfig,
  save_openalex_results,
  search_paper_queries,
)


def run_paper_evidence_pipeline(
  query_rows: list[dict[str, Any]],
  claim_elements: list[dict[str, Any]],
  config: OpenAlexRetrievalConfig,
) -> dict[str, Any]:
  retrieval = search_paper_queries(query_rows, config)
  mapping = map_papers_to_claim_elements(retrieval.get("papers_dedup", []), claim_elements)
  source_quality_results = [
    evaluate_paper_source_quality(paper).to_dict()
    for paper in mapping.get("papers_dedup", [])
  ]
  return {
    **retrieval,
    "claim_elements_count": len(claim_elements),
    "papers_dedup": mapping.get("papers_dedup", []),
    "evidence_links": mapping.get("evidence_links", []),
    "evidence_by_patent": mapping.get("evidence_by_patent", []),
    "source_quality_results": source_quality_results,
  }


def save_paper_evidence_outputs(result: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  openalex_paths = save_openalex_results(result, out)
  summary = build_paper_evidence_summary(result)
  markdown = render_paper_evidence_markdown(summary)
  paths = {
    **openalex_paths,
    "source_quality_results_csv": save_records_csv(
      result.get("source_quality_results", []),
      out / "source_quality_results.csv",
    ),
    "paper_evidence_links_csv": save_records_csv(
      result.get("evidence_links", []),
      out / "paper_evidence_links.csv",
    ),
    "paper_evidence_by_patent_json": str(out / "paper_evidence_by_patent.json"),
    "paper_evidence_report_md": save_paper_evidence_report(markdown, out),
  }
  with Path(paths["paper_evidence_by_patent_json"]).open("w", encoding="utf-8") as handle:
    json.dump(
      {
        "summary": summary,
        "evidence_by_patent": result.get("evidence_by_patent", []),
      },
      handle,
      indent=2,
      ensure_ascii=False,
    )
  paths["output_dir"] = str(out)
  return paths
