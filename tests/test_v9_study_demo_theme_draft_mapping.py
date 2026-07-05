"""Theme draft mapping, review, and UI polish tests for Stage C5B-1.3."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from services_v9.study_demo_theme_draft import (
  build_theme_draft_from_temporary_search,
  can_save_draft_as_new,
  complete_draft_review,
  draft_from_editor_payload,
  summarize_theme_draft_state,
  update_theme_draft,
  validate_theme_draft,
)
from services_v9.study_demo_theme_draft_mapping import (
  apply_mapping_to_draft_payload,
  build_canonical_term_suggestions,
  detect_term_language,
  extract_exact_theme_concepts,
  extract_temporary_search_request_terms,
  suggest_concise_theme_name,
  validate_theme_draft_mapping,
  validate_theme_name,
)
from services_v9.study_demo_theme_lineage import default_saved_theme_fixture, sizing_fixture_theme

FIXTURE_PATH = ROOT / "tests/fixtures/study_demo_active_run_connection_samples.json"
RUN_ID = "study_demo_search_20260705_061319_e973e4c2"


def _search_request() -> dict:
  return dict(json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["artifacts"]["search_request.json"])


def _draft(**overrides: object) -> dict:
  saved = default_saved_theme_fixture()
  draft = build_theme_draft_from_temporary_search(
    _search_request(),
    search_run_id=RUN_ID,
    active_context={"active_search_run_id": RUN_ID, "theme": _search_request()["theme"], "active_context_generation": 7},
    context_generation=7,
    old_theme_keywords=dict(saved.get("keywords", {}) or {}),
  )
  draft.update(overrides)
  return draft


def _reviewed_draft(draft: dict | None = None) -> dict:
  base = dict(draft or _draft())
  return complete_draft_review(base, context_generation=7)


class TestLanguageClassification:
  def test_english_exclusion_to_exclude_en(self) -> None:
    req = {"exclude_keywords": "textile", "theme": "test"}
    mapping = apply_mapping_to_draft_payload(req)
    assert "textile" in mapping["keywords"]["exclude_en"]
    assert "textile" not in mapping["keywords"]["exclude_ja"]

  @pytest.mark.parametrize("term", ["paper sizing", "starch sizing", "activated carbon"])
  def test_exclude_en_language(self, term: str) -> None:
    assert detect_term_language(term) == "en"

  def test_unknown_not_placed_in_ja_en(self) -> None:
    assert detect_term_language("12345") == "unknown"


class TestSemanticMapping:
  @pytest.mark.parametrize(
    ("term", "bucket"),
    [
      ("サイジング剤", "core"),
      ("組成", "material_process"),
      ("付与量", "material_process"),
      ("乾燥条件", "material_process"),
      ("集束性", "use_or_property"),
      ("開繊性", "use_or_property"),
      ("毛羽", "use_or_property"),
      ("耐擦過性", "use_or_property"),
      ("樹脂含浸性", "use_or_property"),
      ("界面接着性", "use_or_property"),
      ("引張強度", "use_or_property"),
      ("引張弾性率", "use_or_property"),
    ],
  )
  def test_theme_text_exact_match_buckets(self, term: str, bucket: str) -> None:
    found = extract_exact_theme_concepts(_search_request()["theme"])
    match = next((item for item in found if item.get("value") == term), None)
    assert match is not None, term
    assert match.get("semantic_bucket") == bucket

  def test_sizing_fixture_mapping(self) -> None:
    draft = _draft()
    keywords = dict(draft.get("keywords", {}) or {})
    assert "組成" in keywords.get("material_process_ja", [])
    assert "集束性" in keywords.get("use_ja", [])
    assert "textile" in keywords.get("exclude_en", [])


class TestThemeName:
  def test_concise_name_from_long_theme(self) -> None:
    name = suggest_concise_theme_name(_search_request()["theme"])
    assert "PAN" in name
    assert len(name) <= 60

  def test_description_preserved_in_draft(self) -> None:
    draft = _draft()
    assert draft["description"] == _search_request()["theme"]


class TestDraftReview:
  def test_not_reviewed_by_default(self) -> None:
    draft = _draft()
    assert draft.get("review_status") == "not_reviewed"
    summary = summarize_theme_draft_state(draft)
    assert summary["workflow"]["draft_reviewed"] is False

  def test_complete_review_sets_signature(self) -> None:
    reviewed = _reviewed_draft()
    assert reviewed.get("review_status") == "reviewed"

  def test_edit_triggers_rereview(self) -> None:
    reviewed = _reviewed_draft()
    edited = update_theme_draft(reviewed, {"name": "更新"})
    assert edited.get("review_status") == "needs_rereview"

  def test_save_blocked_without_review(self) -> None:
    assert not can_save_draft_as_new(_draft())
    assert validate_theme_draft(_draft())


class TestUILabelsAndCleanup:
  def test_no_keyboard_arrow_right_in_ui(self) -> None:
    for path in (ROOT / "ui_v9").rglob("*.py"):
      assert "keyboard_arrow_right" not in path.read_text(encoding="utf-8")

  def test_toast_on_create(self) -> None:
    text = (ROOT / "ui_v9/signal_watch_app.py").read_text(encoding="utf-8")
    assert "study_demo_draft_create_toast" in text
