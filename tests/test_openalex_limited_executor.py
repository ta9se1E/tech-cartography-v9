"""Tests for limited OpenAlex execution (Phase 19)."""

from __future__ import annotations

from unittest.mock import patch

from tech_cartography.evidence.openalex_limited_executor import (
  OpenAlexExecutionConfig,
  deduplicate_paper_records,
  execute_openalex_limited,
  render_openalex_limited_summary,
  select_openalex_queries_for_execution,
)


def _sample_candidates() -> list[dict]:
  return [
    {
      "query_id": "q1",
      "query": "PAN carbon fiber carbonization oxidation",
      "query_type": "material_process",
      "confidence": "medium",
      "publication_number": "US-12565719-B2",
    },
    {
      "query_id": "q2",
      "query": "carbon fiber tensile strength elastic modulus",
      "query_type": "property_condition",
      "confidence": "medium",
      "publication_number": "US-12565719-B2",
    },
    {
      "query_id": "q3",
      "query": "carbon fiber microstructure crystallite",
      "query_type": "structure_property",
      "confidence": "medium",
      "publication_number": "US-12565719-B2",
    },
    {
      "query_id": "q4",
      "query": "carbon fiber surface sizing interface",
      "query_type": "surface_interface",
      "confidence": "low",
      "publication_number": "US-12565719-B2",
    },
    {
      "query_id": "q5",
      "query": "carbon fiber",
      "query_type": "broad_background",
      "confidence": "low",
      "publication_number": "US-12565719-B2",
    },
    {
      "query_id": "q6",
      "query": "PAN precursor stabilization process",
      "query_type": "material_process",
      "confidence": "low",
      "publication_number": "US-12565719-B2",
    },
  ]


def test_medium_confidence_queries_prioritized() -> None:
  selected, _skipped = select_openalex_queries_for_execution(_sample_candidates(), max_queries=3)
  confidences = [row.get("confidence") for row in selected]
  assert confidences.count("medium") >= 2
  types = {row.get("query_type") for row in selected}
  assert "material_process" in types
  assert "property_condition" in types


def test_broad_background_not_dominant() -> None:
  selected, _ = select_openalex_queries_for_execution(_sample_candidates(), max_queries=3)
  broad_count = sum(1 for row in selected if row.get("query_type") == "broad_background")
  assert broad_count <= 1
  assert len(selected) <= 3


def test_max_queries_not_exceeded() -> None:
  selected, skipped = select_openalex_queries_for_execution(_sample_candidates(), max_queries=3)
  assert len(selected) <= 3
  assert len(skipped) >= len(_sample_candidates()) - 3


def test_execute_false_does_not_call_search() -> None:
  cfg = OpenAlexExecutionConfig(execute_openalex=False, max_queries=3)
  with patch("tech_cartography.evidence.openalex_limited_executor.search_openalex") as mocked:
    result = execute_openalex_limited(_sample_candidates(), cfg)
  mocked.assert_not_called()
  assert result["mode"] == "plan_only"
  assert result["executed_queries_count"] == 0
  assert len(result["selected_queries"]) <= 3


def test_execute_true_calls_mock_retriever() -> None:
  cfg = OpenAlexExecutionConfig(
    execute_openalex=True,
    max_queries=2,
    max_results_per_query=5,
    allow_low_confidence_queries=True,
  )

  def _fake_search(query: str, _cfg) -> dict:
    return {
      "status": "ok",
      "works": [
        {
          "id": f"https://openalex.org/W-{query[:3]}",
          "display_name": f"Paper for {query}",
          "abstract_inverted_index": {"carbon": [0], "fiber": [1]},
        },
      ],
    }

  with patch("tech_cartography.evidence.openalex_limited_executor.search_openalex", side_effect=_fake_search):
    result = execute_openalex_limited(_sample_candidates(), cfg)
  assert result["mode"] == "execute"
  assert result["executed_queries_count"] >= 1
  assert result["total_paper_records"] >= 1


def test_api_error_still_produces_summary() -> None:
  cfg = OpenAlexExecutionConfig(execute_openalex=True, max_queries=1, allow_low_confidence_queries=True)

  with patch(
    "tech_cartography.evidence.openalex_limited_executor.search_openalex",
    return_value={"status": "error", "error": "timeout"},
  ):
    result = execute_openalex_limited(_sample_candidates(), cfg)
  md = render_openalex_limited_summary(result)
  assert "API errors" in md
  assert result["executed_queries_count"] == 1
  assert result["total_paper_records"] == 0


def test_deduplicate_paper_records() -> None:
  records = [
    {"doi": "10.1/test", "title": "A"},
    {"doi": "10.1/test", "title": "A duplicate"},
    {"openalex_id": "W2", "title": "B"},
  ]
  deduped = deduplicate_paper_records(records)
  assert len(deduped) == 2


def test_summary_has_no_monetary_amounts() -> None:
  result = execute_openalex_limited(
    _sample_candidates(),
    OpenAlexExecutionConfig(execute_openalex=False),
  )
  md = render_openalex_limited_summary(result)
  assert "$" not in md
  assert "usd" not in md.lower()
