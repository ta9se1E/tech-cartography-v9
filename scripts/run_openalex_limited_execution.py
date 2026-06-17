#!/usr/bin/env python3
"""Run limited OpenAlex execution for claims-based paper queries (Phase 19)."""

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
from tech_cartography.evidence.openalex_limited_executor import (
  OpenAlexExecutionConfig,
  execute_openalex_limited,
  save_openalex_limited_artifacts,
)
from tech_cartography.manual.manual_fulltext_input_schema import load_manual_fulltext_input
from tech_cartography.manual.manual_fulltext_loader import convert_manual_input_to_fulltext_record
from tech_cartography.reports.project_export import load_records_csv


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Limited OpenAlex execution for claims-based queries")
  parser.add_argument("--run-dir", default="")
  parser.add_argument("--publication-number", default="")
  parser.add_argument("--manual-input", default="")
  parser.add_argument("--query-candidates", default="")
  parser.add_argument("--output-dir", default="")
  parser.add_argument("--max-queries", type=int, default=3)
  parser.add_argument("--max-results-per-query", type=int, default=5)
  parser.add_argument("--execute-openalex", action="store_true", default=False)
  parser.add_argument("--no-cache", action="store_true", default=False)
  return parser.parse_args()


def _find_evidence_stage_dir(run_dir: Path) -> Path | None:
  stages = run_dir / "stages" / "evidence_validation"
  if not stages.exists():
    stages = run_dir / "stages" / "openalex_paper_evidence"
  if not stages.exists():
    return None
  candidates = sorted(stages.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
  return candidates[0] if candidates else None


def _resolve_query_candidates(args: argparse.Namespace, stage_dir: Path | None) -> list[dict]:
  if args.query_candidates:
    return load_records_csv(args.query_candidates)
  if stage_dir:
    for name in ("paper_query_candidates_from_claims.csv", "paper_query_candidates.csv"):
      path = stage_dir / name
      if path.exists():
        return load_records_csv(str(path))
  raise FileNotFoundError("query candidates CSV not found; pass --query-candidates")


def _load_claim_elements(stage_dir: Path | None, publication_number: str) -> list[dict]:
  if not stage_dir:
    return []
  for name in ("claim_elements_from_manual_fulltext.csv", "claim_elements.csv"):
    path = stage_dir / name
    if path.exists():
      rows = load_records_csv(str(path))
      return [r for r in rows if str(r.get("publication_number") or "") == publication_number] or rows
  return []


def main() -> int:
  args = parse_args()
  stage_dir = _find_evidence_stage_dir(Path(args.run_dir)) if args.run_dir else None
  output_dir = Path(args.output_dir) if args.output_dir else (stage_dir or Path("outputs/openalex_limited_execution"))
  publication_number = args.publication_number

  if args.manual_input and not publication_number:
    manual_path = Path(args.manual_input)
    if manual_path.is_file():
      data = json.loads(manual_path.read_text(encoding="utf-8"))
      publication_number = str(data.get("publication_number") or manual_path.stem)
    else:
      publication_number = manual_path.stem

  candidates = _resolve_query_candidates(args, stage_dir)
  if publication_number:
    filtered = [c for c in candidates if str(c.get("publication_number") or "") == publication_number]
    if filtered:
      candidates = filtered

  has_description = False
  if args.manual_input:
    manual_path = Path(args.manual_input)
    if manual_path.is_file():
      data = json.loads(manual_path.read_text(encoding="utf-8"))
      has_description = bool(str(data.get("description_text") or "").strip())
      if not publication_number:
        publication_number = str(data.get("publication_number") or "")
    else:
      manual = load_manual_fulltext_input(publication_number, manual_path.parent)
      if manual:
        has_description = bool(manual.description_text)
        convert_manual_input_to_fulltext_record(manual)

  cfg = OpenAlexExecutionConfig(
    max_queries=int(args.max_queries),
    max_results_per_query=int(args.max_results_per_query),
    cache_first=not args.no_cache,
    execute_openalex=bool(args.execute_openalex),
    output_dir=str(output_dir),
  )
  result = execute_openalex_limited(
    candidates,
    cfg,
    publication_number=publication_number,
  )
  paths = save_openalex_limited_artifacts(result, output_dir)

  claim_elements = _load_claim_elements(stage_dir, publication_number)
  if not claim_elements and args.run_dir:
    ev_dir = _find_evidence_stage_dir(Path(args.run_dir))
    if ev_dir:
      claim_elements = _load_claim_elements(ev_dir, publication_number)

  links = map_claim_elements_to_paper_candidates(
    claim_elements,
    result.get("paper_records", []),
    has_description=has_description,
  )
  if links or result.get("paper_records"):
    paths.update(save_claim_paper_candidate_map_artifacts(links, output_dir))
    result["claim_paper_candidate_links"] = links

  payload = {
    "mode": result.get("mode"),
    "execution_status": result.get("execution_status"),
    "executed_queries_count": result.get("executed_queries_count"),
    "total_paper_records": result.get("total_paper_records"),
    "cache_hits": result.get("cache_hits"),
    "api_errors": result.get("api_errors"),
    "claim_paper_links_count": len(links),
    "paths": paths,
  }
  print(json.dumps(payload, indent=2, ensure_ascii=False))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
