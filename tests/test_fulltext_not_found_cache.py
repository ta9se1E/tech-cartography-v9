"""Tests for fulltext not_found cache (Phase 18A)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from tech_cartography.retrieval.fulltext_not_found_cache import (
  build_not_found_cache_key,
  is_known_not_found,
  load_not_found_cache,
  mark_not_found,
)
from tech_cartography.retrieval.bigquery_fulltext_availability_probe import QUERY_STRATEGY
from tech_cartography.retrieval.patent_fulltext_retriever import (
  FullTextRetrievalConfig,
  retrieve_fulltext_for_candidate,
)


def test_mark_and_load_not_found(tmp_path: Path) -> None:
  path = tmp_path / "not_found_cache.json"
  mark_not_found("US-12565719-B2", "claims_only", path=path, probe_status="not_found_in_bigquery", query_strategy=QUERY_STRATEGY)
  cache = load_not_found_cache(path)
  key = build_not_found_cache_key("US-12565719-B2", "claims_only", QUERY_STRATEGY)
  assert key in cache["entries"]


def test_is_known_not_found() -> None:
  key = build_not_found_cache_key("US-12565719-B2", "claims_only", "bigquery_publications_availability")
  assert "US12565719B2" in key


def test_cache_hit_skips_bigquery_execute(tmp_path: Path) -> None:
  cache_path = tmp_path / "not_found_cache.json"
  mark_not_found("US2024000001A1", "claims_only", path=cache_path, query_strategy=QUERY_STRATEGY)
  config = FullTextRetrievalConfig(
    execute=True,
    confirm_fulltext_execute=True,
    use_cache=False,
    enable_availability_probe=False,
    use_not_found_cache=True,
    not_found_cache_path=str(cache_path),
  )
  with patch(
    "tech_cartography.retrieval.patent_fulltext_retriever.execute_fulltext_query",
  ) as execute_mock:
    result = retrieve_fulltext_for_candidate(
      {
        "publication_number": "US2024000001A1",
        "country": "US",
        "title": "Fiber",
      },
      config,
      execute_selected=True,
    )
  execute_mock.assert_not_called()
  assert result["retrieval_status"] == "skipped_known_not_found"
