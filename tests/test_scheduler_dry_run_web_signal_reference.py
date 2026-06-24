"""Scheduler dry-run web signal artifact reference (Phase 25U)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.services.live_scheduler_dry_run import _planned_steps


def test_planned_steps_include_confirm_existing_artifact() -> None:
  steps = _planned_steps(has_active_profile=True, has_web_signal_collection=True)
  assert "confirm_existing_web_signal_artifact" in steps


def test_scheduler_dry_run_no_external_api() -> None:
  text = Path(__file__).resolve().parents[1].joinpath(
    "src/tech_cartography/services/live_scheduler_dry_run.py",
  ).read_text(encoding="utf-8")
  assert "collect_live_web_signals" not in text
  assert "_default_post_tavily" not in text
