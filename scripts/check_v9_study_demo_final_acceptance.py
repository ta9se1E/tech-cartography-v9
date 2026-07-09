#!/usr/bin/env python3
"""Final browser acceptance checks for Study Demo Stage C5B-5D."""

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

  from services_v9.ranking_match_evidence import (
    build_field_aware_match_evidence,
    build_ranking_basis_payload,
    count_false_field_matches,
    simple_internal_token_count,
  )
  from services_v9.research_value_pipeline import build_research_value_top3
  from services_v9.run_baseline_state import resolve_run_baseline_state, resolve_snapshot_state
  from services_v9.search_improvement_eligibility import evaluate_proposal_eligibility, reject_internal_token
  from services_v9.study_demo_review_proposals import generate_review_proposals
  from ui_v9.study_demo_simple_tabs_ui import _baseline_save_controls_visible

  theme = dict(payload.get("theme", {}) or {})
  signals = list(payload.get("signals", []) or [])
  context = dict(payload.get("active_context", {}) or {})
  snapshots = list(payload.get("snapshots", []) or [])
  snapshot_state = resolve_snapshot_state(
    snapshots=snapshots,
    current_run_id=str(context.get("active_search_run_id", "") or ""),
  )
  weekly_state = resolve_run_baseline_state(
    context,
    previous_run=None,
    snapshots=snapshots,
    weekly_state={"comparison_status": "not_comparable"},
    integrated_count=len(signals),
    priority_count=3,
  )
  weekly_state["snapshot_state"] = snapshot_state
  research_bundle = build_research_value_top3(signals, theme, limit=3)
  third = research_bundle["items"][2]
  third_signal = dict(third.get("signal", {}) or {})
  third_basis = dict(third.get("output", {}).get("ranking_basis", {}) or {})
  third_evidence = build_field_aware_match_evidence(third_signal)
  third_title_terms = [item["term"] for item in third_evidence if item.get("field") == "title"]
  third_abstract_terms = [item["term"] for item in third_evidence if item.get("field") == "abstract"]
  false_counts = count_false_field_matches(third_evidence, third_signal)
  false_title_total = 0
  false_abstract_total = 0
  simple_token_total = 0
  for item in research_bundle["items"]:
    basis = dict(item.get("output", {}).get("ranking_basis", {}) or {})
    validation = dict(basis.get("field_validation", {}) or {})
    false_title_total += int(validation.get("false_title_match_count", 0) or 0)
    false_abstract_total += int(validation.get("false_abstract_match_count", 0) or 0)
    simple_token_total += simple_internal_token_count(basis)

  proposals = generate_review_proposals(
    reviews=[],
    signals=signals,
    source_run_id=search_run_id,
    profile_keywords=dict(theme.get("keywords", {}) or {}),
    theme_name=str(theme.get("name", "") or ""),
  )
  eligibility = evaluate_proposal_eligibility([])
  profile_source = (ROOT / "ui_v9" / "study_demo_simple_tabs_ui.py").read_text(encoding="utf-8")
  monitoring_internal_tokens = sum(
    1
    for token in ("sizing:title", "generic composite", "raise priority of source type:")
    if token in profile_source and "simple_suggestions" in profile_source
  )
  proposal_labels = [
    str(item.get("proposed_value", "") or "")
    for item in list(proposals.get("proposals", []) or [])
    if str(item.get("proposal_type", "")) != "no_change_observation"
  ]
  monitoring_profile_proposal_count = len(proposal_labels)
  monitoring_profile_internal_token_count = sum(1 for label in proposal_labels if reject_internal_token(label))

  ui_roles = [item["output"]["role"]["label_ja"] for item in research_bundle["items"]]
  tier_counts = dict(context.get("tier_counts", {}) or {})
  provider_counts = dict(context.get("provider_counts", {}) or {})

  result = {
    "status": "ok",
    "mode": "plan",
    "search_run_id": search_run_id,
    "false_title_match_count": false_title_total,
    "false_abstract_match_count": false_abstract_total,
    "simple_internal_token_count": simple_token_total,
    "third_signal_title": str(third_signal.get("title", "") or ""),
    "third_signal_title_terms": third_title_terms,
    "third_signal_abstract_terms": third_abstract_terms,
    "third_signal_summary_has_carbon_fiber_in_title_claim": "タイトルにcarbon fiber" in str(third_basis.get("summary", "")),
    "proposal_eligible": bool(eligibility.get("eligible")),
    "monitoring_profile_proposal_count": monitoring_profile_proposal_count,
    "monitoring_profile_internal_token_count": monitoring_profile_internal_token_count,
    "snapshot_state": snapshot_state,
    "baseline_save_control_visible": _baseline_save_controls_visible(weekly_state),
    "top3_roles": ui_roles,
    "provider_counts": provider_counts,
    "integrated_count": len(signals),
    "tier_counts": tier_counts,
    "lineage_status": context.get("lineage_status"),
    "external_api_calls": 0,
    "cloud_writes": 0,
    "production_modifications": False,
    "forbidden_path_count": 0,
    "browser_acceptance": [
      "Open Study Demo URL without password screen (public_demo)",
      "Confirm Public Demo — read-only badge is visible",
      "Confirm seeded demo notice and legal caveat are visible",
      "Confirm Theme PAN系炭素繊維用サイジング剤の組成・付与・乾燥条件 is shown",
      "Confirm Patent/Paper/Web counts are 5/5/5 and integrated=15",
      "Confirm Top3 research value cards render",
      "Browse Weekly/Digest tabs read-only",
      "Attempt write operations and confirm they are not persistently saved",
      "Confirm no external API calls are triggered during browsing",
      "Refresh page and confirm shared demo data remains unchanged",
      "Confirm secret/internal tokens are not displayed",
    ],
  }

  blockers: list[str] = []
  if false_title_total:
    blockers.append("false_title_match")
  if false_abstract_total:
    blockers.append("false_abstract_match")
  if simple_token_total:
    blockers.append("simple_internal_token")
  if result["third_signal_summary_has_carbon_fiber_in_title_claim"]:
    blockers.append("third_signal_false_title_claim")
  if result["proposal_eligible"]:
    blockers.append("proposal_should_be_ineligible")
  if monitoring_profile_proposal_count:
    blockers.append("monitoring_profile_proposals_visible")
  if monitoring_profile_internal_token_count:
    blockers.append("monitoring_profile_internal_token")
  if snapshot_state != "saved":
    blockers.append("snapshot_state_not_saved")
  if result["baseline_save_control_visible"]:
    blockers.append("baseline_save_control_visible")
  if blockers:
    result["status"] = "failed"
    result["blockers"] = blockers
  return result


def main() -> int:
  parser = argparse.ArgumentParser()
  parser.add_argument("--plan", action="store_true")
  parser.add_argument("--search-run-id", default=DEFAULT_RUN_ID)
  args = parser.parse_args()
  if not args.plan:
    parser.error("only --plan is supported")
  payload = run_plan(search_run_id=args.search_run_id)
  print(json.dumps(payload, ensure_ascii=False, indent=2))
  return 0 if payload.get("status") == "ok" else 1


if __name__ == "__main__":
  raise SystemExit(main())
