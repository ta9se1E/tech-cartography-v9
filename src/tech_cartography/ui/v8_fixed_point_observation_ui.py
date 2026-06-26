"""v8 fixed-point observation tab (Phase 27B)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from tech_cartography.auth.basic_auth import is_login_required
from tech_cartography.runtime.user_context import resolve_user_context
from tech_cartography.services.live_evidence_gap_builder import load_latest_evidence_gap_artifact
from tech_cartography.services.live_run_history import list_run_history_entries
from tech_cartography.services.live_watch_profile_manager import describe_watch_profile_status, get_active_watch_profile
from tech_cartography.services.v8_evidence_map_export import find_latest_evidence_map_dir
from tech_cartography.services.v8_sources_table import load_case_profile
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_warning_box
from tech_cartography.ui.live_run_history_ui import render_run_history_section
from tech_cartography.ui.live_watch_expansion_ui import render_live_watch_expansion_section
from tech_cartography.ui.login_ui import can_use_admin_features
from tech_cartography.ui.v8_input_ui import get_v8_input_state
from tech_cartography.ui.v8_tab_config import STATE_V8_SELECTED_CASE, V8_TAB_LABELS


def render_v8_fixed_point_observation_tab(*, project_root: Path | str) -> None:
  root = Path(project_root)
  state = get_v8_input_state()
  case_id = str(state.get("selected_case_id") or st.session_state.get(STATE_V8_SELECTED_CASE) or "").strip()
  profile = load_case_profile(case_id, root) if case_id else None

  st.markdown("### 定点観測ループ")
  st.markdown(
    render_info_box(
      "<strong>メール送信</strong>と<strong>Scheduler</strong>は定点観測の必須機能です（デフォルト OFF、機能は保持）。"
      " 週次で Watch Profile を更新し、Digest を確認して次の検索範囲へ反映します。"
      " SMTP や Cloud Scheduler の詳細設定は「管理者設定」タブへ誘導します。"
    ),
    unsafe_allow_html=True,
  )

  watch_status = describe_watch_profile_status(root)
  active, active_path = get_active_watch_profile(root)
  st.markdown("#### Watch Profile 概要")
  if active:
    st.markdown(f"- **theme**: {active.get('theme', '')}")
    st.markdown(f"- **keywords**: {', '.join(active.get('keywords') or [])}")
    st.caption(f"active path: {active_path}")
  else:
    st.markdown(render_warning_box("active Watch Profile がありません。"), unsafe_allow_html=True)
  st.caption(f"status: {watch_status.get('watch_profile_status')}")

  gap_artifact = load_latest_evidence_gap_artifact(root)

  st.markdown("#### Evidence Map → Watch Profile / Digest 連携")
  st.markdown(
    render_info_box(
      "Evidence Map の不足 Evidence は次回 Watch Profile 更新候補に使います。"
      " 例: paper evidence 不足 → 論文検索範囲を広げる /"
      " claim text required → 対象特許の claim 取得を次回タスクにする /"
      " web/company candidate のみ → 一次情報確認を次回タスクにする。"
      " メール Digest では Evidence Gap 変化を追跡します（送信はこの Phase では行いません）。"
    ),
    unsafe_allow_html=True,
  )
  ev_dir = find_latest_evidence_map_dir(case_id or None, root) if case_id else find_latest_evidence_map_dir(None, root)
  if ev_dir and ev_dir.exists():
    st.caption(f"latest Evidence Map: {ev_dir}")
  else:
    st.caption("Evidence Map 未生成 — 「Evidence Map」タブで Generate してください。")

  st.markdown("#### 今回の Evidence Gap（要約）")
  gaps = (gap_artifact or {}).get("evidence_gaps") or []
  if gaps:
    for gap in gaps[:3]:
      st.markdown(f"- [{gap.get('urgency')}] {gap.get('observation')}")
  else:
    st.caption("Gap artifact 未生成 — Gap / Next Actions タブを参照")

  st.markdown("#### 次回検索範囲の変更案")
  policy = (profile or {}).get("watch_profile_update_policy") or {}
  if policy:
    st.markdown(f"- **広げる**: {policy.get('expand_on', '—')}")
    st.markdown(f"- **狭める**: {policy.get('narrow_on', '—')}")
    st.markdown(f"- **重点化**: {policy.get('focus_on', '—')}")
    exclusions = (profile or {}).get("exclusion_keywords") or []
    if exclusions:
      st.markdown(f"- **除外キーワード**: {', '.join(exclusions)}")
  else:
    st.caption("案件未選択 — 入力タブで案件を選ぶと case_profile の変更案を表示します。")

  st.markdown("#### Scope Feedback")
  st.caption("検索範囲の拡張・縮小・重点化は Scope Expansion / Feedback で人間承認します。")
  if can_use_admin_features() and is_login_required():
    render_live_watch_expansion_section(project_root=root, key_prefix="v8_fixed_point_scope")
  else:
    st.markdown(render_info_box("Scope Feedback の詳細操作は管理者が「管理者設定」で行います。"), unsafe_allow_html=True)

  st.markdown("#### 次回 Scheduler 実行予定")
  st.caption(
    "Scheduler は定点観測の自動トリガー（必須機能・デフォルト OFF）。"
    " 本番 cron / Cloud Scheduler 詳細は管理者設定へ。"
  )
  sched = (profile or {}).get("scheduler_policy") or {}
  st.markdown(f"- dry_run_first: {sched.get('dry_run_first', True)}")
  st.markdown(f"- default_enabled: {sched.get('default_enabled', False)}")

  st.markdown("#### メール Digest 送信方針")
  st.caption("メール送信は定点観測ループの必須経路（デフォルト OFF）。Digest Preview で下書き確認。")
  digest = (profile or {}).get("email_digest_policy") or {}
  sections = digest.get("include_sections") or []
  if sections:
    st.markdown(f"- 含めるセクション: {', '.join(sections)}")
  st.markdown(f"- Web Signal ラベル: {digest.get('web_signal_label', 'candidate_information_only')}")

  st.markdown("#### 前回との差分")
  history = list_run_history_entries(root, limit=5, viewer_user_context=resolve_user_context())
  if history:
    for entry in history[:3]:
      st.markdown(f"- {entry.get('run_id')} / {entry.get('action_type')} / {entry.get('status')}")
  else:
    st.caption("Run History に差分記録がまだありません。")

  st.markdown("#### Run History")
  if is_login_required():
    render_run_history_section(project_root=root, key_prefix="v8_fixed_point_run_history", expanded=False)
  else:
    st.caption("ログイン後に Run History を表示します。")

  st.markdown(
    render_caution_box(
      "このタブでは Scheduler 本番起動・メール送信は行いません。"
      f" 詳細は「{V8_TAB_LABELS['admin_settings']}」を参照してください。"
    ),
    unsafe_allow_html=True,
  )

  st.markdown(
    render_info_box(f"次は「{V8_TAB_LABELS['export']}」で成果物をダウンロードできます。"),
    unsafe_allow_html=True,
  )
