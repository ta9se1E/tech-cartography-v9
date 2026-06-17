"""Tests for publication number variants (Phase 18A)."""

from __future__ import annotations

from tech_cartography.retrieval.publication_number_variants import (
  build_google_patents_url_variants,
  build_publication_number_variants,
  infer_country_kind_number,
  normalize_publication_number,
)


def test_us_12565719_b2_variants() -> None:
  variants = build_publication_number_variants("US-12565719-B2")
  required = {
    "US-12565719-B2",
    "US12565719B2",
    "US12565719",
    "US-12565719",
    "US 12565719 B2",
    "US-12565719B2",
  }
  upper_set = {v.upper().replace(" ", "") for v in variants}
  for item in required:
    assert item.upper().replace(" ", "").replace("-", "") in {
      v.replace("-", "") for v in upper_set
    } or item in variants


def test_empty_or_invalid_does_not_crash() -> None:
  assert build_publication_number_variants("") == []
  assert build_publication_number_variants("???") == []
  assert normalize_publication_number("  ") == ""


def test_infer_country_kind_number() -> None:
  info = infer_country_kind_number("US-12565719-B2")
  assert info["country"] == "US"
  assert info["kind"] == "B2"
  assert info["number"] == "12565719"


def test_google_patents_url_variants() -> None:
  urls = build_google_patents_url_variants("US-12565719-B2")
  assert urls
  assert all(u.startswith("https://patents.google.com/patent/") for u in urls)


def test_metadata_a1_only_when_present() -> None:
  with_meta = build_publication_number_variants(
    "US-12565719-B2",
    metadata={"application_publication_number": "US-2023-000001-A1"},
  )
  without = build_publication_number_variants("US-12565719-B2")
  assert len(with_meta) >= len(without)
