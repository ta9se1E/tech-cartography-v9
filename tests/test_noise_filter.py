"""Tests for noise filter."""

from tech_cartography.curation.noise_filter import compute_noise_score, is_likely_noise


def test_noise_terms_raise_score() -> None:
  record = {
    "title": "Battery electrode with graphene and activated carbon",
    "abstract": "carbon nanotube additive",
  }
  score = compute_noise_score(record)
  assert score >= 0.4


def test_pressure_vessel_not_full_noise() -> None:
  record = {
    "title": "Composite pressure vessel for aerospace prepreg tank",
    "abstract": "battery electrode graphene activated carbon mention",
  }
  assert compute_noise_score(record) < 0.65
  assert not is_likely_noise(record)
