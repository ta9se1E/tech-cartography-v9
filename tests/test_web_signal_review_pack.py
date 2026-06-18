"""Tests for Web Signal Review Pack (Phase 23.2)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tech_cartography.web_signals.review_pack import (
  build_web_signal_review_pack,
  deduplicate_signals,
  extract_evidence_sentences,
  render_review_pack_summary_md,
  save_web_signal_review_pack,
  score_review_priority,
)
from tech_cartography.web_signals.schema import WebSignal, WebSignalBatch, utc_now_iso
from tech_cartography.web_signals.synthetic_policy import SYNTHETIC_DEMO_MARKER


def _signal(**overrides: object) -> WebSignal:
  defaults = dict(
    signal_id="wsig-test-1",
    signal_type="company",
    source_title="Carbon fiber production expansion",
    source_url="https://example.co.jp/news/carbon-fiber",
    source_domain="example.co.jp",
    collected_at=utc_now_iso(),
    query="PAN carbon fiber",
    raw_snippet="PAN carbon fiber carbonization capacity expansion announced.",
    confidence="medium",
    verification_status="needs_human_review",
    source_quality="medium_high",
    source_category="company_official",
  )
  defaults.update(overrides)
  return WebSignal(**defaults)


def test_extract_evidence_sentences_english() -> None:
  text = "We develop PAN carbon fiber. Unrelated sentence. Carbonization process improved."
  sentences = extract_evidence_sentences(text, ["carbon fiber", "carbonization"], max_sentences=3)
  assert len(sentences) >= 1
  assert any("carbon" in sentence.lower() for sentence in sentences)


def test_extract_evidence_sentences_japanese() -> None:
  text = "本件は炭素繊維の設備投資に関するお知らせです。無関係な文。"
  sentences = extract_evidence_sentences(text, ["炭素繊維", "設備投資"], max_sentences=3)
  assert sentences
  assert "炭素繊維" in sentences[0]


def test_extract_evidence_sentences_empty_text() -> None:
  assert extract_evidence_sentences("", ["PAN"]) == []
  assert extract_evidence_sentences("   ", ["PAN"]) == []


def test_review_priority_high_for_high_quality() -> None:
  high = score_review_priority(
    _signal(signal_type="national_project", source_quality="high", source_category="public_funding"),
  )
  low = score_review_priority(
    _signal(source_quality="low", source_category="blog", signal_type="other", raw_snippet="x"),
  )
  assert high > low


def test_ir_disclosure_candidates_bucket() -> None:
  batch = WebSignalBatch(
    batch_id="b1",
    topic="topic",
    created_at=utc_now_iso(),
    query_set=[],
    signals=[
      _signal(
        signal_id="ir-1",
        signal_type="ir_disclosure",
        source_title="Earnings presentation",
        disclosure_type="earnings_presentation",
        source_url="https://corp.example.co.jp/ir/earnings",
      ),
    ],
  )
  pack = build_web_signal_review_pack(batch)
  assert len(pack.ir_disclosure_candidates) == 1


def test_money_national_project_candidates_bucket() -> None:
  batch = WebSignalBatch(
    batch_id="b2",
    topic="topic",
    created_at=utc_now_iso(),
    query_set=[],
    signals=[
      _signal(signal_id="m1", signal_type="national_project", source_quality="high"),
      _signal(signal_id="g1", signal_type="grant", source_url="https://www.nedo.go.jp/grant/1"),
    ],
  )
  pack = build_web_signal_review_pack(batch)
  assert len(pack.money_national_project_candidates) == 2


def test_company_local_news_candidates_bucket() -> None:
  batch = WebSignalBatch(
    batch_id="b3",
    topic="topic",
    created_at=utc_now_iso(),
    query_set=[],
    signals=[
      _signal(signal_id="c1", signal_type="company"),
      _signal(signal_id="l1", signal_type="local_news", source_url="https://local.news.co.jp/1"),
    ],
  )
  pack = build_web_signal_review_pack(batch)
  assert len(pack.company_local_news_candidates) == 2


def test_missing_source_url_goes_to_rejected() -> None:
  batch = WebSignalBatch(
    batch_id="b4",
    topic="topic",
    created_at=utc_now_iso(),
    query_set=[],
    signals=[_signal(signal_id="bad-1", source_url="", raw_snippet="", source_title="")],
  )
  pack = build_web_signal_review_pack(batch, save_rejected=True)
  assert pack.items == []
  assert pack.rejected_items
  assert pack.rejected_items[0].rejection_reason == "missing_source_url"


def test_deduplicate_same_url() -> None:
  signals = [
    _signal(signal_id="a", source_url="https://example.com/same"),
    _signal(signal_id="b", source_url="https://example.com/same", source_quality="high"),
  ]
  deduped, removed = deduplicate_signals(signals)
  assert len(deduped) == 1
  assert removed == 1
  assert deduped[0].signal_id == "b"


def test_empty_batch_review_pack() -> None:
  batch = WebSignalBatch(
    batch_id="empty",
    topic="topic",
    created_at=utc_now_iso(),
    query_set=[],
    signals=[],
  )
  pack = build_web_signal_review_pack(batch)
  assert pack.total_signals == 0
  assert pack.items == []
  summary = render_review_pack_summary_md(pack)
  assert "signal candidates" in summary
  assert "FTO" in summary


def test_summary_contains_caution_text() -> None:
  pack = build_web_signal_review_pack(
    WebSignalBatch(batch_id="b", topic="t", created_at=utc_now_iso(), query_set=[], signals=[]),
  )
  summary = render_review_pack_summary_md(pack)
  assert "Synthetic demo signal must be clearly labeled" in summary
  assert "Tavily results are retrieved web candidates" in summary


def test_synthetic_demo_not_rejected_for_invalid_domain(tmp_path: Path) -> None:
  signal = _signal(
    signal_id="syn-1",
    is_synthetic_demo=True,
    verification_status="synthetic_demo",
    source_url="https://example.invalid/synthetic",
    caveat=f"{SYNTHETIC_DEMO_MARKER}. Demo only.",
    confidence="low",
  )
  pack = build_web_signal_review_pack(
    WebSignalBatch(batch_id="syn", topic="t", created_at=utc_now_iso(), query_set=[], signals=[signal]),
    save_rejected=True,
  )
  assert any(item.signal_id == "syn-1" for item in pack.items)
  assert not any(item.signal_id == "syn-1" for item in pack.rejected_items)


def test_save_review_pack_outputs(tmp_path: Path) -> None:
  pack = build_web_signal_review_pack(
    WebSignalBatch(
      batch_id="save",
      topic="t",
      created_at=utc_now_iso(),
      query_set=[],
      signals=[_signal()],
    ),
  )
  paths = save_web_signal_review_pack(pack, tmp_path)
  expected = [
    "web_signal_review_pack.json",
    "web_signal_review_items.csv",
    "high_priority_web_signals.csv",
    "ir_disclosure_candidates.csv",
    "money_national_project_candidates.csv",
    "company_local_news_candidates.csv",
    "rejected_or_low_quality_sources.csv",
    "web_signal_review_summary.md",
  ]
  for name in expected:
    assert (tmp_path / "review_pack" / name).exists(), name
  assert paths["web_signal_review_summary_md"].exists()
