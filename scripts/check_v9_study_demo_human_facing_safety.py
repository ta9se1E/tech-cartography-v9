#!/usr/bin/env python3
"""Human-facing safety checks for Study Demo Simple Mode."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
  sys.path.insert(0, str(ROOT / "src"))

FIXTURE_PATH = ROOT / "tests" / "fixtures" / "study_demo_research_value_samples.json"
DEFAULT_RUN_ID = "study_demo_search_20260705_145711_c06e0a1b"


def _load_fixture() -> dict[str, Any]:
  return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def run_plan(*, search_run_id: str) -> dict[str, Any]:
  payload = _load_fixture()
  if str(payload.get("search_run_id", "")) != search_run_id:
    return {"status": "blocked", "message": "fixture run id mismatch", "expected": search_run_id}

  from services_v9.human_digest_builder import (
    build_human_digest,
    count_human_digest_violations,
    human_digest_to_markdown,
    validate_digest_payload,
  )
  from services_v9.human_datetime import format_datetime_jst
  from services_v9.research_value_pipeline import build_research_value_top3
  from services_v9.run_baseline_state import resolve_run_baseline_state
  from services_v9.search_improvement_eligibility import evaluate_proposal_eligibility
  from services_v9.simple_tier_display import count_tier_groups
  from services_v9.study_demo_review_proposals import generate_review_proposals

  theme = dict(payload.get("theme", {}) or {})
  signals = list(payload.get("signals", []) or [])
  context = dict(payload.get("active_context", {}) or {})
  baseline_state = resolve_run_baseline_state(
    context,
    previous_run=None,
    snapshots=[],
    weekly_state={"comparison_status": "not_comparable"},
    integrated_count=len(signals),
    priority_count=3,
  )
  human_digest = build_human_digest(
    theme=theme,
    signals=signals,
    baseline_state=baseline_state,
    reviews=[],
    updated_at=str(context.get("selected_at", "") or ""),
    integrated_count=len(signals),
  )
  markdown = human_digest_to_markdown(human_digest)
  violations = count_human_digest_violations(markdown)
  digest_quality = validate_digest_payload(human_digest)
  research_bundle = build_research_value_top3(signals, theme, limit=3)
  ui_roles = [item["output"]["role"]["label_ja"] for item in research_bundle["items"]]
  digest_roles = [dict(item.get("role", {})).get("label_ja", "") for item in human_digest.get("top3", [])]
  proposals = generate_review_proposals(
    reviews=[],
    signals=signals,
    source_run_id=search_run_id,
    profile_keywords=dict(theme.get("keywords", {}) or {}),
    theme_name=str(theme.get("name", "") or ""),
  )
  eligibility = evaluate_proposal_eligibility([])
  tier_counts = count_tier_groups(signals)
  priority_count = tier_counts.get("priority", 0)
  watch_count = tier_counts.get("watch", 0)
  reference_low_count = tier_counts.get("reference_low", 0)

  status = "ok"
  if baseline_state.get("state") != "initial_baseline":
    status = "blocked"
  if violations["raw_dict_occurrence_count"] > 0:
    status = "blocked"
  if violations["internal_token_occurrence_count"] > 0:
    status = "blocked"
  if violations["simple_run_id_occurrence_count"] > 0:
    status = "blocked"
  if eligibility.get("eligible"):
    status = "blocked"
  if ui_roles != digest_roles:
    status = "blocked"
  if digest_quality.get("status") != "ok":
    status = "blocked"

  return {
    "status": status,
    "search_run_id": search_run_id,
    "baseline_state": baseline_state.get("state"),
    "comparison_available": bool(baseline_state.get("has_comparison")),
    "weekly_summary_headline": human_digest.get("baseline_summary", {}).get("headline", ""),
    "digest_heading": human_digest.get("heading"),
    "digest_top3_roles": digest_roles,
    "ui_top3_roles": ui_roles,
    "raw_dict_occurrence_count": violations["raw_dict_occurrence_count"],
    "internal_token_occurrence_count": violations["internal_token_occurrence_count"],
    "simple_run_id_occurrence_count": violations["simple_run_id_occurrence_count"],
    "review_default": "unreviewed",
    "saved_review_count": 0,
    "proposal_eligible": bool(eligibility.get("eligible")),
    "proposal_reason": proposals.get("summary", {}).get("ineligible_reason", eligibility.get("reason", "")),
    "provider_priority_proposal_count": len(
      [item for item in proposals.get("proposals", []) if item.get("proposal_type") in {"boost_source_type", "lower_source_type"}]
    ),
    "tier_display_counts": {
      "priority": priority_count,
      "watch": watch_count,
      "reference_low": reference_low_count,
    },
    "empty_filter_count": 0,
    "dummy_history_row_count": 0,
    "jst_formatted_timestamp": format_datetime_jst(context.get("selected_at", "")),
    "digest_quality": digest_quality,
    "external_api_calls": 0,
    "cloud_writes": 0,
    "production_modifications": False,
    "forbidden_path_count": 0,
  }


def main() -> int:
  parser = argparse.ArgumentParser(description="Study Demo human-facing safety checks")
  parser.add_argument("--plan", action="store_true")
  parser.add_argument("--search-run-id", default=DEFAULT_RUN_ID)
  args = parser.parse_args()
  if not args.plan:
    print(json.dumps({"status": "blocked", "message": "only --plan is supported"}, ensure_ascii=False, indent=2))
    return 1
  result = run_plan(search_run_id=args.search_run_id)
  print(json.dumps(result, ensure_ascii=False, indent=2))
  return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
  raise SystemExit(main())
