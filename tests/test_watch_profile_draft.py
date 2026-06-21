"""Tests for Watch Profile Draft service (Phase 25I)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tech_cartography.runtime.live_artifact_paths import LIVE_OUTPUTS_ROOT_ENV
from tech_cartography.services.live_watch_expansion_proposal import (
  REVIEW_STATUS,
  build_expansion_proposals,
  build_proposals_document,
)
from tech_cartography.services.live_web_signal_pack import build_live_web_signal_pack
from tech_cartography.services.watch_profile_draft import (
  apply_human_watch_expansion_decisions,
  build_watch_profile_draft_from_decisions,
  load_latest_watch_profile_draft,
  save_watch_profile_draft,
)


@pytest.fixture
def proposals_document() -> dict:
  pack = build_live_web_signal_pack(
    theme_name="Carbon Fiber Intelligence",
    query="PAN precursor CFRP",
    candidates=[
      {
        "signal_id": "sig-a",
        "title": "Toray PAN precursor project",
        "url": "https://www.toray.com",
        "snippet": "NEDO recycling aerospace application",
        "confidence_label": "high",
        "signal_type": "company_signal",
      },
      {
        "signal_id": "sig-b",
        "title": "Noise stock price update",
        "url": "https://example.com/ir",
        "snippet": "investor relations quarterly results",
        "confidence_label": "low",
        "signal_type": "market_signal",
      },
    ],
    fetched_at="2026-06-18T12:00:00+00:00",
  )
  return build_proposals_document(
    pack=pack,
    digest=None,
    source_pack_path="/tmp/pack.json",
    source_digest_path=None,
    theme_name="Carbon Fiber Intelligence",
  )


def test_only_approved_items_enter_draft(proposals_document: dict) -> None:
  proposals = proposals_document["proposals"]
  assert proposals
  approved_id = proposals[0]["proposal_id"]
  rejected_id = proposals[-1]["proposal_id"]

  draft = build_watch_profile_draft_from_decisions(
    proposals_document=proposals_document,
    approved_proposal_ids=[approved_id],
    rejected_proposal_ids=[rejected_id],
    approved_by="admin",
    source_proposal_path="/tmp/proposals.json",
  )

  approved_values = (
    draft["approved_keywords"]
    + draft["approved_companies"]
    + draft["approved_public_projects"]
    + draft["approved_technology_terms"]
    + draft["approved_market_applications"]
  )
  rejected_values = [item["proposed_value"] for item in draft["rejected_items"]]
  first_value = proposals[0]["proposed_value"]
  last_value = proposals[-1]["proposed_value"]

  if proposals[0]["proposal_type"] != "exclusion_term":
    assert first_value in approved_values or first_value in str(approved_values)
  assert any(item["proposal_id"] == rejected_id for item in draft["rejected_items"])
  assert last_value not in approved_values or last_value in rejected_values


def test_rejected_items_not_in_approved_lists(proposals_document: dict) -> None:
  proposals = proposals_document["proposals"]
  reject_id = proposals[-1]["proposal_id"]
  draft = build_watch_profile_draft_from_decisions(
    proposals_document=proposals_document,
    approved_proposal_ids=[],
    rejected_proposal_ids=[reject_id],
    approved_by="admin",
    source_proposal_path="/tmp/proposals.json",
  )
  rejected_value = proposals[-1]["proposed_value"]
  all_approved = (
    draft["approved_keywords"]
    + draft["approved_companies"]
    + draft["approved_public_projects"]
    + draft["approved_technology_terms"]
    + draft["approved_market_applications"]
  )
  assert rejected_value not in all_approved


def test_apply_decisions_saves_under_live_outputs_root(
  tmp_path: Path,
  proposals_document: dict,
  monkeypatch: pytest.MonkeyPatch,
) -> None:
  live_root = tmp_path / "live_root"
  monkeypatch.setenv(LIVE_OUTPUTS_ROOT_ENV, str(live_root))
  approved_id = proposals_document["proposals"][0]["proposal_id"]
  result = apply_human_watch_expansion_decisions(
    proposals_document=proposals_document,
    approved_proposal_ids=[approved_id],
    rejected_proposal_ids=[],
    approved_by="admin",
    source_proposal_path="/tmp/proposals.json",
    output_root=tmp_path / "project",
  )
  assert result["ok"] is True
  assert str(live_root / "live_watch_profiles") in result["saved_paths"]["json"]
  loaded = load_latest_watch_profile_draft(tmp_path / "project")
  assert loaded is not None
  assert loaded["approved_by"] == "admin"


def test_draft_save_excludes_secrets(tmp_path: Path, proposals_document: dict) -> None:
  draft = build_watch_profile_draft_from_decisions(
    proposals_document=proposals_document,
    approved_proposal_ids=[proposals_document["proposals"][0]["proposal_id"]],
    rejected_proposal_ids=[],
    approved_by="admin",
    source_proposal_path="/tmp/proposals.json",
  )
  saved = save_watch_profile_draft(draft, tmp_path)
  payload = json.loads(Path(saved["json"]).read_text(encoding="utf-8"))
  serialized = json.dumps(payload)
  assert "SMTP_PASSWORD" not in serialized
  assert "API_KEY" not in serialized
  assert "infringement confirmed" not in serialized.lower()


def test_pending_review_status_on_source_proposals(proposals_document: dict) -> None:
  for item in proposals_document["proposals"]:
    assert item["review_status"] == REVIEW_STATUS


def test_build_expansion_proposals_returns_list() -> None:
  pack = build_live_web_signal_pack(theme_name="T", query="PAN CFRP", candidates=[], fetched_at="2026-06-18T00:00:00+00:00")
  assert isinstance(build_expansion_proposals(pack=pack), list)
