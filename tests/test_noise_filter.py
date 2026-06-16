"""Tests for noise filter."""

from tech_cartography.curation.noise_filter import (
  compute_noise_score,
  detect_noise_categories,
  is_likely_noise,
)


def test_display_apparatus_is_noise() -> None:
  record = {"title": "Display apparatus and method of manufacturing the display apparatus", "abstract": ""}
  assert compute_noise_score(record) >= 0.45
  assert "display_or_electronics_noise" in detect_noise_categories(record)


def test_nanoparticle_sensor_is_noise() -> None:
  record = {"title": "Nanoparticle sensor having a nanofibrous membrane scaffold", "abstract": ""}
  assert compute_noise_score(record) >= 0.45
  assert "sensor_membrane_noise" in detect_noise_categories(record)


def test_3d_printing_carbon_graphite_is_noise() -> None:
  record = {
    "title": "Process for producing moulded articles from carbon or graphite by 3D printing",
    "abstract": "",
  }
  assert compute_noise_score(record) >= 0.45
  categories = detect_noise_categories(record)
  assert "carbon_or_graphite_not_fiber" in categories


def test_battery_graphene_cnt_activated_carbon_noise() -> None:
  record = {
    "title": "Battery electrode with graphene and carbon nanotube CNT activated carbon",
    "abstract": "lithium graphite electrode",
  }
  score = compute_noise_score(record)
  assert score >= 0.55
  assert is_likely_noise(record)


def test_pan_carbonization_not_noise() -> None:
  record = {
    "title": "PAN precursor fiber carbonization process",
    "abstract": "polyacrylonitrile stabilization and carbonization for carbon fiber",
  }
  assert compute_noise_score(record) < 0.45
  assert not is_likely_noise(record)


def test_recycling_low_priority_not_full_exclusion() -> None:
  record = {"title": "Recycling method for composite resin waste", "abstract": "composite recycling"}
  score = compute_noise_score(record)
  assert score >= 0.1
  assert score < 0.65
  assert "recycling_only_low_priority" in detect_noise_categories(record)


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
