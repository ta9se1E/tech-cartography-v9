"""Tests for Strategic Watch Brief UI (Phase 23.5)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from tech_cartography.strategic_watch.store import save_strategic_watch_brief
from tech_cartography.strategic_watch.brief_builder import build_strategic_watch_brief
from tech_cartography.ui.strategic_watch_ui import (
  build_strategic_watch_summary_cards,
  get_strategic_watch_caution_text,
  get_strategic_watch_status_counts,
  load_strategic_watch_artifacts,
  normalize_display_value,
  prepare_strategic_watch_display_df,
)

from tests.test_strategic_watch_brief import _write_fixture


def test_missing_files_loader_does_not_crash(tmp_path: Path) -> None:
  artifacts = load_strategic_watch_artifacts(tmp_path)
  assert artifacts.status == "missing"
  assert isinstance(artifacts.watch_items_df, pd.DataFrame)


def test_loader_reads_fixture(tmp_path: Path) -> None:
  _write_fixture(tmp_path)
  brief = build_strategic_watch_brief("US-12565719-B2", project_root=tmp_path)
  out = tmp_path / "outputs/strategic_watch_briefs/US-12565719-B2"
  save_strategic_watch_brief(brief, out)
  artifacts = load_strategic_watch_artifacts(tmp_path, publication_number="US-12565719-B2")
  assert artifacts.status in {"ready", "partial"}
  assert len(artifacts.watch_items_df) >= 1


def test_status_counts_with_empty_data(tmp_path: Path) -> None:
  artifacts = load_strategic_watch_artifacts(tmp_path)
  counts = get_strategic_watch_status_counts(artifacts)
  assert counts["watch_items"] == 0
  assert counts["high_priority"] == 0


def test_prepare_display_df_nan_to_not_available() -> None:
  df = pd.DataFrame([{"watch_theme": float("nan"), "link_score": 75}])
  out = prepare_strategic_watch_display_df(df, ("watch_theme", "link_score"))
  assert out.iloc[0]["watch_theme"] == "not available"


def test_normalize_display_value() -> None:
  assert normalize_display_value(None) == "not available"
  assert normalize_display_value(float("nan")) == "not available"
  assert normalize_display_value("hello") == "hello"


def test_caution_text_contains_fto_notice() -> None:
  text = get_strategic_watch_caution_text()
  assert "FTO" in text
  assert "final conclusions" in text or "最終結論" in text


def test_partial_missing_still_loads(tmp_path: Path) -> None:
  _write_fixture(tmp_path)
  brief = build_strategic_watch_brief("US-12565719-B2", project_root=tmp_path)
  out = tmp_path / "outputs/strategic_watch_briefs/US-12565719-B2"
  save_strategic_watch_brief(brief, out)
  (out / "strategic_watch_brief.md").unlink()
  artifacts = load_strategic_watch_artifacts(tmp_path, publication_number="US-12565719-B2")
  assert artifacts.status == "partial"
  assert not artifacts.watch_items_df.empty


def test_build_summary_cards_returns_dict_list(tmp_path: Path) -> None:
  _write_fixture(tmp_path)
  brief = build_strategic_watch_brief("US-12565719-B2", project_root=tmp_path)
  out = tmp_path / "outputs/strategic_watch_briefs/US-12565719-B2"
  save_strategic_watch_brief(brief, out)
  artifacts = load_strategic_watch_artifacts(tmp_path, publication_number="US-12565719-B2")
  cards = build_strategic_watch_summary_cards(artifacts)
  assert cards
  assert all(isinstance(card, dict) for card in cards)
  assert all("label" in card and "value" in card for card in cards)
  assert cards[2]["label"] == "High Priority"
  assert "not confirmed fact" in cards[2]["help"]


def test_summary_cards_reflect_priority_counts(tmp_path: Path) -> None:
  _write_fixture(tmp_path)
  brief = build_strategic_watch_brief("US-12565719-B2", project_root=tmp_path)
  out = tmp_path / "outputs/strategic_watch_briefs/US-12565719-B2"
  save_strategic_watch_brief(brief, out)
  artifacts = load_strategic_watch_artifacts(tmp_path, publication_number="US-12565719-B2")
  counts = get_strategic_watch_status_counts(artifacts)
  cards = build_strategic_watch_summary_cards(artifacts)
  card_map = {card["label"]: card["value"] for card in cards}
  assert card_map["Medium Priority"] == str(counts["medium_priority"])
  assert card_map["Low Priority"] == str(counts["low_priority"])


def test_summary_cards_empty_artifacts(tmp_path: Path) -> None:
  artifacts = load_strategic_watch_artifacts(tmp_path)
  cards = build_strategic_watch_summary_cards(artifacts)
  assert all(card["value"] == "0" for card in cards)


def test_summary_cards_nan_safe() -> None:
  from tech_cartography.ui.strategic_watch_ui import StrategicWatchUIArtifacts, _safe_card_count

  assert _safe_card_count(float("nan")) == "0"
  assert _safe_card_count(None) == "0"
  artifacts = StrategicWatchUIArtifacts(
    publication_number="US-1",
    status="partial",
    brief_dir="",
    watch_items_df=pd.DataFrame([{"watch_priority": float("nan"), "watch_type": "evidence_gap"}]),
  )
  cards = build_strategic_watch_summary_cards(artifacts)
  assert cards[0]["value"] == "1"
