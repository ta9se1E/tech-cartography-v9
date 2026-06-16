from __future__ import annotations

from tech_cartography.retrieval.controlled_fulltext_plan import (
  build_controlled_fulltext_plan,
  build_fulltext_execute_preview,
  mark_execute_selected_targets,
  pass_fulltext_execute_quality_gate,
  select_fulltext_execute_targets,
)


def _us_rows() -> list[dict]:
  return [
    {
      "publication_number": "US-111",
      "country": "US",
      "title": "PAN carbon fiber precursor",
      "source_route": "us_bigquery_fulltext_candidate",
    },
    {
      "publication_number": "US-222",
      "country": "US",
      "title": "Carbon fiber surface treatment",
      "source_route": "us_bigquery_fulltext_candidate",
    },
    {
      "publication_number": "US-333",
      "country": "US",
      "title": "Carbonization of PAN fibers",
      "source_route": "us_bigquery_fulltext_candidate",
    },
  ]


def test_execute_limit_selects_one_target() -> None:
  plan = build_controlled_fulltext_plan(_us_rows(), [])
  selected = select_fulltext_execute_targets(plan, limit=1)
  assert len(selected) == 1
  assert selected[0]["publication_number"] == "US-111"
  marked = mark_execute_selected_targets(plan, selected)
  assert marked["fulltext_targets"][0]["execute_selected"] is True
  assert marked["fulltext_targets"][1]["execute_selected"] is False


def test_publication_number_selects_single_us_target() -> None:
  plan = build_controlled_fulltext_plan(_us_rows(), [])
  selected = select_fulltext_execute_targets(plan, publication_number="US-222")
  assert len(selected) == 1
  assert selected[0]["publication_number"] == "US-222"


def test_cn_publication_number_not_selected_for_execute() -> None:
  plan = build_controlled_fulltext_plan(
    _us_rows(),
    [{"publication_number": "CN-1", "country": "CN", "title": "CN fiber"}],
  )
  selected = select_fulltext_execute_targets(plan, publication_number="CN-1")
  assert selected == []


def test_default_limit_is_one_when_unspecified() -> None:
  plan = build_controlled_fulltext_plan(_us_rows(), [])
  selected = select_fulltext_execute_targets(plan)
  assert len(selected) == 1


def test_strategic_watch_remains_manual_route() -> None:
  strategic = [
    {
      "publication_number": "CN-121137864-A",
      "country": "CN",
      "assignee": "ZHONGFU SHENYING",
      "source_route": "manual_fulltext_required",
    },
  ]
  plan = build_controlled_fulltext_plan(_us_rows(), strategic)
  assert len(plan["strategic_watch_manual_candidates"]) == 1
  assert plan["strategic_watch_manual_candidates"][0]["country"] == "CN"


def test_fulltext_scope_in_plan() -> None:
  plan = build_controlled_fulltext_plan(_us_rows(), [], fulltext_scope="description_only")
  assert plan["plan_summary"]["fulltext_scope"] == "description_only"


def test_carbon_fiber_candidate_passes_quality_gate() -> None:
  gate = pass_fulltext_execute_quality_gate(
    {
      "publication_number": "US-1",
      "country": "US",
      "title": "PAN precursor carbon fiber carbonization",
      "source_route": "us_bigquery_fulltext_candidate",
    },
  )
  assert gate["passed"] is True


def test_low_quality_us_candidate_fails_quality_gate() -> None:
  gate = pass_fulltext_execute_quality_gate(
    {
      "publication_number": "US-9",
      "country": "US",
      "title": "Stretchable display panel",
      "source_route": "us_bigquery_fulltext_candidate",
    },
  )
  assert gate["passed"] is False


def test_quality_gate_excludes_low_priority_from_execute() -> None:
  rows = [
    {
      "publication_number": "US-111",
      "country": "US",
      "title": "System and method for a vessel assessment tool",
      "source_route": "us_bigquery_fulltext_candidate",
    },
    {
      "publication_number": "US-222",
      "country": "US",
      "title": "PAN carbon fiber precursor",
      "source_route": "us_bigquery_fulltext_candidate",
    },
  ]
  plan = build_controlled_fulltext_plan(rows, [])
  selected = select_fulltext_execute_targets(plan, limit=1)
  assert selected[0]["publication_number"] == "US-222"


def test_recommended_expensive_command_in_preview() -> None:
  plan = build_controlled_fulltext_plan(_us_rows(), [])
  preview = build_fulltext_execute_preview(
    plan,
    execute=True,
    confirm_fulltext_execute=True,
    fulltext_scope="claims_only",
    dry_run_by_pub={
      "US111": {
        "estimated_bytes": 10**12,
        "estimated_gb": 900.0,
        "estimated_usd": 4.5,
        "cost_guard_status": "blocked_by_gb_but_usd_allowed_requires_confirmation",
        "fulltext_scope": "claims_only",
      },
    },
    scope_estimates=[
      {
        "publication_number": "US-111",
        "scope": "claims_only",
        "estimated_gb": 900.0,
        "estimated_usd": 4.5,
        "cost_guard_status": "blocked_by_gb_but_usd_allowed_requires_confirmation",
      },
    ],
  )
  assert "allow-expensive-fulltext" in preview["recommended_expensive_command"]
  assert preview["fulltext_scope"] == "claims_only"
