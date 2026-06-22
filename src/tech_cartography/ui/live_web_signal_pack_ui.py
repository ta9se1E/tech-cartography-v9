"""Live Web Signal Pack UI (Phase 25E)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from tech_cartography.auth.basic_auth import is_login_required
from tech_cartography.runtime.external_api_guard import check_live_tavily_smoke_allowed
from tech_cartography.services.live_tavily_search import (
  MAX_MAX_RESULTS,
  MIN_MAX_RESULTS,
  clamp_max_results,
  live_tavily_block_message,
)
from tech_cartography.runtime.user_context import resolve_user_context
from tech_cartography.services.live_web_signal_pack import (
  SAFETY_NOTICE,
  load_latest_live_web_signal_pack,
  run_live_web_signal_pack,
)
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_warning_box
from tech_cartography.ui.login_ui import (
  can_use_admin_features,
  get_auth_role,
  is_basic_authenticated,
)

LIVE_CANDIDATE_COLUMNS = (
  "title",
  "url",
  "snippet",
  "signal_type",
  "confidence_label",
  "review_status",
)


def should_show_live_web_signal_pack_ui() -> bool:
  return is_login_required() and can_use_admin_features()


def render_live_web_signal_pack_section(
  *,
  project_root: Path | str,
  key_prefix: str = "live_web_signal_pack",
) -> None:
  if not should_show_live_web_signal_pack_ui():
    return

  allowed, block_reason = check_live_tavily_smoke_allowed(
    login_required=is_login_required(),
    is_authenticated=is_basic_authenticated(),
    auth_role=get_auth_role(),
  )

  with st.expander("Live Web Signal Pack（管理者向け）", expanded=False):
    st.markdown(
      render_caution_box(
        "外部API（Tavily）を <strong>1回</strong> 呼び出し、結果を Web Signal candidate pack として保存します。"
        " API credit を消費します。"
        " 結果は確認候補であり、事実認定ではありません。"
        " APIキー本体は表示しません。"
      ),
      unsafe_allow_html=True,
    )

    if not allowed:
      st.markdown(
        render_warning_box(live_tavily_block_message(block_reason)),
        unsafe_allow_html=True,
      )
      return

    theme_name = st.text_input(
      "theme_name",
      value="Carbon Fiber Intelligence",
      key=f"{key_prefix}_theme_name",
    )
    query = st.text_input(
      "検索クエリ",
      value="carbon fiber patent intelligence",
      key=f"{key_prefix}_query",
    )
    max_results = st.number_input(
      "max_results",
      min_value=MIN_MAX_RESULTS,
      max_value=MAX_MAX_RESULTS,
      value=2,
      step=1,
      key=f"{key_prefix}_max_results",
    )
    st.caption("search_depth: basic（固定）")
    st.markdown(render_info_box(SAFETY_NOTICE), unsafe_allow_html=True)

    if st.button("Web Signal Packを作成", key=f"{key_prefix}_run", type="primary"):
      result = run_live_web_signal_pack(
        theme_name=theme_name,
        query=query,
        max_results=clamp_max_results(max_results),
        login_required=is_login_required(),
        is_authenticated=is_basic_authenticated(),
        auth_role=get_auth_role(),
        output_root=project_root,
        user_context=resolve_user_context(),
      )
      st.session_state[f"{key_prefix}_last_result"] = result

    last_result: dict[str, Any] | None = st.session_state.get(f"{key_prefix}_last_result")
    if not last_result:
      return

    if last_result.get("ok"):
      st.success(str(last_result.get("message") or "Web Signal Pack 作成完了"))
    else:
      st.warning(str(last_result.get("message") or live_tavily_block_message(last_result.get("error"))))

    rows = last_result.get("candidates") or []
    if rows:
      display_df = pd.DataFrame(rows)
      cols = [c for c in LIVE_CANDIDATE_COLUMNS if c in display_df.columns]
      st.dataframe(display_df[cols], use_container_width=True, hide_index=True)

    saved_paths = last_result.get("saved_paths") or {}
    for label in ("json", "csv", "markdown"):
      if saved_paths.get(label):
        st.caption(f"保存 ({label}): {saved_paths[label]}")

    next_actions = last_result.get("next_actions") or []
    if next_actions:
      st.markdown("**Next actions**")
      for action in next_actions:
        st.markdown(f"- {action}")


def render_live_web_signal_candidates_section(
  *,
  project_root: Path | str,
  key_prefix: str = "live_web_signal_candidates",
) -> None:
  """Show latest live pack on market tab (analyst/live only — not demo)."""
  pack = load_latest_live_web_signal_pack(project_root)
  if not pack:
    return

  candidates = pack.get("candidates") or []
  if not candidates:
    return

  with st.expander("Live Web Signal Candidates（確認候補）", expanded=False):
    st.markdown(
      render_caution_box(
        "Live Tavily 検索から生成した <strong>確認候補</strong> です。"
        " 直接関係・市場真実・法的判断の証明ではありません。"
      ),
      unsafe_allow_html=True,
    )
    st.caption(
      f"theme: {pack.get('theme_name')} | query: {pack.get('query')} | fetched_at: {pack.get('fetched_at')}"
    )
    display_df = pd.DataFrame(candidates)
    cols = [c for c in LIVE_CANDIDATE_COLUMNS if c in display_df.columns]
    st.dataframe(display_df[cols], use_container_width=True, hide_index=True)
    st.markdown(render_info_box(str(pack.get("safety_notice") or SAFETY_NOTICE)), unsafe_allow_html=True)

    next_actions = pack.get("next_actions") or []
    if next_actions:
      st.markdown("**Next actions**")
      for action in next_actions:
        st.markdown(f"- {action}")
