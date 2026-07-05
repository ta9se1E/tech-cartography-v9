#!/usr/bin/env python3
"""Read-only mapping report for Study Demo theme draft promotion."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
  sys.path.insert(0, str(ROOT / "src"))


def _load_search_request(run_id: str) -> dict:
  fixture_path = ROOT / "tests/fixtures/study_demo_active_run_connection_samples.json"
  payload = json.loads(fixture_path.read_text(encoding="utf-8"))
  if str(payload.get("search_run_id", "")) != run_id:
    raise RuntimeError(f"fixture run id mismatch: {run_id}")
  return dict(payload["artifacts"]["search_request.json"])


def run_plan(*, search_run_id: str) -> dict:
  from services_v9.study_demo_theme_draft import build_theme_draft_from_temporary_search
  from services_v9.study_demo_theme_draft_mapping import validate_theme_draft_mapping
  from services_v9.study_demo_theme_lineage import default_saved_theme_fixture

  search_request = _load_search_request(search_run_id)
  saved = default_saved_theme_fixture()
  draft = build_theme_draft_from_temporary_search(
    search_request,
    search_run_id=search_run_id,
    active_context={"active_search_run_id": search_run_id, "theme": search_request["theme"], "active_context_generation": 1},
    context_generation=1,
    old_theme_keywords=dict(saved.get("keywords", {}) or {}),
  )
  validation = validate_theme_draft_mapping(
    list(draft.get("mapping_terms", []) or []),
    dict(draft.get("keywords", {}) or {}),
    old_theme_keywords=dict(saved.get("keywords", {}) or {}),
  )
  report = dict(draft.get("mapping_report", {}) or {})
  language_mismatch = sum(1 for item in validation if item.get("code") == "language_bucket_mismatch")
  explicit_exclusions = [
    item
    for item in list(draft.get("mapping_terms", []) or [])
    if str(item.get("semantic_bucket", "")) == "exclude"
    and str(item.get("provenance", "")) == "explicit_request_field"
    and item.get("accepted_for_theme")
  ]
  explicit_exclusion_candidates = [
    item
    for item in list(draft.get("term_candidates", []) or [])
    if str(item.get("semantic_bucket", "")) == "exclude"
    and str(item.get("value", "")).lower()
    in {str(x.get("normalized_value", "")).lower() for x in explicit_exclusions}
  ]
  blocking = sum(1 for item in validation if item.get("severity") == "error")
  return {
    "status": "ok" if blocking == 0 and language_mismatch == 0 else "failed",
    "search_run_id": search_run_id,
    "suggested_theme_name": draft.get("suggested_theme_name"),
    "review_status": draft.get("review_status"),
    "language_bucket_mismatch": language_mismatch,
    "old_theme_contamination": report.get("old_theme_contamination_count", 0),
    "blocking_error_count": blocking,
    "warning_count": report.get("warning_count", 0),
    "raw_term_count": report.get("raw_term_count", 0),
    "exact_match_count": report.get("exact_match_count", 0),
    "alias_suggestion_count": report.get("alias_suggestion_count", 0),
    "sample_core_ja": list(dict(draft.get("keywords", {}) or {}).get("core_ja", []))[:5],
    "sample_use_ja": list(dict(draft.get("keywords", {}) or {}).get("use_ja", []))[:5],
    "sample_material_ja": list(dict(draft.get("keywords", {}) or {}).get("material_process_ja", []))[:5],
    "sample_exclude_en": list(dict(draft.get("keywords", {}) or {}).get("exclude_en", []))[:5],
    "explicit_exclusion_count": report.get("explicit_exclusion_count", len(explicit_exclusions)),
    "explicit_exclusion_candidate_count": len(explicit_exclusion_candidates),
    "external_api_calls": 0,
    "cloud_writes": 0,
  }


def main() -> int:
  parser = argparse.ArgumentParser()
  parser.add_argument("--plan", action="store_true")
  parser.add_argument("--search-run-id", default="")
  args = parser.parse_args()
  if not args.plan:
    parser.error("only --plan is supported")
  run_id = str(args.search_run_id or "").strip()
  if not run_id:
    fixture_path = ROOT / "tests/fixtures/study_demo_active_run_connection_samples.json"
    run_id = str(json.loads(fixture_path.read_text(encoding="utf-8")).get("search_run_id", "") or "")
  payload = run_plan(search_run_id=run_id)
  print(json.dumps(payload, ensure_ascii=False, indent=2))
  return 0 if payload.get("status") == "ok" else 1


if __name__ == "__main__":
  raise SystemExit(main())
