"""Tests for top fulltext candidate selector."""

from tech_cartography.curation.patent_ranker import rank_patent_records
from tech_cartography.curation.technology_classifier import classify_patent_record
from tech_cartography.curation.top_candidate_selector import select_top_fulltext_candidates


def _record(**kwargs) -> dict:
  base = {
    "publication_number": kwargs.pop("publication_number", "US-2024-000001"),
    "title": kwargs.pop("title", "PAN precursor fiber carbonization"),
    "abstract": kwargs.pop("abstract", "polyacrylonitrile stabilization oxidation carbonization tensile strength"),
    "assignee": kwargs.pop("assignee", "Toray Industries"),
    "country": kwargs.pop("country", "US"),
    "publication_date": "20240101",
    "claims_source": "not_fetched",
    "search_intents": kwargs.pop("search_intents", ["core_manufacturing"]),
    "matched_terms": kwargs.pop("matched_terms", ["PAN", "carbonization", "carbon fiber"]),
  }
  base.update(kwargs)
  return classify_patent_record(base)


def test_us_core_manufacturing_preferred_for_top5() -> None:
  records = [
    _record(
      publication_number="US-2024-000010",
      country="US",
      title="PAN precursor carbonization surface treatment sizing",
      assignee="Toray Industries",
    ),
    _record(
      publication_number="CN-2024-000011",
      country="CN",
      title="PAN precursor carbonization",
      assignee="Zhongfu Shenying",
    ),
    _record(
      publication_number="US-2024-000012",
      country="US",
      title="Precursor fiber bundle carbonization tensile strength",
      assignee="Hexcel",
    ),
    _record(
      publication_number="US-2024-000099",
      country="US",
      title="Display apparatus semiconductor thin film",
      abstract="display device electronic device",
      search_intents=["other_related"],
      matched_terms=["display"],
    ),
  ]
  ranked = rank_patent_records(records)
  top5 = select_top_fulltext_candidates(ranked, top_n=5)
  assert top5
  assert all(item["country"] == "US" for item in top5)
  assert "why_selected_japanese" in top5[0]
  assert top5[0]["source_route"] == "us_bigquery_fulltext_candidate"
  noisy_numbers = [item["publication_number"] for item in top5]
  assert "US-2024-000099" not in noisy_numbers


def test_cn_ep_jp_manual_route() -> None:
  records = [
    _record(publication_number="JP-2020-000001", country="JP", assignee="Teijin"),
    _record(publication_number="EP-2020-000002", country="EP", assignee="SGL Carbon"),
    _record(publication_number="CN-2020-000003", country="CN", assignee="Zhongfu"),
  ]
  ranked = rank_patent_records(records)
  top5 = select_top_fulltext_candidates(ranked, top_n=3)
  assert top5
  for item in top5:
    assert item["source_route"] == "manual_fulltext_required"
    assert item["manual_route_reason"]


def test_noisy_us_excluded_from_top5() -> None:
  records = [
    _record(
      publication_number="US-2024-000050",
      country="US",
      title="Nanoparticle sensor having a nanofibrous membrane scaffold",
      abstract="nanofibrous membrane sensor",
      search_intents=["other_related"],
      matched_terms=["sensor"],
    ),
    _record(
      publication_number="US-2024-000051",
      country="US",
      title="PAN precursor carbonization with tensile strength control",
      abstract="polyacrylonitrile carbonization furnace",
    ),
  ]
  ranked = rank_patent_records(records)
  top5 = select_top_fulltext_candidates(ranked, top_n=5)
  selected_numbers = [item["publication_number"] for item in top5]
  assert "US-2024-000051" in selected_numbers
  assert "US-2024-000050" not in selected_numbers


def test_why_selected_japanese_present() -> None:
  records = [_record()]
  ranked = rank_patent_records(records)
  top5 = select_top_fulltext_candidates(ranked, top_n=1)
  assert top5[0]["why_selected_japanese"]
  assert "quality_flags" in top5[0]
  assert "noise_reasons" in top5[0]
