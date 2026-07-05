"""Theme lineage UI sections for Study Demo theme setup tab."""

from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

from services_v9.study_demo_theme_draft import (
  build_theme_draft_from_temporary_search,
  find_existing_draft_for_run,
)
from services_v9.study_demo_theme_lineage import (
  build_search_plan_from_watch_profile,
  build_theme_record,
  build_watch_profile_from_theme,
  default_saved_theme_fixture,
  summarize_lineage_status,
  theme_dirty,
)


def render_standard_theme_summary(
  *,
  saved_theme: Mapping[str, Any] | None,
  widget_theme: Mapping[str, Any],
) -> None:
  current = dict(widget_theme or {})
  dirty = theme_dirty(saved_theme, current)
  st.write(f"- 現在選択中: {current.get('name', '未設定')}")
  st.write(f"- Theme ID: `{current.get('theme_id', '未割当')}` / version `{current.get('theme_version', 1)}`")
  st.write(f"- Theme signature: `{str(current.get('theme_signature', ''))[:8]}`")
  st.write(f"- 保存状態: `{current.get('status', 'draft')}`")
  st.write(f"- 未保存変更: {'あり' if dirty else 'なし'}")
  st.write(f"- 最終保存: {saved_theme.get('updated_at', '未保存') if saved_theme else '未保存'}")
  if dirty:
    st.warning(
      "入力内容が保存済みテーマと異なります。"
      "先に保存するか、保存済み設定からSearch Planを生成してください。"
    )


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
  st.write(f"- context_type: `{enriched.get('context_type', active_context.get('context_type', '—'))}`")
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
  existing_draft: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
  st.markdown("### C. 一時検索runからテーマ案へ昇格")
  if not active_context:
    return {"promote_theme_draft": False, "theme_draft": None}
  run_origin = str(active_context.get("run_origin", "temporary_search") or "temporary_search")
  if run_origin != "temporary_search":
    st.caption("標準監視テーマ由来runのため、一時検索昇格は不要です。")
    return {"promote_theme_draft": False, "theme_draft": None}

  run_id = str(active_context.get("active_search_run_id", "") or "")
  if find_existing_draft_for_run(existing_draft, run_id):
    st.info(f"このSearch Run向けの未保存テーマ案が既にあります: `{existing_draft.get('draft_id', '')}`")
    st.caption("Dセクションで内容を確認・編集してください。重複作成はしません。")
    return {"promote_theme_draft": False, "theme_draft": None, "duplicate_skipped": True}

  confirm = st.checkbox(
    "一時検索条件をテーマ案として作成します。既存テーマは上書きしません",
    key="ui_promote_theme_confirm",
  )
  clicked = st.button("この検索条件からテーマ案を作成", key="btn_promote_theme_draft")
  if clicked and not confirm:
    st.warning("確認チェックボックスをオンにしてください。")
    return {"promote_theme_draft": False, "theme_draft": None}
  if clicked and confirm and search_request:
    from services_v9.study_demo_theme_lineage import default_saved_theme_fixture

    saved = default_saved_theme_fixture()
    draft = build_theme_draft_from_temporary_search(
      search_request,
      search_run_id=run_id,
      active_context=active_context,
      context_generation=active_context.get("active_context_generation"),
      old_theme_keywords=dict(saved.get("keywords", {}) or {}),
    )
    draft["loaded_into_editor"] = True
    return {"promote_theme_draft": True, "theme_draft": draft, "show_create_toast": True}
  return {"promote_theme_draft": False, "theme_draft": None}


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
  return {
    "saved_themes": [dict(saved)],
    "selected_saved_theme_id": str(saved.get("theme_id", "")),
    "saved_theme": dict(saved),
    "widget_theme": dict(saved),
    "unsaved_theme_draft": None,
    "watch_profile": None,
    "search_plan": None,
    "theme_saved_from_draft": False,
    "draft_message": None,
  }


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
