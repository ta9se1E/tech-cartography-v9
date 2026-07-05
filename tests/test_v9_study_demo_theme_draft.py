"""Theme draft review/edit/save-as-new tests for Study Demo Stage C5B-1.1."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from services_v9.study_demo_theme_draft import (
  build_new_saved_theme_from_draft,
  build_theme_draft_from_temporary_search,
  draft_from_editor_payload,
  draft_widget_key,
  find_existing_draft_for_run,
  save_theme_to_storage,
  should_show_old_plan_warning,
  update_theme_draft,
  validate_draft_generation_precondition,
  validate_theme_draft,
)
from services_v9.study_demo_theme_lineage import (
  compute_theme_signature,
  default_saved_theme_fixture,
  promote_temporary_search_to_theme_draft,
)

FIXTURE_PATH = ROOT / "tests/fixtures/study_demo_active_run_connection_samples.json"
RUN_ID = "study_demo_search_20260705_061319_e973e4c2"


def _search_request() -> dict:
  return dict(json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["artifacts"]["search_request.json"])


def _active_context() -> dict:
  return {
    "active_search_run_id": RUN_ID,
    "theme": _search_request()["theme"],
    "run_origin": "temporary_search",
    "active_context_generation": 7,
  }


def _draft(**overrides: object) -> dict:
  draft = build_theme_draft_from_temporary_search(
    _search_request(),
    search_run_id=RUN_ID,
    active_context=_active_context(),
    context_generation=7,
  )
  draft.update(overrides)
  return draft


class TestDraftCreation:
  def test_create_from_temporary_search(self) -> None:
    draft = _draft()
    assert draft["status"] == "draft"
    assert draft["source"] == "promoted_from_temporary_search"
    assert draft["source_search_run_id"] == RUN_ID
    assert draft["source_run_origin"] == "temporary_search"
    assert draft.get("draft_id")

  def test_saved_theme_unchanged_on_create(self) -> None:
    saved = default_saved_theme_fixture()
    sig_before = compute_theme_signature(saved)
    _draft()
    assert compute_theme_signature(saved) == sig_before

  def test_no_duplicate_for_same_run(self) -> None:
    draft = _draft()
    assert find_existing_draft_for_run(draft, RUN_ID)

  def test_different_run_not_matched(self) -> None:
    draft = _draft()
    assert not find_existing_draft_for_run(draft, "other_run")


class TestDraftContent:
  def test_inherits_active_run_theme_text(self) -> None:
    draft = _draft()
    req = _search_request()
    assert req["theme"][:40] in draft["description"]
    assert draft["name"]

  def test_keywords_from_request(self) -> None:
    draft = _draft()
    keywords = dict(draft.get("keywords", {}) or {})
    core_ja = " ".join(keywords.get("core_ja", []))
    assert "炭素繊維" in core_ja

  def test_exclude_from_request(self) -> None:
    draft = _draft()
    keywords = dict(draft.get("keywords", {}) or {})
    assert "textile" in keywords.get("exclude_ja", []) or "textile" in keywords.get("exclude_en", [])

  def test_no_old_theme_seed_mixing(self) -> None:
    draft = _draft()
    saved = default_saved_theme_fixture()
    for seed in saved.get("seed_publication_numbers", []):
      assert seed not in list(draft.get("seed_publication_numbers", []) or [])

  def test_provider_settings_from_request(self) -> None:
    draft = _draft()
    provider = dict(draft.get("provider_settings", {}) or {})
    assert provider.get("enable_patent") is True


class TestDraftActions:
  def test_keep_updates_signature(self) -> None:
    draft = _draft()
    old_sig = draft["theme_draft_signature"]
    updated = draft_from_editor_payload(
      draft,
      {"name": "更新後テーマ名", "description": draft["description"], "core_ja": "炭素繊維", "core_en": "carbon"},
    )
    assert updated["theme_draft_signature"] != old_sig
    assert updated["dirty"] is True

  def test_save_as_new_new_id(self) -> None:
    draft = _draft()
    saved_old = default_saved_theme_fixture()
    saved = build_new_saved_theme_from_draft(draft, existing_themes=[saved_old])
    assert saved["theme_id"] != saved_old["theme_id"]
    assert saved["theme_version"] == 1
    assert saved["status"] == "saved"
    assert compute_theme_signature(saved_old) == compute_theme_signature(default_saved_theme_fixture())

  def test_save_as_new_provenance(self) -> None:
    draft = _draft()
    saved = build_new_saved_theme_from_draft(draft, existing_themes=[default_saved_theme_fixture()])
    assert saved["created_from_draft_id"] == draft["draft_id"]
    assert saved["source_search_run_id"] == RUN_ID

  def test_same_name_new_id(self) -> None:
    draft = _draft()
    draft["name"] = default_saved_theme_fixture()["name"]
    saved = build_new_saved_theme_from_draft(draft, existing_themes=[default_saved_theme_fixture()])
    assert saved["same_name_warning"] is True
    assert saved["theme_id"] != default_saved_theme_fixture()["theme_id"]

  def test_session_only_storage(self) -> None:
    saved = build_new_saved_theme_from_draft(_draft(), existing_themes=[default_saved_theme_fixture()])
    result = save_theme_to_storage(saved, persist_to_cloud=False)
    assert result["status"] == "session_only"


class TestSearchPlanWarning:
  def test_old_plan_warning_when_draft_exists(self) -> None:
    draft = _draft()
    saved = default_saved_theme_fixture()
    plan = {"source_theme_id": saved["theme_id"], "source_theme_version": saved["theme_version"]}
    assert should_show_old_plan_warning(draft, plan, saved)


class TestConcurrency:
  def test_source_run_mismatch(self) -> None:
    draft = _draft()
    errors = validate_draft_generation_precondition(draft, {"active_search_run_id": "other"})
    assert "source_run_mismatch" in errors

  def test_stale_signature_rejected(self) -> None:
    draft = _draft()
    with pytest.raises(ValueError):
      update_theme_draft(draft, {"name": "x"}, expected_signature="stale")


class TestUIWiring:
  def test_d_section_present(self) -> None:
    text = (ROOT / "ui_v9/study_demo_theme_draft_ui.py").read_text(encoding="utf-8")
    assert "D. 作成した未保存テーマ案" in text

  def test_tabs_use_draft_section(self) -> None:
    text = (ROOT / "ui_v9/tabs.py").read_text(encoding="utf-8")
    assert "render_theme_draft_section" in text

  def test_draft_widget_keys_include_draft_id(self) -> None:
    key = draft_widget_key("draft_abc123", "name")
    assert "draft_abc123" in key
    assert key != "ui_theme_name_input"

  def test_signal_watch_handles_draft_events(self) -> None:
    text = (ROOT / "ui_v9/signal_watch_app.py").read_text(encoding="utf-8")
    assert "_handle_study_demo_theme_events" in text
    assert "_clear_theme_draft_if_run_changed" in text


class TestDiscard:
  def test_discard_is_noop_on_cloud(self) -> None:
    from services_v9.study_demo_theme_draft import discard_theme_draft

    discard_theme_draft(_draft())
    saved = default_saved_theme_fixture()
    assert compute_theme_signature(saved) == compute_theme_signature(default_saved_theme_fixture())


class TestStorageFailure:
  def test_storage_failure_raises(self) -> None:
    class _BrokenClient:
      def bucket(self, _name: str) -> object:
        raise OSError("storage down")

    saved = build_new_saved_theme_from_draft(_draft(), existing_themes=[default_saved_theme_fixture()])
    with pytest.raises(OSError):
      save_theme_to_storage(saved, storage_client=_BrokenClient(), persist_to_cloud=True)
