"""Tests for Japanese UI labels in the v9 signal watch app."""

from __future__ import annotations

from services_v9.demo_data import load_demo_signals, load_demo_watch_profile
from services_v9.digest_export import build_weekly_digest_markdown
from services_v9.signal_scoring import enrich_signals
from ui_v9.labels import action_label_ja, status_label_ja, type_label_ja


def test_type_labels_are_translated_to_japanese() -> None:
  assert type_label_ja("patent") == "特許"
  assert type_label_ja("paper") == "論文"
  assert type_label_ja("web") == "Web情報"
  assert type_label_ja("company") == "企業情報"


def test_status_labels_are_translated_to_japanese() -> None:
  assert status_label_ja("New") == "新規"
  assert status_label_ja("Rising") == "注目度上昇"
  assert status_label_ja("Dropped") == "注目度低下"
  assert status_label_ja("Stable") == "継続監視"


def test_action_labels_are_translated_to_japanese() -> None:
  assert action_label_ja("Read Now") == "今すぐ読む"
  assert action_label_ja("Watch") == "監視する"
  assert action_label_ja("Ignore") == "今回は見送る"


def test_digest_markdown_contains_japanese_sections() -> None:
  signals = enrich_signals(load_demo_signals())
  watch_profile = load_demo_watch_profile()
  digest = build_weekly_digest_markdown(signals, watch_profile)
  assert "今週まず読むべき3件" in digest
  assert "注意事項" in digest
