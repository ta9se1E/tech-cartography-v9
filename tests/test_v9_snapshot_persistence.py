"""Tests for v9 snapshot persistence and snapshot diff helpers."""

from __future__ import annotations

from pathlib import Path

from services_v9.demo_data import load_demo_signals_payload, load_demo_watch_profile_payload
from services_v9.digest_export import build_weekly_digest_markdown, signals_to_csv, signals_to_json
from services_v9.persistence import (
  ensure_v9_run_dirs,
  list_snapshots,
  load_snapshot,
  load_watch_profile,
  save_digest_files,
  save_snapshot,
  save_watch_profile,
)
from services_v9.signal_models import Signal, WatchProfile
from services_v9.signal_scoring import enrich_signals
from services_v9.snapshot_diff import apply_snapshot_status, compare_snapshots


def _sample_previous_current() -> tuple[list[dict], list[dict]]:
  previous = [
    {"id": "sig-1", "title": "A", "type": "patent", "source_url": "u1", "source_name": "s", "published_date": "2026-07-01", "score": 0.60, "previous_score": 0.50, "status": "Stable", "action": "Watch", "why_read": "w", "what_to_check": "c", "next_action": "n", "tags": [], "companies": []},
    {"id": "sig-2", "title": "B", "type": "paper", "source_url": "u2", "source_name": "s", "published_date": "2026-07-01", "score": 0.70, "previous_score": 0.70, "status": "Stable", "action": "Watch", "why_read": "w", "what_to_check": "c", "next_action": "n", "tags": [], "companies": []},
    {"id": "sig-3", "title": "C", "type": "web", "source_url": "u3", "source_name": "s", "published_date": "2026-07-01", "score": 0.72, "previous_score": 0.72, "status": "Stable", "action": "Watch", "why_read": "w", "what_to_check": "c", "next_action": "n", "tags": [], "companies": []},
    {"id": "sig-4", "title": "D", "type": "company", "source_url": "u4", "source_name": "s", "published_date": "2026-07-01", "score": 0.67, "previous_score": 0.67, "status": "Stable", "action": "Watch", "why_read": "w", "what_to_check": "c", "next_action": "n", "tags": [], "companies": []},
  ]
  current = [
    {**previous[0], "score": 0.61},
    {**previous[1], "score": 0.85},
    {**previous[2], "score": 0.54},
    {"id": "sig-5", "title": "E", "type": "paper", "source_url": "u5", "source_name": "s", "published_date": "2026-07-02", "score": 0.80, "previous_score": None, "status": "New", "action": "Read Now", "why_read": "w", "what_to_check": "c", "next_action": "n", "tags": [], "companies": []},
  ]
  return previous, current


def test_ensure_v9_run_dirs_creates_directories(tmp_path: Path) -> None:
  dirs = ensure_v9_run_dirs(tmp_path / "v9_runs")
  assert dirs["root"].exists()
  assert dirs["snapshots"].exists()
  assert dirs["digests"].exists()


def test_save_and_load_watch_profile(tmp_path: Path) -> None:
  profile = load_demo_watch_profile_payload()
  path = save_watch_profile(profile, base_dir=tmp_path / "v9_runs")
  loaded = load_watch_profile(base_dir=tmp_path / "v9_runs")
  assert path.exists()
  assert loaded["theme_name"] == profile["theme_name"]


def test_save_and_load_snapshot(tmp_path: Path) -> None:
  signals = load_demo_signals_payload()
  watch_profile = load_demo_watch_profile_payload()
  path = save_snapshot(signals, watch_profile, run_note="test", base_dir=tmp_path / "v9_runs")
  payload = load_snapshot(path)
  assert path.exists()
  assert payload["run_note"] == "test"
  assert len(payload["signals"]) >= 10
  assert payload["watch_profile"]["schema_version"] == "v9.2"


def test_list_snapshots_returns_saved_files(tmp_path: Path) -> None:
  signals = load_demo_signals_payload()
  watch_profile = load_demo_watch_profile_payload()
  save_snapshot(signals, watch_profile, run_note="first", base_dir=tmp_path / "v9_runs")
  save_snapshot(signals, watch_profile, run_note="second", base_dir=tmp_path / "v9_runs")
  snapshots = list_snapshots(base_dir=tmp_path / "v9_runs")
  assert len(snapshots) == 2


def test_compare_snapshots_detects_new_rising_dropped_and_stable() -> None:
  previous, current = _sample_previous_current()
  diff = compare_snapshots(previous, current)
  assert diff["counts"]["New"] >= 1
  assert diff["counts"]["Rising"] >= 1
  assert diff["counts"]["Dropped"] >= 2
  assert diff["counts"]["Stable"] >= 1


def test_apply_snapshot_status_recalculates_statuses() -> None:
  previous, current = _sample_previous_current()
  updated = apply_snapshot_status(current, previous)
  status_by_id = {item["id"]: item["status"] for item in updated}
  assert status_by_id["sig-1"] == "Stable"
  assert status_by_id["sig-2"] == "Rising"
  assert status_by_id["sig-3"] == "Dropped"
  assert status_by_id["sig-5"] == "New"


def test_save_digest_files(tmp_path: Path) -> None:
  signals = enrich_signals([Signal.from_dict(item) for item in load_demo_signals_payload()])
  watch_profile = WatchProfile.from_dict(load_demo_watch_profile_payload())
  markdown = build_weekly_digest_markdown(signals, watch_profile)
  csv_text = signals_to_csv(signals)
  json_text = signals_to_json(signals, watch_profile)
  saved = save_digest_files(markdown, csv_text, json_text, snapshot_id="2026-07-04_001", base_dir=tmp_path / "v9_runs")
  assert saved["markdown"].exists()
  assert saved["csv"].exists()
  assert saved["json"].exists()
