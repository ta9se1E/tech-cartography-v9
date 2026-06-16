from __future__ import annotations

from tech_cartography.retrieval.controlled_fulltext_plan import (
  build_controlled_fulltext_plan,
  mark_execute_selected_targets,
  select_fulltext_execute_targets,
)


def _us_rows() -> list[dict]:
  return [
    {"publication_number": "US-111", "country": "US", "title": "A", "source_route": "us_bigquery_fulltext_candidate"},
    {"publication_number": "US-222", "country": "US", "title": "B", "source_route": "us_bigquery_fulltext_candidate"},
    {"publication_number": "US-333", "country": "US", "title": "C", "source_route": "us_bigquery_fulltext_candidate"},
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
