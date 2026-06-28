"""v8 admin settings tab — isolates operator details (Phase 27B)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from tech_cartography.auth.basic_auth import is_login_required
from tech_cartography.ui.api_secret_status_ui import render_api_secret_status_expander
from tech_cartography.ui.auth_status_ui import render_auth_status_expander
from tech_cartography.ui.demo_safe_ui import render_usage_notices_expander
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_warning_box
from tech_cartography.ui.email_operation_status_ui import render_email_operation_status_panel
from tech_cartography.ui.iap_cutover_status_ui import render_iap_cutover_status_expander
from tech_cartography.ui.live_approved_member_email_send_ui import render_live_approved_member_email_send_section
from tech_cartography.ui.live_artifact_storage_ui import render_live_artifact_storage_expander
from tech_cartography.ui.live_digest_preview_ui import render_live_digest_preview_section
from tech_cartography.ui.live_email_send_ui import render_live_email_send_section
from tech_cartography.ui.live_operation_console_ui import render_live_operation_console_section
from tech_cartography.ui.live_run_history_ui import render_run_history_section
from tech_cartography.ui.live_scheduler_dry_run_ui import render_live_scheduler_dry_run_section
from tech_cartography.ui.live_tavily_search_ui import render_live_tavily_smoke_test_section
from tech_cartography.ui.live_watch_profile_ui import render_live_watch_profile_section
from tech_cartography.ui.live_web_signal_collection_ui import render_live_web_signal_collection_section
from tech_cartography.ui.login_ui import can_use_admin_features
from tech_cartography.ui.v8_judge_mode_ui import render_judge_conclusion_card, render_judge_next_tab_hint


def render_v8_admin_settings_tab(
  *,
  project_root: Path | str,
) -> None:
  root = Path(project_root)
  is_admin = can_use_admin_features()

  render_judge_conclusion_card("admin_settings")
  render_judge_next_tab_hint("admin_settings")

  st.markdown("### 管理者設定｜Demo Safety")
  if not is_login_required():
    st.markdown(render_warning_box("ログイン設定がありません。"), unsafe_allow_html=True)
    return

  if not is_admin:
    st.markdown(
      render_caution_box(
        "一般ユーザー向け画面から運用詳細を隔離しています。"
        " IAP / SMTP / Scheduler / Operation Status の詳細は管理者のみ表示されます。"
      ),
      unsafe_allow_html=True,
    )
    st.caption("member ロール — 最小情報のみ表示")
    st.markdown(
      render_caution_box("認証状態の詳細は admin のみ表示されます。運用操作は管理者に依頼してください。"),
      unsafe_allow_html=True,
    )
    render_usage_notices_expander()
    return

  st.markdown(
    render_caution_box(
      "secret 値（SMTP パスワード、API キー、OAuth/JWT 全文）は表示しません。"
      " 運用コンソール系 UI はこのタブに集約しています。"
      " v8「定点観測」タブではメール/Scheduler の計画と説明のみ — "
      "本番 ON/OFF や secret はここで扱います。"
    ),
    unsafe_allow_html=True,
  )

  import os
  disable_email = os.environ.get("DISABLE_EMAIL_SEND", "(unset)")
  disable_scheduler = os.environ.get("DISABLE_SCHEDULER", "(unset)")
  st.markdown("#### 定点観測ループと管理者設定の役割分担")
  st.markdown(
    render_info_box(
      "メール送信設定と Scheduler 設定は管理者向けです。"
      " 定点観測タブでは Email Digest Plan / Scheduler Follow-up Plan のプレビューのみ。"
      " SMTP パスワード / API キー / OAuth secret / JWT 全文は表示しません。"
    ),
    unsafe_allow_html=True,
  )
  st.caption(f"DISABLE_EMAIL_SEND={disable_email}")
  st.caption(f"DISABLE_SCHEDULER={disable_scheduler}")
  st.caption("メール送信と Scheduler は必須機能として保持（デフォルト OFF）。")

  st.markdown("#### 外部AI連携（Phase27R.5 — 将来拡張 / デフォルト OFF）")
  from tech_cartography.runtime.v8_external_ai_config import (
    EXTERNAL_AI_SAFETY_NOTICES,
    external_ai_status_lines,
  )
  from tech_cartography.services.v8_external_ai_summary import build_external_ai_summary_prompt

  st.markdown(
    render_info_box(
      "外部AI連携は、Top5選抜理由や Evidence / GAP サマリーの高度化に利用予定です。"
      " 提出デモでは実行せず、既存データに基づくローカル要約のみ表示します。"
    ),
    unsafe_allow_html=True,
  )
  with st.expander("External AI — feature flags / plan preview", expanded=False):
    for line in external_ai_status_lines():
      st.caption(line)
    for notice in EXTERNAL_AI_SAFETY_NOTICES[:4]:
      st.caption(notice)
    plan = build_external_ai_summary_prompt(
      target="evidence_map_executive_summary",
      case_id="case_01_pan_graphitization",
      source_artifacts=["evidence_map.md", "gap_next_actions.md"],
    )
    st.caption(f"plan.execution_status={plan.execution_status}")
    st.caption("Weekly Digest / Watch Profile / Scope Expansion / Email / Scheduler への接続は設計のみ")
    st.caption("docs/external_ai_integration_phase27r5.md を参照")

  st.markdown("#### Phase27N — Cloud Run 反映準備")
  try:
    from tech_cartography.services.v8_cloud_run_readiness import build_cloud_run_readiness_report

    cr = build_cloud_run_readiness_report(project_root=root)
    st.markdown(
      render_info_box(
        f"Cloud Run readiness: <strong>{cr.overall_status}</strong> — "
        f"app={cr.app_entrypoint_status} / streamlit={cr.streamlit_command_status} / "
        f"demo_data={cr.demo_data_status}。"
        " この Phase では Cloud Build / Cloud Run deploy を実行しません。"
        " Secret 値は表示しません。"
      ),
      unsafe_allow_html=True,
    )
    st.caption(f"LIVE_OUTPUTS_ROOT — ローカル outputs/ / Cloud Run 推奨 /tmp/tech_cartography_outputs")
    st.caption("DISABLE_EMAIL_SEND=true / DISABLE_SCHEDULER=true を Cloud Run では推奨")
    if cr.known_blockers:
      st.caption(f"known_blockers: {cr.known_blockers[0][:80]}")
  except Exception as exc:
    st.warning(f"Cloud Run Readiness 取得エラー: {exc}")

  st.markdown("#### Phase27J — Manual Claim Injection")
  st.markdown(
    render_info_box(
      "Phase27J では claim 本文をユーザーが手動投入します。システムは生成しません。"
      " Cloud Build / Cloud Run deploy / メール送信 / Scheduler 起動はこの Phase では実行しません。"
    ),
    unsafe_allow_html=True,
  )

  st.markdown("#### Phase27I — ローカル検証")
  st.markdown(
    render_info_box(
      "Phase27I は Cloud 反映前のローカル検証です。"
      " Cloud Build / Cloud Run deploy はこの Phase では実行しません。"
      " メール送信と Scheduler は設定として残しますが、この Phase では実行しません。"
    ),
    unsafe_allow_html=True,
  )

  render_auth_status_expander(project_root=root, key="v8_admin_auth")
  render_iap_cutover_status_expander(project_root=root, key="v8_admin_iap")
  render_api_secret_status_expander(key="v8_admin_api")

  st.markdown("#### Cloud Storage / artifact")
  render_live_artifact_storage_expander(project_root=root, key="v8_admin_artifact")

  st.markdown("#### Email / Scheduler / Operation")
  render_email_operation_status_panel(key_prefix="v8_admin_email_status")
  render_live_scheduler_dry_run_section(project_root=root, key_prefix="v8_admin_scheduler")
  render_live_operation_console_section(project_root=root, key_prefix="v8_admin_operation")

  st.markdown("#### Live 手動操作（既存 v7 機能）")
  render_live_watch_profile_section(project_root=root, key_prefix="v8_admin_watch")
  render_live_web_signal_collection_section(project_root=root, key_prefix="v8_admin_web_signal")
  render_live_tavily_smoke_test_section(project_root=root, key_prefix="v8_admin_tavily")
  render_live_digest_preview_section(project_root=root, key_prefix="v8_admin_digest")
  render_live_email_send_section(project_root=root, key_prefix="v8_admin_email_send")
  render_live_approved_member_email_send_section(project_root=root, key_prefix="v8_admin_approved_send")

  st.markdown("#### Run History（詳細）")
  render_run_history_section(project_root=root, key_prefix="v8_admin_run_history", expanded=True)

  st.caption("v7 全タブ UI は削除していません。環境変数 APP_UI_VERSION=v7 で従来 UI に切り替えできます。")

  render_usage_notices_expander()
