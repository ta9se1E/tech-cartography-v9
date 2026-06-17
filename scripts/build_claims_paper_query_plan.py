#!/usr/bin/env python3
"""Build claims-based OpenAlex paper query plan (Phase 18C/18D)."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = PROJECT_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
  sys.path.insert(0, str(SRC_ROOT))

from tech_cartography.evidence.claims_based_paper_query_builder import (
  build_claims_paper_query_plan,
  save_claims_paper_query_artifacts,
)
from tech_cartography.manual.manual_fulltext_input_schema import load_manual_fulltext_input
from tech_cartography.manual.manual_fulltext_loader import convert_manual_input_to_fulltext_record
from tech_cartography.reports.project_export import load_records_csv


def parse_args() -> argparse.Namespace:
  parser = argparse.ArgumentParser(description="Build claims-based paper query plan")
  parser.add_argument("--run-dir", default="")
  parser.add_argument("--publication-number", default="")
  parser.add_argument("--manual-input", default="")
  parser.add_argument("--output-dir", default="")
  parser.add_argument("--min-queries", type=int, default=5)
  parser.add_argument("--max-queries", type=int, default=10)
  parser.add_argument("--quality-report", action="store_true", default=False)
  parser.add_argument("--fail-if-not-ready", action="store_true", default=False)
  return parser.parse_args()


def _find_evidence_stage_dir(run_dir: Path) -> Path | None:
  stages = run_dir / "stages" / "evidence_validation"
  if not stages.exists():
    return None
  candidates = sorted(stages.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
  return candidates[0] if candidates else None


def _load_claim_elements(stage_dir: Path, publication_number: str) -> list[dict]:
  for name in ("claim_elements_from_manual_fulltext.csv", "claim_elements.csv"):
    path = stage_dir / name
    if not path.exists():
      continue
    rows = load_records_csv(str(path))
    return [row for row in rows if str(row.get("publication_number") or "") == publication_number]
  return []


def _load_fulltext_record(stage_dir: Path, publication_number: str) -> dict | None:
  readiness_path = stage_dir / "fulltext_readiness.json"
  if readiness_path.exists():
    data = json.loads(readiness_path.read_text(encoding="utf-8"))
    for row in data.get("classified_records", []):
      if str(row.get("publication_number") or "") == publication_number:
        return row
  return None


def main() -> int:
  args = parse_args()
  claim_elements: list[dict] = []
  output_dir = Path(args.output_dir) if args.output_dir else None

  if args.manual_input:
    manual_path = Path(args.manual_input)
    if manual_path.is_file():
      manual_data = json.loads(manual_path.read_text(encoding="utf-8"))
      from tech_cartography.manual.manual_fulltext_input_schema import manual_fulltext_input_from_dict

      manual = manual_fulltext_input_from_dict(manual_data)
    else:
      pub = args.publication_number or manual_path.stem
      manual = load_manual_fulltext_input(pub, manual_path.parent)
    if manual is None:
      raise FileNotFoundError(f"Manual input not found: {args.manual_input}")
    records = [convert_manual_input_to_fulltext_record(manual)]
    if not output_dir:
      output_dir = Path("outputs/claims_paper_query_plans") / str(manual.publication_number)

  elif args.run_dir:
    run_dir = Path(args.run_dir)
    stage_dir = _find_evidence_stage_dir(run_dir)
    if stage_dir is None:
      raise FileNotFoundError(f"evidence_validation stage not found under {run_dir}")
    pub = args.publication_number
    if not pub:
      raise ValueError("--publication-number is required with --run-dir")
    record = _load_fulltext_record(stage_dir, pub)
    if record is None:
      manual_json = Path("outputs/manual_fulltext_inputs") / f"{pub}.json"
      if manual_json.exists():
        manual = load_manual_fulltext_input(pub, manual_json.parent)
        if manual:
          record = convert_manual_input_to_fulltext_record(manual)
    if record is None:
      raise FileNotFoundError(f"No fulltext record found for {pub}")
    records = [record]
    claim_elements = _load_claim_elements(stage_dir, pub)
    if not output_dir:
      output_dir = stage_dir

  else:
    raise ValueError("Provide --manual-input or --run-dir")

  claim_element_result = {"elements": claim_elements}
  plan = build_claims_paper_query_plan(
    records,
    claim_element_result,
    min_queries=int(args.min_queries),
    max_queries=int(args.max_queries),
  )
  paths = save_claims_paper_query_artifacts(
    plan,
    output_dir or Path("."),
    include_quality_report=bool(args.quality_report or True),
  )
  payload = {
    "total_queries": plan.get("total_queries", 0),
    "openalex_mode": plan.get("openalex_mode", "plan_only"),
    "confidence_levels": plan.get("confidence_levels", []),
    "plan_ready_for_openalex": plan.get("plan_ready_for_openalex", False),
    "quality_summary": plan.get("quality_summary", {}),
    "paths": paths,
  }
  print(json.dumps(payload, indent=2, ensure_ascii=False))

  if args.fail_if_not_ready and not plan.get("plan_ready_for_openalex"):
    return 2
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
