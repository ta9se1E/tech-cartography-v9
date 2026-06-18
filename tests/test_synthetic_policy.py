"""Tests for synthetic demo signal policy (Phase 23.0)."""

from __future__ import annotations

from tech_cartography.web_signals.schema import WebSignal, utc_now_iso
from tech_cartography.web_signals.synthetic_policy import (
  SYNTHETIC_DEMO_MARKER,
  ensure_synthetic_policy,
)


def _signal(**overrides: object) -> WebSignal:
  defaults = dict(
    signal_id="wsig-syn-1",
    signal_type="market",
    source_title="Title",
    source_url="https://example.invalid/demo",
    source_domain="example.invalid",
    collected_at=utc_now_iso(),
    query="demo",
    raw_snippet="demo snippet",
    confidence="high",
    verification_status="unverified",
    is_synthetic_demo=True,
    caveat="",
  )
  defaults.update(overrides)
  return WebSignal(**defaults)


def test_ensure_synthetic_policy_sets_verification_status() -> None:
  result = ensure_synthetic_policy(_signal())
  assert result.verification_status == "synthetic_demo"
  assert result.confidence in {"low", "weak"}
  assert SYNTHETIC_DEMO_MARKER in result.caveat
  assert result.source_title.startswith("[Synthetic demo signal]")


def test_non_synthetic_does_not_keep_synthetic_marker_in_caveat() -> None:
  result = ensure_synthetic_policy(
    _signal(
      is_synthetic_demo=False,
      caveat=f"{SYNTHETIC_DEMO_MARKER} should be removed",
      verification_status="needs_human_review",
      confidence="medium",
    ),
  )
  assert SYNTHETIC_DEMO_MARKER not in result.caveat


def test_non_synthetic_cannot_be_verified_without_url() -> None:
  result = ensure_synthetic_policy(
    _signal(
      is_synthetic_demo=False,
      source_url="",
      source_domain="",
      verification_status="verified_source",
      confidence="medium",
    ),
  )
  assert result.verification_status == "needs_human_review"
