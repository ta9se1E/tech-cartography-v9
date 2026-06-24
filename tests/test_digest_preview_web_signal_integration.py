"""Digest Preview Web Signal integration tests (Phase 25U)."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.services.live_digest_preview import generate_live_digest_preview
from tech_cartography.services.live_web_signal_review import (
  build_web_signal_review,
  integrate_review_into_preview,
  render_web_signal_section_markdown,
)


def test_integrate_adds_web_signal_section() -> None:
  pack = {
    "theme_name": "Theme",
    "candidates": [
      {
        "signal_id": "s1",
        "title": "Pack signal",
        "url": "https://example.com/p",
        "snippet": "s",
        "signal_type": "company_signal",
        "confidence_label": "medium",
        "review_status": "needs_human_review",
        "score": 0.5,
      },
    ],
  }
  preview = generate_live_digest_preview(pack, source_pack_path="/tmp/pack.json")
  summary = {
    "artifact_exists": True,
    "artifact_path": "/tmp/collection.json",
    "theme_name": "Theme",
    "queries_used": ["q1"],
    "result_count": 1,
    "web_signals": [
      {"title": "C", "url": "https://c.example.com", "domain": "c.example.com", "confidence_label": "candidate"},
    ],
    "warnings": [],
  }
  review = build_web_signal_review("/tmp", source_summary=summary)
  merged = integrate_review_into_preview(preview, review)
  assert merged["uses_web_signals"] is True
  assert "Web Signal候補" in merged["markdown_body"]
  assert "Web Signal候補" in merged["plain_text_body"]


def test_no_artifact_shows_not_collected_message() -> None:
  review = build_web_signal_review("/tmp", source_summary={"artifact_exists": False, "web_signals": []})
  md = render_web_signal_section_markdown(review)
  assert "まだ収集されていません" in md


def test_digest_preview_source_no_auto_collect() -> None:
  text = Path(__file__).resolve().parents[1].joinpath(
    "src/tech_cartography/services/live_digest_preview.py",
  ).read_text(encoding="utf-8")
  assert "collect_live_web_signals" not in text
