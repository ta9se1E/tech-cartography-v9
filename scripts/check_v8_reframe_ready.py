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

CLAIMS_INPUT_COLUMNS = (
  "case_id",
  "publication_number",
  "patent_title",
  "claim_no",
  "claim_text",
  "claim_source_type",
  "claim_source_url",
  "claim_source_path",
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
    "phase27d patent shortlist reading priority not legal value",
    ("読む優先度", "heuristic", "特許価値"),
  ),
  (
    "phase27d claim map connection",
    ("Claim Map", "Phase27"),
  ),
  (
    "phase27e claim map not legal interpretation",
    ("Claim Map", "技術整理", "法的"),
  ),
  (
    "phase27e claim text not loaded",
    ("claim text not loaded", "not_loaded"),
  ),
  (
    "phase27f supporting evidence candidate",
    ("supporting evidence candidate", "候補"),
  ),
  (
    "phase27f evidence map not proof",
    ("not proof", "証明"),
  ),
  (
    "phase27f claim text required",
    ("claim_text_required", "claim text required"),
  ),
  (
    "phase27g gap not invalidity",
    ("Gap", "未確認", "弱点", "無効性"),
  ),
  (
    "phase27g next actions human verification",
    ("Next Action", "人間", "確認"),
  ),
  (
    "phase27g watch profile update proposal",
    ("Watch Profile", "update proposal"),
  ),
  (
    "phase27g email digest summary",
    ("digest summary", "Digest"),
  ),
  (
    "phase27g scheduler follow-up",
    ("Scheduler", "follow"),
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

  phase27c_files = (
    "src/tech_cartography/runtime/v8_sources_schema.py",
    "src/tech_cartography/services/v8_sources_loader.py",
    "src/tech_cartography/services/v8_sources_repository.py",
    "src/tech_cartography/services/v8_export_package.py",
  )
  for rel in phase27c_files:
    _check_file_exists(PROJECT_ROOT / rel, failures)

  sources_ui = _read(PROJECT_ROOT / "src/tech_cartography/ui/v8_sources_ui.py")
  export_ui = _read(PROJECT_ROOT / "src/tech_cartography/ui/v8_export_ui.py")
  export_pkg = _read(PROJECT_ROOT / "src/tech_cartography/services/v8_export_package.py")
  export_schema = _read(PROJECT_ROOT / "src/tech_cartography/runtime/v8_sources_schema.py")
  export_blob = export_pkg + export_schema
  if "Export Package" in sources_ui and "CSV" in sources_ui:
    print("PASS: v8_sources_ui has export controls")
  else:
    failures.append("v8_sources_ui missing export controls")
  if "Export Package" in export_ui and "manifest" in export_ui:
    print("PASS: v8_export_ui has export package controls")
  else:
    failures.append("v8_export_ui missing export package controls")

  for token in ("candidate information only", "human review", "FTO"):
    if token.lower() in export_blob.lower():
      continue
    failures.append(f"v8_export_package missing notice token: {token}")
  if not any("v8_export_package missing" in f for f in failures):
    print("PASS: export package docs mention safety notices")

  phase27d_files = (
    "src/tech_cartography/runtime/v8_patent_shortlist_schema.py",
    "src/tech_cartography/services/v8_patent_shortlist.py",
    "src/tech_cartography/services/v8_patent_shortlist_export.py",
  )
  for rel in phase27d_files:
    _check_file_exists(PROJECT_ROOT / rel, failures)

  shortlist_ui = _read(PROJECT_ROOT / "src/tech_cartography/ui/v8_patent_shortlist_ui.py")
  if "Generate / Refresh Patent Shortlist" in shortlist_ui:
    print("PASS: v8_patent_shortlist_ui has generate control")
  else:
    failures.append("v8_patent_shortlist_ui missing Generate / Refresh Patent Shortlist")

  shortlist_blob = _read(PROJECT_ROOT / "src/tech_cartography/services/v8_patent_shortlist.py")
  shortlist_schema = _read(PROJECT_ROOT / "src/tech_cartography/runtime/v8_patent_shortlist_schema.py")
  score_tokens = ("heuristic", "draft", "reading priority", "読む優先度")
  if any(tok.lower() in (shortlist_blob + shortlist_schema + shortlist_ui).lower() for tok in score_tokens):
    print("PASS: patent shortlist score labels mention draft/heuristic/reading priority")
  else:
    failures.append("patent shortlist missing draft/heuristic/reading priority labels")

  if "patent_shortlist" in export_ui:
    print("PASS: v8_export_ui references patent_shortlist artifacts")
  else:
    failures.append("v8_export_ui missing patent_shortlist references")

  if "読むべき特許" in sources_ui or "patent_shortlist" in sources_ui:
    print("PASS: v8_sources_ui links to patent shortlist")
  else:
    failures.append("v8_sources_ui missing patent shortlist navigation")

  try:
    sys.path.insert(0, str(PROJECT_ROOT / "src"))
    from tech_cartography.services.v8_patent_shortlist import build_patent_shortlist

    for case_id in CASE_IDS:
      shortlist = build_patent_shortlist(case_id=case_id, top_n=5, project_root=PROJECT_ROOT)
      if len(shortlist.patent_candidates) >= 3:
        print(f"PASS: {case_id} produces {len(shortlist.patent_candidates)} patent candidates")
      else:
        failures.append(
          f"{case_id} produces only {len(shortlist.patent_candidates)} patent candidates (need >=3)",
        )
  except Exception as exc:
    failures.append(f"patent shortlist build failed: {exc}")

  legal_forbidden = re.compile(
    r"(fto\s*clearance|infringement\s*analysis|validity\s*judgement|legal\s*conclusion)",
    re.IGNORECASE,
  )
  for rel in phase27d_files + ("src/tech_cartography/ui/v8_patent_shortlist_ui.py",):
    text = _read(PROJECT_ROOT / rel)
    if legal_forbidden.search(text) and "no_legal" not in text.lower():
      failures.append(f"{rel} may claim legal judgement without disclaimer")

  phase27e_files = (
    "src/tech_cartography/runtime/v8_claim_map_schema.py",
    "src/tech_cartography/services/v8_claim_input_loader.py",
    "src/tech_cartography/services/v8_claim_map.py",
    "src/tech_cartography/services/v8_claim_map_export.py",
  )
  for rel in phase27e_files:
    _check_file_exists(PROJECT_ROOT / rel, failures)

  claim_map_ui = _read(PROJECT_ROOT / "src/tech_cartography/ui/v8_claim_map_ui.py")
  if "Generate / Refresh Claim Map" in claim_map_ui:
    print("PASS: v8_claim_map_ui has generate control")
  else:
    failures.append("v8_claim_map_ui missing Generate / Refresh Claim Map")

  claim_blob = _read(PROJECT_ROOT / "src/tech_cartography/services/v8_claim_map.py")
  claim_schema = _read(PROJECT_ROOT / "src/tech_cartography/runtime/v8_claim_map_schema.py")
  if "claim text not loaded" in (claim_blob + claim_schema + claim_map_ui).lower():
    print("PASS: claim map mentions claim text not loaded")
  else:
    failures.append("claim map missing claim text not loaded notice")

  if "claim_map" in export_ui:
    print("PASS: v8_export_ui references claim_map artifacts")
  else:
    failures.append("v8_export_ui missing claim_map references")

  try:
    from tech_cartography.services.v8_claim_map import build_claim_map

    import csv as csv_mod

    for case_id in CASE_IDS:
      claims_csv = PROJECT_ROOT / "cases" / case_id / "claims_input.csv"
      _check_file_exists(claims_csv, failures)
      if claims_csv.exists():
        with claims_csv.open(encoding="utf-8", newline="") as handle:
          reader = csv_mod.DictReader(handle)
          fieldnames = reader.fieldnames or []
          missing_claim_cols = [c for c in CLAIMS_INPUT_COLUMNS if c not in fieldnames]
          if missing_claim_cols:
            failures.append(f"{case_id}/claims_input.csv missing columns: {', '.join(missing_claim_cols)}")
          else:
            print(f"PASS: {case_id}/claims_input.csv has required columns")
          claim_rows = list(reader)
        if len(claim_rows) >= 3:
          print(f"PASS: {case_id}/claims_input.csv has {len(claim_rows)} rows")
        else:
          failures.append(f"{case_id}/claims_input.csv has only {len(claim_rows)} rows (need >=3)")

      claim_map = build_claim_map(case_id=case_id, project_root=PROJECT_ROOT)
      if claim_map.claim_count >= 3:
        print(f"PASS: {case_id} produces {claim_map.claim_count} claim map records")
      else:
        failures.append(f"{case_id} produces only {claim_map.claim_count} claim map records (need >=3)")
  except Exception as exc:
    failures.append(f"claim map build failed: {exc}")

  for rel in phase27e_files + ("src/tech_cartography/ui/v8_claim_map_ui.py",):
    text = _read(PROJECT_ROOT / rel)
    if legal_forbidden.search(text) and "no_legal" not in text.lower():
      failures.append(f"{rel} may claim legal judgement without disclaimer")

  phase27f_files = (
    "src/tech_cartography/runtime/v8_evidence_map_schema.py",
    "src/tech_cartography/services/v8_evidence_map.py",
    "src/tech_cartography/services/v8_evidence_map_export.py",
  )
  for rel in phase27f_files:
    _check_file_exists(PROJECT_ROOT / rel, failures)

  evidence_map_ui = _read(PROJECT_ROOT / "src/tech_cartography/ui/v8_evidence_map_ui.py")
  fixed_point_ui = _read(PROJECT_ROOT / "src/tech_cartography/ui/v8_fixed_point_observation_ui.py")
  if "Generate / Refresh Evidence Map" in evidence_map_ui:
    print("PASS: v8_evidence_map_ui has generate control")
  else:
    failures.append("v8_evidence_map_ui missing Generate / Refresh Evidence Map")

  ev_blob = _read(PROJECT_ROOT / "src/tech_cartography/services/v8_evidence_map.py")
  ev_schema = _read(PROJECT_ROOT / "src/tech_cartography/runtime/v8_evidence_map_schema.py")
  if "supporting evidence candidate" in (ev_blob + ev_schema + evidence_map_ui).lower():
    print("PASS: evidence map mentions supporting evidence candidate")
  else:
    failures.append("evidence map missing supporting evidence candidate notice")

  if "evidence_map" in export_ui:
    print("PASS: v8_export_ui references evidence_map artifacts")
  else:
    failures.append("v8_export_ui missing evidence_map references")

  if "Evidence Map" in fixed_point_ui and ("Digest" in fixed_point_ui or "Watch Profile" in fixed_point_ui):
    print("PASS: fixed point observation UI references Evidence Map gaps")
  else:
    failures.append("v8_fixed_point_observation_ui missing Evidence Map gap references")

  try:
    from tech_cartography.services.v8_evidence_map import build_evidence_map

    for case_id in CASE_IDS:
      emap = build_evidence_map(case_id=case_id, project_root=PROJECT_ROOT)
      if emap.link_count >= 1:
        print(f"PASS: {case_id} produces {emap.link_count} evidence map links")
      else:
        failures.append(f"{case_id} produces no evidence map links")
      if emap.claim_text_required_count >= 1:
        print(f"PASS: {case_id} has claim_text_required_count={emap.claim_text_required_count}")
      else:
        failures.append(f"{case_id} missing claim_text_required links")
  except Exception as exc:
    failures.append(f"evidence map build failed: {exc}")

  for rel in phase27f_files + ("src/tech_cartography/ui/v8_evidence_map_ui.py",):
    text = _read(PROJECT_ROOT / rel)
    if legal_forbidden.search(text) and "no_legal" not in text.lower():
      failures.append(f"{rel} may claim legal judgement without disclaimer")

  phase27g_files = (
    "src/tech_cartography/runtime/v8_gap_next_actions_schema.py",
    "src/tech_cartography/services/v8_gap_next_actions.py",
    "src/tech_cartography/services/v8_gap_next_actions_export.py",
  )
  for rel in phase27g_files:
    _check_file_exists(PROJECT_ROOT / rel, failures)

  gap_ui = _read(PROJECT_ROOT / "src/tech_cartography/ui/v8_gap_next_actions_ui.py")
  if "Generate / Refresh Gap" in gap_ui:
    print("PASS: v8_gap_next_actions_ui has generate control")
  else:
    failures.append("v8_gap_next_actions_ui missing Generate / Refresh Gap")

  gap_blob = _read(PROJECT_ROOT / "src/tech_cartography/services/v8_gap_next_actions.py")
  gap_schema = _read(PROJECT_ROOT / "src/tech_cartography/runtime/v8_gap_next_actions_schema.py")
  if "invalidity" in (gap_blob + gap_schema + gap_ui).lower() or "弱点" in gap_schema:
    print("PASS: gap next actions mentions gap is not invalidity / weakness")
  else:
    failures.append("gap next actions missing invalidity / weakness disclaimer")

  if "人間" in gap_schema or "human verification" in gap_ui.lower():
    print("PASS: next actions described as human verification tasks")
  else:
    failures.append("docs/UI missing next actions human verification notice")

  if "watch_profile_update_proposal" in gap_blob or "Watch Profile" in gap_ui:
    print("PASS: watch profile update proposal referenced")
  else:
    failures.append("missing watch profile update proposal")

  if "digest_summary" in gap_blob:
    print("PASS: digest summary referenced")
  else:
    failures.append("missing digest summary")

  if "scheduler" in gap_ui.lower() and "digest" in gap_ui.lower():
    print("PASS: gap UI mentions scheduler / digest follow-up")
  else:
    failures.append("gap UI missing scheduler / digest follow-up")

  fixed_point_ui = _read(PROJECT_ROOT / "src/tech_cartography/ui/v8_fixed_point_observation_ui.py")
  if "gap_next_actions" in fixed_point_ui or "Gap / Next Actions" in fixed_point_ui:
    print("PASS: fixed point observation UI references Gap / Next Actions")
  else:
    failures.append("fixed point UI missing Gap / Next Actions references")

  if "gap_next_actions" in export_ui:
    print("PASS: v8_export_ui references gap_next_actions artifacts")
  else:
    failures.append("v8_export_ui missing gap_next_actions references")

  try:
    from tech_cartography.services.v8_gap_next_actions import build_gap_next_actions_report

    for case_id in CASE_IDS:
      report = build_gap_next_actions_report(case_id=case_id, project_root=PROJECT_ROOT)
      if report.gap_count >= 1:
        print(f"PASS: {case_id} produces {report.gap_count} gaps")
      else:
        failures.append(f"{case_id} produces no gaps")
      if len(report.top_3_actions) >= 1:
        print(f"PASS: {case_id} produces top_3_actions={len(report.top_3_actions)}")
      else:
        failures.append(f"{case_id} missing top_3_actions")
      if report.watch_profile_update_proposal.strip():
        print(f"PASS: {case_id} has watch_profile_update_proposal")
      else:
        failures.append(f"{case_id} empty watch_profile_update_proposal")
      if report.digest_summary.strip():
        print(f"PASS: {case_id} has digest_summary")
      else:
        failures.append(f"{case_id} empty digest_summary")
  except Exception as exc:
    failures.append(f"gap next actions build failed: {exc}")

  for rel in phase27g_files + ("src/tech_cartography/ui/v8_gap_next_actions_ui.py",):
    text = _read(PROJECT_ROOT / rel)
    if legal_forbidden.search(text) and "no_legal" not in text.lower():
      failures.append(f"{rel} may claim legal judgement without disclaimer")

  fake_doi_re = re.compile(r"10\.(0000|1234)/|example\.com|fake-doi|placeholder", re.IGNORECASE)
  import csv as csv_mod

  for case_id in CASE_IDS:
    csv_path = PROJECT_ROOT / "cases" / case_id / "source_candidates.csv"
    if not csv_path.exists():
      continue
    with csv_path.open(encoding="utf-8", newline="") as handle:
      reader = csv_mod.DictReader(handle)
      rows = list(reader)
    patent_count = sum(1 for r in rows if str(r.get("type") or "").lower() == "patent")
    if patent_count >= 5:
      print(f"PASS: {case_id} has {patent_count} patent rows")
    else:
      failures.append(f"{case_id} has only {patent_count} patent rows (need >=5)")
    for row in rows:
      url = str(row.get("url") or "")
      if fake_doi_re.search(url):
        failures.append(f"{case_id} has fake-like DOI/url: {url}")

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
