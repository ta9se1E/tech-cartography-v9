"""Lineage banner for Study Demo downstream tabs."""

from __future__ import annotations

from typing import Any, Mapping

import streamlit as st

from services_v9.study_demo_theme_lineage import summarize_lineage_status


def _short(value: Any, length: int = 8) -> str:
  text = str(value or "")
  return text[:length] if text else "—"


def render_lineage_banner(
  *,
  active_context: Mapping[str, Any] | None,
  downstream_bundle: Mapping[str, Any] | None = None,
) -> None:
  if not active_context:
    return

  bundle = dict(downstream_bundle or {})
  enriched = dict(bundle.get("enriched_context", {}) or active_context)
  status = dict(bundle.get("lineage_status", {}) or summarize_lineage_status(enriched))
  lineage_state = str(status.get("lineage_status", enriched.get("lineage_status", "")) or "unavailable")

  if lineage_state == "mismatch":
    st.error(
      "Theme / Watch Profile / Search Planの署名が一致しません。"
      "自動修復や検索実行は行いません。"
    )
    mismatched = status.get("mismatched_fields", [])
    if mismatched:
      st.caption(f"不一致: {', '.join(str(item) for item in mismatched)}")

  lines = [
    f"**作成経路:** {status.get('creation_path_label', enriched.get('run_origin', 'unknown'))}",
    f"- search_run_id: `{active_context.get('active_search_run_id', '')}`",
    f"- run_origin: `{enriched.get('run_origin', 'temporary_search')}`",
    f"- context_type: `{enriched.get('context_type', active_context.get('context_type', '—'))}`",
    f"- lineage status: `{lineage_state}`",
    f"- Active Runテーマ: {active_context.get('theme', '')}",
  ]

  if lineage_state == "temporary_unconnected":
    lines.extend(
      [
        f"- Watch Profile接続: {status.get('watch_profile_connection', '未接続')}",
        f"- 標準監視テーマ: {status.get('standard_theme_name', '未設定')}",
        "- 一時検索runは標準監視テーマと未接続です。",
      ]
    )
  elif lineage_state == "connected":
    lines.extend(
      [
        f"- Theme version: {enriched.get('source_theme_version', '—')}",
        f"- Watch Profile version: {enriched.get('source_watch_profile_version', '—')}",
        f"- Search Plan ID: `{enriched.get('source_search_plan_id', '—')}`",
        f"- Theme signature: `{_short(enriched.get('source_theme_signature'))}`",
      ]
    )
  elif lineage_state == "partial":
    lines.append(f"- Watch Profile接続: {status.get('watch_profile_connection', '部分接続')}")

  st.info("\n".join(lines))

  if lineage_state == "temporary_unconnected":
    st.caption(
      "改善提案を適用するには、テーマ設定タブで「この検索条件からテーマ案を作成」してください。"
    )
