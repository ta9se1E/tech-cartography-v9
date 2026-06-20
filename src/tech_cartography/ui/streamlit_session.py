"""Streamlit session_state key conventions — widget keys vs internal state keys."""

from __future__ import annotations

from pathlib import Path
from typing import Any

# Widget keys (managed by Streamlit widgets; do not overwrite after widget creation)
WIDGET_PIPELINE_ROOT = "easy_pipeline_root_input"
WIDGET_SELECTED_RUN_ID = "selected_run_id_input"
WIDGET_DISPLAY_MODE = "easy_display_mode_input"
WIDGET_UI_MODE = "easy_ui_mode_input"
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
STATE_PENDING_SELECTED_RUN_ID = "pending_selected_run_id"
STATE_DEMO_MODE = "demo_mode_enabled"
STATE_DEMO_PUBLICATION_NUMBER = "demo_publication_number"
STATE_UI_MODE = "ui_view_mode"

DEMO_RUN_ID = "demo_us_12565719_b2"
DEMO_PUBLICATION_NUMBER = "US-12565719-B2"

WIDGET_KEYS = frozenset(
  {
    WIDGET_PIPELINE_ROOT,
    WIDGET_SELECTED_RUN_ID,
    WIDGET_DISPLAY_MODE,
    WIDGET_UI_MODE,
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
    STATE_PENDING_SELECTED_RUN_ID,
    STATE_DEMO_MODE,
    STATE_DEMO_PUBLICATION_NUMBER,
    STATE_UI_MODE,
  },
)

PENDING_KEYS = frozenset(
  {
    STATE_PENDING_SELECTED_RUN_ID,
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
  from tech_cartography.runtime.cloud_run_config import default_app_mode

  root = default_pipeline_root or default_pipeline_root_path()
  ui_mode = default_app_mode()
  state: dict[str, Any] = {
    STATE_PIPELINE_ROOT: root,
    STATE_SELECTED_RUN_ID: "",
    STATE_DISPLAY_MODE: DISPLAY_MODE_OPTIONS[0],
    STATE_MANIFEST_PATH: "",
    STATE_SAVED_RUN_ID: "",
    STATE_WEEKLY_EMAIL_ENABLED: False,
    STATE_DEMO_MODE: False,
    STATE_DEMO_PUBLICATION_NUMBER: "",
    STATE_UI_MODE: ui_mode,
  }
  if user:
    if user.get("last_run_id"):
      state[STATE_SELECTED_RUN_ID] = str(user["last_run_id"])
    state[STATE_WEEKLY_EMAIL_ENABLED] = bool(user.get("weekly_email_enabled"))
  if ui_mode == "demo":
    state[STATE_DEMO_MODE] = True
    state[STATE_DEMO_PUBLICATION_NUMBER] = DEMO_PUBLICATION_NUMBER
    state[STATE_SELECTED_RUN_ID] = DEMO_RUN_ID
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
  if STATE_UI_MODE in state:
    updates[WIDGET_UI_MODE] = state[STATE_UI_MODE]
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
    if widget_key not in st.session_state:
      st.session_state[widget_key] = value


def apply_pending_widget_state_updates() -> None:
  """Apply deferred widget values before widgets are instantiated."""
  import streamlit as st

  pending = st.session_state.pop(STATE_PENDING_SELECTED_RUN_ID, None)
  if pending:
    st.session_state[STATE_SELECTED_RUN_ID] = pending
    st.session_state[WIDGET_SELECTED_RUN_ID] = pending


def apply_internal_state_updates(updates: dict[str, Any]) -> None:
  """Write internal keys; defer selected run widget sync until before next widget render."""
  import streamlit as st

  for key, value in updates.items():
    if key in INTERNAL_KEYS:
      st.session_state[key] = value
  if STATE_SELECTED_RUN_ID in updates:
    st.session_state[STATE_PENDING_SELECTED_RUN_ID] = updates[STATE_SELECTED_RUN_ID]


def activate_evidence_map_demo_state() -> dict[str, Any]:
  """Internal session_state updates for one-click Evidence Map demo (no widget keys)."""
  return {
    STATE_DEMO_MODE: True,
    STATE_DEMO_PUBLICATION_NUMBER: DEMO_PUBLICATION_NUMBER,
    STATE_SELECTED_RUN_ID: DEMO_RUN_ID,
    STATE_PENDING_SELECTED_RUN_ID: DEMO_RUN_ID,
    STATE_MANIFEST_PATH: "",
  }


def deactivate_demo_mode_state() -> dict[str, Any]:
  return {STATE_DEMO_MODE: False, STATE_DEMO_PUBLICATION_NUMBER: ""}
