"""Scheduler dry-run evidence gap reference tests (Phase 25V)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.services.live_scheduler_dry_run import _planned_steps


def test_planned_steps_include_evidence_gap_and_brief() -> None:
  steps = _planned_steps(has_active_profile=True, has_web_signal_collection=True)
  assert "confirm_evidence_gap_artifact" in steps
  assert "confirm_strategic_watch_brief_artifact" in steps


def test_scheduler_no_auto_build() -> None:
  text = Path("src/tech_cartography/services/live_scheduler_dry_run.py").read_text(encoding="utf-8")
  assert "run_live_evidence_gap_build" not in text
  assert "run_live_strategic_watch_brief_build" not in text
