"""P0 hackathon demo theme/source/metrics consistency tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from services_v9.demo_data import build_operation_status_rows
from services_v9.study_demo_active_loader import build_temporary_search_source_payload
from services_v9.study_demo_live_lineage_loader import resolve_display_search_plan
from services_v9.study_demo_run_metrics import (
  UNKNOWN_METRIC_LABEL,
  build_active_run_operation_rows,
  build_active_run_source_rows,
  build_canonical_run_metrics,
  format_unknown_metric,
  resolve_active_source_label,
  validate_run_metric_consistency,
)
from services_v9.study_demo_saved_theme_editor import (
  apply_editor_selection_metadata,
  editor_dirty_vs_saved,
  editor_values_to_theme_record,
  saved_theme_editor_widget_key,
  theme_to_editor_values,
  validate_theme_update_save_guard,
)
from services_v9.study_demo_theme_lineage import default_saved_theme_fixture, sizing_fixture_theme

FIXTURE_PATH = ROOT / "tests" / "fixtures" / "study_demo_p0_watch_profile_samples.json"


def _load_fixture() -> dict:
  return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _fake_client(artifacts: dict, run_id: str) -> object:
  prefix = f"search_runs/{run_id}/"

  class _Blob:
    def __init__(self, name: str, payload: object):
      self.name = name
      self._payload = payload

    def download_as_bytes(self) -> bytes:
      return json.dumps(self._payload).encode()

  class _Bucket:
    def list_blobs(self, *, prefix: str = ""):
      for key, value in artifacts.items():
        yield _Blob(f"{prefix}{key}", value)

  class _Client:
    def bucket(self, _name: str) -> _Bucket:
      return _Bucket()

  return _Client()


class TestThemeEditorSync:
  def test_active_theme_applied_to_selector_metadata(self) -> None:
    fx = _load_fixture()
    theme = dict(fx["themes"]["new_theme"])
    state = apply_editor_selection_metadata({}, theme)
    assert state["selected_saved_theme_id"] == "theme_6d2dfb753f7e"
    assert state["editor_hydrated_theme_id"] == "theme_6d2dfb753f7e"

  def test_selector_and_editor_theme_match(self) -> None:
    fx = _load_fixture()
    theme = dict(fx["themes"]["new_theme"])
    state = apply_editor_selection_metadata({}, theme)
    editor = editor_values_to_theme_record(state["editor_values"], base_theme=theme)
    assert editor["theme_id"] == state["selected_saved_theme_id"]

  def test_new_theme_editor_has_sizing_content(self) -> None:
    fx = _load_fixture()
    values = theme_to_editor_values(fx["themes"]["new_theme"])
    assert "サイジング" in values["name"]
    assert "組成" in values["material_process_ja"]

  def test_old_theme_not_mixed_into_new_editor(self) -> None:
    fx = _load_fixture()
    new_values = theme_to_editor_values(fx["themes"]["new_theme"])
    old_values = theme_to_editor_values(fx["themes"]["old_theme"])
    assert "欠陥" not in new_values["name"]
    assert "欠陥" in old_values["name"]

  def test_old_theme_selection_yields_old_editor(self) -> None:
    old = dict(_load_fixture()["themes"]["old_theme"])
    state = apply_editor_selection_metadata({}, old)
    assert "欠陥" in state["editor_values"]["name"]

  def test_widget_keys_include_theme_id_and_version(self) -> None:
    key = saved_theme_editor_widget_key("theme_6d2dfb753f7e", 1, "name")
    assert "theme_6d2dfb753f7e" in key and "_v1_" in key

  def test_widget_keys_differ_by_theme(self) -> None:
    a = saved_theme_editor_widget_key("theme_a", 1, "name")
    b = saved_theme_editor_widget_key("theme_b", 1, "name")
    assert a != b

  def test_unsaved_change_detection(self) -> None:
    fx = _load_fixture()
    theme = dict(fx["themes"]["new_theme"])
    values = theme_to_editor_values(theme)
    values["name"] = "changed"
    assert editor_dirty_vs_saved(theme, values)

  def test_save_guard_blocks_selector_editor_mismatch(self) -> None:
    errors = validate_theme_update_save_guard(
      selected_theme_id="theme_6d2dfb753f7e",
      editor_theme_id="theme_default_saved",
    )
    assert "selector_editor_mismatch" in errors

  def test_watch_profile_and_plan_in_theme_state(self) -> None:
    fx = _load_fixture()
    state = apply_editor_selection_metadata({}, fx["themes"]["new_theme"])
    state["watch_profile"] = fx["watch_profile"]
    state["search_plan"] = fx["search_plan"]
    plan = resolve_display_search_plan(active_context=fx["active_context"], theme_state=state)
    assert plan["search_plan_id"] == "plan_wp_theme_6d2dfb753f7e"


class TestInformationSource:
  def test_watch_profile_label_is_saved_standard_run(self) -> None:
    ctx = _load_fixture()["active_context"]
    assert resolve_active_source_label(ctx) == "保存済み標準検索run"

  def test_source_payload_watch_profile_fields(self) -> None:
    fx = _load_fixture()
    source = build_temporary_search_source_payload(
      fx["active_context"],
      storage_client=_fake_client(fx["artifacts"], fx["search_run_id"]),
    )
    assert source["label"] == "保存済み標準検索run"
    assert source["is_watch_profile_run"] is True
    assert source["active_context"]["run_origin"] == "watch_profile"

  def test_provider_success_in_metrics(self) -> None:
    fx = _load_fixture()
    source = build_temporary_search_source_payload(
      fx["active_context"],
      storage_client=_fake_client(fx["artifacts"], fx["search_run_id"]),
    )
    metrics = source["canonical_metrics"]
    assert metrics["provider_success_rate"] == 100.0
    assert metrics["provider_counts"] == {"patent": 5, "paper": 5, "web": 5}

  def test_active_retrieval_sources(self) -> None:
    fx = _load_fixture()
    source = build_temporary_search_source_payload(
      fx["active_context"],
      storage_client=_fake_client(fx["artifacts"], fx["search_run_id"]),
    )
    assert set(source["canonical_metrics"]["active_retrieval_sources"]) == {"patent", "paper", "web"}

  def test_active_run_source_rows_not_demo(self) -> None:
    fx = _load_fixture()
    source = build_temporary_search_source_payload(
      fx["active_context"],
      storage_client=_fake_client(fx["artifacts"], fx["search_run_id"]),
    )
    rows = build_active_run_source_rows(source["canonical_metrics"])
    assert all(row["mode"] == "loaded" for row in rows)
    assert all(row["provider_status"] == "success" for row in rows)

  def test_active_run_operation_rows_not_demo(self) -> None:
    fx = _load_fixture()
    source = build_temporary_search_source_payload(
      fx["active_context"],
      storage_client=_fake_client(fx["artifacts"], fx["search_run_id"]),
    )
    rows = build_active_run_operation_rows(source["canonical_metrics"])
    patent = next(item for item in rows if item["label"] == "patent")
    assert patent["mode"] == "loaded"

  def test_legacy_demo_operation_rows_still_configurable(self) -> None:
    rows = build_operation_status_rows(bigquery_mode="loaded", openalex_mode="loaded", web_search_mode="loaded")
    patent = next(item for item in rows if item["label"] == "patent")
    assert patent["mode"] == "loaded"


class TestCanonicalMetrics:
  def test_integrated_and_ranked_equal_15(self) -> None:
    fx = _load_fixture()
    source = build_temporary_search_source_payload(
      fx["active_context"],
      storage_client=_fake_client(fx["artifacts"], fx["search_run_id"]),
    )
    metrics = source["canonical_metrics"]
    assert metrics["integrated_count"] == 15
    assert metrics["ranked_count"] == 15

  def test_tier_counts(self) -> None:
    fx = _load_fixture()
    source = build_temporary_search_source_payload(
      fx["active_context"],
      storage_client=_fake_client(fx["artifacts"], fx["search_run_id"]),
    )
    tiers = source["canonical_metrics"]["tier_counts"]
    assert tiers == {"A": 3, "B": 2, "C": 3, "D": 7}

  def test_tier_sum_equals_integrated(self) -> None:
    fx = _load_fixture()
    source = build_temporary_search_source_payload(
      fx["active_context"],
      storage_client=_fake_client(fx["artifacts"], fx["search_run_id"]),
    )
    metrics = source["canonical_metrics"]
    assert metrics["tier_sum"] == metrics["integrated_count"]

  def test_unknown_metric_not_zero(self) -> None:
    assert format_unknown_metric(None) == UNKNOWN_METRIC_LABEL
    assert format_unknown_metric(0) == "0"

  def test_derived_metric_source_present(self) -> None:
    fx = _load_fixture()
    metrics = build_canonical_run_metrics(
      context=fx["active_context"],
      resolved={"stored_artifact_counts": {"patent": 5, "paper": 5, "web": 5}},
      provider_status=fx["artifacts"]["provider_status.json"],
    )
    assert "provider_counts" in metrics.get("metric_sources", {})

  def test_no_inconsistency_for_fixture(self) -> None:
    fx = _load_fixture()
    source = build_temporary_search_source_payload(
      fx["active_context"],
      storage_client=_fake_client(fx["artifacts"], fx["search_run_id"]),
    )
    assert not validate_run_metric_consistency(source["canonical_metrics"])

  def test_detect_inconsistency(self) -> None:
    metrics = {
      "integrated_count": 15,
      "ranked_count": 10,
      "tier_sum": 15,
      "provider_counts": {"patent": 5, "paper": 5, "web": 5},
      "provider_success": {
        "patent": {"success": True, "count": 5},
        "paper": {"success": True, "count": 5},
        "web": {"success": True, "count": 5},
      },
    }
    assert "integrated_ranked_mismatch" in validate_run_metric_consistency(metrics)


class TestP0Script:
  def test_plan_script_ok(self) -> None:
    from scripts.check_v9_study_demo_p0_ui_consistency import run_plan

    result = run_plan(search_run_id="study_demo_search_20260705_145711_c06e0a1b")
    assert result["status"] == "ok"
    assert result["legacy_contamination_count"] == 0
    assert result["metric_inconsistency_count"] == 0
