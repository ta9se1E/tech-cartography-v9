"""Tests for strategic watch selector."""

from tech_cartography.curation.patent_ranker import rank_patent_records, score_patent_record
from tech_cartography.curation.strategic_watch_selector import (
  assign_manual_route_reason,
  score_strategic_watch_candidate,
  select_strategic_watch_candidates,
)
from tech_cartography.curation.technology_classifier import classify_patent_record
from tech_cartography.curation.top_candidate_selector import select_top_fulltext_candidates


def _classified(**kwargs) -> dict:
  record = {
    "publication_number": kwargs.pop("publication_number", "CN-2024-000001"),
    "title": kwargs.pop("title", "Large-tow polyacrylonitrile-based carbon fiber carbonization"),
    "abstract": kwargs.pop(
      "abstract",
      "PAN precursor dry-jet wet-spinning pre-oxidation carbonization tensile strength modulus",
    ),
    "assignee": kwargs.pop("assignee", "ZHONGFU SHENYING CARBON FIBER CO LTD"),
    "country": kwargs.pop("country", "CN"),
    "publication_date": "20240101",
    "claims_source": "not_fetched",
    "search_intents": kwargs.pop("search_intents", ["core_manufacturing"]),
    "matched_terms": kwargs.pop("matched_terms", ["PAN", "carbonization", "carbon fiber"]),
  }
  record.update(kwargs)
  return classify_patent_record(record)


def test_zhongfu_cn_patent_in_strategic_watch() -> None:
  records = [
    _classified(),
    _classified(
      publication_number="US-2024-000099",
      country="US",
      assignee="Unknown Labs",
      title="Display apparatus semiconductor thin film",
      abstract="display device electronic device",
      search_intents=["other_related"],
      matched_terms=["display"],
    ),
  ]
  ranked = rank_patent_records(records)
  watch = select_strategic_watch_candidates(ranked, top_n=5)
  pubs = [item["publication_number"] for item in watch]
  assert "CN-2024-000001" in pubs
  assert "US-2024-000099" not in pubs


def test_cn_not_penalized_for_country_in_watch_score() -> None:
  cn = score_strategic_watch_candidate(rank_patent_records([_classified()])[0])
  us_core = score_strategic_watch_candidate(
    rank_patent_records(
      [
        _classified(
          publication_number="US-2024-000010",
          country="US",
          assignee="Toray Industries",
          title="PAN precursor carbonization",
        ),
      ],
    )[0],
  )
  assert cn["strategic_watch_score"] >= 0.5
  assert us_core["strategic_watch_score"] >= cn["strategic_watch_score"] * 0.8


def test_cn_core_beats_us_noisy_in_watch() -> None:
  records = [
    _classified(),
    _classified(
      publication_number="US-2024-000099",
      country="US",
      assignee="Unknown",
      title="Display apparatus semiconductor",
      abstract="display device",
      search_intents=["other_related"],
      matched_terms=["display"],
    ),
  ]
  ranked = rank_patent_records(records)
  watch = select_strategic_watch_candidates(ranked, top_n=2)
  assert watch[0]["publication_number"] == "CN-2024-000001"


def test_manual_route_reason_present_for_cn() -> None:
  reason = assign_manual_route_reason(_classified())
  assert "CN" in reason
  assert "PDF" in reason or "手動" in reason


def test_watch_reason_japanese_present() -> None:
  ranked = rank_patent_records([_classified()])
  watch = select_strategic_watch_candidates(ranked, top_n=1)
  assert watch[0]["watch_reason_japanese"]
  assert watch[0]["recommended_next_action"]


def test_top5_us_while_strategic_watch_keeps_cn() -> None:
  records = [
    _classified(),
    _classified(
      publication_number="US-2024-000010",
      country="US",
      assignee="Toray Industries",
      title="PAN precursor carbonization surface treatment sizing tensile strength",
      abstract="polyacrylonitrile precursor fiber carbonization furnace",
    ),
  ]
  ranked = rank_patent_records(records)
  top5 = select_top_fulltext_candidates(ranked, top_n=5)
  watch = select_strategic_watch_candidates(ranked, top_n=5)
  assert all(item["country"] == "US" for item in top5)
  assert any(item["country"] == "CN" for item in watch)


def test_fulltext_and_strategic_scores_separated_in_ranker() -> None:
  cn_scored = score_patent_record(_classified())
  us_scored = score_patent_record(
    _classified(
      publication_number="US-2024-000010",
      country="US",
      assignee="Toray Industries",
    ),
  )
  assert cn_scored["strategic_score"] >= us_scored["strategic_score"] * 0.85
  assert us_scored["fulltext_route_score"] > cn_scored["fulltext_route_score"]
