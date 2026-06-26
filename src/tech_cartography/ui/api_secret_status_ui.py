"""Admin-only API secret status UI (Phase 25C)."""

from __future__ import annotations

import streamlit as st

from tech_cartography.runtime.api_secret_config import get_api_secret_status
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box


def render_api_secret_status_expander(*, expanded: bool = False, key: str = "api_secret_status") -> None:
  """Show configured/missing state only — never secret values."""
  status = get_api_secret_status()
  execution_label = "無効（disabled）" if status["external_api_execution"] == "disabled" else "有効（enabled）"

  with st.expander("API設定状態（管理者向け）", expanded=expanded):
    st.markdown(
      render_caution_box(
        "APIキー本体は表示しません。Secret Manager / 環境変数の設定有無のみ確認できます。"
      ),
      unsafe_allow_html=True,
    )
    st.markdown(f"**外部API実行状態:** {execution_label}")

    rows = []
    for name, state in status["secrets"].items():
      label = "configured" if state == "configured" else "missing"
      rows.append({"APIキー名": name, "設定状態": label})

    st.dataframe(rows, width="stretch", hide_index=True)

    missing = status["missing_keys"]
    if missing:
      st.markdown(f"**不足しているキー:** {', '.join(missing)}")
    else:
      st.markdown("**不足しているキー:** なし")

    if status["external_api_execution"] == "disabled":
      st.markdown(
        render_info_box(
          "DISABLE_EXTERNAL_API=true のため、キーが設定されていても外部APIは実行されません。"
          " Phase 25C では確認のみです。"
        ),
        unsafe_allow_html=True,
      )
