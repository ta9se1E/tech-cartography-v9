"""Tests for the lightweight Tech Cartography v9 signal watch app."""

from __future__ import annotations

from services_v9.demo_data import load_demo_signals, load_demo_watch_profile
from services_v9.digest_export import build_weekly_digest_markdown
from services_v9.signal_scoring import (
  classify_action,
  classify_status,
  enrich_signals,
  select_diverse_top_signals,
  suggest_watch_profile_updates,
)


def _load_enriched_signals():
  return enrich_signals(load_demo_signals())


def test_demo_signals_can_be_loaded() -> None:
  signals = load_demo_signals()
  assert signals
  assert signals[0].title


def test_demo_signal_count_is_at_least_ten() -> None:
  signals = load_demo_signals()
  assert len(signals) >= 10


def test_status_classification_behaves_as_expected() -> None:
  assert classify_status(0.82, None) == "New"
  assert classify_status(0.82, 0.70) == "Rising"
  assert classify_status(0.50, 0.64) == "Dropped"
  assert classify_status(0.61, 0.59) == "Stable"


def test_action_classification_behaves_as_expected() -> None:
  assert classify_action(0.82, "New") == "Read Now"
  assert classify_action(0.60, "Stable") == "Watch"
  assert classify_action(0.42, "Dropped") == "Ignore"


def test_diverse_selection_returns_top_n() -> None:
  signals = _load_enriched_signals()
  top_signals = select_diverse_top_signals(signals, top_n=10, max_per_type=4)
  assert len(top_signals) == 10
  assert {"patent", "paper", "web"}.issubset({signal.type for signal in top_signals})


def test_digest_markdown_contains_top3_and_note() -> None:
  signals = _load_enriched_signals()
  watch_profile = load_demo_watch_profile()
  digest = build_weekly_digest_markdown(signals, watch_profile)
  assert "## This Week's Top 3 Reads" in digest
  assert "1. **" in digest
  assert "## Notes" in digest
  assert "lightweight signal watch preview" in digest


def test_watch_profile_suggestions_are_generated() -> None:
  signals = _load_enriched_signals()
  watch_profile = load_demo_watch_profile()
  suggestions = suggest_watch_profile_updates(signals, watch_profile)
  assert suggestions
  assert any(
    suggestion.startswith(prefix)
    for prefix in (
      "add keyword:",
      "exclude noisy keyword:",
      "add company:",
      "raise priority of source type:",
      "lower priority of irrelevant source:",
      "keep current watch profile:",
    )
    for suggestion in suggestions
  )
