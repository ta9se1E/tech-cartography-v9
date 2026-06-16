"""Tests for web signal quality."""

from tech_cartography.evidence.web_signal_quality import evaluate_web_signal_quality


def test_press_release_medium_or_high() -> None:
  signal = {
    "signal_id": "ws1",
    "company": "TORAY",
    "source_title": "Capacity expansion press release",
    "source_url": "https://www.toray.com/news/press-release-example",
    "source_name": "Press release",
    "signal_type": "production_expansion",
    "signal_date": "2025-01-01",
    "business_signal": "Expansion candidate",
  }
  result = evaluate_web_signal_quality(signal)
  assert result["quality_level"] in {"high", "medium"}


def test_missing_url_warning() -> None:
  signal = {
    "signal_id": "ws2",
    "company": "TEIJIN",
    "source_title": "No URL",
    "warnings": ["Missing source_url"],
  }
  result = evaluate_web_signal_quality(signal)
  assert result["quality_level"] in {"low", "unknown"}
  assert result["recommended_use"] == "do_not_cite"
