"""Shared compact Study Demo UI components for Simple Mode."""

from __future__ import annotations

from typing import Any, Mapping, Sequence

import streamlit as st

from services_v9.human_datetime import format_datetime_jst
from services_v9.human_digest_builder import short_theme_label
from services_v9.study_demo_auth import format_expiry_jst
from services_v9.study_demo_config import is_study_demo_shared_state
from services_v9.study_demo_run_metrics import format_unknown_metric
from services_v9.study_demo_ui_mode import should_show_technical_ids
from ui_v9.labels import action_label_ja, score_level_label_ja, status_label_ja, type_label_ja
from ui_v9.study_demo_source_link import render_external_source_link


def render_compact_header(
  *,
  environ: Mapping[str, str] | None = None,
  source_info: Mapping[str, Any] | None = None,
  theme_state: Mapping[str, Any] | None = None,
) -> None:
  active_context = dict((source_info or {}).get("active_context", {}) or {})
  saved_theme = dict((theme_state or {}).get("saved_theme", {}) or {})
  theme_name = str(saved_theme.get("name", "") or active_context.get("theme", "") or "未設定")
  theme_short = short_theme_label(theme_name)
  updated = format_datetime_jst(active_context.get("selected_at", "") or saved_theme.get("updated_at", ""))
  lineage = str(active_context.get("lineage_status", "") or "")
  status_label = "接続済み" if lineage == "connected" else "要確認"

  header_left, header_right = st.columns([4, 1])
  with header_left:
    st.markdown("### Tech Cartography")
    st.caption("DEMO")
    st.markdown(f"**{theme_short}**")
    if theme_short != theme_name:
      st.caption(theme_name)
    st.caption(f"保存済み実データ | {status_label} | {updated}")
  with header_right:
    from services_v9.study_demo_auth import SESSION_AUTHENTICATED_KEY, clear_authentication

    if st.button("ログアウト", key="v9_study_demo_logout_button"):
      clear_authentication(st.session_state)
      st.session_state.pop(SESSION_AUTHENTICATED_KEY, None)
      st.rerun()

  expiry_text = format_expiry_jst(environ=environ)
  shared_note = (
    "変更内容は参加者全員に共有されます"
    if is_study_demo_shared_state(environ)
    else "共有状態設定を確認してください"
  )
  with st.expander("デモ環境について", expanded=False):
    st.markdown(
      "\n".join(
        [
          "**勉強会用デモ環境**",
          "",
          "・保存済み実データを使用しています",
          f"・{shared_note}",
          "・一時キーワード検索: Patent / Paper / Web 有効",
          "・ページ表示・履歴表示: 外部APIを実行しない",
          "・自動週次実行: 停止中",
          "・メール送信: 停止中",
          f"・公開終了日時: {expiry_text}",
          "",
          "v9は軽量なR&Dシグナル監視プレビューです。"
          "PDF/OCR深掘り、クレーム解釈、法的判断、FTO判断、侵害判断、"
          "特許性判断、技術的妥当性の証明は行いません。",
        ]
      )
    )


def render_context_bar(
  *,
  source_info: Mapping[str, Any],
  theme_state: Mapping[str, Any] | None = None,
) -> None:
  active_context = dict(source_info.get("active_context", {}) or {})
  saved_theme = dict((theme_state or {}).get("saved_theme", {}) or {})
  theme_name = str(saved_theme.get("name", "") or active_context.get("theme", "") or "未設定")
  lineage = str(active_context.get("lineage_status", "") or "")
  status_label = "接続済み" if lineage == "connected" else "要確認"
  updated = format_datetime_jst(active_context.get("selected_at", "") or saved_theme.get("updated_at", ""))
  st.info(f"**{short_theme_label(theme_name)}** | 最終更新: {updated} | 状態: {status_label}")


def render_provider_cards(*, metrics: Mapping[str, Any]) -> None:
  provider_counts = dict(metrics.get("provider_counts", {}) or {})
  provider_success = dict(metrics.get("provider_success", {}) or {})
  cols = st.columns(3)
  for column, (name, label) in zip(cols, (("patent", "Patent"), ("paper", "Paper"), ("web", "Web"))):
    item = dict(provider_success.get(name, {}) or {})
    status = str(item.get("status", "") or "—")
    status_ja = "成功" if status == "success" else status
    count = format_unknown_metric(provider_counts.get(name))
    with column:
      st.metric(label, f"{count}件")
      st.caption(status_ja)


def render_theme_summary_card(
  *,
  saved_theme: Mapping[str, Any],
  lineage_status: str = "",
  source_types: Sequence[str] | None = None,
) -> None:
  sources = ", ".join(str(item).title() for item in (source_types or ("Patent", "Paper", "Web")))
  status_label = "接続済み" if lineage_status == "connected" else "要確認"
  st.markdown(f"#### {saved_theme.get('name', '未設定')}")
  st.write(str(saved_theme.get("description", "") or ""))
  st.caption(f"情報源: {sources} | 状態: {status_label}")
  if should_show_technical_ids():
    with st.expander("技術情報（Theme）", expanded=False):
      st.write(f"- theme_id: `{saved_theme.get('theme_id', '')}`")
      st.write(f"- version: `{saved_theme.get('theme_version', '')}`")
      st.write(f"- signature: `{str(saved_theme.get('theme_signature', ''))[:12]}`")


def render_signal_card_simple(
  *,
  signal: Any,
  display_signal: Mapping[str, Any] | None = None,
  explanation: Mapping[str, Any] | None = None,
  search_run_id: str = "",
  key_namespace: str,
  index: int,
) -> None:
  title = str(getattr(signal, "title", "") or (display_signal or {}).get("title", "") or "").strip()
  if not title:
    return
  related_level = score_level_label_ja(str((explanation or {}).get("score_level", "") or ""))
  related_text = f" | 関連度 {related_level}" if related_level else ""
  tier = str((display_signal or {}).get("relevance_tier", "") or getattr(signal, "tier", "") or "")
  tier_text = f" | Tier {tier}" if tier else ""
  st.markdown(f"**{title}**")
  st.caption(
    f"{type_label_ja(signal.type)} | {status_label_ja(signal.status)} | "
    f"{action_label_ja(signal.action)}{related_text}{tier_text}"
  )
  st.write(signal.why_read)
  st.write(f"次の行動: {signal.next_action}")
  render_external_source_link(
    signal,
    key_namespace=key_namespace,
    search_run_id=search_run_id,
    label="出典URLを開く",
  )
  signal_id = str((display_signal or {}).get("id", "") or "")
  if signal_id:
    with st.expander("レビュー", expanded=False):
      try:
        from ui_v9.study_demo_review_proposals_ui import render_enhanced_review_input

        render_enhanced_review_input(
          signal=dict(display_signal or {}),
          signal_id=signal_id,
          search_run_id=search_run_id,
          context_generation=None,
          active_run_id=search_run_id,
        )
      except Exception:
        pass
  if should_show_technical_ids():
    with st.expander("技術情報（シグナル）", expanded=False):
      st.write(f"- signal_id: `{signal_id}`")
      st.write(f"- score: `{getattr(signal, 'score', '')}`")
      if explanation:
        st.json(dict(explanation))


def render_advanced_details(*, title: str, lines: Sequence[str]) -> None:
  if not should_show_technical_ids():
    return
  with st.expander(title, expanded=False):
    for line in lines:
      st.write(line)


__all__ = [
  "render_advanced_details",
  "render_compact_header",
  "render_context_bar",
  "render_provider_cards",
  "render_signal_card_simple",
  "render_theme_summary_card",
]
