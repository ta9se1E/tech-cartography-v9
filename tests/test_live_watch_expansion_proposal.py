"""Tests for live watch expansion proposal service (Phase 25I)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tech_cartography.runtime.live_artifact_paths import LIVE_OUTPUTS_ROOT_ENV
from tech_cartography.services.live_watch_expansion_proposal import (
  REVIEW_STATUS,
  SAFETY_LABEL,
  SAFETY_NOTICE,
  build_expansion_proposals,
  build_proposals_document,
  save_live_watch_expansion_proposals,
)
from tech_cartography.services.live_web_signal_pack import build_live_web_signal_pack


@pytest.fixture
def sample_pack() -> dict:
  candidates = [
    {
      "signal_id": "sig-1",
      "title": "Toray carbon fiber precursor recycling project",
      "url": "https://www.toray.com/news",
      "snippet": "NEDO grant for CFRP aerospace application and surface treatment",
      "confidence_label": "high",
      "signal_type": "company_signal",
      "review_status": "needs_human_review",
    },
    {
      "signal_id": "sig-2",
      "title": "EU Horizon battery composite research",
      "url": "https://example.eu/project",
      "snippet": "demonstration funding for oxidation defect analysis",
      "confidence_label": "medium",
      "signal_type": "public_project_signal",
      "review_status": "needs_human_review",
    },
  ]
  return build_live_web_signal_pack(
    theme_name="Carbon Fiber Intelligence",
    query="carbon fiber PAN precursor patent",
    candidates=candidates,
    fetched_at="2026-06-18T12:00:00+00:00",
  )


def test_build_expansion_proposals_from_web_signal_pack(sample_pack: dict) -> None:
  proposals = build_expansion_proposals(pack=sample_pack, theme_name="Carbon Fiber Intelligence")
  assert proposals
  assert all(item["review_status"] == REVIEW_STATUS for item in proposals)
  assert all(item["safety_label"] == SAFETY_LABEL for item in proposals)
  types = {item["proposal_type"] for item in proposals}
  assert "technology_term" in types
  assert "company" in types or "public_project" in types


def test_proposals_are_not_auto_approved(sample_pack: dict) -> None:
  proposals = build_expansion_proposals(pack=sample_pack)
  assert all(item["review_status"] == "pending_human_review" for item in proposals)
  assert all("approved" not in item["review_status"] for item in proposals)


def test_proposals_exclude_forbidden_phrases(sample_pack: dict) -> None:
  pack = dict(sample_pack)
  pack["candidates"] = [
    {
      "signal_id": "bad-1",
      "title": "infringement confirmed report",
      "url": "https://example.com",
      "snippet": "fto cleared validity analysis",
      "confidence_label": "low",
      "signal_type": "unknown",
    },
  ]
  proposals = build_expansion_proposals(pack=pack)
  serialized = json.dumps(proposals)
  assert "infringement confirmed" not in serialized.lower()
  assert "fto cleared" not in serialized.lower()


def test_save_proposals_under_live_outputs_root(tmp_path: Path, sample_pack: dict, monkeypatch: pytest.MonkeyPatch) -> None:
  live_root = tmp_path / "live_root"
  monkeypatch.setenv(LIVE_OUTPUTS_ROOT_ENV, str(live_root))
  document = build_proposals_document(
    pack=sample_pack,
    digest=None,
    source_pack_path="pack.json",
    source_digest_path=None,
    theme_name="Carbon Fiber Intelligence",
  )
  saved = save_live_watch_expansion_proposals(document, tmp_path / "project")
  assert str(live_root / "live_watch_expansion") in saved["json"]
  payload = json.loads(Path(saved["json"]).read_text(encoding="utf-8"))
  assert payload["safety_notice"] == SAFETY_NOTICE
  assert "TAVILY_API_KEY" not in json.dumps(payload)
  assert "SMTP_PASSWORD" not in json.dumps(payload)


def test_document_has_expansion_proposals_alias(sample_pack: dict) -> None:
  document = build_proposals_document(
    pack=sample_pack,
    digest=None,
    source_pack_path="pack.json",
    source_digest_path=None,
    theme_name="Theme",
  )
  assert document["proposals"] == document["expansion_proposals"]
