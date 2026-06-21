"""Tests for next cycle search plan service (Phase 25J)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tech_cartography.runtime.live_artifact_paths import LIVE_OUTPUTS_ROOT_ENV
from tech_cartography.services.live_next_cycle_search_plan import (
  MAX_QUERY_CANDIDATES,
  REVIEW_STATUS,
  SAFETY_LABEL,
  build_next_cycle_search_plan,
  build_query_candidates_from_draft,
  save_next_cycle_search_plan,
)


@pytest.fixture
def sample_draft() -> dict:
  return {
    "theme_name": "Carbon Fiber Intelligence",
    "approved_keywords": ["PAN", "precursor"],
    "approved_companies": ["Toray"],
    "approved_public_projects": ["NEDO"],
    "approved_technology_terms": ["recycling"],
    "approved_market_applications": ["aerospace"],
  }


def test_build_query_candidates_from_draft(sample_draft: dict) -> None:
  candidates = build_query_candidates_from_draft(sample_draft)
  assert candidates
  assert len(candidates) <= MAX_QUERY_CANDIDATES
  assert all(item["review_status"] == REVIEW_STATUS for item in candidates)
  assert all(item["safety_label"] == SAFETY_LABEL for item in candidates)
  queries = [item["query"].lower() for item in candidates]
  assert len(queries) == len(set(queries))


def test_empty_draft_returns_no_candidates() -> None:
  assert build_query_candidates_from_draft({"theme_name": "Theme"}) == []


def test_plan_includes_plan_id_and_source_path(sample_draft: dict) -> None:
  plan = build_next_cycle_search_plan(
    draft=sample_draft,
    source_watch_profile_draft_path="/tmp/draft.json",
  )
  assert plan["plan_id"]
  assert plan["source_watch_profile_draft_path"] == "/tmp/draft.json"
  assert plan["query_candidates"]


def test_save_plan_under_live_outputs_root(
  tmp_path: Path,
  sample_draft: dict,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  live_root = tmp_path / "live_root"
  monkeypatch.setenv(LIVE_OUTPUTS_ROOT_ENV, str(live_root))
  plan = build_next_cycle_search_plan(
    draft=sample_draft,
    source_watch_profile_draft_path="/tmp/draft.json",
  )
  saved = save_next_cycle_search_plan(plan, tmp_path / "project")
  assert str(live_root / "live_next_cycle_search") in saved["json"]
  payload = json.loads(Path(saved["json"]).read_text(encoding="utf-8"))
  serialized = json.dumps(payload)
  assert "SMTP_PASSWORD" not in serialized
  assert "API_KEY" not in serialized
