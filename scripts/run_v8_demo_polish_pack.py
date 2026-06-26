#!/usr/bin/env python3
"""Run v8 Demo Polish Pack generation (Phase 27L)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
  sys.path.insert(0, str(SRC))

from tech_cartography.services.v8_demo_polish import build_demo_polish_report
from tech_cartography.services.v8_demo_polish_export import export_demo_polish


def main() -> int:
  parser = argparse.ArgumentParser(description="Generate v8 Demo Polish Pack for demo presentation")
  parser.add_argument("--case-id", required=True)
  parser.add_argument("--publication-number", default="")
  args = parser.parse_args()

  report = build_demo_polish_report(
    case_id=args.case_id,
    publication_number=args.publication_number or None,
    project_root=PROJECT_ROOT,
  )
  export_result = export_demo_polish(report, project_root=PROJECT_ROOT)

  ev = report.evidence_demo_status
  gap = report.gap_demo_status
  print(f"case_id: {args.case_id}")
  print(f"publication_number: {report.publication_number}")
  print(f"claim_text_required_count: {ev.claim_text_required_count if ev else 0}")
  print(f"manual_claim_count: {ev.manual_claim_count if ev else 0}")
  print(f"evidence_link_count: {ev.evidence_link_count if ev else 0}")
  print(f"gap_count: {gap.gap_count if gap else 0}")
  print(f"output_dir: {export_result.output_dir}")
  print(f"manifest: {export_result.manifest_path}")
  return 0


if __name__ == "__main__":
  sys.exit(main())
