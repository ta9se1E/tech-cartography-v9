"""Tests for live web signal review (Phase 25U)."""

from __future__ import annotations

from tech_cartography.services.live_web_signal_review import (
  build_web_signal_review,
  render_web_signal_section_markdown,
)


def _summary_with_signals() -> dict:
  return {
    "artifact_exists": True,
    "artifact_path": "/tmp/collection.json",
    "status": "success",
    "theme_name": "Theme",
    "queries_used": ["q1", "q2"],
    "result_count": 3,
    "web_signals": [
      {"title": "A", "url": "https://a.example.com/x", "domain": "a.example.com", "confidence_label": "candidate"},
      {"title": "B", "url": "https://b.example.com/y", "domain": "b.example.com", "confidence_label": "candidate"},
      {"title": "C", "url": "https://a.example.com/x", "domain": "a.example.com", "confidence_label": "candidate"},
    ],
    "warnings": [],
  }


def test_build_review_has_safety_flags() -> None:
  review = build_web_signal_review("/tmp", source_summary=_summary_with_signals())
  flags = review["safety_flags"]
  assert flags["candidate_information_only"] is True
  assert flags["legal_judgement"] is False
  assert flags["fto_judgement"] is False
  assert flags["infringement_judgement"] is False
  assert flags["validity_judgement"] is False


def test_duplicate_url_count() -> None:
  review = build_web_signal_review("/tmp", source_summary=_summary_with_signals())
  assert review["duplicate_url_count"] == 1


def test_domain_summary() -> None:
  review = build_web_signal_review("/tmp", source_summary=_summary_with_signals())
  assert review["signals_by_domain"]["a.example.com"] == 2
  assert review["signals_by_domain"]["b.example.com"] == 1


def test_markdown_section_includes_candidate_notice() -> None:
  review = build_web_signal_review("/tmp", source_summary=_summary_with_signals())
  md = render_web_signal_section_markdown(review)
  assert "Web Signal候補" in md
  assert "候補情報" in md
  assert "FTO" in md


def test_empty_artifact_notice() -> None:
  review = build_web_signal_review("/tmp", source_summary={"artifact_exists": False, "web_signals": []})
  md = render_web_signal_section_markdown(review)
  assert "まだ収集されていません" in md
