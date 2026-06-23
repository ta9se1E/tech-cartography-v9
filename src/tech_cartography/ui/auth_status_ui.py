"""Authentication status UI for admin diagnostics (Phase 25N)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from tech_cartography.auth.basic_auth import is_login_required
from tech_cartography.runtime.auth_provider_config import auth_provider_mode_summary, get_auth_provider_mode
from tech_cartography.runtime.iap_role_mapping import role_mapping_status
from tech_cartography.runtime.user_context import resolve_user_context
from tech_cartography.ui.easy_japanese_ui import render_info_box, render_warning_box
from tech_cartography.ui.email_operation_status_ui import render_email_operation_status_panel
from tech_cartography.ui.login_ui import (
  can_use_admin_features,
  get_last_iap_identity_status,
  is_app_authenticated,
  is_basic_authenticated,
  is_iap_authenticated,
)


def should_show_auth_status_ui() -> bool:
  return is_login_required() and can_use_admin_features()


def _next_setup_hint(mode: str, iap_status: dict[str, Any] | None) -> str:
  if mode == "basic":
    return "AUTH_PROVIDER_MODE=basic — 既存 Basic Login を継続利用中。IAP 切替時は hybrid → iap の順で検証してください。"
  if mode == "hybrid":
    return "AUTH_PROVIDER_MODE=hybrid — IAP ヘッダーがあれば Google IAP、なければ Basic Login。移行期間向けです。"
  if mode == "iap":
    status = str((iap_status or {}).get("status") or "")
    if status != "ok":
      return "AUTH_PROVIDER_MODE=iap — Cloud Run + IAP 経由でアクセスし、role mapping env を設定してください。"
    return "AUTH_PROVIDER_MODE=iap — IAP identity が有効です。Direct Cloud Run URL ではヘッダーを信頼しないでください。"
  return "認証モードを確認してください。"


def _resolve_project_root(project_root: Path | str | None) -> Path:
  """Resolve project root for nested UI panels (Cloud Run /workspace safe)."""
  if project_root is None:
    return Path.cwd()
  return Path(project_root).expanduser().resolve()


def render_auth_status_expander(
  *,
  project_root: Path | str | None = None,
  key: str = "auth_status",
  expanded: bool = False,
) -> None:
  root = _resolve_project_root(project_root)
  if not should_show_auth_status_ui():
    return

  with st.expander("Authentication Status（管理者向け）", expanded=expanded):
    st.markdown(
      render_info_box(
        "認証モードと現在ユーザーの診断表示です。"
        " password / JWT / API キー / SMTP 設定は表示しません。"
      ),
      unsafe_allow_html=True,
    )

    summary = auth_provider_mode_summary()
    mode = get_auth_provider_mode()
    user = resolve_user_context()
    iap_status = get_last_iap_identity_status()
    mapping = role_mapping_status()

    st.markdown(f"**AUTH_PROVIDER_MODE:** `{summary['auth_provider_mode']}`")
    st.markdown(f"**IAP_JWT_VERIFY_MODE:** `{summary['iap_jwt_verify_mode']}`")
    st.markdown(f"**IAP_EXPECTED_AUDIENCE configured:** `{summary['iap_expected_audience_configured']}`")

    st.markdown(
      f"**current user:** `{user.get('user_id')}` / role=`{user.get('role')}` / "
      f"provider=`{user.get('auth_provider')}` / is_admin=`{user.get('is_admin')}`"
    )
    st.caption(f"display_name: {user.get('display_name')}")

    st.markdown(
      f"**session flags:** app_authenticated={is_app_authenticated()} "
      f"iap={is_iap_authenticated()} basic={is_basic_authenticated()}"
    )

    iap_identity_status = str((iap_status or {}).get("status") or "not_checked")
    st.markdown(f"**IAP identity status:** `{iap_identity_status}`")
    if iap_status and iap_status.get("message"):
      st.caption(str(iap_status.get("message")))

    jwt_info = (iap_status or {}).get("jwt_verification") or {}
    st.markdown(
      f"**JWT verification:** status=`{jwt_info.get('status')}` verified=`{jwt_info.get('verified')}`"
    )
    if jwt_info.get("message"):
      st.caption(str(jwt_info.get("message")))
    if jwt_info.get("production_caution"):
      st.markdown(render_warning_box(str(jwt_info["production_caution"])), unsafe_allow_html=True)

    st.markdown(
      "**role mapping:** "
      f"admin_emails={mapping['admin_email_count']} "
      f"member_emails={mapping['member_email_count']} "
      f"allowed_domains={mapping['allowed_domain_count']}"
    )

    warnings: list[str] = []
    if mode == "iap" and not mapping.get("configured"):
      warnings.append("iap mode ですが ADMIN_EMAILS / ALLOWED_EMAIL_DOMAINS が未設定です。")
    if summary["iap_jwt_verify_mode"] == "strict" and summary["iap_expected_audience_configured"] != "yes":
      warnings.append("IAP_JWT_VERIFY_MODE=strict ですが IAP_EXPECTED_AUDIENCE が未設定です。")
    for item in (iap_status or {}).get("warnings") or []:
      warnings.append(str(item))

    if warnings:
      st.markdown("**warnings**")
      for warning in warnings:
        st.markdown(render_warning_box(warning), unsafe_allow_html=True)

    render_email_operation_status_panel(
      project_root=root,
      key_prefix=f"{key}_email_ops",
      expanded=False,
    )

    st.info(_next_setup_hint(mode, iap_status))
