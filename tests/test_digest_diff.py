"""Tests for digest diff (Phase 24.0)."""

from __future__ import annotations

from pathlib import Path

import pandas as pd

from tech_cartography.reports.project_export import save_records_csv
from tech_cartography.delivery.digest_diff import (
  WeeklyDigestSnapshot,
  build_digest_snapshot,
  compare_digest_snapshots,
  load_latest_snapshot,
  render_digest_diff_markdown,
  save_digest_snapshot,
)


def _write_snapshot_fixture(root: Path, pub: str = "US-12565719-B2") -> None:
  watch_dir = root / "outputs" / "strategic_watch_briefs" / pub
  watch_dir.mkdir(parents=True, exist_ok=True)
  save_records_csv(
    [{"watch_id": "watch-1", "watch_theme": "CFRP signal"}],
    watch_dir / "strategic_watch_items.csv",
  )
  review_dir = root / "outputs" / "web_signals" / "tavily_pan_carbon_fiber" / "review_pack"
  review_dir.mkdir(parents=True, exist_ok=True)
  save_records_csv(
    [{"signal_id": "wsig-1", "source_title": "NEDO project"}],
    review_dir / "high_priority_web_signals.csv",
  )
  link_dir = root / "outputs" / "web_signal_links" / pub
  link_dir.mkdir(parents=True, exist_ok=True)
  save_records_csv(
    [{"link_id": "wlink-1", "web_signal_title": "NEDO"}],
    link_dir / "high_priority_web_signal_links.csv",
  )
  oa_dir = root / "outputs" / "openalex_limited_execution"
  oa_dir.mkdir(parents=True, exist_ok=True)
  save_records_csv(
    [{"paper_id": "paper-1", "title": "Carbon fiber paper"}],
    oa_dir / "selected_evidence_papers.csv",
  )


def test_build_snapshot(tmp_path: Path) -> None:
  _write_snapshot_fixture(tmp_path)
  snap = build_digest_snapshot(tmp_path, "US-12565719-B2")
  assert snap.watch_item_ids == ["watch-1"]
  assert snap.web_signal_ids == ["wsig-1"]
  assert snap.link_ids == ["wlink-1"]
  assert snap.paper_ids == ["paper-1"]


def test_initial_digest_no_previous() -> None:
  current = WeeklyDigestSnapshot(
    snapshot_id="snap-1",
    created_at="2026-06-19T00:00:00+00:00",
    publication_number="US-1",
    watch_item_ids=["watch-1"],
    web_signal_ids=["wsig-1"],
  )
  diff = compare_digest_snapshots(None, current)
  assert diff.is_initial
  assert "watch-1" in diff.added_watch_items
  assert "Initial Snapshot" in diff.diff_markdown or "初回Snapshot" in diff.diff_markdown


def test_detect_added_web_signals() -> None:
  previous = WeeklyDigestSnapshot(
    snapshot_id="snap-old",
    created_at="2026-06-18T00:00:00+00:00",
    publication_number="US-1",
    web_signal_ids=["wsig-1"],
  )
  current = WeeklyDigestSnapshot(
    snapshot_id="snap-new",
    created_at="2026-06-19T00:00:00+00:00",
    publication_number="US-1",
    web_signal_ids=["wsig-1", "wsig-2"],
    watch_item_ids=["watch-new"],
  )
  diff = compare_digest_snapshots(previous, current)
  assert "wsig-2" in diff.added_web_signals
  assert "watch-new" in diff.added_watch_items


def test_save_and_load_snapshot(tmp_path: Path) -> None:
  snap = WeeklyDigestSnapshot(
    snapshot_id="snap-test",
    created_at="2026-06-19T00:00:00+00:00",
    publication_number="US-1",
    watch_item_ids=["w1"],
  )
  out = tmp_path / "outputs" / "delivery"
  save_digest_snapshot(snap, out)
  loaded = load_latest_snapshot(out)
  assert loaded is not None
  assert loaded.watch_item_ids == ["w1"]


def test_render_diff_markdown() -> None:
  diff = compare_digest_snapshots(
    None,
    WeeklyDigestSnapshot(
      snapshot_id="s",
      created_at="t",
      publication_number="US-1",
      watch_item_ids=["w1"],
    ),
  )
  md = render_digest_diff_markdown(diff, "US-1", initial=True)
  assert "Initial Snapshot" in md or "初回Snapshot" in md
