"""Tests for full text cache."""

from tech_cartography.retrieval.fulltext_cache import (
  cache_status,
  load_fulltext_from_cache,
  save_fulltext_to_cache,
)


def test_cache_roundtrip(tmp_path) -> None:
  record = {
    "publication_number": "US2024000001A1",
    "claims": "Claim 1 text",
    "source_route": "us_bigquery_fulltext_candidate",
    "evidence_coverage": {"has_claims": True},
  }
  path = save_fulltext_to_cache(record, str(tmp_path))
  assert path
  assert cache_status("US2024000001A1", str(tmp_path)) == "cache_hit"
  loaded = load_fulltext_from_cache("US2024000001A1", str(tmp_path))
  assert loaded is not None
  assert loaded["claims"] == "Claim 1 text"
