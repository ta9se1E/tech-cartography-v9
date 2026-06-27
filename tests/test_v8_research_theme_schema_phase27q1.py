"""Phase27Q.1 research theme schema tests."""

from __future__ import annotations

from tech_cartography.runtime.v8_research_theme_schema import (
  ResearchThemeProfile,
  normalize_publication_number,
  resolve_search_mode,
)
from tech_cartography.services.v8_research_theme_defaults import (
  CASE_01_PAN_PRECURSOR_DEFECT_THEME,
  FIRST_TEST_SEED_PUBLICATIONS,
  load_research_theme_profile,
)
from tech_cartography.services.v8_sources_table import project_root_from_here


def test_default_theme_loads() -> None:
  profile = CASE_01_PAN_PRECURSOR_DEFECT_THEME
  assert "PAN" in profile.theme_name
  assert len(profile.core_keywords) >= 5
  assert len(profile.seed_publication_numbers) >= 3


def test_seed_normalization() -> None:
  assert normalize_publication_number("JP-2022090764-A") == "JP2022090764A"
  assert normalize_publication_number("jp2022090764a") == "JP2022090764A"


def test_empty_seed_falls_back_to_keyword_only() -> None:
  profile = ResearchThemeProfile(case_id="test", search_mode="seed_and_keywords", seed_publication_numbers=[])
  assert profile.search_mode == "keyword_only"


def test_case_01_profile_file_loads() -> None:
  root = project_root_from_here()
  profile = load_research_theme_profile("case_01_pan_graphitization", root)
  assert profile.case_id == "case_01_pan_graphitization"
  assert profile.theme_name


def test_first_test_seeds_present() -> None:
  profile = CASE_01_PAN_PRECURSOR_DEFECT_THEME
  normalized = {normalize_publication_number(s) for s in profile.seed_publication_numbers}
  for seed in FIRST_TEST_SEED_PUBLICATIONS:
    assert normalize_publication_number(seed) in normalized


def test_resolve_search_mode_with_seeds() -> None:
  assert resolve_search_mode("seed_and_keywords", ["JP2022090764A"]) == "seed_and_keywords"
