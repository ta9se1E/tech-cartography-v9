"""Tests for Streamlit session_state key separation."""

from pathlib import Path
import inspect

import pytest
import streamlit as st

from tech_cartography.ui.streamlit_session import (
  STATE_DISPLAY_MODE,
  STATE_PENDING_SELECTED_RUN_ID,
  STATE_PIPELINE_ROOT,
  STATE_SELECTED_RUN_ID,
  STATE_WEEKLY_EMAIL_ENABLED,
  WIDGET_DISPLAY_MODE,
  WIDGET_KEYS,
  WIDGET_PIPELINE_ROOT,
  WIDGET_SELECTED_RUN_ID,
  INTERNAL_KEYS,
  apply_pending_widget_state_updates,
  assert_no_widget_internal_key_collision,
  default_app_session_state,
  merge_session_defaults,
  prime_widget_keys_from_internal,
  sync_internal_from_widget_values,
)


def test_widget_and_internal_keys_do_not_collide() -> None:
  assert_no_widget_internal_key_collision()
  assert WIDGET_PIPELINE_ROOT not in INTERNAL_KEYS
  assert STATE_PIPELINE_ROOT not in WIDGET_KEYS
  assert WIDGET_SELECTED_RUN_ID not in INTERNAL_KEYS
  assert STATE_SELECTED_RUN_ID not in WIDGET_KEYS
  assert WIDGET_DISPLAY_MODE not in INTERNAL_KEYS
  assert STATE_DISPLAY_MODE not in WIDGET_KEYS


def test_default_app_session_state_initializes() -> None:
  state = default_app_session_state()
  assert STATE_PIPELINE_ROOT in state
  assert state[STATE_SELECTED_RUN_ID] == ""
  assert state[STATE_DISPLAY_MODE] == "かんたん表示"
  assert state[STATE_WEEKLY_EMAIL_ENABLED] is False


def test_default_session_state_uses_user_last_run_id() -> None:
  state = default_app_session_state({"last_run_id": "20260616_163006", "weekly_email_enabled": True})
  assert state[STATE_SELECTED_RUN_ID] == "20260616_163006"
  assert state[STATE_WEEKLY_EMAIL_ENABLED] is True


def test_merge_session_defaults_preserves_existing() -> None:
  merged = merge_session_defaults(
    {STATE_PIPELINE_ROOT: "/custom/path", STATE_SELECTED_RUN_ID: "run-1"},
    user={"last_run_id": "ignored"},
  )
  assert merged[STATE_PIPELINE_ROOT] == "/custom/path"
  assert merged[STATE_SELECTED_RUN_ID] == "run-1"
  assert merged[STATE_DISPLAY_MODE] == "かんたん表示"


def test_sync_internal_from_widget_values() -> None:
  synced = sync_internal_from_widget_values(
    pipeline_root="outputs/pipeline_runs",
    selected_run_id="20260616_163006",
    display_mode="詳細表示",
  )
  assert synced[STATE_PIPELINE_ROOT] == "outputs/pipeline_runs"
  assert synced[STATE_SELECTED_RUN_ID] == "20260616_163006"
  assert synced[STATE_DISPLAY_MODE] == "詳細表示"


def test_prime_widget_keys_from_internal() -> None:
  primed = prime_widget_keys_from_internal(
    {
      STATE_PIPELINE_ROOT: "outputs/pipeline_runs",
      STATE_SELECTED_RUN_ID: "run-abc",
      STATE_DISPLAY_MODE: "かんたん表示",
    },
  )
  assert primed[WIDGET_PIPELINE_ROOT] == "outputs/pipeline_runs"
  assert primed[WIDGET_SELECTED_RUN_ID] == "run-abc"
  assert primed[WIDGET_DISPLAY_MODE] == "かんたん表示"


def test_widget_and_internal_selected_run_id_keys_differ() -> None:
  assert WIDGET_SELECTED_RUN_ID != STATE_SELECTED_RUN_ID
  assert WIDGET_SELECTED_RUN_ID == "selected_run_id_input"
  assert STATE_SELECTED_RUN_ID == "selected_run_id"


def test_apply_pending_selected_run_id_updates_internal_and_widget(monkeypatch: pytest.MonkeyPatch) -> None:
  fake_state = {STATE_PENDING_SELECTED_RUN_ID: "20260616_163006"}
  monkeypatch.setattr(st, "session_state", fake_state, raising=False)
  apply_pending_widget_state_updates()
  assert STATE_PENDING_SELECTED_RUN_ID not in fake_state
  assert fake_state[STATE_SELECTED_RUN_ID] == "20260616_163006"
  assert fake_state[WIDGET_SELECTED_RUN_ID] == "20260616_163006"


def test_apply_pending_noop_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
  fake_state: dict[str, str] = {}
  monkeypatch.setattr(st, "session_state", fake_state, raising=False)
  apply_pending_widget_state_updates()
  assert STATE_SELECTED_RUN_ID not in fake_state
  assert WIDGET_SELECTED_RUN_ID not in fake_state


def test_sync_internal_from_widget_values_is_widget_to_internal_only() -> None:
  source = inspect.getsource(sync_internal_from_widget_values)
  assert "WIDGET_" not in source
  synced = sync_internal_from_widget_values(
    pipeline_root="outputs/pipeline_runs",
    selected_run_id="run-xyz",
    display_mode="詳細表示",
  )
  assert set(synced.keys()) <= INTERNAL_KEYS


def test_app_py_does_not_assign_widget_selected_run_id_directly() -> None:
  app_text = Path("app.py").read_text(encoding="utf-8")
  assert "st.session_state[WIDGET_SELECTED_RUN_ID] =" not in app_text
  assert "STATE_PENDING_SELECTED_RUN_ID" in app_text
  assert "apply_pending_widget_state_updates" in app_text


def test_app_py_latest_run_uses_pending_selected_run_id() -> None:
  app_text = Path("app.py").read_text(encoding="utf-8")
  assert "st.session_state[STATE_PENDING_SELECTED_RUN_ID]" in app_text
  assert "st.session_state[STATE_SELECTED_RUN_ID]" in app_text
  assert "load_latest_run_button" in app_text
  assert "apply_pending_widget_state_updates()" in app_text
