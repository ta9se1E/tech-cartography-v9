#!/usr/bin/env python3
"""Run v8 One Case Real Demo E2E check (Phase 27N.5)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
  sys.path.insert(0, str(SRC))

from tech_cartography.runtime.v8_one_case_demo_schema import (
  DEFAULT_ONE_CASE_ID,
  DEFAULT_ONE_CASE_INPUT_CSV,
)
from tech_cartography.services.v8_one_case_demo_e2e import OneCaseDemoRunOptions, run_one_case_demo_e2e


def _print_summary(summary) -> None:
  print(f"case_id: {summary.case_id}")
  print(f"input_csv_exists: {str(summary.input_csv_exists).lower()}")
  print(f"imported_count: {summary.imported_count if summary.imported_count is not None else '—'}")
  print(f"deduped_count: {summary.deduped_count if summary.deduped_count is not None else '—'}")
  print(f"top100_count: {summary.top100_count if summary.top100_count is not None else '—'}")
  print(f"top20_count: {summary.top20_count if summary.top20_count is not None else '—'}")
  print(f"top5_count: {summary.top5_count if summary.top5_count is not None else '—'}")
  pubs = summary.top5_publication_numbers or []
  print(f"top5_publication_numbers: {', '.join(pubs) if pubs else '—'}")
  print(f"manual_claim_count: {summary.manual_claim_count}")
  print(f"claim_text_required_count: {summary.claim_text_required_count}")
  ev = summary.evidence_link_count
  gap = summary.gap_count
  print(f"evidence_link_count: {ev if ev is not None else 'artifact_missing'}")
  print(f"gap_count: {gap if gap is not None else 'artifact_missing'}")
  print(f"demo_polish_pack_path: {summary.demo_polish_pack_path or '—'}")
  print(f"demo_readiness_status: {summary.demo_readiness_status or '—'}")
  print(f"overall_status: {summary.overall_status}")
  print(f"next_user_action: {summary.next_user_action}")
  print(f"output_dir: {summary.output_dir}")
  print(f"manifest: {summary.manifest_path}")


def main() -> int:
  parser = argparse.ArgumentParser(description="One Case Real Demo E2E check (Case 1)")
  parser.add_argument("--case-id", default=DEFAULT_ONE_CASE_ID)
  parser.add_argument("--input-csv", default=DEFAULT_ONE_CASE_INPUT_CSV)
  parser.add_argument("--max-rows", type=int, default=1000)
  parser.add_argument("--skip-import", action="store_true")
  parser.add_argument("--skip-shortlist", action="store_true")
  parser.add_argument("--skip-refresh", action="store_true")
  parser.add_argument("--skip-demo-polish", action="store_true")
  parser.add_argument("--skip-readiness", action="store_true")
  args = parser.parse_args()

  if not Path(PROJECT_ROOT / args.input_csv).is_file():
    print("=" * 60)
    print("実在特許 CSV が見つかりません")
    print("=" * 60)
    print(f"配置先: {PROJECT_ROOT / args.input_csv}")
    print("")
    print("BigQuery 等で別途抽出した実在特許 CSV を上記パスに置いてください。")
    print("fixture / 架空1000件 CSV は使用しません。")
    print("")
    print("参考: docs/one_case_real_demo_runbook.md")
    print("       cases/case_01_pan_graphitization/large_candidates/README.md")
    print("=" * 60)

  options = OneCaseDemoRunOptions(
    case_id=args.case_id,
    input_csv=args.input_csv,
    max_rows=args.max_rows,
    skip_import=args.skip_import,
    skip_shortlist=args.skip_shortlist,
    skip_refresh=args.skip_refresh,
    skip_demo_polish=args.skip_demo_polish,
    skip_readiness=args.skip_readiness,
    project_root=PROJECT_ROOT,
  )
  summary, exit_code = run_one_case_demo_e2e(options)
  _print_summary(summary)
  return exit_code


if __name__ == "__main__":
  sys.exit(main())
