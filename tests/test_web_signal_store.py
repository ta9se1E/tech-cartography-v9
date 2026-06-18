"""Tests for Web Signal store (Phase 23.0)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.web_signals.schema import WebSignal, WebSignalBatch, utc_now_iso
from tech_cartography.web_signals.store import (
  SUMMARY_CAUTION,
  load_web_signal_batch,
  render_web_signal_summary_md,
  save_web_signal_batch,
  web_signals_to_dataframe,
)


def _sample_batch() -> WebSignalBatch:
  signal = WebSignal(
    signal_id="wsig-store-1",
    signal_type="national_project",
    source_title="[Synthetic demo signal] Example",
    source_url="https://example.invalid/demo",
    source_domain="example.invalid",
    collected_at=utc_now_iso(),
    query="PAN carbon fiber",
    raw_snippet="demo",
    confidence="low",
    verification_status="synthetic_demo",
    is_synthetic_demo=True,
    caveat="Synthetic demo signal. This is not real-world evidence.",
    next_verification_action="Verify with JST/NEDO source",
  )
  return WebSignalBatch(
    batch_id="wsbatch-test",
    topic="PAN carbon fiber",
    created_at=utc_now_iso(),
    query_set=["PAN carbon fiber"],
    signals=[signal],
    source_policy_version="phase23.0",
    notes="test batch",
  )


def test_json_csv_save_and_load(tmp_path: Path) -> None:
  batch = _sample_batch()
  paths = save_web_signal_batch(batch, tmp_path / "batch1")
  assert paths["web_signals_json"].exists()
  assert paths["web_signals_csv"].exists()
  assert paths["web_signal_summary_md"].exists()

  loaded = load_web_signal_batch(paths["web_signals_json"])
  assert loaded is not None
  assert loaded.batch_id == "wsbatch-test"
  assert len(loaded.signals) == 1
  assert loaded.signals[0].signal_type == "national_project"


def test_web_signals_to_dataframe() -> None:
  batch = _sample_batch()
  df = web_signals_to_dataframe(batch.signals)
  assert len(df) == 1
  assert df.iloc[0]["signal_type"] == "national_project"
  assert bool(df.iloc[0]["is_synthetic_demo"]) is True


def test_summary_md_contains_caveats() -> None:
  md = render_web_signal_summary_md(_sample_batch())
  assert "signal candidates" in md
  assert "Synthetic demo signal" in md
  assert "FTO, infringement, or validity analysis" in md
  assert SUMMARY_CAUTION in md
