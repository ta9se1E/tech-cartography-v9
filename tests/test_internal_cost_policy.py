"""Tests for internal cost policy (Phase 16.2)."""

from __future__ import annotations

from tech_cartography.costs.internal_cost_policy import (
  GlobalHardStop,
  InternalCostPolicy,
  compute_buffered_cost,
  get_internal_cost_policy,
  load_internal_cost_policy,
  public_policy_summary,
  validate_internal_cost_policy,
)


def test_watch_run_raw_cap() -> None:
  policy = get_internal_cost_policy("watch_run")
  assert policy.raw_cost_cap_usd == 1.5


def test_claims_check_raw_cap() -> None:
  policy = get_internal_cost_policy("claims_check")
  assert policy.raw_cost_cap_usd == 2.5


def test_full_deep_dive_raw_cap() -> None:
  policy = get_internal_cost_policy("full_deep_dive")
  assert policy.raw_cost_cap_usd == 10.0


def test_technical_review_raw_cap() -> None:
  policy = get_internal_cost_policy("technical_review")
  assert policy.raw_cost_cap_usd == 20.0


def test_deep_research_raw_cap() -> None:
  policy = get_internal_cost_policy("deep_research")
  assert policy.raw_cost_cap_usd == 40.0


def test_safety_margin() -> None:
  policy = get_internal_cost_policy("watch_run")
  assert policy.safety_margin == 1.3
  assert compute_buffered_cost(1.5, 1.3) == 1.95


def test_expose_cost_to_user_false() -> None:
  policy_set = load_internal_cost_policy()
  for policy in policy_set.policies.values():
    assert policy.expose_cost_to_user is False


def test_public_policy_summary_has_no_amounts() -> None:
  policy = get_internal_cost_policy("claims_check")
  summary = public_policy_summary(policy)
  blob = str(summary).lower()
  assert "usd" not in blob
  assert "raw_cost" not in blob
  assert "buffered" not in blob
  assert "margin" not in blob
  assert summary["policy_name"] == "claims_check"
  assert summary["user_facing_name_japanese"]


def test_unknown_policy_falls_back_to_watch_run() -> None:
  policy = get_internal_cost_policy("unknown_policy_xyz")
  assert policy.policy_name == "watch_run"


def test_hard_stop_exceeded_policy_errors() -> None:
  policy = InternalCostPolicy(
    policy_name="too_high",
    raw_cost_cap_usd=100.0,
    buffered_cost_cap_usd=130.0,
  )
  errors = validate_internal_cost_policy(policy, GlobalHardStop(max_raw_cost_usd_per_run=40.0))
  assert errors
