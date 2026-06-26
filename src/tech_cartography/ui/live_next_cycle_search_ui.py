"""Next Cycle Search UI — admin manual Tavily from approved Watch Profile Draft (Phase 25J)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from tech_cartography.auth.basic_auth import is_login_required
from tech_cartography.runtime.cloud_run_config import is_external_api_disabled
from tech_cartography.runtime.external_api_guard import check_live_tavily_smoke_allowed
from tech_cartography.runtime.user_context import resolve_user_context
from tech_cartography.services.live_next_cycle_search_plan import (
  SAFETY_NOTICE as PLAN_SAFETY_NOTICE,
  create_next_cycle_search_plan_from_latest_draft,
  find_latest_next_cycle_search_plan_path,
  load_latest_next_cycle_search_plan,
)
from tech_cartography.services.live_next_cycle_tavily_runner import (
  MAX_SELECTED_QUERIES,
  SAFETY_NOTICE as PACK_SAFETY_NOTICE,
  run_next_cycle_tavily_searches,
)
from tech_cartography.services.live_tavily_search import (
  MAX_MAX_RESULTS,
  MIN_MAX_RESULTS,
  clamp_max_results,
  live_tavily_block_message,
)
from tech_cartography.services.watch_profile_draft import find_latest_watch_profile_draft_path
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_warning_box
from tech_cartography.ui.login_ui import (
  can_use_admin_features,
  get_auth_role,
  is_basic_authenticated,
)


def should_show_live_next_cycle_search_ui() -> bool:
  return is_login_required() and can_use_admin_features()


def render_live_next_cycle_search_section(
  *,
  project_root: Path | str,
  key_prefix: str = "live_next_cycle_search",
) -> None:
  if not should_show_live_next_cycle_search_ui():
    return

  draft_path = find_latest_watch_profile_draft_path(project_root)
  plan_path = find_latest_next_cycle_search_plan_path(project_root)
  allowed, block_reason = check_live_tavily_smoke_allowed(
    login_required=is_login_required(),
    is_authenticated=is_basic_authenticated(),
    auth_role=get_auth_role(),
  )

  with st.expander("Next Cycle Search（承認済みWatch Profileから検索）", expanded=False):
    st.markdown(
      render_caution_box(
        "承認済み Watch Profile Draft から次回検索クエリ候補を作成し、"
        "<strong>選択した query だけ</strong> Tavily を手動実行します。"
        " 自動実行・scheduler・一斉送信はありません。"
        " APIキー本体は表示しません。"
      ),
      unsafe_allow_html=True,
    )
    st.markdown(render_info_box(PLAN_SAFETY_NOTICE), unsafe_allow_html=True)

    if not draft_path:
      st.markdown(
        render_warning_box("latest watch_profile_draft がありません。先に Watch Expansion を承認してください。"),
        unsafe_allow_html=True,
      )
      return

    st.caption(f"source watch_profile_draft: {draft_path}")

    theme_name = st.text_input(
      "theme_name",
      value="Carbon Fiber Intelligence",
      key=f"{key_prefix}_theme_name",
    )
    user_note = st.text_input(
      "user_note（任意）",
      value="",
      key=f"{key_prefix}_user_note",
    )

    if st.button("次回検索クエリ候補を作成", key=f"{key_prefix}_create_plan", type="secondary"):
      result = create_next_cycle_search_plan_from_latest_draft(
        output_root=project_root,
        theme_name=theme_name,
        user_note=user_note or None,
        login_required=is_login_required(),
        is_authenticated=is_basic_authenticated(),
        auth_role=get_auth_role(),
        user_context=resolve_user_context(),
      )
      st.session_state[f"{key_prefix}_last_plan_result"] = result
      if result.get("ok"):
        st.session_state[f"{key_prefix}_active_plan"] = result.get("plan")
        st.session_state[f"{key_prefix}_active_plan_path"] = (result.get("saved_paths") or {}).get("json")

    plan_result: dict[str, Any] | None = st.session_state.get(f"{key_prefix}_last_plan_result")
    if plan_result and not plan_result.get("ok"):
      st.warning(str(plan_result.get("message") or "クエリ候補作成に失敗しました。"))

    plan: dict[str, Any] | None = st.session_state.get(f"{key_prefix}_active_plan")
    active_plan_path = st.session_state.get(f"{key_prefix}_active_plan_path")
    if plan is None:
      plan = load_latest_next_cycle_search_plan(project_root)
      if plan and plan_path:
        active_plan_path = str(plan_path)

    query_candidates = list((plan or {}).get("query_candidates") or [])
    if not query_candidates:
      st.info("次回検索クエリ候補がありません。上のボタンで作成してください。")
      return

    if active_plan_path:
      st.caption(f"search plan: {active_plan_path}")

    display_df = pd.DataFrame(query_candidates)
    cols = [
      column
      for column in (
        "query_type",
        "query",
        "priority_label",
        "review_status",
        "safety_label",
        "reason",
      )
      if column in display_df.columns
    ]
    st.dataframe(display_df[cols], width="stretch", hide_index=True)

    if is_external_api_disabled():
      st.markdown(
        render_warning_box("外部API無効（DISABLE_EXTERNAL_API=true）— Tavily 検索は実行できません。"),
        unsafe_allow_html=True,
      )
    elif not allowed:
      st.markdown(
        render_warning_box(live_tavily_block_message(block_reason)),
        unsafe_allow_html=True,
      )

    selected_rows: list[dict[str, Any]] = []
    for row in query_candidates:
      query_id = str(row.get("query_id") or "")
      label = f"{row.get('query_type')}: {row.get('query')}"
      if st.checkbox(label, key=f"{key_prefix}_query_{query_id}"):
        selected_rows.append(row)

    if len(selected_rows) > MAX_SELECTED_QUERIES:
      st.warning(f"選択 query は最大 {MAX_SELECTED_QUERIES} 個までです。先頭 {MAX_SELECTED_QUERIES} 個のみ実行されます。")

    max_results = st.number_input(
      "max_results_per_query",
      min_value=MIN_MAX_RESULTS,
      max_value=MAX_MAX_RESULTS,
      value=2,
      step=1,
      key=f"{key_prefix}_max_results",
    )

    run_disabled = is_external_api_disabled() or not allowed or not selected_rows
    if st.button(
      "選択したクエリでTavily検索",
      key=f"{key_prefix}_run_tavily",
      type="primary",
      disabled=run_disabled,
    ):
      run_result = run_next_cycle_tavily_searches(
        selected_query_candidates=selected_rows,
        max_results_per_query=clamp_max_results(max_results),
        output_root=project_root,
        theme_name=str(plan.get("theme_name") or theme_name),
        source_plan_path=str(active_plan_path) if active_plan_path else None,
        source_watch_profile_draft_path=str(draft_path),
        login_required=is_login_required(),
        is_authenticated=is_basic_authenticated(),
        auth_role=get_auth_role(),
        user_context=resolve_user_context(),
      )
      st.session_state[f"{key_prefix}_last_run_result"] = run_result

    run_result: dict[str, Any] | None = st.session_state.get(f"{key_prefix}_last_run_result")
    if not run_result:
      st.caption(f"選択 query のみ実行（最大 {MAX_SELECTED_QUERIES} 件 / max_results 1〜3）。")
      return

    if run_result.get("ok"):
      st.success(str(run_result.get("message") or "検索完了"))
    else:
      st.warning(str(run_result.get("message") or "検索に失敗しました。"))

    query_runs = run_result.get("query_runs") or []
    if query_runs:
      st.dataframe(pd.DataFrame(query_runs), width="stretch", hide_index=True)

    candidates = run_result.get("candidates") or []
    if candidates:
      result_df = pd.DataFrame(candidates)
      show_cols = [
        column
        for column in ("query", "title", "url", "signal_type", "confidence_label", "review_status", "safety_label")
        if column in result_df.columns
      ]
      st.dataframe(result_df[show_cols], width="stretch", hide_index=True)

    saved_paths = run_result.get("saved_paths") or {}
    for label in ("json", "csv", "markdown"):
      if saved_paths.get(label):
        st.caption(f"保存 ({label}): {saved_paths[label]}")

    st.markdown(render_info_box(PACK_SAFETY_NOTICE), unsafe_allow_html=True)


def render_live_next_cycle_search_reports_section(
  *,
  project_root: Path | str,
  key_prefix: str = "reports_live_next_cycle_search",
) -> None:
  from tech_cartography.services.live_next_cycle_tavily_runner import load_latest_next_cycle_web_signal_pack

  pack = load_latest_next_cycle_web_signal_pack(project_root)
  if not pack:
    return

  with st.expander("Next Cycle Web Signal Pack", expanded=False):
    st.markdown(
      render_caution_box("Next Cycle 手動 Tavily 検索の結果 pack です。確定事実ではありません。"),
      unsafe_allow_html=True,
    )
    st.markdown(f"**theme_name:** {pack.get('theme_name')}")
    st.caption(f"source_type: {pack.get('source_type')} | fetched_at: {pack.get('fetched_at')}")
    candidates = pack.get("candidates") or []
    if candidates:
      df = pd.DataFrame(candidates)
      cols = [c for c in ("query", "title", "url", "signal_type", "confidence_label", "review_status") if c in df.columns]
      st.dataframe(df[cols], width="stretch", hide_index=True)
    st.markdown(render_info_box(str(pack.get("safety_notice") or PACK_SAFETY_NOTICE)), unsafe_allow_html=True)
