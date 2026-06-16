"""Tests for OpenAlex cache."""

from tech_cartography.retrieval.openalex_cache import (
  get_openalex_cache_key,
  load_openalex_cache,
  openalex_cache_status,
  save_openalex_cache,
)


def test_cache_roundtrip(tmp_path) -> None:
  cache_dir = str(tmp_path)
  query = "carbon fiber carbonization"
  assert openalex_cache_status(query, cache_dir) == "cache_miss"
  save_openalex_cache(
    query,
    {"works": [{"id": "https://openalex.org/W1", "title": "Test"}]},
    cache_dir,
    max_results=10,
  )
  assert openalex_cache_status(query, cache_dir) == "cache_hit"
  cached = load_openalex_cache(query, cache_dir, max_results=10)
  assert cached is not None
  assert len(cached["works"]) == 1


def test_cache_key_normalization() -> None:
  key_a = get_openalex_cache_key("Carbon  Fiber", 10)
  key_b = get_openalex_cache_key("carbon fiber", 10)
  assert key_a == key_b
