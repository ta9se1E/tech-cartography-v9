#!/usr/bin/env python3
"""Run v8 Demo Readiness check for three cases (Phase 27M)."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
  sys.path.insert(0, str(SRC))

from tech_cartography.services.v8_demo_readiness import build_demo_readiness_report
from tech_cartography.services.v8_demo_readiness_export import export_demo_readiness


def main() -> int:
  report = build_demo_readiness_report(project_root=PROJECT_ROOT)
  export_result = export_demo_readiness(report, project_root=PROJECT_ROOT)

  print(f"overall_status: {report.overall_status}")
  for case in report.cases:
    ev = case.evidence_link_count
    gap = case.gap_count
    ev_label = ev if ev is not None else "artifact_missing"
    gap_label = gap if gap is not None else "artifact_missing"
    print(
      f"  {case.case_id}: {case.overall_status} — step={case.current_recommended_step} "
      f"evidence={ev_label} gap={gap_label}"
    )
  print("common_next_actions:")
  for action in report.common_next_actions:
    print(f"  - {action}")
  print(f"output_dir: {export_result.output_dir}")
  print(f"manifest: {export_result.manifest_path}")
  return 0


if __name__ == "__main__":
  sys.exit(main())
