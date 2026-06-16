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
  assert scored["score_breakdown"]["core_technology_score"] >= 0
  assert "fulltext_route_score" in scored["score_breakdown"]
  assert "strategic_score" in scored


def test_fulltext_route_and_strategic_score_separated() -> None:
  cn = score_patent_record(
    _classified(
      publication_number="CN-2024-000001",
      country="CN",
      assignee="ZHONGFU SHENYING CARBON FIBER CO LTD",
      title="PAN precursor carbonization large-tow",
      abstract="polyacrylonitrile dry-jet wet-spinning carbonization",
    ),
  )
  us = score_patent_record(_classified(publication_number="US-2024-000010", country="US"))
  assert cn["strategic_score"] == cn["total_score"]
  assert us["fulltext_route_score"] > cn["fulltext_route_score"]
  assert cn["strategic_score"] >= us["strategic_score"] * 0.8


def test_zhongfu_assignee_boosted() -> None:
  zhongfu = score_patent_record(
    _classified(
      publication_number="CN-2024-000001",
      country="CN",
      assignee="ZHONGFU SHENYING CARBON FIBER CO LTD",
    ),
  )
  generic = score_patent_record(
    _classified(
      publication_number="CN-2024-000002",
      country="CN",
      assignee="Generic Composite Co",
      title="Generic composite article",
      abstract="general composite",
      matched_terms=["composite"],
    ),
  )
  assert zhongfu["score_breakdown"]["assignee_importance_score"] > generic["score_breakdown"]["assignee_importance_score"]


def test_pan_carbonization_tensile_strength_high_score() -> None:
  good = score_patent_record(
    _classified(
      title="PAN precursor fiber carbonization with tensile strength and modulus control",
      abstract="polyacrylonitrile stabilization oxidation carbonization furnace residence time",
      matched_terms=["PAN", "carbonization", "tensile strength", "modulus"],
    ),
  )
  weak = score_patent_record(
    _classified(
      title="Generic composite article",
      abstract="general composite",
      search_intents=["other_related"],
      matched_terms=["composite"],
    ),
  )
  assert good["total_score"] > weak["total_score"]


def test_surface_treatment_interface_adhesion_high_score() -> None:
  scored = score_patent_record(
    _classified(
      title="Surface treatment and sizing for interface adhesion",
      abstract="epoxy sizing resin impregnation interfacial shear strength",
      search_intents=["surface_interface"],
      matched_terms=["surface treatment", "sizing", "interface adhesion"],
    ),
  )
  assert scored["score_breakdown"]["core_technology_score"] >= 0.2
  assert scored["total_score"] >= 0.43


def test_unknown_assignee_penalized() -> None:
  known = score_patent_record(_classified(assignee="Toray Industries"))
  unknown = score_patent_record(_classified(assignee="Unknown"))
  assert known["total_score"] > unknown["total_score"]


def test_display_apparatus_low_score() -> None:
  noisy = score_patent_record(
    _classified(
      title="Display apparatus and method of manufacturing the display apparatus",
      abstract="semiconductor thin film electronic device",
      search_intents=["other_related"],
      matched_terms=["display"],
    ),
  )
  core = score_patent_record(_classified())
  assert noisy["total_score"] < core["total_score"]


def test_application_only_lower_than_core_manufacturing() -> None:
  app_record = _classified(
    title="Aerospace pressure vessel composite tank",
    abstract="pressure vessel aerospace application",
    search_intents=["application_pressure_aerospace"],
    matched_terms=["pressure vessel", "aerospace"],
  )
  app_only = score_patent_record(app_record)
  core = score_patent_record(
    _classified(
      title="PAN precursor carbonization process",
      abstract="polyacrylonitrile precursor fiber carbonization furnace",
      search_intents=["core_manufacturing"],
      matched_terms=["PAN", "carbonization", "precursor fiber"],
    ),
  )
  assert core["total_score"] > app_only["total_score"]


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
      title="PAN carbon fiber carbonization prepreg surface treatment",
      search_intents=["core_manufacturing", "bundle_prepreg"],
    ),
  ]
  ranked = rank_patent_records(records)
  candidates = select_fulltext_candidates(ranked, top_n=5)
  assert len(candidates) <= 5
  assert candidates[0]["country"] == "US"


def test_fulltext_candidates_limited_to_five() -> None:
  records = [
    _classified(
      publication_number=f"US-2024-{index:06d}",
      assignee=f"Company {index % 4}",
      title=f"PAN precursor carbonization surface treatment {index}",
    )
    for index in range(12)
  ]
  ranked = rank_patent_records(records)
  candidates = select_fulltext_candidates(ranked, top_n=5)
  assert len(candidates) <= 5
