"""Approved member live digest email send UI (Phase 25Q)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from tech_cartography.auth.basic_auth import is_login_required
from tech_cartography.runtime.approved_member_send_config import (
  approved_member_block_message,
  get_approved_member_send_status,
  get_confirmation_text,
  is_approved_member_send_enabled,
  parse_approved_member_emails,
)
from tech_cartography.runtime.cloud_run_config import is_email_send_disabled
from tech_cartography.runtime.user_context import resolve_user_context
from tech_cartography.services.live_approved_member_email_sender import (
  ACTION_TYPE,
  send_live_digest_email_to_approved_member,
)
from tech_cartography.services.live_email_sender import (
  LIVE_EMAIL_SAFETY_NOTICE_JA,
  build_outbound_body,
  load_latest_digest_for_send,
)
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_warning_box
from tech_cartography.ui.email_operation_status_ui import render_email_operation_status_compact
from tech_cartography.ui.login_ui import (
  can_use_admin_features,
  get_auth_role,
  is_app_authenticated,
)


def should_show_live_approved_member_email_send_ui() -> bool:
  return is_login_required() and can_use_admin_features()


def render_live_approved_member_email_send_section(
  *,
  project_root: Path | str,
  key_prefix: str = "live_approved_member_email_send",
) -> None:
  if not should_show_live_approved_member_email_send_ui():
    return

  preview, preview_path = load_latest_digest_for_send(project_root)
  status = get_approved_member_send_status()
  approved_emails = parse_approved_member_emails()
  confirmation_text = get_confirmation_text()
  user_context = resolve_user_context()

  with st.expander("Approved Member Digest Send（承認済みメンバーへ手動送信 / IAP本番向け）", expanded=False):
    render_email_operation_status_compact(project_root=project_root, key_prefix=f"{key_prefix}_ops_status")
    st.markdown(
      render_caution_box(
        "<strong>承認済みメンバーへ1通だけ</strong> 手動送信します（IAP admin 向け）。"
        " self-only 送信とは別経路です。"
        " 一斉送信・自由入力送信・scheduler 連携はありません。"
      ),
      unsafe_allow_html=True,
    )
    st.markdown(render_info_box(LIVE_EMAIL_SAFETY_NOTICE_JA), unsafe_allow_html=True)
    st.caption(f"action_type: {ACTION_TYPE}")

    if not is_approved_member_send_enabled():
      st.markdown(
        render_warning_box("承認済みメンバー送信は無効です（ENABLE_APPROVED_MEMBER_SEND=false）。"),
        unsafe_allow_html=True,
      )
    elif is_email_send_disabled():
      st.markdown(
        render_warning_box("メール送信停止中です（DISABLE_EMAIL_SEND=true）。"),
        unsafe_allow_html=True,
      )
    elif not approved_emails:
      st.markdown(
        render_warning_box(approved_member_block_message("approved_list_empty")),
        unsafe_allow_html=True,
      )
    elif status.get("missing_smtp_fields"):
      st.markdown(
        render_warning_box(approved_member_block_message("missing_smtp_config")),
        unsafe_allow_html=True,
      )
      st.caption(f"SMTP 不足: {', '.join(status['missing_smtp_fields'])}")

    if get_auth_role() != "admin" and not user_context.get("is_admin"):
      st.markdown(
        render_warning_box(approved_member_block_message("member_not_allowed")),
        unsafe_allow_html=True,
      )
      return

    if not preview or not preview_path:
      st.markdown(
        render_warning_box("latest live_digest_preview がありません。先にメール下書きを作成してください。"),
        unsafe_allow_html=True,
      )
      return

    st.caption(f"preview: {preview_path}")
    st.caption(
      f"auth: provider={user_context.get('auth_provider')} "
      f"user_id={user_context.get('user_id')} role={user_context.get('role')}"
    )
    st.markdown(f"**subject:** {preview.get('subject')}")
    body_preview = build_outbound_body(
      plain_text_body=str(preview.get("body") or preview.get("plain_text_body") or ""),
    )
    with st.expander("body preview", expanded=False):
      st.text(body_preview[:4000])

    if not approved_emails:
      return

    recipient = st.selectbox(
      "送信先（承認済みメンバー — 自由入力不可）",
      options=approved_emails,
      key=f"{key_prefix}_recipient",
    )
    confirm_text = st.text_input(
      f"確認テキスト（{confirmation_text} と完全一致）",
      value="",
      key=f"{key_prefix}_confirm",
    )

    send_disabled = (
      not is_approved_member_send_enabled()
      or is_email_send_disabled()
      or not approved_emails
      or confirm_text != confirmation_text
      or not recipient
    )

    if st.button(
      "承認済みメンバーへDigestを送信",
      key=f"{key_prefix}_send",
      type="primary",
      disabled=send_disabled,
    ):
      result = send_live_digest_email_to_approved_member(
        recipient=recipient,
        confirm_text=confirm_text,
        output_root=project_root,
        login_required=is_login_required(),
        is_authenticated=is_app_authenticated(),
        auth_role=get_auth_role(),
        preview=preview,
        preview_source_path=preview_path,
        user_context=user_context,
      )
      st.session_state[f"{key_prefix}_last_result"] = result

    last_result: dict[str, Any] | None = st.session_state.get(f"{key_prefix}_last_result")
    if not last_result:
      st.caption("これは送信されません — 上記ボタンで明示確認後のみ1通送信します。")
      return

    if last_result.get("ok"):
      st.success(str(last_result.get("message") or "送信完了"))
      if last_result.get("reset_required"):
        st.markdown(
          render_caution_box(
            str(last_result.get("post_send_safety_note") or "送信テスト後はメール送信をOFFに戻してください。")
          ),
          unsafe_allow_html=True,
        )
        with st.expander("安全復帰コマンド（手動実行）", expanded=True):
          st.code(str(last_result.get("reset_command_hint") or ""), language="bash")
    else:
      st.warning(str(last_result.get("message") or "送信できませんでした"))

    if last_result.get("action_type"):
      st.caption(f"recorded action_type: {last_result.get('action_type')}")
    if last_result.get("recipient_masked"):
      st.caption(f"recipient_masked: {last_result['recipient_masked']}")
    saved_paths = last_result.get("saved_paths") or {}
    for label in ("json", "markdown"):
      if saved_paths.get(label):
        st.caption(f"送信ログ ({label}): {saved_paths[label]}")
