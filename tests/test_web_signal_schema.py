"""Tests for Web Signal schema and validation (Phase 23.0)."""

from __future__ import annotations

import pytest

from tech_cartography.web_signals.schema import (
  WebSignal,
  apply_validation_rules,
  build_web_signal,
  normalize_signal_type,
  utc_now_iso,
  validate_web_signal,
)
from tech_cartography.web_signals.synthetic_policy import ensure_synthetic_policy


def _base_signal(**overrides: object) -> WebSignal:
  defaults = dict(
    signal_id="wsig-test-1",
    signal_type="company",
    source_title="Example title",
    source_url="https://example.co.jp/news/1",
    source_domain="example.co.jp",
    collected_at=utc_now_iso(),
    query="PAN carbon fiber",
    raw_snippet="snippet",
    confidence="medium",
    verification_status="needs_human_review",
    is_synthetic_demo=False,
    caveat="Web signals are signal candidates.",
    next_verification_action="Review source page",
  )
  defaults.update(overrides)
  return WebSignal(**defaults)


def test_allowed_signal_type_validation() -> None:
  signal = _base_signal(signal_type="local_news")
  assert signal.signal_type == "local_news"
  assert not validate_web_signal(apply_validation_rules(signal))


def test_invalid_signal_type_raises_on_build() -> None:
  with pytest.raises(ValueError, match="invalid signal_type"):
    build_web_signal(
      signal_type="not_a_real_type",
      signal_id="x",
      source_title="t",
      source_url="https://example.com",
      source_domain="example.com",
      collected_at=utc_now_iso(),
      query="q",
      raw_snippet="s",
    )


def test_invalid_signal_type_normalizes_on_direct_init() -> None:
  assert normalize_signal_type("not_a_real_type") == "other"


def test_synthetic_demo_requires_verification_status() -> None:
  signal = apply_validation_rules(
    _base_signal(
      is_synthetic_demo=True,
      verification_status="unverified",
      confidence="high",
      caveat="placeholder",
    ),
  )
  assert signal.verification_status == "synthetic_demo"
  assert signal.confidence in {"low", "weak"}
  assert "Synthetic demo signal" in signal.caveat


def test_synthetic_signal_caveat_contains_marker() -> None:
  signal = ensure_synthetic_policy(
    _base_signal(
      is_synthetic_demo=True,
      verification_status="synthetic_demo",
      confidence="low",
      caveat="",
    ),
  )
  assert "Synthetic demo signal" in signal.caveat


def test_human_signal_not_high_without_verified_source() -> None:
  signal = apply_validation_rules(
    _base_signal(
      signal_type="human",
      related_person="Example Person",
      verification_status="needs_human_review",
      confidence="high",
    ),
  )
  assert signal.confidence != "high"


def test_money_signal_not_high_without_source_url() -> None:
  signal = apply_validation_rules(
    _base_signal(
      signal_type="money",
      source_url="",
      source_domain="",
      verification_status="unverified",
      confidence="high",
    ),
  )
  assert signal.confidence != "high"


def test_non_synthetic_without_url_not_high() -> None:
  signal = apply_validation_rules(
    _base_signal(source_url="", source_domain="", confidence="high"),
  )
  assert signal.confidence != "high"
