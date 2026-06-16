"""Tests for patent ranker."""

from tech_cartography.curation.patent_ranker import (
  rank_patent_records,
  score_patent_record,
  select_fulltext_candidates,
  select_top_patents,
)
from tech_cartography.curation.technology_classifier import classify_patent_record


def _classified(**kwargs) -> dict:
  record = {
    "publication_number": kwargs.pop("publication_number", "US-2024-000001"),
    "title": kwargs.pop("title", "PAN carbon fiber carbonization"),
    "abstract": kwargs.pop("abstract", "High modulus composite"),
    "assignee": kwargs.pop("assignee", "Toray Industries"),
    "country": kwargs.pop("country", "US"),
    "publication_date": kwargs.pop("publication_date", "20240101"),
    "claims_source": "not_fetched",
    "search_intents": kwargs.pop("search_intents", ["core_manufacturing"]),
    "matched_terms": kwargs.pop("matched_terms", ["carbon fiber", "PAN"]),
  }
  record.update(kwargs)
  classified = classify_patent_record(record)
  classified["noise_score"] = 0.0
  classified["noise_signals"] = []
  return classified


def test_score_breakdown_present() -> None:
  scored = score_patent_record(_classified())
  assert "total_score" in scored
  assert "score_breakdown" in scored
  assert scored["score_breakdown"]["theme_relevance_score"] >= 0


def test_top20_sorted_by_rank() -> None:
  records = [
    _classified(publication_number=f"US-2024-{index:06d}", title=f"Patent {index}")
    for index in range(25)
  ]
  ranked = rank_patent_records(records)
  top20 = select_top_patents(ranked, top_n=20)
  assert len(top20) == 20
  assert top20[0]["rank"] == 1
  assert top20[-1]["rank"] == 20
  scores = [float(item["total_score"]) for item in top20]
  assert scores == sorted(scores, reverse=True)


def test_us_patent_preferred_for_fulltext_candidates() -> None:
  records = [
    _classified(
      publication_number="JP-2020-000001",
      country="JP",
      assignee="Teijin Ltd",
      title="PAN carbon fiber carbonization",
    ),
    _classified(
      publication_number="US-2024-000010",
      country="US",
      assignee="Toray Industries",
      title="PAN carbon fiber carbonization prepreg",
      search_intents=["core_manufacturing", "bundle_prepreg"],
    ),
  ]
  ranked = rank_patent_records(records)
  candidates = select_fulltext_candidates(ranked, top_n=5)
  assert len(candidates) <= 5
  assert any(item["country"] == "US" for item in candidates)


def test_fulltext_candidates_limited_to_five() -> None:
  records = [
    _classified(publication_number=f"US-2024-{index:06d}", assignee=f"Company {index % 4}")
    for index in range(12)
  ]
  ranked = rank_patent_records(records)
  candidates = select_fulltext_candidates(ranked, top_n=5)
  assert len(candidates) <= 5
