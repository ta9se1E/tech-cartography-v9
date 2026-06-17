"""Tests for adaptive retrieval controller (Phase 16.2)."""

from __future__ import annotations

from tech_cartography.costs.adaptive_retrieval_controller import (
  build_adaptive_retrieval_plan,
  build_public_stop_reason,
  select_next_candidate_under_budget,
  should_execute_candidate,
  update_remaining_budget,
)
from tech_cartography.costs.internal_cost_policy import get_internal_cost_policy


def _us_candidate(pub: str = "US-12565719-B2") -> dict:
  return {"publication_number": pub, "country": "US", "title": "Fiber"}


def _cn_candidate() -> dict:
  return {"publication_number": "CN-2024-000001", "country": "CN", "title": "Fiber"}


def test_execute_allowed_within_raw_cap() -> None:
  policy = get_internal_cost_policy("claims_check")
  budget = update_remaining_budget(policy, [])
  decision = should_execute_candidate(
    _us_candidate(),
    policy,
    budget,
    {"estimated_usd": 0.5, "fulltext_scope": "claims_only"},
  )
  assert decision["allowed"] is True


def test_next_candidate_skipped_when_exceeds_cap() -> None:
  policy = get_internal_cost_policy("claims_check")
  ledger = [{"actual_usd_estimate": 2.4}]
  budget = update_remaining_budget(policy, ledger)
  decision = should_execute_candidate(
    _us_candidate(),
    policy,
    budget,
    {"estimated_usd": 0.5, "fulltext_scope": "claims_only"},
  )
  assert decision["allowed"] is False
  assert decision["retrieval_status"] == "skipped_budget_guard"


def test_remaining_budget_decreases_after_ledger() -> None:
  policy = get_internal_cost_policy("claims_check")
  before = update_remaining_budget(policy, [])
  after = update_remaining_budget(policy, [{"actual_usd_estimate": 1.0}])
  assert after["remaining_raw_budget_usd"] < before["remaining_raw_budget_usd"]


def test_cache_hit_allowed_even_with_low_budget() -> None:
  policy = get_internal_cost_policy("claims_check")
  budget = update_remaining_budget(policy, [{"actual_usd_estimate": 2.49}])
  decision = should_execute_candidate(
    _us_candidate(),
    policy,
    budget,
    {"estimated_usd": 10.0, "cache_hit": True, "fulltext_scope": "claims_only"},
  )
  assert decision["allowed"] is True


def test_cn_candidate_manual_route() -> None:
  policy = get_internal_cost_policy("claims_check")
  budget = update_remaining_budget(policy, [])
  decision = should_execute_candidate(
    _cn_candidate(),
    policy,
    budget,
    {"estimated_usd": 0.1, "fulltext_scope": "claims_only"},
  )
  assert decision["allowed"] is False
  assert decision["retrieval_status"] == "skipped_policy_scope"


def test_watch_run_no_fulltext_targets() -> None:
  policy = get_internal_cost_policy("watch_run")
  plan = build_adaptive_retrieval_plan([_us_candidate()], policy)
  assert plan["selected_count"] == 0
  assert plan["fulltext_enabled"] is False


def test_claims_check_selects_us_top1_claims_only() -> None:
  policy = get_internal_cost_policy("claims_check")
  candidates = [_us_candidate("US-1"), _us_candidate("US-2")]
  plan = build_adaptive_retrieval_plan(
    candidates,
    policy,
    estimates={
      "US1": {"estimated_usd": 0.5, "fulltext_scope": "claims_only"},
      "US2": {"estimated_usd": 0.5, "fulltext_scope": "claims_only"},
    },
  )
  assert plan["selected_count"] == 1
  selected = plan["selected_candidates"][0]
  assert selected["publication_number"] == "US-1"


def test_public_stop_reason_has_no_amounts() -> None:
  text = build_public_stop_reason("budget_exceeded")
  assert "$" not in text
  assert "usd" not in text.lower()
  assert "ドル" not in text


def test_select_next_under_budget() -> None:
  policy = get_internal_cost_policy("claims_check")
  picked = select_next_candidate_under_budget([_us_candidate()], policy, [])
  assert picked is not None
