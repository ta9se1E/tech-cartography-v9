"""Theme lineage UI sections for Study Demo theme setup tab."""

from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

from services_v9.study_demo_theme_lineage import (
  build_search_plan_from_watch_profile,
  build_search_plan_preview_summary,
  build_theme_record,
  build_watch_profile_from_theme,
  default_saved_theme_fixture,
  promote_temporary_search_to_theme_draft,
  summarize_lineage_status,
  theme_dirty,
)


def render_standard_theme_section(
  *,
  saved_theme: Mapping[str, Any] | None,
  widget_theme: Mapping[str, Any],
) -> dict[str, bool]:
  st.markdown("### A. 標準監視テーマ")
  current = dict(widget_theme or {})
  dirty = theme_dirty(saved_theme, current)
  st.write(f"- Theme name: {current.get('name', '未設定')}")
  st.write(f"- Theme ID: `{current.get('theme_id', '未割当')}` / version `{current.get('theme_version', 1)}`")
  st.write(f"- Theme signature: `{str(current.get('theme_signature', ''))[:8]}`")
  st.write(f"- 保存状態: `{current.get('status', 'draft')}`")
  st.write(f"- 未保存変更: {'あり' if dirty else 'なし'}")
  st.write(f"- 最終保存: {saved_theme.get('updated_at', '未保存') if saved_theme else '未保存'}")

  col1, col2, col3, col4 = st.columns(4)
  events = {
    "save_theme": False,
    "load_saved_theme": False,
    "generate_watch_profile": False,
    "generate_search_plan": False,
  }
  with col1:
    events["save_theme"] = st.button("テーマを保存", key="btn_theme_save_theme")
  with col2:
    events["load_saved_theme"] = st.button("保存済みテーマを読み込む", key="btn_theme_load_saved")
  with col3:
    events["generate_watch_profile"] = st.button("Watch Profile案を生成", key="btn_theme_gen_profile")
  with col4:
    events["generate_search_plan"] = st.button("Search Planを生成", key="btn_theme_gen_plan")

  if dirty:
    st.warning(
      "入力内容が保存済みテーマと異なります。"
      "先に保存するか、保存済み設定からSearch Planを生成してください。"
    )
  return events


def render_active_analysis_target_section(
  *,
  active_context: Mapping[str, Any] | None,
  downstream_bundle: Mapping[str, Any] | None,
) -> None:
  st.markdown("### B. 現在の分析対象")
  if not active_context:
    st.info("Active Context未設定。情報源タブで検索runを分析対象に設定してください。")
    return

  enriched = dict((downstream_bundle or {}).get("enriched_context", {}) or active_context)
  status = dict((downstream_bundle or {}).get("lineage_status", {}) or summarize_lineage_status(enriched))
  st.write(f"- active run ID: `{active_context.get('active_search_run_id', '')}`")
  st.write(f"- run_origin: `{enriched.get('run_origin', 'temporary_search')}`")
  st.write(f"- Active Runテーマ: {active_context.get('theme', '')}")
  st.write(f"- lineage status: `{status.get('lineage_status', 'unavailable')}`")
  st.write(f"- Watch Profile接続: {status.get('watch_profile_connection', '未接続')}")
  if status.get("lineage_status") == "temporary_unconnected":
    st.write(f"- 標準監視テーマ: {status.get('standard_theme_name', '')}")
    st.caption("古い標準監視テーマとActive Runテーマは別物です。混同しないでください。")


def render_temporary_search_promotion_section(
  *,
  active_context: Mapping[str, Any] | None,
  search_request: Mapping[str, Any] | None,
) -> dict[str, Any]:
  st.markdown("### C. 一時検索runからテーマ案へ昇格")
  if not active_context:
    return {"promote_theme_draft": False, "theme_draft": None}
  run_origin = str(active_context.get("run_origin", "temporary_search") or "temporary_search")
  if run_origin != "temporary_search":
    st.caption("標準監視テーマ由来runのため、一時検索昇格は不要です。")
    return {"promote_theme_draft": False, "theme_draft": None}

  confirm = st.checkbox(
    "一時検索条件をテーマ案として作成します。既存テーマは上書きしません",
    key="ui_promote_theme_confirm",
  )
  clicked = st.button("この検索条件からテーマ案を作成", key="btn_promote_theme_draft")
  draft = None
  if clicked and confirm and search_request:
    draft = promote_temporary_search_to_theme_draft(
      search_request,
      search_run_id=str(active_context.get("active_search_run_id", "") or ""),
    )
    st.success(f"テーマ案 draft を作成しました: `{draft.get('theme_id')}`（自動保存・自動適用はしません）")
  elif clicked and not confirm:
    st.warning("確認チェックボックスをオンにしてください。")
  return {"promote_theme_draft": bool(clicked and confirm), "theme_draft": draft}


def render_search_plan_preview_section(search_plan: Mapping[str, Any] | None) -> None:
  st.markdown("### Search Plan Preview")
  if not search_plan:
    st.info("Search Plan未生成。保存済みWatch Profileから生成してください。")
    return
  summary = build_search_plan_preview_summary(search_plan)
  st.write(f"- Search Plan ID: `{summary.get('search_plan_id')}` v{summary.get('search_plan_version')}")
  st.write(f"- signature: `{summary.get('search_plan_signature_short')}`")
  st.write(f"- 元Theme: `{summary.get('source_theme_id')}` v{summary.get('source_theme_version')}")
  st.write(f"- 元Watch Profile: `{summary.get('source_watch_profile_id')}` v{summary.get('source_watch_profile_version')}")
  st.write(f"- Patent query: {summary.get('patent_query_summary')}")
  st.write(f"- Paper query: {summary.get('paper_query_summary')}")
  st.write(f"- Web query: {summary.get('web_query_summary')}")
  st.write(f"- 完全一致語: {', '.join(summary.get('exact_phrases', []) or []) or 'なし'}")
  st.write(f"- 除外語: {', '.join(summary.get('exclude_keywords', []) or []) or 'なし'}")
  year_range = dict(summary.get("year_range", {}) or {})
  st.write(f"- 年範囲: {year_range.get('start', '—')} - {year_range.get('end', '—')}")
  st.write(f"- Seed公報: {', '.join(summary.get('seed_publications', []) or []) or 'なし'}")
  st.write(f"- provider上限: {summary.get('provider_limits')}")
  st.write(f"- query数: {summary.get('estimated_query_count')}")
  st.write(f"- 外部実行可否: {summary.get('external_execution_allowed')}")
  if summary.get("validation_messages"):
    st.warning("; ".join(str(item) for item in summary.get("validation_messages", [])))
  with st.expander("Provider plan details", expanded=False):
    for provider, plan in dict(search_plan.get("provider_plans", {}) or {}).items():
      st.markdown(f"**{provider}**")
      st.json(plan)


def render_study_demo_capability_legend() -> None:
  st.markdown("**Study Demo 実行状態**")
  st.markdown("- 一時キーワード検索: Patent / Paper / Web 有効")
  st.markdown("- テーマ由来の標準検索: 実行前確認が必要")
  st.markdown("- ページ表示 / 履歴表示: 外部APIを実行しない")
  st.markdown("- 自動週次: 停止中")
  st.markdown("- メール: 停止中")
  st.markdown("- 本番環境: 変更しない")


def default_theme_state() -> dict[str, Any]:
  saved = default_saved_theme_fixture()
  return {"saved_theme": saved, "widget_theme": dict(saved), "watch_profile": None, "search_plan": None}


def generate_watch_profile_from_saved_theme(saved_theme: Mapping[str, Any]) -> dict[str, Any]:
  if str(saved_theme.get("status", "")) != "saved":
    raise ValueError("saved theme required")
  return build_watch_profile_from_theme(saved_theme)


def generate_search_plan_from_saved_profile(
  watch_profile: Mapping[str, Any],
  theme: Mapping[str, Any],
  *,
  provider_limit: int = 5,
) -> dict[str, Any]:
  return build_search_plan_from_watch_profile(
    watch_profile,
    theme,
    provider_limits={"patent": provider_limit, "paper": provider_limit, "web": provider_limit},
    external_execution_allowed=False,
  )


def build_theme_from_widgets(form: Mapping[str, Any]) -> dict[str, Any]:
  from services_v9.study_demo_theme_lineage import theme_from_form_widgets

  return theme_from_form_widgets(form)
