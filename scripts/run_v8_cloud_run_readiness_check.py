#!/usr/bin/env python3
"""Run v8 Cloud Run Readiness check (Phase 27N) — prepare only, no deploy."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC = PROJECT_ROOT / "src"
if str(SRC) not in sys.path:
  sys.path.insert(0, str(SRC))

from tech_cartography.services.v8_cloud_run_readiness import build_cloud_run_readiness_report
from tech_cartography.services.v8_cloud_run_readiness_export import export_cloud_run_readiness


def main() -> int:
  report = build_cloud_run_readiness_report(project_root=PROJECT_ROOT)
  export_result = export_cloud_run_readiness(report, project_root=PROJECT_ROOT)

  print(f"overall_status: {report.overall_status}")
  if report.known_blockers:
    print("known_blockers:")
    for blocker in report.known_blockers:
      print(f"  - {blocker}")
  else:
    print("known_blockers: (none)")
  print(f"demo_data_status: {report.demo_data_status}")
  print(f"app_entrypoint_status: {report.app_entrypoint_status}")
  print(f"streamlit_command_status: {report.streamlit_command_status}")
  print(f"output_dir: {export_result.output_dir}")
  print(f"manifest: {export_result.manifest_path}")
  print("Cloud Build executed: false")
  print("Cloud Run deploy executed: false")
  return 0


if __name__ == "__main__":
  sys.exit(main())
