"""IAP cutover status UI for admin diagnostics (Phase 25O)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from tech_cartography.runtime.auth_provider_config import auth_provider_mode_summary, get_auth_provider_mode
from tech_cartography.runtime.iap_role_mapping import role_mapping_status
from tech_cartography.runtime.user_context import resolve_user_context
from tech_cartography.ui.auth_status_ui import should_show_auth_status_ui
from tech_cartography.ui.easy_japanese_ui import render_info_box, render_warning_box
from tech_cartography.ui.login_ui import get_last_iap_identity_status


def should_show_iap_cutover_status_ui() -> bool:
  return should_show_auth_status_ui()


def _recommended_mode(current_mode: str, iap_status: dict[str, Any] | None) -> str:
  iap_ok = str((iap_status or {}).get("status") or "") == "ok"
  if current_mode == "basic":
    return "hybrid"
  if current_mode == "hybrid" and iap_ok:
    return "iap"
  if current_mode == "iap":
    return "iap"
  return "hybrid"


def _cutover_checklist(current_mode: str, iap_status: dict[str, Any] | None) -> list[tuple[str, bool]]:
  iap_ok = str((iap_status or {}).get("status") or "") == "ok"
  return [
    ("AUTH_PROVIDER_MODE=hybrid で再デプロイ", current_mode in {"hybrid", "iap"}),
    ("Cloud Run IAP を手動で有効化", False),  # runtime からは GCP 状態を確定できない
    ("Google ログインで入れることを確認", iap_ok),
    ("Run History に auth_provider=google_iap", iap_ok),
    ("問題なければ AUTH_PROVIDER_MODE=iap へ", current_mode == "iap"),
  ]


def render_iap_cutover_status_expander(
  *,
  project_root: Path | str,
  key: str = "iap_cutover_status",
  expanded: bool = False,
) -> None:
  del project_root
  if not should_show_iap_cutover_status_ui():
    return

  with st.expander("IAP Cutover Status（管理者向け）", expanded=expanded):
    st.markdown(
      render_info_box(
        "Cloud Run IAP 切替の進捗確認です。"
        " パスワード・JWT・API キー等の機密値は表示しません。"
        " GCP 操作は docs/phase25o_cloud_run_iap_cutover_runbook.md を手動で実行してください。"
      ),
      unsafe_allow_html=True,
    )

    summary = auth_provider_mode_summary()
    mode = get_auth_provider_mode()
    user = resolve_user_context()
    iap_status = get_last_iap_identity_status()
    mapping = role_mapping_status()
    recommended = _recommended_mode(mode, iap_status)

    st.markdown(f"**AUTH_PROVIDER_MODE:** `{summary['auth_provider_mode']}`")
    st.markdown(f"**recommended next mode:** `{recommended}`")
    st.markdown(
      f"**current user:** `{user.get('user_id')}` / role=`{user.get('role')}` / "
      f"provider=`{user.get('auth_provider')}`"
    )

    iap_identity_status = str((iap_status or {}).get("status") or "not_checked")
    st.markdown(f"**IAP identity status:** `{iap_identity_status}`")
    st.markdown(f"**IAP JWT verify mode:** `{summary['iap_jwt_verify_mode']}`")
    st.markdown(
      "**role mapping:** "
      f"admin={mapping['admin_email_count']} "
      f"member={mapping['member_email_count']} "
      f"domains={mapping['allowed_domain_count']}"
    )

    st.markdown("**cutover checklist**")
    for label, done in _cutover_checklist(mode, iap_status):
      mark = "✅" if done else "⬜"
      st.markdown(f"- {mark} {label}")

    warnings: list[str] = []
    if mode == "iap" and iap_identity_status != "ok":
      warnings.append("iap mode ですが現在セッションで IAP identity が有効ではありません。")
    if mode in {"iap", "hybrid"} and not mapping.get("configured"):
      warnings.append("role mapping env が未設定です。IAP 切替前に設定してください。")
    if summary["iap_jwt_verify_mode"] == "strict" and summary["iap_expected_audience_configured"] != "yes":
      warnings.append("JWT strict ですが audience が未設定です。")
    for item in (iap_status or {}).get("warnings") or []:
      warnings.append(str(item))

    if warnings:
      st.markdown("**warnings**")
      for warning in warnings:
        st.markdown(render_warning_box(warning), unsafe_allow_html=True)

    st.markdown(
      render_warning_box(
        "ロールバック: IAP を --no-iap で無効化し、AUTH_PROVIDER_MODE=basic へ戻せます。"
        " 手順は Runbook（phase25o）を参照してください。"
      ),
      unsafe_allow_html=True,
    )

    st.caption(
      "preflight: scripts/check_iap_cutover_ready.py "
      "(read-only — IAP を自動 ON/OFF しません)"
    )
