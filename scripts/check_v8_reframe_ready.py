#!/usr/bin/env python3
"""Phase27A/27B readiness check for v8 reframe and user-flow UI."""

from __future__ import annotations

import csv
import re
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DOCS = (
  "docs/v8_product_reframe.md",
  "docs/v8_three_case_validation_plan.md",
  "docs/v8_user_flow_and_tabs.md",
  "docs/v8_cursor_roadmap.md",
  "README_v8_LOCAL_FIRST.md",
)

V8_UI_FILES = (
  "src/tech_cartography/ui/v8_user_flow_app.py",
  "src/tech_cartography/ui/v8_tab_config.py",
  "src/tech_cartography/ui/v8_intro_ui.py",
  "src/tech_cartography/ui/v8_input_ui.py",
  "src/tech_cartography/ui/v8_sources_ui.py",
  "src/tech_cartography/ui/v8_patent_shortlist_ui.py",
  "src/tech_cartography/ui/v8_claim_map_ui.py",
  "src/tech_cartography/ui/v8_evidence_map_ui.py",
  "src/tech_cartography/ui/v8_gap_next_actions_ui.py",
  "src/tech_cartography/ui/v8_fixed_point_observation_ui.py",
  "src/tech_cartography/ui/v8_export_ui.py",
  "src/tech_cartography/ui/v8_admin_settings_ui.py",
)

V8_TAB_LABELS_REQUIRED = (
  "はじめに",
  "入力",
  "Sources一覧",
  "読むべき特許",
  "Claim Map",
  "Evidence Map",
  "Gap / Next Actions",
  "定点観測",
  "Export",
  "管理者設定",
)

USER_FACING_UI_FILES = tuple(
  path
  for path in V8_UI_FILES
  if "admin_settings" not in path
)

FORBIDDEN_USER_FACING = (
  "SMTP_PASSWORD",
  "TAVILY_API_KEY",
  "eyJhbGci",
)

CASE_IDS = (
  "case_01_pan_graphitization",
  "case_02_sizing_interface",
  "case_03_pressure_vessel_filament_winding",
)

CASE_FILES = (
  "case_profile.yaml",
  "source_candidates.csv",
  "expected_outputs.md",
  "validation_checklist.md",
)

CSV_COLUMNS = (
  "type",
  "title",
  "organization",
  "year",
  "url",
  "publication_number",
  "source_status",
  "evidence_role",
  "case_id",
  "notes",
)

DOC_KEYWORD_CHECKS: tuple[tuple[str, tuple[str, ...]], ...] = (
  (
    "email send required for fixed point observation",
    ("メール送信", "定点観測"),
  ),
  (
    "scheduler required for fixed point observation",
    ("Scheduler", "定点観測"),
  ),
  (
    "watch profile / scope feedback / run history",
    ("Watch Profile", "Scope Feedback", "Run History"),
  ),
  (
    "local-first development",
    ("ローカル", "local-first"),
  ),
  (
    "no FTO/infringement/validity/legal judgement",
    ("FTO", "侵害", "有効性"),
  ),
  (
    "no fake evidence",
    ("架空", "fake"),
  ),
  (
    "cloud build only at milestones",
    ("Cloud Build", "節目"),
  ),
)


def _read(path: Path) -> str:
  if not path.exists():
    return ""
  return path.read_text(encoding="utf-8")


def _check_file_exists(path: Path, failures: list[str]) -> bool:
  if path.exists():
    print(f"PASS: artifact exists: {path.relative_to(PROJECT_ROOT)}")
    return True
  failures.append(f"missing file: {path.relative_to(PROJECT_ROOT)}")
  return False


def _docs_blob() -> str:
  parts: list[str] = []
  for rel in REQUIRED_DOCS:
    parts.append(_read(PROJECT_ROOT / rel))
  return "\n".join(parts)


DEPRECATED_PATTERN = re.compile(r"use_container_width\s*=")


def _scan_deprecated_streamlit_width() -> list[str]:
  hits: list[str] = []
  for scan_root in (PROJECT_ROOT / "app.py", PROJECT_ROOT / "src", PROJECT_ROOT / "tests"):
    paths = [scan_root] if scan_root.is_file() else sorted(scan_root.rglob("*.py"))
    for path in paths:
      rel = str(path.relative_to(PROJECT_ROOT))
      if rel in {"scripts/check_v8_reframe_ready.py", "tests/test_streamlit_width_deprecation.py"}:
        continue
      for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if DEPRECATED_PATTERN.search(line):
          hits.append(f"{rel}:{line_no}")
  return hits


def _keyword_present(blob: str, keywords: tuple[str, ...]) -> bool:
  lowered = blob.lower()
  return any(kw.lower() in lowered for kw in keywords)


def main(argv: list[str] | None = None) -> int:
  del argv
  failures: list[str] = []

  print("v8 reframe readiness:")

  for rel in REQUIRED_DOCS:
    _check_file_exists(PROJECT_ROOT / rel, failures)

  for rel in V8_UI_FILES:
    _check_file_exists(PROJECT_ROOT / rel, failures)

  tab_config = _read(PROJECT_ROOT / "src/tech_cartography/ui/v8_tab_config.py")
  for label in V8_TAB_LABELS_REQUIRED:
    if label in tab_config:
      print(f"PASS: v8 tab label present: {label}")
    else:
      failures.append(f"v8_tab_config missing label: {label}")

  fixed_point = _read(PROJECT_ROOT / "src/tech_cartography/ui/v8_fixed_point_observation_ui.py")
  if "メール送信" in fixed_point and "Scheduler" in fixed_point:
    print("PASS: fixed point observation UI mentions email send and scheduler")
  else:
    failures.append("v8_fixed_point_observation_ui missing email/scheduler mention")

  admin_ui = _read(PROJECT_ROOT / "src/tech_cartography/ui/v8_admin_settings_ui.py")
  admin_tokens = ("operation", "admin", "IAP", "Scheduler")
  if all(token.lower() in admin_ui.lower() for token in admin_tokens):
    print("PASS: admin settings UI contains operation/admin related functions")
  else:
    failures.append("v8_admin_settings_ui missing operation/admin related content")

  for rel in USER_FACING_UI_FILES:
    text = _read(PROJECT_ROOT / rel)
    for token in FORBIDDEN_USER_FACING:
      if token in text:
        failures.append(f"user-facing UI {rel} mentions forbidden token: {token}")
  if not any("forbidden token" in f for f in failures):
    print("PASS: user-facing tabs do not mention SMTP_PASSWORD or TAVILY_API_KEY")

  app_py = _read(PROJECT_ROOT / "app.py")
  if "APP_UI_VERSION" in app_py and "v8_user_flow_app" in app_py:
    print("PASS: app.py wires v8 UI with APP_UI_VERSION switch")
  else:
    failures.append("app.py missing APP_UI_VERSION or v8_user_flow_app wiring")

  width_hits = _scan_deprecated_streamlit_width()
  if width_hits:
    failures.append(f"deprecated use_container_width= remains: {', '.join(width_hits)}")
  else:
    print("PASS: Streamlit width migration: yes")

  for case_id in CASE_IDS:
    case_dir = PROJECT_ROOT / "cases" / case_id
    for name in CASE_FILES:
      _check_file_exists(case_dir / name, failures)

    csv_path = case_dir / "source_candidates.csv"
    if csv_path.exists():
      with csv_path.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        fieldnames = reader.fieldnames or []
        missing_cols = [col for col in CSV_COLUMNS if col not in fieldnames]
        if missing_cols:
          failures.append(
            f"{case_id}/source_candidates.csv missing columns: {', '.join(missing_cols)}"
          )
        else:
          print(f"PASS: {case_id}/source_candidates.csv has required columns")

  blob = _docs_blob()
  for label, keywords in DOC_KEYWORD_CHECKS:
    if _keyword_present(blob, keywords):
      print(f"PASS: docs mention {label}")
    else:
      failures.append(f"docs missing keyword group for: {label} ({keywords})")

  if failures:
    print("\nFAILURES:")
    for item in failures:
      print(f"  - {item}")
    print(f"\nv8 reframe readiness: FAIL ({len(failures)} issue(s))")
    return 1

  print("\nv8 reframe readiness: PASS")
  return 0


if __name__ == "__main__":
  sys.exit(main())
