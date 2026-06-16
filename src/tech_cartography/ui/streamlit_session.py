"""Streamlit session_state key conventions — widget keys vs internal state keys."""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Widget keys (managed by Streamlit widgets; do not overwrite after widget creation)
WIDGET_PIPELINE_ROOT = "easy_pipeline_root_input"
WIDGET_SELECTED_RUN_ID = "selected_run_id_input"
WIDGET_DISPLAY_MODE = "easy_display_mode_input"
WIDGET_WEEKLY_EMAIL = "weekly_email_checkbox"
WIDGET_WEEKLY_DAY = "weekly_email_day_input"
WIDGET_WEEKLY_TIME = "weekly_email_time_input"
WIDGET_SETTINGS_DISPLAY_NAME = "settings_display_name_input"
WIDGET_SETTINGS_COMPANY_NAME = "settings_company_name_input"
WIDGET_EMAIL_DESTINATION_DISPLAY = "weekly_email_destination_display"
WIDGET_WATCH_THEME_DISPLAY = "weekly_watch_theme_display"

# Internal state keys (app-managed)
STATE_PIPELINE_ROOT = "easy_pipeline_root"
STATE_SELECTED_RUN_ID = "selected_run_id"
STATE_DISPLAY_MODE = "display_mode"
STATE_MANIFEST_PATH = "easy_manifest_path"
STATE_SAVED_RUN_ID = "easy_saved_run_id"
STATE_CURRENT_USER = "current_user"
STATE_WEEKLY_EMAIL_ENABLED = "weekly_email_enabled"

WIDGET_KEYS = frozenset(
  {
    WIDGET_PIPELINE_ROOT,
    WIDGET_SELECTED_RUN_ID,
    WIDGET_DISPLAY_MODE,
    WIDGET_WEEKLY_EMAIL,
    WIDGET_WEEKLY_DAY,
    WIDGET_WEEKLY_TIME,
    WIDGET_SETTINGS_DISPLAY_NAME,
    WIDGET_SETTINGS_COMPANY_NAME,
    WIDGET_EMAIL_DESTINATION_DISPLAY,
    WIDGET_WATCH_THEME_DISPLAY,
  },
)

INTERNAL_KEYS = frozenset(
  {
    STATE_PIPELINE_ROOT,
    STATE_SELECTED_RUN_ID,
    STATE_DISPLAY_MODE,
    STATE_MANIFEST_PATH,
    STATE_SAVED_RUN_ID,
    STATE_CURRENT_USER,
    STATE_WEEKLY_EMAIL_ENABLED,
  },
)

DISPLAY_MODE_OPTIONS = ("かんたん表示", "詳細表示")


def default_pipeline_root() -> str:
  project_root = Path(__file__).resolve().parents[3]
  return str(project_root / "outputs" / "pipeline_runs")


def assert_no_widget_internal_key_collision() -> None:
  overlap = WIDGET_KEYS & INTERNAL_KEYS
  if overlap:
    raise ValueError(f"Widget and internal session_state keys collide: {sorted(overlap)}")


def default_pipeline_root_path() -> str:
  return default_pipeline_root()


def default_app_session_state(
  user: dict[str, Any] | None = None,
  *,
  default_pipeline_root: str | None = None,
) -> dict[str, Any]:
  root = default_pipeline_root or default_pipeline_root_path()
  state: dict[str, Any] = {
    STATE_PIPELINE_ROOT: root,
    STATE_SELECTED_RUN_ID: "",
    STATE_DISPLAY_MODE: DISPLAY_MODE_OPTIONS[0],
    STATE_MANIFEST_PATH: "",
    STATE_SAVED_RUN_ID: "",
    STATE_WEEKLY_EMAIL_ENABLED: False,
  }
  if user:
    if user.get("last_run_id"):
      state[STATE_SELECTED_RUN_ID] = str(user["last_run_id"])
    state[STATE_WEEKLY_EMAIL_ENABLED] = bool(user.get("weekly_email_enabled"))
  return state


def merge_session_defaults(
  existing: dict[str, Any],
  user: dict[str, Any] | None = None,
  *,
  default_pipeline_root: str | None = None,
) -> dict[str, Any]:
  merged = dict(existing)
  for key, value in default_app_session_state(user, default_pipeline_root=default_pipeline_root).items():
    if key not in merged:
      merged[key] = value
  return merged


def prime_widget_keys_from_internal(state: dict[str, Any]) -> dict[str, Any]:
  """Values to set on widget keys before widgets render (safe before instantiation)."""
  updates: dict[str, Any] = {}
  if STATE_PIPELINE_ROOT in state:
    updates[WIDGET_PIPELINE_ROOT] = state[STATE_PIPELINE_ROOT]
  if STATE_SELECTED_RUN_ID in state:
    updates[WIDGET_SELECTED_RUN_ID] = state[STATE_SELECTED_RUN_ID]
  if STATE_DISPLAY_MODE in state:
    updates[WIDGET_DISPLAY_MODE] = state[STATE_DISPLAY_MODE]
  return updates


def sync_internal_from_widget_values(
  *,
  pipeline_root: str,
  selected_run_id: str,
  display_mode: str,
) -> dict[str, Any]:
  return {
    STATE_PIPELINE_ROOT: pipeline_root,
    STATE_SELECTED_RUN_ID: selected_run_id,
    STATE_DISPLAY_MODE: display_mode,
  }


def init_app_session_state(user: dict[str, Any] | None = None) -> None:
  """Initialize internal session_state keys before any widgets are created."""
  import streamlit as st

  assert_no_widget_internal_key_collision()
  merged = merge_session_defaults(dict(st.session_state), user)
  for key, value in merged.items():
    if key in INTERNAL_KEYS and key not in st.session_state:
      st.session_state[key] = value
  for widget_key, value in prime_widget_keys_from_internal(dict(st.session_state)).items():
    st.session_state[widget_key] = value


def apply_internal_state_updates(updates: dict[str, Any]) -> None:
  """Write internal keys and prime widget keys before rerun."""
  import streamlit as st

  for key, value in updates.items():
    if key in INTERNAL_KEYS:
      st.session_state[key] = value
  for widget_key, value in prime_widget_keys_from_internal(updates).items():
    st.session_state[widget_key] = value
