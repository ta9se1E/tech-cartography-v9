"""Tests for web signal loader."""

from pathlib import Path

from tech_cartography.ingestion.web_signal_loader import (
  load_web_signals_from_csv,
  normalize_web_signal_record,
  save_demo_web_signal_template,
)


def test_normalize_terms_from_csv_string() -> None:
  record = normalize_web_signal_record(
    {
      "company": "TORAY",
      "source_title": "Test signal",
      "technology_terms": "carbon fiber, prepreg, aerospace",
      "signal_type": "partnership",
    },
  )
  assert record["technology_terms"] == ["carbon fiber", "prepreg", "aerospace"]
  assert record["normalized_company"] == "TORAY"


def test_missing_url_warning() -> None:
  record = normalize_web_signal_record(
    {"company": "TEIJIN", "source_title": "No URL signal"},
  )
  assert any("source_url" in warning.lower() for warning in record["warnings"])


def test_load_template_csv() -> None:
  path = Path("case_studies/carbon_fiber/web_signals/carbon_fiber_web_signals_template.csv")
  signals = load_web_signals_from_csv(str(path))
  assert len(signals) >= 2
  assert signals[0]["normalized_company"]


def test_save_demo_template(tmp_path) -> None:
  path = save_demo_web_signal_template(str(tmp_path))
  assert Path(path).exists()
