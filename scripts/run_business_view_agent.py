#!/usr/bin/env python3
"""Run Business View Agent."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.agents.business_view_agent import run_business_view_assessment
from tech_cartography.reports.business_assessment_export import save_business_view_outputs
from tech_cartography.reports.business_view_report import build_business_view_summary
from tech_cartography.reports.project_export import build_output_directory, load_records_csv


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Run Business View Agent")
  parser.add_argument("--technical-assessments-json", required=True)
  parser.add_argument("--patent-technical-summary-csv", required=True)
  parser.add_argument("--web-signal-links-csv", required=True)
  parser.add_argument("--ranked-patents-csv", default="")
  parser.add_argument("--patent-evidence-maps-json", default="")
  parser.add_argument("--output-dir", default="outputs/business_view_assessment")
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


def _load_json_list(path: Path) -> list[dict]:
  with path.open(encoding="utf-8") as handle:
    data = json.load(handle)
  if isinstance(data, list):
    return data
  return []


def main() -> int:
  args = parse_args()
  tech_json = _resolve_latest(Path(args.technical_assessments_json), "technical_assessments.json")
  tech_csv = _resolve_latest(Path(args.patent_technical_summary_csv), "patent_technical_summary.csv")
  web_csv = _resolve_latest(Path(args.web_signal_links_csv), "web_signal_patent_links.csv")
  ranked_csv = (
    _resolve_latest(Path(args.ranked_patents_csv), Path(args.ranked_patents_csv).name)
    if args.ranked_patents_csv
    else Path("")
  )
  evidence_json = (
    _resolve_latest(Path(args.patent_evidence_maps_json), "patent_evidence_maps.json")
    if args.patent_evidence_maps_json
    else Path("")
  )

  technical_assessments = _load_json_list(tech_json) if tech_json.exists() else []
  patent_technical_summary = load_records_csv(tech_csv) if tech_csv.exists() else []
  web_signal_links = load_records_csv(web_csv) if web_csv.exists() else []
  ranked_patents = load_records_csv(ranked_csv) if ranked_csv and ranked_csv.exists() else None
  patent_evidence_maps = _load_json_list(evidence_json) if evidence_json and evidence_json.exists() else None

  result = run_business_view_assessment(
    technical_assessments,
    patent_technical_summary,
    web_signal_links,
    ranked_patents=ranked_patents,
    patent_evidence_maps=patent_evidence_maps,
  )
  output_dir = build_output_directory(args.output_dir)
  paths = save_business_view_outputs(result, output_dir)
  payload = {
    "technical_assessments_json": str(tech_json),
    "patent_technical_summary_csv": str(tech_csv),
    "web_signal_links_csv": str(web_csv),
    "paths": paths,
    "summary": build_business_view_summary(result),
  }
  print(json.dumps(payload, indent=2, ensure_ascii=False))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
