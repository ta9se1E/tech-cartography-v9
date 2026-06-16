"""Tests for OpenAlex retriever."""

from __future__ import annotations

import json
from unittest.mock import patch

from tech_cartography.domain.paper_record import (
  PaperRecord,
  reconstruct_abstract_from_inverted_index,
)
from tech_cartography.retrieval.openalex_cache import save_openalex_cache
from tech_cartography.retrieval.openalex_retriever import (
  OpenAlexRetrievalConfig,
  build_openalex_search_url,
  search_openalex,
  search_paper_queries,
)


def _sample_work() -> dict:
  return {
    "id": "https://openalex.org/W123",
    "display_name": "Carbon fiber surface treatment",
    "publication_year": 2020,
    "doi": "https://doi.org/10.1000/test",
    "abstract_inverted_index": {"carbon": [0], "fiber": [1], "surface": [2], "treatment": [3]},
    "authorships": [{"author": {"display_name": "Alice"}}],
    "primary_location": {
      "landing_page_url": "https://example.org/paper",
      "source": {"display_name": "Carbon Journal", "type": "journal"},
    },
    "cited_by_count": 12,
    "open_access": {"is_oa": True},
    "concepts": [{"display_name": "Materials science"}],
    "keywords": [{"display_name": "carbon fiber"}],
  }


def test_config_defaults_execute_false() -> None:
  config = OpenAlexRetrievalConfig()
  assert config.execute is False


def test_execute_false_does_not_call_urlopen() -> None:
  config = OpenAlexRetrievalConfig(execute=False)
  with patch("tech_cartography.retrieval.openalex_retriever.urllib.request.urlopen") as mocked:
    result = search_openalex("carbon fiber", config)
    mocked.assert_not_called()
  assert result["status"] == "plan_only"


def test_cache_hit_does_not_call_urlopen(tmp_path) -> None:
  cache_dir = str(tmp_path)
  query = "carbon fiber"
  save_openalex_cache(query, {"works": [_sample_work()]}, cache_dir, max_results=10)
  config = OpenAlexRetrievalConfig(execute=True, use_cache=True, cache_dir=cache_dir)
  with patch("tech_cartography.retrieval.openalex_retriever.urllib.request.urlopen") as mocked:
    result = search_openalex(query, config)
    mocked.assert_not_called()
  assert result["status"] == "cache_hit"
  assert len(result["works"]) == 1


def test_paper_record_from_openalex_work() -> None:
  record = PaperRecord.from_openalex_work(_sample_work())
  assert record.title == "Carbon fiber surface treatment"
  assert record.doi == "10.1000/test"
  assert record.display_url == "https://example.org/paper"
  assert record.source_name == "Carbon Journal"


def test_abstract_inverted_index_reconstruction() -> None:
  abstract = reconstruct_abstract_from_inverted_index(
    {"carbon": [0], "fiber": [1], "surface": [2], "treatment": [3]},
  )
  assert abstract == "carbon fiber surface treatment"


def test_display_url_priority() -> None:
  work = {
    "id": "https://openalex.org/W999",
    "display_name": "No landing page",
    "doi": "https://doi.org/10.2000/abc",
    "primary_location": {},
  }
  record = PaperRecord.from_openalex_work(work)
  assert record.display_url == "https://doi.org/10.2000/abc"


def test_search_paper_queries_plan_only() -> None:
  rows = [
    {
      "query_id": "q1",
      "query": "carbon fiber",
      "priority": "high",
      "publication_number": "US1",
      "element_id": "e1",
      "element_type": "material",
    },
  ]
  config = OpenAlexRetrievalConfig(execute=False)
  result = search_paper_queries(rows, config)
  assert result["mode"] == "plan_only"
  assert result["executed_queries"] == 0
  assert len(result["query_plan"]) == 1


def test_search_paper_queries_execute_with_mock(tmp_path) -> None:
  rows = [
    {
      "query_id": "q1",
      "query": "carbon fiber",
      "priority": "high",
      "publication_number": "US1",
      "element_id": "e1",
      "element_type": "material",
    },
  ]
  config = OpenAlexRetrievalConfig(
    execute=True,
    use_cache=False,
    cache_dir=str(tmp_path),
    sleep_sec=0,
  )
  payload = json.dumps({"results": [_sample_work()], "meta": {}}).encode("utf-8")

  class _FakeResponse:
    def __enter__(self):
      return self

    def __exit__(self, *args):  # noqa: ANN002
      return False

    def read(self) -> bytes:
      return payload

  with patch("tech_cartography.retrieval.openalex_retriever.urllib.request.urlopen", return_value=_FakeResponse()):
    result = search_paper_queries(rows, config)
  assert result["mode"] == "execute"
  assert result["total_papers_raw"] >= 1
  assert build_openalex_search_url("carbon fiber").startswith("https://api.openalex.org/works")
