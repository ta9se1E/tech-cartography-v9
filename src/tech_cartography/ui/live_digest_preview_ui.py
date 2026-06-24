"""Live digest mail preview UI — no email send (Phase 25F)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from tech_cartography.auth.basic_auth import is_login_required
from tech_cartography.runtime.user_context import resolve_user_context
from tech_cartography.services.live_digest_preview import (
  SAFETY_NOTICE,
  can_create_live_digest_preview,
  create_live_digest_preview_from_latest_pack,
  email_send_is_disabled,
  load_latest_live_digest_preview,
)
from tech_cartography.services.live_web_signal_pack import (
  find_latest_live_web_signal_pack_path,
  load_latest_live_web_signal_pack,
)
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_warning_box
from tech_cartography.ui.login_ui import (
  can_use_admin_features,
  get_auth_role,
  is_basic_authenticated,
)


def should_show_live_digest_preview_ui() -> bool:
  return is_login_required() and can_use_admin_features()


def render_live_digest_preview_section(
  *,
  project_root: Path | str,
  key_prefix: str = "live_digest_preview",
) -> None:
  if not should_show_live_digest_preview_ui():
    return

  pack_path = find_latest_live_web_signal_pack_path(project_root)
  pack = load_latest_live_web_signal_pack(project_root)
  _allowed, guard_message = can_create_live_digest_preview()

  with st.expander("Live Digest Mail Preview（送信なし）", expanded=False):
    st.markdown(
      render_caution_box(
        "<strong>これは送信されません。</strong> "
        "週次 Digest メールの下書きプレビューを作成・保存するのみです。"
        " DISABLE_EMAIL_SEND=true でも preview 作成は可能です。"
      ),
      unsafe_allow_html=True,
    )

    if email_send_is_disabled():
      st.caption("メール送信: 無効（DISABLE_EMAIL_SEND=true）— preview のみ")

    if not pack_path or not pack:
      st.markdown(
        render_warning_box("latest live_web_signal_pack が見つかりません。先に Web Signal Pack を作成してください。"),
        unsafe_allow_html=True,
      )
      return

    st.caption(f"source pack: {pack_path}")
    st.markdown(f"**theme_name:** {pack.get('theme_name')}")
    st.caption(guard_message)

    recipient_group_name = st.text_input(
      "recipient_group_name",
      value="炭素繊維R&Dチーム",
      key=f"{key_prefix}_recipient_group",
    )
    user_note = st.text_area(
      "user_note（任意）",
      value="",
      key=f"{key_prefix}_user_note",
      height=80,
    )

    if st.button("メール下書きを作成", key=f"{key_prefix}_create", type="primary"):
      result = create_live_digest_preview_from_latest_pack(
        output_root=project_root,
        theme_name=str(pack.get("theme_name") or ""),
        recipient_group_name=recipient_group_name,
        user_note=user_note,
        login_required=is_login_required(),
        is_authenticated=is_basic_authenticated(),
        auth_role=get_auth_role(),
        user_context=resolve_user_context(),
      )
      st.session_state[f"{key_prefix}_last_result"] = result

    last_result: dict[str, Any] | None = st.session_state.get(f"{key_prefix}_last_result")
    if not last_result:
      return

    if last_result.get("ok"):
      st.success(str(last_result.get("message") or "プレビュー作成完了"))
    else:
      st.warning(str(last_result.get("message") or "プレビュー作成に失敗しました"))

    preview = last_result.get("preview") or {}
    if preview.get("subject"):
      st.markdown(f"**subject:** {preview['subject']}")
    if preview.get("markdown_body"):
      st.markdown(preview["markdown_body"])

    if preview.get("web_signal_section_markdown"):
      st.markdown("---")
      st.markdown(preview["web_signal_section_markdown"])
    elif preview.get("uses_web_signals") is False:
      st.caption("Web Signal候補はまだ収集されていません。")

    saved_paths = last_result.get("saved_paths") or {}
    for label in ("json", "markdown", "text"):
      if saved_paths.get(label):
        st.caption(f"保存 ({label}): {saved_paths[label]}")

    st.markdown(render_info_box(SAFETY_NOTICE), unsafe_allow_html=True)


def render_live_digest_preview_reports_section(
  *,
  project_root: Path | str,
  key_prefix: str = "reports_live_digest_preview",
) -> None:
  """Show latest digest preview on reports tab (analyst/live, not demo)."""
  preview = load_latest_live_digest_preview(project_root)
  if not preview:
    return

  with st.expander("Live Digest Preview（送信なし）", expanded=False):
    st.markdown(
      render_caution_box("これは送信ログではなく、下書きプレビューです。"),
      unsafe_allow_html=True,
    )
    st.markdown(f"**subject:** {preview.get('subject')}")
    st.caption(f"created_at: {preview.get('created_at')}")

    key_signals = preview.get("key_signals") or []
    if key_signals:
      display_df = pd.DataFrame(key_signals)
      cols = [c for c in ("title", "url", "signal_type", "confidence_label", "review_status", "why_review") if c in display_df.columns]
      st.dataframe(display_df[cols], use_container_width=True, hide_index=True)

    next_actions = preview.get("next_actions") or []
    if next_actions:
      st.markdown("**next_actions**")
      for action in next_actions:
        st.markdown(f"- {action}")

    st.markdown(render_info_box(str(preview.get("safety_notice") or SAFETY_NOTICE)), unsafe_allow_html=True)

  from tech_cartography.ui.live_approved_member_email_send_ui import render_live_approved_member_email_send_section

  render_live_approved_member_email_send_section(
    project_root=project_root,
    key_prefix=f"{key_prefix}_approved_member_email_send",
  )
  from tech_cartography.ui.live_email_send_ui import render_live_email_send_section

  render_live_email_send_section(project_root=project_root, key_prefix=f"{key_prefix}_email_send")
