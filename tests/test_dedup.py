"""Tests for patent record deduplication."""

from tech_cartography.curation.dedup import (
  deduplicate_patent_records,
  merge_search_intents_for_duplicate,
  normalize_publication_number,
)


def test_normalize_publication_number() -> None:
  assert normalize_publication_number("US-2020-000001") == "US2020000001"


def test_deduplicate_merges_search_intents() -> None:
  records = [
    {
      "publication_number": "US-2020-000001",
      "title": "First title",
      "abstract": "A",
      "search_intent": "core_manufacturing",
      "query_plan_id": "core_manufacturing",
      "matched_terms": ["carbon fiber"],
      "source_type": "bigquery_lightweight",
      "evidence_level": "metadata_only",
    },
    {
      "publication_number": "US2020000001",
      "title": "Second title",
      "abstract": "B",
      "search_intent": "application",
      "query_plan_id": "application",
      "matched_terms": ["aerospace"],
      "source_type": "bigquery_lightweight",
      "evidence_level": "metadata_only",
    },
  ]
  deduped = deduplicate_patent_records(records)
  assert len(deduped) == 1
  assert deduped[0]["title"] == "First title"
  assert "core_manufacturing" in deduped[0]["search_intents"]
  assert "application" in deduped[0]["search_intents"]
  assert "carbon fiber" in deduped[0]["matched_terms"]
  assert "aerospace" in deduped[0]["matched_terms"]


def test_merge_search_intents_for_duplicate() -> None:
  merged = merge_search_intents_for_duplicate(
    [
      {"search_intent": "core_manufacturing", "query_plan_id": "core_manufacturing"},
      {"search_intent": "company_watch", "query_plan_id": "company_watch"},
    ],
  )
  assert merged["search_intents"] == ["core_manufacturing", "company_watch"]
