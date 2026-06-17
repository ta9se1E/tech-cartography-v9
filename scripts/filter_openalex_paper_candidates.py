#!/usr/bin/env python3
"""Filter OpenAlex paper candidates by PAN/carbon-fiber relevance (Phase 19.1 / 20.1)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.evidence.claims_paper_candidate_mapper import (
  map_claim_elements_to_paper_candidates,
  save_claim_paper_candidate_map_artifacts,
)
from tech_cartography.evidence.paper_candidate_relevance_filter import (
  apply_relevance_to_paper_records,
  load_openalex_paper_records,
  save_paper_candidate_relevance_artifacts,
)
from tech_cartography.reports.project_export import load_records_csv


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Filter OpenAlex paper candidates by relevance")
  parser.add_argument("--paper-records", required=True, help="Path to openalex_paper_records.csv or .json")
  parser.add_argument("--claim-elements", default="", help="Optional claim elements CSV")
  parser.add_argument("--output-dir", default="", help="Output directory (defaults to paper-records parent)")
  parser.add_argument("--top-n", type=int, default=5)
  parser.add_argument("--publication-number", default="")
  parser.add_argument("--skip-claim-links", action="store_true", help="Skip claim-paper link generation")
  return parser.parse_args()


def _resolve_claim_elements(args: argparse.Namespace, output_dir: Path) -> list[dict]:
  if args.claim_elements:
    claim_path = Path(args.claim_elements)
    if claim_path.exists():
      return load_records_csv(str(claim_path))

  if args.publication_number:
    pub = str(args.publication_number).strip()
    candidates = [
      output_dir / "claim_elements_from_manual_fulltext.csv",
      output_dir / "claim_elements.csv",
      Path(f"outputs/claims_paper_query_plans/{pub}/claim_elements.csv"),
      Path(f"outputs/evidence_validation/{pub}/claim_elements_from_manual_fulltext.csv"),
    ]
    for path in candidates:
      if path.exists():
        return load_records_csv(str(path))

  return []


def main() -> int:
  args = parse_args()
  paper_path = Path(args.paper_records)
  if not paper_path.exists():
    raise FileNotFoundError(f"paper records not found: {paper_path}")

  papers = load_openalex_paper_records(paper_path)
  if args.publication_number:
    filtered_pub = [p for p in papers if str(p.get("publication_number") or "") == args.publication_number]
    if filtered_pub:
      papers = filtered_pub

  output_dir = Path(args.output_dir) if args.output_dir else paper_path.parent
  claim_elements = _resolve_claim_elements(args, output_dir)
  if not claim_elements and args.publication_number:
    claim_elements = [
      {
        "element_id": f"{args.publication_number}-manual",
        "element_type": "material",
        "element_text": "manual claims loaded",
        "publication_number": args.publication_number,
      },
    ]

  result = apply_relevance_to_paper_records(papers, claim_elements or None, top_n=int(args.top_n))
  paths = save_paper_candidate_relevance_artifacts(result, output_dir)

  link_count = 0
  if not args.skip_claim_links and claim_elements:
    selected_papers = result.get("selected_papers") or []
    links = map_claim_elements_to_paper_candidates(
      claim_elements,
      selected_papers,
      has_description=False,
    )
    link_paths = save_claim_paper_candidate_map_artifacts(links, output_dir)
    paths.update(link_paths)
    link_count = len(links)

  payload = {
    "total_paper_candidates": len(papers),
    "selected_evidence_papers": len(result.get("selected_papers", [])),
    "excluded_off_topic_count": result.get("excluded_off_topic_count", 0),
    "broad_background_count": result.get("broad_background_count", 0),
    "claim_paper_link_count": link_count,
    "paths": paths,
  }
  print(json.dumps(payload, indent=2, ensure_ascii=False))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
