"""Live Tavily web search smoke test UI (Phase 25D)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from tech_cartography.auth.basic_auth import is_login_required
from tech_cartography.services.live_tavily_search import (
  MAX_MAX_RESULTS,
  MIN_MAX_RESULTS,
  SAFETY_NOTICE,
  clamp_max_results,
  live_tavily_block_message,
  run_live_tavily_search_smoke,
  save_live_tavily_search_result,
)
from tech_cartography.runtime.external_api_guard import check_live_tavily_smoke_allowed
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_warning_box
from tech_cartography.ui.login_ui import (
  can_use_admin_features,
  get_auth_role,
  is_basic_authenticated,
)


def should_show_live_tavily_smoke_test() -> bool:
  return is_login_required() and can_use_admin_features()


def render_live_tavily_smoke_test_section(
  *,
  project_root: Path | str,
  key_prefix: str = "live_tavily_smoke",
) -> None:
  if not should_show_live_tavily_smoke_test():
    return

  allowed, block_reason = check_live_tavily_smoke_allowed(
    login_required=is_login_required(),
    is_authenticated=is_basic_authenticated(),
    auth_role=get_auth_role(),
  )

  with st.expander("Live Web Search Smoke Test（管理者向け）", expanded=False):
    st.markdown(
      render_caution_box(
        "外部API（Tavily）を <strong>1回</strong> 呼び出します。"
        " API credit を消費します。"
        " 結果は Web Signal candidate であり、事実認定ではありません。"
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

    if st.button("Tavilyで1回検索", key=f"{key_prefix}_run", type="primary"):
      bounded = clamp_max_results(max_results)
      result = run_live_tavily_search_smoke(
        query,
        max_results=bounded,
        login_required=is_login_required(),
        is_authenticated=is_basic_authenticated(),
        auth_role=get_auth_role(),
      )
      if result.get("ok"):
        try:
          saved = save_live_tavily_search_result(result, project_root)
          result["saved_paths"] = saved
        except (OSError, ValueError) as exc:
          result["ok"] = False
          result["error"] = "save_failed"
          result["message"] = f"結果保存に失敗しました: {exc}"
      st.session_state[f"{key_prefix}_last_result"] = result

    last_result: dict[str, Any] | None = st.session_state.get(f"{key_prefix}_last_result")
    if not last_result:
      return

    if last_result.get("ok"):
      st.success(str(last_result.get("message") or "Tavily 検索完了"))
    else:
      st.warning(str(last_result.get("message") or live_tavily_block_message(last_result.get("error"))))

    rows = last_result.get("results") or []
    if rows:
      display_df = pd.DataFrame(rows)[["title", "url", "snippet", "score", "provider", "fetched_at"]]
      st.dataframe(display_df, width="stretch", hide_index=True)

    saved_paths = last_result.get("saved_paths") or {}
    if saved_paths:
      st.caption(f"保存: {saved_paths.get('json')}")
      st.caption(f"保存: {saved_paths.get('markdown')}")
