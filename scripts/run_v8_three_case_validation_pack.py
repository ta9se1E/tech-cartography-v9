#!/usr/bin/env python3
"""Run v8 three-case local validation pack (Phase 27I)."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
  sys.path.insert(0, str(SRC))

from tech_cartography.services.v8_case_validation_export import export_validation_pack
from tech_cartography.services.v8_case_validation_pack import build_three_case_validation_pack


def main() -> int:
  pack = build_three_case_validation_pack(project_root=PROJECT_ROOT, ensure_artifacts=True)
  export_result = export_validation_pack(pack, project_root=PROJECT_ROOT)

  print(f"overall_status: {pack.overall_status}")
  for report in pack.cases:
    print(f"  {report.case_id}: readiness_for_demo={report.readiness_for_demo} ({report.overall_status})")
  print("common_blocking_issues:")
  for issue in pack.common_blocking_issues[:10]:
    print(f"  - {issue}")
  print(f"output_dir: {export_result.output_dir}")
  print(f"manifest: {export_result.manifest_path}")

  if pack.overall_status == "fail":
    return 1
  return 0


if __name__ == "__main__":
  sys.exit(main())
