"""Simple Mode information source tab for Study Demo."""

from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

from services_v9.human_datetime import format_datetime_jst
from services_v9.study_demo_run_metrics import format_unknown_metric
from services_v9.study_demo_ui_mode import should_show_legacy_tools, should_show_technical_ids
from ui_v9.study_demo_compact_components import render_provider_cards


def render_simple_sources_tab(
  *,
  source_info: Mapping[str, Any],
  theme_state: Mapping[str, Any] | None,
  study_demo_authenticated: bool,
  search_plan_state: Mapping[str, Any],
  retrieval_reload_state: Mapping[str, Any],
  retrieval_manifest_status_message: str | None,
  csv_template_text: str,
  json_template_text: str,
) -> dict[str, object]:
  events: dict[str, object] = {}
  metrics = dict(source_info.get("canonical_metrics", {}) or {})
  active_context = dict(source_info.get("active_context", {}) or {})

  st.markdown("#### 現在の取得状況")
  render_provider_cards(metrics=metrics)
  integrated = format_unknown_metric(metrics.get("integrated_count", source_info.get("loaded_count")))
  executed_at = format_datetime_jst(active_context.get("selected_at", ""))
  cost = dict(source_info.get("cost_estimate", {}) or metrics.get("cost_estimate", {}) or {})
  cost_value = cost.get("total_usd_estimate", cost.get("estimated_total_usd"))
  cost_text = "未計測" if cost_value in {None, "", "—", "-"} else str(cost_value)
  st.write(f"**統合後:** {integrated}件")
  st.caption(f"最終実行日時: {executed_at} | 参考費用: {cost_text}")

  saved_theme = dict((theme_state or {}).get("saved_theme", {}) or {})
  from services_v9.study_demo_live_lineage_loader import resolve_display_search_plan

  display_plan = resolve_display_search_plan(active_context=active_context, theme_state=dict(theme_state or {}))
  with st.expander("今回の検索条件", expanded=False):
    st.write(f"**Theme:** {saved_theme.get('name', active_context.get('theme', ''))}")
    providers = dict(display_plan.get("provider_plans", {}) or {})
    for name, label in (("patent", "Patent"), ("paper", "Paper"), ("web", "Web")):
      st.write(f"**{label}:** {dict(providers.get(name, {}) or {}).get('query_text_summary', '—')}")
    excludes = list(display_plan.get("exclude_keywords", []) or [])
    if excludes:
      st.write(f"**除外語:** {', '.join(str(item) for item in excludes)}")

  with st.expander("過去の検索を見る", expanded=False):
    try:
      from services_v9.study_demo_search.storage import list_search_history

      history = list_search_history(limit=10)
    except Exception:
      history = []
    comparable_history = [
      item
      for item in history
      if str(item.get("search_run_id", "") or "").strip()
      and str(item.get("theme", "") or "").strip()
      and str(item.get("created_at", "") or "").strip()
    ]
    if not comparable_history:
      st.caption("過去の検索履歴はまだありません。今回のRunが初回ベースラインです。")
    for item in comparable_history:
      run_id = str(item.get("search_run_id", "") or "")
      active_mark = "（現在使用中）" if run_id == str(active_context.get("active_search_run_id", "")) else ""
      created = format_datetime_jst(item.get("created_at", ""))
      theme = str(item.get("theme", "") or "")
      count = item.get("integrated_count", "")
      label = f"{created} | {theme} | {count}件{active_mark}"
      if should_show_technical_ids():
        label = f"{label} | `{run_id}`"
      st.write(f"- {label}")

  if st.button("新しい検索を作成", key="btn_simple_new_search"):
    st.session_state["ui_simple_new_search_open"] = True

  if st.session_state.get("ui_simple_new_search_open"):
    from ui_v9.study_demo_search_ui import render_study_demo_keyword_search_section

    events = render_study_demo_keyword_search_section(authenticated=study_demo_authenticated)

  if should_show_legacy_tools():
    with st.expander("旧機能・手動投入", expanded=False):
      from ui_v9.study_demo_sources_ui import render_study_demo_legacy_sources_section

      legacy_events = render_study_demo_legacy_sources_section(
        retrieval_reload_state=retrieval_reload_state,
        retrieval_manifest_status_message=retrieval_manifest_status_message,
        csv_template_text=csv_template_text,
        json_template_text=json_template_text,
      )
      events.update(legacy_events)

  return events


__all__ = ["render_simple_sources_tab"]
