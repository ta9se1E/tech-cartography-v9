"""Tests for the bilingual v9.2 watch profile schema and query previews."""

from __future__ import annotations

from services_v9.demo_data import load_demo_signals_payload, load_demo_watch_profile_payload
from services_v9.digest_export import build_weekly_digest_markdown
from services_v9.persistence import load_snapshot, save_snapshot
from services_v9.query_preview import build_query_preview_bundle
from services_v9.signal_models import Signal, WatchProfile
from services_v9.signal_scoring import enrich_signals
from services_v9.watch_profile_schema import (
  default_bilingual_watch_profile,
  migrate_watch_profile,
  parse_publication_numbers,
  parse_terms,
  split_terms,
)


def test_split_terms_supports_comma() -> None:
  assert split_terms("a,b,c") == ["a", "b", "c"]


def test_split_terms_supports_newline() -> None:
  assert split_terms("a\nb\nc") == ["a", "b", "c"]


def test_split_terms_supports_japanese_comma() -> None:
  assert split_terms("表面欠陥、内部ボイド") == ["表面欠陥", "内部ボイド"]


def test_parse_terms_trims_spaces_and_deduplicates() -> None:
  assert parse_terms("  PAN , PAN\n void ") == ["PAN", "void"]


def test_parse_terms_preserves_japanese_terms() -> None:
  assert parse_terms("表面欠陥, 内部ボイド") == ["表面欠陥", "内部ボイド"]


def test_parse_terms_preserves_english_terms() -> None:
  assert parse_terms("surface defect, internal void") == ["surface defect", "internal void"]


def test_parse_publication_numbers_normalizes_seed_publications() -> None:
  values = parse_publication_numbers("JP-2022-090764-A, jp2023163084a")
  assert values == ["JP2022090764A", "JP2023163084A"]


def test_default_profile_has_v92_schema_and_keyword_groups() -> None:
  profile = default_bilingual_watch_profile()
  assert profile["schema_version"] == "v9.2"
  assert "core_en" in profile["keywords"]
  assert "core_ja" in profile["keywords"]


def test_migrate_old_v91_profile() -> None:
  old_profile = {
    "theme": "旧テーマ",
    "include_keywords": ["PAN carbon fiber precursor", "表面欠陥"],
    "exclude_keywords": ["graphene"],
    "target_companies": ["東レ"],
    "source_types": ["patent", "paper"],
    "countries": ["JP"],
    "cadence": "Weekly",
    "priority_rules": ["旧ルール"],
  }
  migrated = migrate_watch_profile(old_profile)
  assert migrated["schema_version"] == "v9.2"
  assert migrated["theme_name"] == "旧テーマ"
  assert migrated["keywords"]["core_en"] == ["PAN carbon fiber precursor"]
  assert migrated["keywords"]["core_ja"] == ["表面欠陥"]


def test_query_preview_bundle_returns_four_types() -> None:
  bundle = build_query_preview_bundle(load_demo_watch_profile_payload())
  assert set(bundle) == {"patent", "paper", "web", "company"}


def test_digest_markdown_contains_watch_theme_and_seed_publications() -> None:
  signals = enrich_signals([Signal.from_dict(item) for item in load_demo_signals_payload()])
  watch_profile = WatchProfile.from_dict(load_demo_watch_profile_payload())
  digest = build_weekly_digest_markdown(signals, watch_profile)
  assert "監視テーマ" in digest
  assert "Seed公報" in digest


def test_snapshot_can_store_new_watch_profile(tmp_path) -> None:
  signals = [Signal.from_dict(item).to_dict() for item in load_demo_signals_payload()]
  profile = load_demo_watch_profile_payload()
  path = save_snapshot(signals, profile, run_note="bilingual", base_dir=tmp_path / "v9_runs")
  loaded = load_snapshot(path)
  assert loaded["watch_profile"]["schema_version"] == "v9.2"
