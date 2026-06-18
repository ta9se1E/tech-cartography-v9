"""Tests for Web Signal source quality rules (Phase 23.0)."""

from __future__ import annotations

from tech_cartography.web_signals.source_quality import classify_source_quality


def test_jst_nedo_meti_grants_high() -> None:
  for url in (
    "https://www.jst.go.jp/",
    "https://www.nedo.go.jp/",
    "https://www.meti.go.jp/",
    "https://grants.jst.go.jp/",
  ):
    result = classify_source_quality(url)
    assert result["source_quality"] == "high"
    assert result["source_domain"]


def test_kaken_high() -> None:
  result = classify_source_quality("https://kaken.nii.ac.jp/grant/KAKENHI-PROJECT-123/")
  assert result["source_quality"] == "high"


def test_unknown_domain_unknown_quality() -> None:
  result = classify_source_quality("https://totally-unknown-example-12345.example/")
  assert result["source_quality"] == "unknown"
  assert result["source_category"] == "unknown"


def test_missing_url_unknown() -> None:
  result = classify_source_quality("")
  assert result["source_quality"] == "unknown"
