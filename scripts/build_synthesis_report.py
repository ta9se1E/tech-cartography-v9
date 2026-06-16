#!/usr/bin/env python3
"""Build Carbon Fiber Evidence Map synthesis report."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.agents.synthesis_agent import run_synthesis_report
from tech_cartography.reports.project_export import build_output_directory, load_records_csv
from tech_cartography.reports.synthesis_export import save_synthesis_outputs
from tech_cartography.reports.synthesis_report import build_synthesis_report_summary


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Build Carbon Fiber Evidence Map synthesis report")
  parser.add_argument("--cluster-summary-json", required=True)
  parser.add_argument("--top20-csv", required=True)
  parser.add_argument("--top5-csv", required=True)
  parser.add_argument("--technical-assessments-json", required=True)
  parser.add_argument("--patent-technical-summary-csv", required=True)
  parser.add_argument("--business-assessments-json", required=True)
  parser.add_argument("--patent-business-summary-csv", required=True)
  parser.add_argument("--retrieval-summary-json", default="")
  parser.add_argument("--fulltext-summary-json", default="")
  parser.add_argument("--claim-element-summary-json", default="")
  parser.add_argument("--claim-paper-summary-json", default="")
  parser.add_argument("--evidence-gaps-csv", default="")
  parser.add_argument("--source-quality-csv", default="")
  parser.add_argument("--web-signals-by-company-csv", default="")
  parser.add_argument("--web-signals-by-cluster-csv", default="")
  parser.add_argument("--theme", default="PAN系炭素繊維")
  parser.add_argument("--output-dir", default="outputs/synthesis_report")
  return parser.parse_args()


def _resolve_latest(path: Path, pattern: str) -> Path:
  if path.exists():
    return path
  if "latest" in str(path):
    parent = path.parent.parent
    candidates = sorted(parent.glob(f"*/{pattern}"))
    if candidates:
      return candidates[-1]
  return path


def _load_json(path: Path) -> dict[str, Any]:
  with path.open(encoding="utf-8") as handle:
    data = json.load(handle)
  return data if isinstance(data, dict) else {}


def _load_json_list(path: Path) -> list[dict]:
  with path.open(encoding="utf-8") as handle:
    data = json.load(handle)
  if isinstance(data, list):
    return data
  return []


def main() -> int:
  args = parse_args()
  cluster_path = _resolve_latest(Path(args.cluster_summary_json), "cluster_summary.json")
  top20_path = _resolve_latest(Path(args.top20_csv), "top20_patents.csv")
  top5_path = _resolve_latest(Path(args.top5_csv), "top5_fulltext_candidates.csv")
  tech_json_path = _resolve_latest(Path(args.technical_assessments_json), "technical_assessments.json")
  tech_csv_path = _resolve_latest(Path(args.patent_technical_summary_csv), "patent_technical_summary.csv")
  biz_json_path = _resolve_latest(Path(args.business_assessments_json), "business_assessments.json")
  biz_csv_path = _resolve_latest(Path(args.patent_business_summary_csv), "patent_business_summary.csv")

  cluster_data = _load_json(cluster_path) if cluster_path.exists() else {}
  cluster_summary = cluster_data.get("clusters", []) if isinstance(cluster_data, dict) else cluster_data
  top20_patents = load_records_csv(top20_path) if top20_path.exists() else []
  top5_candidates = load_records_csv(top5_path) if top5_path.exists() else []
  technical_assessments = _load_json_list(tech_json_path) if tech_json_path.exists() else []
  patent_technical_summary = load_records_csv(tech_csv_path) if tech_csv_path.exists() else []
  business_assessments = _load_json_list(biz_json_path) if biz_json_path.exists() else []
  patent_business_summary = load_records_csv(biz_csv_path) if biz_csv_path.exists() else []

  retrieval_summary = None
  if args.retrieval_summary_json:
    retrieval_path = _resolve_latest(Path(args.retrieval_summary_json), "retrieval_summary.json")
    retrieval_summary = _load_json(retrieval_path) if retrieval_path.exists() else None

  fulltext_summary = None
  if args.fulltext_summary_json:
    fulltext_path = _resolve_latest(Path(args.fulltext_summary_json), "fulltext_retrieval_summary.json")
    fulltext_summary = _load_json(fulltext_path) if fulltext_path.exists() else None

  claim_element_summary = None
  if args.claim_element_summary_json:
    claim_path = _resolve_latest(Path(args.claim_element_summary_json), "record_claim_element_summary.json")
    claim_element_summary = _load_json(claim_path) if claim_path.exists() else None

  claim_paper_summary = None
  if args.claim_paper_summary_json:
    claim_paper_path = _resolve_latest(Path(args.claim_paper_summary_json), "claim_paper_evidence_map_summary.json")
    claim_paper_summary = _load_json(claim_paper_path) if claim_paper_path.exists() else None

  evidence_gaps = None
  if args.evidence_gaps_csv:
    gaps_path = _resolve_latest(Path(args.evidence_gaps_csv), "evidence_gaps.csv")
    evidence_gaps = load_records_csv(gaps_path) if gaps_path.exists() else None

  source_quality_results = None
  if args.source_quality_csv:
    quality_path = _resolve_latest(Path(args.source_quality_csv), "source_quality_results.csv")
    source_quality_results = load_records_csv(quality_path) if quality_path.exists() else None

  web_signals_by_company = None
  if args.web_signals_by_company_csv:
    company_path = _resolve_latest(Path(args.web_signals_by_company_csv), "web_signals_by_company.csv")
    web_signals_by_company = load_records_csv(company_path) if company_path.exists() else None

  web_signals_by_cluster = None
  if args.web_signals_by_cluster_csv:
    cluster_signals_path = _resolve_latest(Path(args.web_signals_by_cluster_csv), "web_signals_by_cluster.csv")
    web_signals_by_cluster = load_records_csv(cluster_signals_path) if cluster_signals_path.exists() else None

  result = run_synthesis_report(
    cluster_summary,
    top20_patents,
    top5_candidates,
    technical_assessments,
    patent_technical_summary,
    business_assessments,
    patent_business_summary,
    retrieval_summary=retrieval_summary,
    fulltext_summary=fulltext_summary,
    claim_element_summary=claim_element_summary,
    claim_paper_summary=claim_paper_summary,
    evidence_gaps=evidence_gaps,
    source_quality_results=source_quality_results,
    web_signals_by_company=web_signals_by_company,
    web_signals_by_cluster=web_signals_by_cluster,
    theme=args.theme,
  )
  output_dir = build_output_directory(args.output_dir)
  paths = save_synthesis_outputs(result, output_dir)
  payload = {
    "theme": args.theme,
    "paths": paths,
    "summary": build_synthesis_report_summary(result),
  }
  print(json.dumps(payload, indent=2, ensure_ascii=False))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
