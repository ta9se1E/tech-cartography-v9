"""Email operation safety status UI (Phase 25Q.2)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from tech_cartography.auth.basic_auth import is_login_required
from tech_cartography.runtime.email_operation_status import (
  SAFETY_LEVEL_CONTROLLED,
  SAFETY_LEVEL_MISCONFIGURED,
  SAFETY_LEVEL_RISKY,
  SAFETY_LEVEL_SAFE_OFF,
  build_post_send_reset_command,
  get_email_operation_status,
  safety_level_label_ja,
)
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_warning_box
from tech_cartography.ui.login_ui import can_use_admin_features


def should_show_email_operation_status_ui() -> bool:
  return is_login_required() and can_use_admin_features()


def _render_status_banner(status: dict[str, Any]) -> None:
  level = str(status.get("safety_level") or "")
  message = str(status.get("status_message") or "")
  if level == SAFETY_LEVEL_SAFE_OFF:
    st.markdown(render_info_box(f"✅ {message}"), unsafe_allow_html=True)
  elif level == SAFETY_LEVEL_CONTROLLED:
    st.markdown(render_caution_box(f"⚠️ {message}"), unsafe_allow_html=True)
  elif level == SAFETY_LEVEL_RISKY:
    st.markdown(
      render_warning_box(f"🔴 {message}"),
      unsafe_allow_html=True,
    )
  elif level == SAFETY_LEVEL_MISCONFIGURED:
    st.markdown(render_warning_box(f"🟠 {message}"), unsafe_allow_html=True)
  else:
    st.markdown(render_info_box(message), unsafe_allow_html=True)


def render_email_operation_status_panel(
  *,
  project_root: Path | str,
  key_prefix: str = "email_operation_status",
  expanded: bool = False,
  show_reset_command: bool = True,
) -> dict[str, Any] | None:
  del project_root
  if not should_show_email_operation_status_ui():
    return None

  status = get_email_operation_status()
  with st.expander("メール送信 運用状態（管理者向け）", expanded=expanded):
    _render_status_banner(status)
    st.caption(f"safety_level: {safety_level_label_ja(str(status.get('safety_level') or ''))}")

    st.markdown("**現在の設定**")
    st.markdown(f"- DISABLE_EMAIL_SEND: `{status.get('email_send_disabled')}`")
    st.markdown(f"- ENABLE_APPROVED_MEMBER_SEND: `{status.get('approved_member_send_enabled')}`")
    st.markdown(f"- approved member count: `{status.get('approved_member_count')}`")
    st.markdown(f"- EMAIL_SEND_MODE: `{status.get('email_send_mode')}`")
    st.markdown(f"- SMTP configured: `{status.get('smtp_configured')}`")
    st.markdown(f"- SMTP password configured: `{status.get('smtp_password_configured')}`")
    st.markdown(f"- scheduler disabled: `{status.get('scheduler_disabled')}`")
    st.markdown(f"- auth provider mode: `{status.get('auth_provider_mode')}`")

    warnings = status.get("warnings") or []
    if warnings:
      st.markdown("**warnings**")
      for warning in warnings:
        st.markdown(f"- {warning}")

    st.markdown("**next recommended action**")
    st.markdown(str(status.get("next_recommended_action") or ""))

    if show_reset_command and str(status.get("safety_level")) != SAFETY_LEVEL_SAFE_OFF:
      st.markdown("**送信後の安全復帰コマンド（ターミナルで手動実行）**")
      st.code(build_post_send_reset_command(), language="bash")
      st.caption("アプリから Cloud Run env は変更しません。コピーして手動実行してください。")

  return status


def render_email_operation_status_compact(
  *,
  project_root: Path | str,
  key_prefix: str = "email_operation_status_compact",
) -> None:
  """Compact banner for embedding above send forms."""
  del project_root
  if not should_show_email_operation_status_ui():
    return

  status = get_email_operation_status()
  level = str(status.get("safety_level") or "")
  if level == SAFETY_LEVEL_SAFE_OFF:
    st.caption(f"メール送信状態: {safety_level_label_ja(level)} — {status.get('status_message')}")
    return

  _render_status_banner(status)
  if level in {SAFETY_LEVEL_CONTROLLED, SAFETY_LEVEL_RISKY, SAFETY_LEVEL_MISCONFIGURED}:
    with st.expander("安全復帰コマンドを表示", expanded=False):
      st.code(build_post_send_reset_command(), language="bash")
