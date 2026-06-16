"""Tests for technology classifier."""

from tech_cartography.curation.technology_classifier import classify_patent_record


def _record(**kwargs) -> dict:
  base = {
    "publication_number": "US-2024-000001",
    "title": "",
    "abstract": "",
    "assignee": "",
    "search_intents": [],
    "matched_terms": [],
  }
  base.update(kwargs)
  return base


def test_bundle_prepreg_classification() -> None:
  result = classify_patent_record(
    _record(title="Carbon fiber bundle and prepreg laminate", abstract="tow processing"),
  )
  assert result["primary_cluster_id"] == "bundle_prepreg"


def test_core_manufacturing_classification() -> None:
  result = classify_patent_record(
    _record(
      title="PAN precursor carbonization process",
      matched_terms=["PAN", "carbonization"],
    ),
  )
  assert result["primary_cluster_id"] == "core_manufacturing"


def test_surface_interface_classification() -> None:
  result = classify_patent_record(
    _record(
      title="Carbon fiber surface treatment for interface adhesion",
      abstract="sizing agent improves resin impregnation",
    ),
  )
  assert result["primary_cluster_id"] == "surface_interface"


def test_application_pressure_aerospace_classification() -> None:
  result = classify_patent_record(
    _record(
      title="Composite pressure vessel for aerospace tank",
      abstract="automotive spring application",
    ),
  )
  assert result["primary_cluster_id"] == "application_pressure_aerospace"


def test_company_watch_assignee_effect() -> None:
  result = classify_patent_record(
    _record(
      title="Carbon fiber manufacturing",
      assignee="Toray Industries, Inc.",
      search_intents=["company_watch"],
    ),
  )
  assert result["primary_cluster_id"] == "company_watch" or "company_watch" in result["secondary_cluster_ids"]
