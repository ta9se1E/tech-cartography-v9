"""Case study pipeline for carbon fiber evidence map."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tech_cartography.config import load_carbon_fiber_demo_profile
from tech_cartography.curation.noise_filter import (
  compute_noise_score,
  detect_noise_categories,
  detect_noise_signals,
)
from tech_cartography.curation.patent_ranker import (
  rank_patent_records,
  select_fulltext_candidates,
  select_top_patents,
)
from tech_cartography.curation.strategic_watch_selector import (
  build_company_watch_summary,
  build_country_watch_summary,
  select_strategic_watch_candidates,
)
from tech_cartography.curation.top_candidate_selector import enrich_top_records_for_display
from tech_cartography.curation.technology_classifier import (
  build_cluster_summary,
  classify_patent_record,
)
from tech_cartography.domain.search_profile import SearchProfile
from tech_cartography.reports.evidence_map_report import (
  build_evidence_map_summary,
  render_evidence_map_markdown,
  save_evidence_map_report,
)
from tech_cartography.reports.project_export import (
  build_output_directory,
  load_records_csv,
  save_records_csv,
  save_retrieval_summary,
  save_summary_csv,
)


def run_case_study_pipeline(
  records: list[dict[str, Any]],
  *,
  profile: SearchProfile | None = None,
  top_n: int = 20,
  fulltext_top_n: int = 5,
  strategic_watch_top_n: int = 20,
) -> dict[str, Any]:
  profile = profile or load_carbon_fiber_demo_profile()

  classified_records: list[dict[str, Any]] = []
  for record in records:
    enriched = classify_patent_record(record)
    enriched["noise_signals"] = detect_noise_signals(enriched)
    enriched["noise_categories"] = detect_noise_categories(enriched)
    enriched["noise_score"] = compute_noise_score(enriched)
    classified_records.append(enriched)

  ranked_records = rank_patent_records(classified_records, profile)
  top_records = enrich_top_records_for_display(select_top_patents(ranked_records, top_n=top_n))
  fulltext_candidates = select_fulltext_candidates(ranked_records, top_n=fulltext_top_n)
  strategic_watch_candidates = select_strategic_watch_candidates(
    ranked_records,
    top_n=strategic_watch_top_n,
  )
  country_watch_summary = build_country_watch_summary(strategic_watch_candidates)
  company_watch_summary = build_company_watch_summary(strategic_watch_candidates)
  cluster_summary = build_cluster_summary(ranked_records)

  summary = build_evidence_map_summary(
    classified_records,
    ranked_records,
    top_records=top_records,
    fulltext_candidates=fulltext_candidates,
    strategic_watch_candidates=strategic_watch_candidates,
    country_watch_summary=country_watch_summary,
    company_watch_summary=company_watch_summary,
    cluster_summary=cluster_summary,
  )
  markdown = render_evidence_map_markdown(summary)

  return {
    "classified_records": classified_records,
    "ranked_records": ranked_records,
    "top_records": top_records,
    "fulltext_candidates": fulltext_candidates,
    "strategic_watch_candidates": strategic_watch_candidates,
    "country_watch_summary": country_watch_summary,
    "company_watch_summary": company_watch_summary,
    "cluster_summary": cluster_summary,
    "summary": summary,
    "markdown": markdown,
  }


def save_case_study_outputs(result: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
  output_path = Path(output_dir)
  output_path.mkdir(parents=True, exist_ok=True)
  paths = {
    "classified_patents_csv": save_records_csv(
      result["classified_records"],
      output_path / "classified_patents.csv",
    ),
    "ranked_patents_csv": save_records_csv(
      result["ranked_records"],
      output_path / "ranked_patents.csv",
    ),
    "top20_patents_csv": save_records_csv(
      result["top_records"],
      output_path / "top20_patents.csv",
    ),
    "top5_fulltext_candidates_csv": save_records_csv(
      result["fulltext_candidates"],
      output_path / "top5_fulltext_candidates.csv",
    ),
    "strategic_watch_candidates_csv": save_records_csv(
      result["strategic_watch_candidates"],
      output_path / "strategic_watch_candidates.csv",
    ),
    "country_watch_summary_csv": save_summary_csv(
      result["country_watch_summary"],
      output_path / "country_watch_summary.csv",
    ),
    "company_watch_summary_csv": save_summary_csv(
      result["company_watch_summary"],
      output_path / "company_watch_summary.csv",
    ),
    "cluster_summary_json": save_retrieval_summary(
      {"clusters": result["cluster_summary"]},
      output_path / "cluster_summary.json",
    ),
    "report_markdown": save_evidence_map_report(
      result["markdown"],
      output_path,
    ),
  }
  return paths
