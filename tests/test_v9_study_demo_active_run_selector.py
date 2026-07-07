"""Tests for Study Demo active run selector visibility and activation logic."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from services_v9.study_demo_active_run_selector import (
  SELECTOR_WIDGET_KEYS,
  format_save_result_message,
  missing_activation_artifacts,
  resolve_activation_state,
  should_show_active_run_selector,
  summarize_run_for_selector,
)
from services_v9.study_demo_config import PRODUCTION_PERSIST_BUCKET
from ui_v9.study_demo_search_ui import (
  KEY_ACTIVATE_RUN_BUTTON,
  KEY_CONFIRM_ACTIVATE_RUN,
  KEY_RELOAD_ACTIVE_CONTEXT_BUTTON,
  STATE_SELECTED_HISTORY_RUN_ID,
  render_active_run_selector,
)

FIXTURE_PATH = ROOT / "tests/fixtures/study_demo_active_run_connection_samples.json"


def _fixture_artifacts() -> tuple[str, dict]:
  payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
  run_id = str(payload["search_run_id"])
  artifacts = dict(payload["artifacts"])
  for name in (
    "patent_results.json",
    "paper_results.json",
    "web_results.json",
    "usage_metrics.json",
    "search_status.json",
  ):
    artifacts.setdefault(name, {"status": "ok"})
  artifacts.setdefault("search_report.md", "# report\n")
  return run_id, artifacts


def test_should_show_selector_when_run_selected() -> None:
  assert should_show_active_run_selector(
    authenticated=True,
    history_run_ids=["run-a"],
    selected_run_id="run-a",
  )


def test_should_show_selector_without_active_context() -> None:
  assert should_show_active_run_selector(
    authenticated=True,
    history_run_ids=["run-a"],
    selected_run_id="run-a",
  )


def test_should_not_show_selector_when_unauthenticated() -> None:
  assert not should_show_active_run_selector(
    authenticated=False,
    history_run_ids=["run-a"],
    selected_run_id="run-a",
  )


def test_should_not_show_selector_without_selection() -> None:
  assert not should_show_active_run_selector(
    authenticated=True,
    history_run_ids=["run-a"],
    selected_run_id="",
  )


def test_resolve_requires_confirm_and_button() -> None:
  run_id, artifacts = _fixture_artifacts()
  none = resolve_activation_state(
    selected_run_id=run_id,
    active_run_id="",
    confirm_checked=False,
    activate_clicked=False,
    reload_clicked=False,
    artifacts=artifacts,
  )
  assert none["action"] == "none"

  no_confirm = resolve_activation_state(
    selected_run_id=run_id,
    active_run_id="",
    confirm_checked=False,
    activate_clicked=True,
    reload_clicked=False,
    artifacts=artifacts,
  )
  assert no_confirm["action"] == "error"
  assert no_confirm["error_code"] == "confirm_required"

  no_button = resolve_activation_state(
    selected_run_id=run_id,
    active_run_id="",
    confirm_checked=True,
    activate_clicked=False,
    reload_clicked=False,
    artifacts=artifacts,
  )
  assert no_button["action"] == "none"


def test_resolve_save_with_confirm_and_button() -> None:
  run_id, artifacts = _fixture_artifacts()
  decision = resolve_activation_state(
    selected_run_id=run_id,
    active_run_id="",
    confirm_checked=True,
    activate_clicked=True,
    reload_clicked=False,
    artifacts=artifacts,
  )
  assert decision["action"] == "save"


def test_same_active_run_is_idempotent() -> None:
  run_id, artifacts = _fixture_artifacts()
  decision = resolve_activation_state(
    selected_run_id=run_id,
    active_run_id=run_id,
    confirm_checked=False,
    activate_clicked=True,
    reload_clicked=False,
    artifacts=artifacts,
  )
  assert decision["action"] == "idempotent"


def test_switch_active_run_requires_confirm() -> None:
  run_id, artifacts = _fixture_artifacts()
  decision = resolve_activation_state(
    selected_run_id=run_id,
    active_run_id="other-run",
    confirm_checked=False,
    activate_clicked=True,
    reload_clicked=False,
    artifacts=artifacts,
  )
  assert decision["action"] == "error"
  assert decision["error_code"] == "confirm_required_switch"


def test_missing_artifacts_error() -> None:
  run_id, _ = _fixture_artifacts()
  decision = resolve_activation_state(
    selected_run_id=run_id,
    active_run_id="",
    confirm_checked=True,
    activate_clicked=True,
    reload_clicked=False,
    artifacts={},
  )
  assert decision["action"] == "error"
  assert decision["error_code"] == "missing_artifacts"
  assert "不足artifact" in decision["message"]


def test_generation_conflict_message() -> None:
  msg = format_save_result_message(status="conflict", search_run_id="run-a")
  assert "再読み込み" in msg


def test_save_success_message() -> None:
  msg = format_save_result_message(status="saved", search_run_id="run-a")
  assert "run-a" in msg


def test_summarize_run_for_selector_uses_integrated() -> None:
  run_id, artifacts = _fixture_artifacts()
  summary = summarize_run_for_selector(
    search_run_id=run_id,
    artifacts=artifacts,
    integrated={"relevance_summary": {"tier_a": 3}, "ranked_count": 4, "signals": []},
  )
  assert summary["tier_counts"]["A"] == 3
  assert summary["ranked_count"] == 4


def test_widget_keys_are_unique() -> None:
  assert len(SELECTOR_WIDGET_KEYS) == len(set(SELECTOR_WIDGET_KEYS))
  assert KEY_CONFIRM_ACTIVATE_RUN in SELECTOR_WIDGET_KEYS
  assert KEY_ACTIVATE_RUN_BUTTON in SELECTOR_WIDGET_KEYS
  assert KEY_RELOAD_ACTIVE_CONTEXT_BUTTON in SELECTOR_WIDGET_KEYS
  assert STATE_SELECTED_HISTORY_RUN_ID in SELECTOR_WIDGET_KEYS


def test_ui_source_places_selector_before_summary() -> None:
  source = Path(ROOT / "ui_v9/study_demo_search_ui.py").read_text(encoding="utf-8")
  selector_idx = source.index("render_active_run_selector(")
  summary_idx = source.index("_render_search_result(history_result)")
  assert selector_idx < summary_idx


def test_ui_does_not_gate_selector_on_data_mode() -> None:
  source = Path(ROOT / "ui_v9/study_demo_search_ui.py").read_text(encoding="utf-8")
  body = source.split("def render_active_run_selector")[1].split("def _reload_active_context_from_storage")[0]
  gate_snippet = body.split("if not should_show_active_run_selector")[1].split("artifacts = dict")[0]
  assert "ui_data_source_mode" not in gate_snippet


def test_tabs_collapses_legacy_data_mode() -> None:
  source = Path(ROOT / "ui_v9/tabs.py").read_text(encoding="utf-8")
  assert "手動アップロード・旧データ投入機能" in source
  assert 'st.expander("手動アップロード・旧データ投入機能"' in source


@pytest.mark.parametrize("data_mode", ["unselected", "temporary_search", "legacy_demo", "retrieval_saved"])
def test_selector_render_independent_of_data_mode(data_mode: str) -> None:
  run_id, artifacts = _fixture_artifacts()
  loaded = {"search_run_id": run_id, "artifacts": artifacts}
  mock_st = MagicMock()
  mock_st.session_state = {
    "ui_data_source_mode": data_mode,
    "v9_study_demo_active_context": {},
  }
  mock_st.button.return_value = False
  mock_st.checkbox.return_value = False
  with patch("ui_v9.study_demo_search_ui.st", mock_st):
    with patch("ui_v9.study_demo_search_ui.list_search_history", return_value=[{"search_run_id": run_id}]):
      with patch("ui_v9.study_demo_search_ui.build_search_result_from_artifacts") as build_mock:
        build_mock.return_value = {
          "search_run_id": run_id,
          "integrated_signals": {"relevance_summary": {"tier_a": 1}, "signals": []},
        }
        events = render_active_run_selector(selected_run_id=run_id, loaded=loaded, authenticated=True)
  assert events == {}
  assert mock_st.markdown.call_args_list[0].args[0] == "#### 分析対象として使用"
  assert mock_st.checkbox.called
  assert mock_st.button.called


def test_selector_render_without_active_context() -> None:
  run_id, artifacts = _fixture_artifacts()
  mock_st = MagicMock()
  mock_st.session_state = {}
  mock_st.button.return_value = False
  mock_st.checkbox.return_value = False
  with patch("ui_v9.study_demo_search_ui.st", mock_st):
    with patch("ui_v9.study_demo_search_ui.list_search_history", return_value=[{"search_run_id": run_id}]):
      with patch("ui_v9.study_demo_search_ui.build_search_result_from_artifacts") as build_mock:
        build_mock.return_value = {"search_run_id": run_id, "integrated_signals": {"signals": []}}
        render_active_run_selector(
          selected_run_id=run_id,
          loaded={"search_run_id": run_id, "artifacts": artifacts},
          authenticated=True,
        )
  assert mock_st.checkbox.called


def test_activate_save_does_not_call_providers() -> None:
  run_id, artifacts = _fixture_artifacts()
  mock_st = MagicMock()
  mock_st.session_state = {}
  mock_st.button.side_effect = [False, True]
  mock_st.checkbox.return_value = True
  with patch("ui_v9.study_demo_search_ui.st", mock_st):
    with patch("ui_v9.study_demo_search_ui.list_search_history", return_value=[{"search_run_id": run_id}]):
      with patch("ui_v9.study_demo_search_ui.build_search_result_from_artifacts") as build_mock:
        build_mock.return_value = {"search_run_id": run_id, "integrated_signals": {"signals": []}}
        with patch("services_v9.study_demo_analysis_context.save_active_context_to_storage") as save_mock:
          save_mock.return_value = {"status": "saved", "context": {"active_search_run_id": run_id}, "generation": 2}
          with patch("services_v9.study_demo_analysis_context.build_active_context_from_run") as build_ctx:
            build_ctx.return_value = {"active_search_run_id": run_id}
            decision = resolve_activation_state(
              selected_run_id=run_id,
              active_run_id="",
              confirm_checked=True,
              activate_clicked=True,
              reload_clicked=False,
              artifacts=artifacts,
            )
            assert decision["action"] == "save"
            with patch("services_v9.study_demo_search.patent_provider.run_study_demo_patent_execute") as patent_mock:
              render_active_run_selector(
                selected_run_id=run_id,
                loaded={"search_run_id": run_id, "artifacts": artifacts},
                authenticated=True,
              )
  patent_mock.assert_not_called()
  save_mock.assert_called_once()
  mock_st.rerun.assert_called_once()


def test_activate_rejects_production_bucket() -> None:
  from services_v9.study_demo_analysis_context import build_active_context_from_run

  run_id, artifacts = _fixture_artifacts()
  with pytest.raises(ValueError):
    build_active_context_from_run(
      search_run_id=run_id,
      artifacts=artifacts,
      bucket_name=PRODUCTION_PERSIST_BUCKET,
    )


def test_missing_activation_artifacts_list() -> None:
  missing = missing_activation_artifacts({})
  assert "search_request.json" in missing
  assert "integrated_signals.json" in missing
