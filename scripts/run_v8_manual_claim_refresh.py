#!/usr/bin/env python3
"""Run v8 manual claim refresh after user-provided claim text (Phase 27K)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
  sys.path.insert(0, str(SRC))

from tech_cartography.services.v8_manual_claim_injection import claim_text_loaded_in_csv
from tech_cartography.services.v8_manual_claim_refresh import refresh_after_manual_claim
from tech_cartography.services.v8_manual_claim_refresh_export import export_manual_claim_refresh


def main() -> int:
  parser = argparse.ArgumentParser(description="Refresh v8 artifacts after manual claim text injection")
  parser.add_argument("--case-id", required=True)
  parser.add_argument("--publication-number", required=True)
  parser.add_argument("--claim-no", default="1")
  parser.add_argument("--top-n", type=int, default=5)
  args = parser.parse_args()

  loaded, claim_text = claim_text_loaded_in_csv(
    args.case_id,
    args.publication_number,
    args.claim_no,
    project_root=PROJECT_ROOT,
  )
  if not loaded:
    print(
      f"ERROR: claims_input.csv に {args.publication_number} claim {args.claim_no} の "
      "claim 本文がありません。",
      file=sys.stderr,
    )
    print(
      "先に Claim Map タブで手動投入するか、claims_input.csv を直接編集してください。",
      file=sys.stderr,
    )
    return 1

  report = refresh_after_manual_claim(
    case_id=args.case_id,
    publication_number=args.publication_number,
    claim_no=args.claim_no,
    top_n=args.top_n,
    project_root=PROJECT_ROOT,
  )
  export_result = export_manual_claim_refresh(report, project_root=PROJECT_ROOT)

  print(f"case_id: {args.case_id}")
  print(f"publication_number: {args.publication_number}")
  print(f"claim_text_status: manual_input")
  print(f"claim_text_length: {len(claim_text)}")
  print(
    f"claim_text_required_count: {report.claim_text_required_count_before} → "
    f"{report.claim_text_required_count_after}"
  )
  print(f"validation_readiness_before: {report.validation_readiness_before}")
  print(f"validation_readiness_after: {report.validation_readiness_after}")
  print("remaining_blocking_issues:")
  for issue in report.remaining_blocking_issues:
    print(f"  - {issue}")
  print(f"output_dir: {export_result.output_dir}")
  print(f"manifest: {export_result.manifest_path}")
  return 0


if __name__ == "__main__":
  sys.exit(main())
