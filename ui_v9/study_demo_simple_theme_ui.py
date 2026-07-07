"""Simple Mode theme tab for Study Demo."""

from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

from services_v9.study_demo_ui_mode import should_show_technical_ids
from ui_v9.study_demo_compact_components import render_theme_summary_card


def _keywords_text(theme: Mapping[str, Any], bucket: str, *, lang: str) -> str:
  keywords = dict(theme.get("keywords", {}) or {})
  key = f"{bucket}_{lang}"
  values = keywords.get(key, [])
  if isinstance(values, str):
    return values
  return ", ".join(str(item) for item in list(values or []))


def render_simple_theme_tab(
  *,
  theme_state: Mapping[str, Any],
  source_info: Mapping[str, Any] | None,
  profile_summary: Mapping[str, object],
  search_plan_state: Mapping[str, Any],
) -> dict[str, bool]:
  state = dict(theme_state or {})
  saved_themes = list(state.get("saved_themes", []) or [])
  saved_theme = dict(state.get("saved_theme", {}) or {})
  if not saved_themes and saved_theme:
    saved_themes = [saved_theme]
  active_context = dict((source_info or {}).get("active_context", {}) or {}) or None
  downstream_bundle = dict((source_info or {}).get("study_demo_downstream", {}) or {}) or None
  lineage_status = dict((downstream_bundle or {}).get("lineage_status", {}) or {})
  connected = str(lineage_status.get("lineage_status", active_context.get("lineage_status", "") if active_context else ""))

  render_theme_summary_card(
    saved_theme=saved_theme,
    lineage_status=connected,
  )

  from services_v9.study_demo_live_lineage_loader import resolve_display_search_plan

  display_plan = resolve_display_search_plan(active_context=active_context, theme_state=state)
  with st.expander("検索条件を見る", expanded=False):
    providers = dict(display_plan.get("provider_plans", {}) or {})
    for name, label in (("patent", "Patent"), ("paper", "Paper"), ("web", "Web")):
      plan_item = dict(providers.get(name, {}) or {})
      st.write(f"**{label}:** {plan_item.get('query_text_summary', '—')}")
    excludes = list(display_plan.get("exclude_keywords", []) or [])
    if excludes:
      st.write(f"**除外語:** {', '.join(str(item) for item in excludes)}")
    limits = dict(display_plan.get("provider_limits", {}) or {})
    if limits:
      st.write(
        f"**件数上限:** Patent {limits.get('patent', '—')} / "
        f"Paper {limits.get('paper', '—')} / Web {limits.get('web', '—')}"
      )
    if should_show_technical_ids():
      st.write(f"- Search Plan ID: `{display_plan.get('search_plan_id', '')}`")
      st.write(f"- validation_status: `{display_plan.get('validation_status', '')}`")

  button_left, button_right = st.columns(2)
  with button_left:
    if st.button("テーマを変更", key="btn_simple_theme_edit"):
      st.session_state["ui_simple_theme_edit_open"] = True
  with button_right:
    if st.button("検索条件を見る", key="btn_simple_search_conditions_scroll"):
      st.session_state["ui_simple_search_conditions_hint"] = True

  if len(saved_themes) > 1:
    with st.expander("別の保存済みテーマを選ぶ", expanded=False):
      from ui_v9.study_demo_theme_draft_ui import render_saved_theme_selector

      selector_events = render_saved_theme_selector(
        saved_themes=saved_themes,
        selected_theme_id=str(state.get("selected_saved_theme_id", saved_theme.get("theme_id", "")) or ""),
        show_technical_ids=should_show_technical_ids(),
      )
  else:
    selector_events = {}

  theme_events: dict[str, bool] = {}
  editor_events: dict[str, bool] = {}
  if st.session_state.get("ui_simple_theme_edit_open"):
    st.markdown("#### テーマ編集")
    from ui_v9.study_demo_saved_theme_editor_ui import render_saved_theme_editor_form

    editor_events = render_saved_theme_editor_form(theme_state=state)
    theme_events.update(editor_events)
    with st.expander("詳細設定", expanded=False):
      st.text_area(
        "core 日本語",
        value=_keywords_text(saved_theme, "core", lang="ja"),
        key=f"simple_detail_core_ja_{saved_theme.get('theme_id', '')}",
        disabled=True,
      )
      st.text_area(
        "application 日本語",
        value=_keywords_text(saved_theme, "use", lang="ja"),
        key=f"simple_detail_use_ja_{saved_theme.get('theme_id', '')}",
        disabled=True,
      )
      st.text_area(
        "material_process 日本語",
        value=_keywords_text(saved_theme, "material_process", lang="ja"),
        key=f"simple_detail_mp_ja_{saved_theme.get('theme_id', '')}",
        disabled=True,
      )

  return {
    "save_profile": False,
    "load_profile": False,
    "regenerate_search_plan": False,
    **theme_events,
    **selector_events,
    **editor_events,
  }


__all__ = ["render_simple_theme_tab"]
