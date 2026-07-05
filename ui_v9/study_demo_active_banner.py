"""Shared Active Analysis banner for Study Demo downstream tabs."""

from __future__ import annotations

from typing import Any, Mapping

import streamlit as st


def _format_provider_counts(raw_counts: Mapping[str, Any]) -> str:
  parts: list[str] = []
  for name, label in (("patent", "Patent"), ("paper", "Paper"), ("web", "Web")):
    value = raw_counts.get(name)
    parts.append(f"{label} {value if value is not None else 'unknown'}")
  return " / ".join(parts)


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

  resolved = dict((downstream_bundle or {}).get("resolved_context", {}) or {})
  if not resolved and downstream_bundle:
    resolved = {
      "raw_provider_counts": downstream_bundle.get("raw_provider_counts", {}),
      "stored_artifact_counts": downstream_bundle.get("stored_artifact_counts", {}),
      "integrated_ranked_count": downstream_bundle.get("integrated_ranked_count", 0),
      "tier_counts": downstream_bundle.get("tier_counts", {}),
      "count_validation_status": downstream_bundle.get("count_validation_status", ""),
      "count_validation_message": downstream_bundle.get("count_validation_message", ""),
    }

  tier_counts = dict(resolved.get("tier_counts", {}) or {})
  raw_provider_counts = dict(resolved.get("raw_provider_counts", {}) or {})
  stored_artifact_counts = dict(resolved.get("stored_artifact_counts", {}) or {})
  integrated_ranked_count = int(resolved.get("integrated_ranked_count", 0) or 0)

  lines = [
    "**現在の分析対象: 一時検索**",
    f"- search_run_id: `{active_context.get('active_search_run_id', '')}`",
    f"- テーマ: {active_context.get('theme', '')}",
    f"- 取得結果: {_format_provider_counts(raw_provider_counts)}",
  ]
  if any(stored_artifact_counts.values()):
    lines.append(
      "- 保存済み行数: "
      f"Patent {stored_artifact_counts.get('patent', 0)} / "
      f"Paper {stored_artifact_counts.get('paper', 0)} / "
      f"Web {stored_artifact_counts.get('web', 0)}"
    )
  lines.extend(
    [
      f"- 統合後: {integrated_ranked_count}件",
      f"- Tier: A {tier_counts.get('A', 0)} / B {tier_counts.get('B', 0)} / "
      f"C {tier_counts.get('C', 0)} / D {tier_counts.get('D', 0)}",
      f"- 選択日時: {active_context.get('selected_at', '')}",
      "- 外部検索: この画面表示では実行しない",
      "- 自動週次: 停止中",
      "- メール: 停止中",
    ]
  )
  st.info("\n".join(lines))

  validation_status = str(resolved.get("count_validation_status", "") or "")
  validation_message = str(resolved.get("count_validation_message", "") or "")
  if validation_status in {"mismatch", "stored_mismatch", "warning"} and validation_message:
    st.warning(validation_message)
  if raw_provider_counts and integrated_ranked_count:
    raw_total = sum(value for value in raw_provider_counts.values() if value is not None)
    if raw_total and raw_total != integrated_ranked_count:
      st.caption("取得件数と統合後件数が一致しない場合、重複除去・family統合等の可能性があります。")

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
