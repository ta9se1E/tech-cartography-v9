"""Shared Active Analysis banner for Study Demo downstream tabs."""

from __future__ import annotations

from typing import Any, Mapping

import streamlit as st


def render_active_analysis_banner(
  *,
  active_context: Mapping[str, Any] | None,
  downstream_bundle: Mapping[str, Any] | None = None,
) -> None:
  if not active_context:
    st.warning(
      "分析対象が未選択です。情報源タブで保存済み検索runを選択し、"
      "「この検索runを分析対象に設定」を押してください。"
    )
    return

  provider_counts = dict(active_context.get("provider_counts", {}) or {})
  tier_counts = dict(active_context.get("tier_counts", {}) or {})
  st.info(
    "\n".join(
      [
        "**現在の分析対象: 一時検索**",
        f"- search_run_id: `{active_context.get('active_search_run_id', '')}`",
        f"- テーマ: {active_context.get('theme', '')}",
        f"- Patent / Paper / Web: {provider_counts.get('patent', 0)} / {provider_counts.get('paper', 0)} / {provider_counts.get('web', 0)}",
        f"- Tier A / B / C / D: {tier_counts.get('A', 0)} / {tier_counts.get('B', 0)} / {tier_counts.get('C', 0)} / {tier_counts.get('D', 0)}",
        f"- 選択日時: {active_context.get('selected_at', '')}",
        "- 外部検索: この画面表示では実行しない",
        "- 自動週次: 停止中",
        "- メール: 停止中",
      ]
    )
  )
  if downstream_bundle:
    weekly_state = dict(downstream_bundle.get("weekly_state", {}) or {})
    if weekly_state.get("state") == "initial_baseline":
      st.caption(str(weekly_state.get("message", "")))


def render_study_demo_mode_legend() -> None:
  st.caption(
    "一時キーワード検索: Patent / Paper / Web 有効 | "
    "ページ表示・履歴表示: 外部APIを実行しない | "
    "自動週次実行: 停止中 | メール送信: 停止中 | 本番環境: 変更しない"
  )
