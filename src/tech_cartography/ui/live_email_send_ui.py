"""Self-only live digest email send UI (Phase 25G)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from tech_cartography.auth.basic_auth import is_login_required
from tech_cartography.runtime.auth_provider_config import get_auth_provider_mode
from tech_cartography.runtime.email_send_config import (
  get_email_send_status,
  is_email_send_disabled,
  parse_recipient_allowlist,
  self_only_block_message,
)
from tech_cartography.runtime.user_context import resolve_user_context
from tech_cartography.services.live_email_sender import (
  CONFIRMATION_TEXT,
  LIVE_EMAIL_SAFETY_NOTICE_JA,
  build_outbound_body,
  load_latest_digest_for_send,
  send_live_digest_email_self_only,
)
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_warning_box
from tech_cartography.ui.login_ui import (
  can_use_admin_features,
  get_auth_role,
  is_app_authenticated,
  is_iap_authenticated,
)


def should_show_live_email_send_ui() -> bool:
  if not (is_login_required() and can_use_admin_features()):
    return False
  # IAP mode: use Approved Member Send to avoid routing confusion (Phase 25Q.1).
  if get_auth_provider_mode() == "iap" and is_iap_authenticated():
    return False
  return True


def render_live_email_send_section(
  *,
  project_root: Path | str,
  key_prefix: str = "live_email_send",
) -> None:
  if not should_show_live_email_send_ui():
    return

  preview, preview_path = load_latest_digest_for_send(project_root)
  status = get_email_send_status()
  allowlist = parse_recipient_allowlist()
  default_recipient = allowlist[0] if allowlist else ""
  user_context = resolve_user_context()

  with st.expander("Self-only Email Send Test（自分宛てのみ / Basic向け）", expanded=False):
    st.markdown(
      render_caution_box(
        "<strong>自分宛てに1通だけ</strong> テスト送信します（Basic Login 向け）。"
        " IAP 本番では <strong>Approved Member Digest Send</strong> を使用してください。"
        " 一斉送信・自動送信・scheduler 連携はありません。"
      ),
      unsafe_allow_html=True,
    )
    st.markdown(render_info_box(LIVE_EMAIL_SAFETY_NOTICE_JA), unsafe_allow_html=True)

    if is_email_send_disabled():
      st.markdown(
        render_warning_box(self_only_block_message("disabled_by_env")),
        unsafe_allow_html=True,
      )
    elif not status.get("self_only_mode"):
      st.markdown(
        render_warning_box(self_only_block_message("invalid_send_mode")),
        unsafe_allow_html=True,
      )
    elif status.get("missing_smtp_fields"):
      st.caption(f"SMTP 不足: {', '.join(status['missing_smtp_fields'])}")

    if not preview or not preview_path:
      st.markdown(
        render_warning_box("latest live_digest_preview がありません。先にメール下書きを作成してください。"),
        unsafe_allow_html=True,
      )
      return

    st.caption(f"preview: {preview_path}")
    st.caption(f"action_type: self_only_email_send")
    st.markdown(f"**subject:** {preview.get('subject')}")
    body_preview = build_outbound_body(
      plain_text_body=str(preview.get("body") or preview.get("plain_text_body") or ""),
    )
    with st.expander("body preview", expanded=False):
      st.text(body_preview[:4000])

    recipient = st.text_input(
      "recipient（allowlist内のみ）",
      value=default_recipient,
      key=f"{key_prefix}_recipient",
    )
    confirm_text = st.text_input(
      f"確認テキスト（{CONFIRMATION_TEXT} と完全一致）",
      value="",
      key=f"{key_prefix}_confirm",
    )

    send_disabled = (
      is_email_send_disabled()
      or not status.get("self_only_mode")
      or confirm_text != CONFIRMATION_TEXT
      or not recipient.strip()
    )

    if st.button(
      "自分宛てに1通送信（self-only）",
      key=f"{key_prefix}_send",
      type="primary",
      disabled=send_disabled,
    ):
      result = send_live_digest_email_self_only(
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
    else:
      st.warning(str(last_result.get("message") or "送信できませんでした"))

    if last_result.get("recipient_masked"):
      st.caption(f"recipient_masked: {last_result['recipient_masked']}")
    saved_paths = last_result.get("saved_paths") or {}
    for label in ("json", "markdown"):
      if saved_paths.get(label):
        st.caption(f"送信ログ ({label}): {saved_paths[label]}")
