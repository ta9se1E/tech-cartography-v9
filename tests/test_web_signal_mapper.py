"""Tests for web signal mapper."""

from tech_cartography.evidence.web_signal_mapper import (
  build_web_signal_links,
  classify_web_signal_relation,
  compute_signal_patent_relevance,
  map_web_signals_to_patents,
)


def _patent(**overrides) -> dict:
  base = {
    "publication_number": "US2024000001A1",
    "title": "Carbon fiber prepreg aerospace composite",
    "abstract": "PAN precursor carbonization and prepreg for aerospace applications",
    "assignee": "TORAY INDUSTRIES",
    "primary_cluster_id": "bundle_prepreg",
    "primary_cluster_name": "Bundle / Prepreg",
    "matched_terms": ["prepreg", "carbon fiber"],
  }
  base.update(overrides)
  return base


def _signal(**overrides) -> dict:
  base = {
    "signal_id": "ws1",
    "company": "TORAY",
    "normalized_company": "TORAY",
    "source_title": "Prepreg capacity expansion",
    "source_url": "https://www.toray.com/news/press-release",
    "source_name": "Press release",
    "signal_type": "production_expansion",
    "technology_terms": ["carbon fiber", "prepreg", "aerospace"],
    "signal_date": "2025-01-01",
    "business_signal": "Expansion candidate",
    "display_url": "https://www.toray.com/news/press-release",
  }
  base.update(overrides)
  return base


def test_business_signal_candidate() -> None:
  relevance = compute_signal_patent_relevance(_signal(), _patent())
  from tech_cartography.evidence.web_signal_quality import evaluate_web_signal_quality

  relation = classify_web_signal_relation(relevance, evaluate_web_signal_quality(_signal()))
  assert relation == "business_signal_candidate"


def test_weak_signal_company_only() -> None:
  signal = _signal(technology_terms=["unrelated topic"], signal_type="hiring")
  relevance = compute_signal_patent_relevance(signal, _patent())
  from tech_cartography.evidence.web_signal_quality import evaluate_web_signal_quality

  relation = classify_web_signal_relation(relevance, evaluate_web_signal_quality(signal))
  assert relation == "weak_signal"


def test_background_signal_terms_only() -> None:
  signal = _signal(
    company="UNKNOWN CORP",
    normalized_company="UNKNOWN CORP",
    signal_type="market_report",
    technology_terms=["carbon fiber", "aerospace"],
  )
  relevance = compute_signal_patent_relevance(signal, _patent(assignee="OTHER COMPANY"))
  from tech_cartography.evidence.web_signal_quality import evaluate_web_signal_quality

  relation = classify_web_signal_relation(relevance, evaluate_web_signal_quality(signal))
  assert relation == "technology_background_signal"


def test_unrelated_signal() -> None:
  signal = _signal(
    company="UNKNOWN CORP",
    normalized_company="UNKNOWN CORP",
    technology_terms=["blockchain"],
    signal_type="unknown",
    source_url="",
    source_name="",
  )
  links = build_web_signal_links([signal], [_patent(assignee="OTHER COMPANY")])
  assert links == []


def test_map_web_signals_to_patents() -> None:
  result = map_web_signals_to_patents([_signal()], [_patent()])
  assert result["signals_loaded"] == 1
  assert result["links"]
  assert result["by_company"]
