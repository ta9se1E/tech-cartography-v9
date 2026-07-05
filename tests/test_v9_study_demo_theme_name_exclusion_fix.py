"""Localized theme name and explicit exclusion provenance tests for Stage C5B-1.4.1."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from services_v9.study_demo_theme_draft import build_theme_draft_from_temporary_search
from services_v9.study_demo_theme_draft_mapping import (
  PROVENANCE_RANK,
  _pick_stronger_term,
  _sanitize_japanese_theme_name,
  apply_mapping_to_draft_payload,
  merge_terms_with_provenance,
  suggest_concise_theme_name,
)
from services_v9.study_demo_theme_lineage import default_saved_theme_fixture

FIXTURE_PATH = ROOT / "tests/fixtures/study_demo_active_run_connection_samples.json"
RUN_ID = "study_demo_search_20260705_061319_e973e4c2"
EXPECTED_NAME = "PAN系炭素繊維用サイジング剤の組成・付与・乾燥条件"
EXPLICIT_EXCLUDES = ["textile", "paper sizing", "starch sizing", "activated carbon"]


def _search_request() -> dict:
  return dict(json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["artifacts"]["search_request.json"])


def _draft() -> dict:
  saved = default_saved_theme_fixture()
  return build_theme_draft_from_temporary_search(
    _search_request(),
    search_run_id=RUN_ID,
    context_generation=1,
    old_theme_keywords=dict(saved.get("keywords", {}) or {}),
  )


class TestThemeNameFix:
  def test_no_dry_corruption(self) -> None:
    assert _sanitize_japanese_theme_name("PAN系のDry燥条件") == "PAN系の乾燥条件"
    assert "Dry" not in suggest_concise_theme_name(_search_request()["theme"], _search_request())

  def test_fixture_expected_name_exact(self) -> None:
    draft = _draft()
    assert draft.get("suggested_theme_name") == EXPECTED_NAME

  def test_description_unchanged(self) -> None:
    draft = _draft()
    assert draft.get("description") == _search_request()["theme"]

  def test_english_theme_name_normalization_allowed(self) -> None:
    name = suggest_concise_theme_name("Carbon fiber sizing agent study", {"theme": "Carbon fiber sizing agent study"})
    assert "Carbon" in name


class TestExplicitExclusions:
  @pytest.mark.parametrize("term", EXPLICIT_EXCLUDES)
  def test_exclude_en(self, term: str) -> None:
    draft = _draft()
    keywords = dict(draft.get("keywords", {}) or {})
    assert term in keywords.get("exclude_en", [])
    assert term not in keywords.get("exclude_ja", [])

  @pytest.mark.parametrize("term", ["paper sizing", "starch sizing", "activated carbon"])
  def test_explicit_provenance(self, term: str) -> None:
    draft = _draft()
    record = next(
      (
        item
        for item in list(draft.get("mapping_terms", []) or [])
        if str(item.get("value", "")).lower() == term
      ),
      None,
    )
    assert record is not None, term
    assert record.get("provenance") == "explicit_request_field"
    assert record.get("accepted_for_theme") is True
    assert record.get("requires_user_review") is False
    assert record.get("confidence") == "high"

  def test_not_in_candidates(self) -> None:
    draft = _draft()
    candidate_values = {str(item.get("value", "")).lower() for item in list(draft.get("term_candidates", []) or [])}
    for term in ["paper sizing", "starch sizing", "activated carbon"]:
      assert term not in candidate_values

  def test_alias_dictionary_does_not_override_explicit(self) -> None:
    explicit = {
      "value": "paper sizing",
      "normalized_value": "paper sizing",
      "language": "en",
      "semantic_bucket": "exclude",
      "provenance": "explicit_request_field",
      "source_field": "exclude_keywords",
      "mapping_method": "direct_field_mapping",
      "confidence": "high",
      "requires_user_review": False,
      "accepted_for_theme": True,
    }
    alias = {
      "value": "paper sizing",
      "normalized_value": "paper sizing",
      "language": "en",
      "semantic_bucket": "exclude",
      "provenance": "canonical_alias_suggestion",
      "requires_user_review": True,
      "accepted_for_theme": False,
    }
    merged, candidates = merge_terms_with_provenance([explicit], [alias])
    assert len(merged) == 1
    assert merged[0]["provenance"] == "explicit_request_field"
    assert not candidates

  def test_provenance_priority_order(self) -> None:
    assert PROVENANCE_RANK["explicit_request_field"] > PROVENANCE_RANK["canonical_alias_suggestion"]
    winner = _pick_stronger_term(
      {"provenance": "canonical_alias_suggestion", "accepted_for_theme": False, "requires_user_review": True},
      {"provenance": "explicit_request_field", "accepted_for_theme": True, "requires_user_review": False, "source_field": "exclude_keywords"},
    )
    assert winner["provenance"] == "explicit_request_field"


class TestRegression:
  def test_material_and_use_buckets(self) -> None:
    draft = _draft()
    keywords = dict(draft.get("keywords", {}) or {})
    for term in ["組成", "付与量", "乾燥条件"]:
      assert term in keywords.get("material_process_ja", [])
    for term in ["集束性", "開繊性", "毛羽", "耐擦過性", "樹脂含浸性", "界面接着性", "引張強度", "引張弾性率"]:
      assert term in keywords.get("use_ja", [])

  def test_mapping_report_counts(self) -> None:
    mapping = apply_mapping_to_draft_payload(_search_request())
    report = dict(mapping.get("mapping_report", {}) or {})
    assert report.get("explicit_exclusion_count", 0) >= 3
    assert report.get("explicit_exclusion_candidate_count", 0) == 0

  def test_ui_explicit_exclude_labels(self) -> None:
    text = (ROOT / "ui_v9/study_demo_theme_draft_ui.py").read_text(encoding="utf-8")
    assert "確定済み / 一時検索で明示" in text
