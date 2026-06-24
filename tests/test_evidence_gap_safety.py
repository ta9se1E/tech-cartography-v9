"""Evidence gap safety tests (Phase 25V)."""

from __future__ import annotations

from pathlib import Path

BUILDER = Path("src/tech_cartography/services/live_evidence_gap_builder.py")
BRIEF = Path("src/tech_cartography/services/live_strategic_watch_brief.py")
SCHEMA = Path("src/tech_cartography/runtime/evidence_gap_schema.py")

FORBIDDEN = ("smtplib", "send_email", "deep_research", "urllib.request", "collect_live_web_signals", "_default_post_tavily")


def test_services_no_external_api() -> None:
  for path in (BUILDER, BRIEF):
    text = path.read_text(encoding="utf-8").lower()
    for token in FORBIDDEN:
      assert token not in text


def test_schema_blocks_auto_human_verified() -> None:
  text = SCHEMA.read_text(encoding="utf-8")
  assert "human_verified" in text
  assert "verified_by_human" in text


def test_builder_safety_flags() -> None:
  text = BUILDER.read_text(encoding="utf-8")
  assert "default_safety_flags" in text
  assert "WHAT_NOT_TO_CONCLUDE" in text
