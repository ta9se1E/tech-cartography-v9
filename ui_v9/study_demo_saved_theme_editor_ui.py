"""Study Demo saved theme editor widgets (selector ↔ editor SSOT)."""

from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

from services_v9.study_demo_saved_theme_editor import (
  EDITOR_FIELDS,
  editor_dirty_vs_saved,
  saved_theme_editor_widget_key,
  theme_to_editor_values,
  validate_theme_update_save_guard,
)


def hydrate_saved_theme_editor_widgets(theme_state: Mapping[str, Any]) -> None:
  theme = dict(theme_state.get("saved_theme", {}) or {})
  theme_id = str(theme_state.get("selected_saved_theme_id", "") or theme.get("theme_id", ""))
  version = int(theme_state.get("selected_saved_theme_version", theme.get("theme_version", 1)) or 1)
  values = dict(theme_state.get("editor_values", {}) or theme_to_editor_values(theme))
  for field in EDITOR_FIELDS:
    key = saved_theme_editor_widget_key(theme_id, version, field)
    if field in values:
      st.session_state[key] = values.get(field)


def read_saved_theme_editor_from_session(theme_state: Mapping[str, Any]) -> dict[str, Any]:
  theme_id = str(theme_state.get("selected_saved_theme_id", "") or "")
  version = int(theme_state.get("selected_saved_theme_version", 1) or 1)
  values: dict[str, Any] = {}
  for field in EDITOR_FIELDS:
    key = saved_theme_editor_widget_key(theme_id, version, field)
    if key in st.session_state:
      values[field] = st.session_state.get(key)
  return values


def render_saved_theme_editor_form(*, theme_state: Mapping[str, Any]) -> dict[str, Any]:
  state = dict(theme_state or {})
  theme_id = str(state.get("selected_saved_theme_id", "") or "")
  version = int(state.get("selected_saved_theme_version", 1) or 1)
  saved_theme = dict(state.get("saved_theme", {}) or {})
  key = lambda field: saved_theme_editor_widget_key(theme_id, version, field)

  events: dict[str, Any] = {"save_theme": False, "save_theme_blocked": False, "save_theme_block_reason": None}

  editor_values = read_saved_theme_editor_from_session(state)
  if saved_theme and editor_values:
    dirty = editor_dirty_vs_saved(saved_theme, editor_values)
    if dirty:
      st.warning("入力内容が保存済みテーマと異なります。別Themeへ切替える前に確認してください。")

  upper_left, upper_right = st.columns(2)
  with upper_left:
    st.text_input("テーマ名", key=key("name"))
    st.text_area("テーマ説明", key=key("description"), height=160)
    st.text_area("コアキーワード 英語", key=key("core_en"), height=160)
    st.text_area("用途キーワード 英語", key=key("use_en"), height=140)
    st.text_area("材料・プロセスキーワード 英語", key=key("material_process_en"), height=180)
    st.text_area("除外キーワード 英語", key=key("exclude_en"), height=120)
  with upper_right:
    st.text_area("コアキーワード 日本語", key=key("core_ja"), height=160)
    st.text_area("用途キーワード 日本語", key=key("use_ja"), height=140)
    st.text_area("材料・プロセスキーワード 日本語", key=key("material_process_ja"), height=180)
    st.text_area("除外キーワード 日本語", key=key("exclude_ja"), height=120)

  pub_left, pub_right = st.columns(2)
  with pub_left:
    st.text_area("Seed publication numbers", key=key("seed_publications"), height=120)
  with pub_right:
    st.text_area("追加候補 publication numbers", key=key("candidate_publications"), height=120)

  st.caption(
    f"編集対象 Theme ID: `{theme_id}` / version `{version}` / "
    f"signature `{str(saved_theme.get('theme_signature', ''))[:8]}`"
  )

  with st.expander("現在の標準監視テーマを更新保存", expanded=False):
    save_errors = validate_theme_update_save_guard(
      selected_theme_id=theme_id,
      editor_theme_id=theme_id,
    )
    if save_errors:
      st.error("選択中Themeと編集対象Themeが一致しないため保存できません。")
      events["save_theme_blocked"] = True
      events["save_theme_block_reason"] = "selector_editor_mismatch"
    else:
      events["save_theme"] = st.button("標準監視テーマを更新保存", key=f"btn_save_theme_{theme_id}_v{version}")
  return events


__all__ = [
  "hydrate_saved_theme_editor_widgets",
  "read_saved_theme_editor_from_session",
  "render_saved_theme_editor_form",
]
