"""Weekly Decision Cockpit safety tests (Phase 25W)."""

from __future__ import annotations

from pathlib import Path

COCKPIT = Path("src/tech_cartography/services/live_weekly_decision_cockpit.py")

FORBIDDEN = ("smtplib", "send_email", "deep_research", "urllib.request", "collect_live_web_signals")


def test_cockpit_no_forbidden_calls() -> None:
  text = COCKPIT.read_text(encoding="utf-8").lower()
  for token in FORBIDDEN:
    assert token not in text


def test_cockpit_has_safety_notice() -> None:
  text = COCKPIT.read_text(encoding="utf-8")
  assert "COCKPIT_NOTICE_JA" in text
  assert "default_safety_flags" in text
  assert "candidate_information_only" in text or "default_safety_flags" in text
