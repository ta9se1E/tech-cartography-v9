"""Live Beta Release Pack UI — stakeholder handoff (Phase 25L)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from tech_cartography.auth.basic_auth import is_login_required
from tech_cartography.runtime.live_artifact_paths import describe_live_artifact_storage
from tech_cartography.services.live_beta_release_pack import (
  build_and_save_live_beta_release_pack,
  render_live_beta_release_pack_markdown,
)
from tech_cartography.services.live_operation_status import (
  build_operation_cycle_status,
  find_latest_operation_status_path,
  load_latest_operation_status,
)
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_warning_box
from tech_cartography.ui.login_ui import can_use_admin_features


def should_show_live_beta_release_pack_ui() -> bool:
  return is_login_required() and can_use_admin_features()


def _load_operation_status_for_display(project_root: Path | str) -> dict[str, Any]:
  latest_path = find_latest_operation_status_path(project_root)
  if latest_path is None:
    return {
      "status": "missing",
      "message": "保存済み live_operation_status がありません。先に Live Operation Console で状態を保存してください。",
    }
  payload = load_latest_operation_status(project_root)
  if not payload:
    return {
      "status": "invalid",
      "latest_path": str(latest_path),
      "message": "latest live_operation_status の読み込みに失敗しました。",
    }
  return {"status": "ok", "payload": payload, "latest_path": str(latest_path)}


def render_live_beta_release_pack_section(
  *,
  project_root: Path | str,
  key_prefix: str = "live_beta_release_pack",
  expanded: bool = True,
) -> None:
  if not should_show_live_beta_release_pack_ui():
    return

  with st.expander("Live Beta Release Pack（共有用）", expanded=expanded):
    st.markdown(
      render_caution_box(
        "職場の仲間・上司・関係者向けに、Live Beta の状態・使い方・安全範囲・デモ台本を"
        " <strong>1つの共有パック</strong>として出力します。"
        " ログイン情報・APIキー・SMTP 設定は含めません。"
      ),
      unsafe_allow_html=True,
    )

    operation_view = _load_operation_status_for_display(project_root)
    if operation_view.get("status") == "missing":
      st.markdown(
        render_warning_box(
          "先に <strong>Live Operation Console</strong> で状態を保存してください。"
          " 保存がなくても共有パックは作成できますが、latest operation status は missing として記録されます。"
        ),
        unsafe_allow_html=True,
      )
    elif operation_view.get("status") == "ok":
      payload = operation_view.get("payload") or {}
      st.markdown(f"**latest operation status:** `{operation_view.get('latest_path')}`")
      st.caption(f"checked_at: {payload.get('checked_at')} / next: {payload.get('next_recommended_action')}")
    else:
      st.warning(str(operation_view.get("message") or "operation status を読み込めません。"))

    inventory = describe_live_artifact_storage(project_root)
    counts = inventory.get("artifact_counts") or {}
    st.markdown(
      "**artifact inventory:** "
      f"web_signal={counts.get('web_signal_packs', 0)}, "
      f"digest={counts.get('digest_previews', 0)}, "
      f"email={counts.get('email_send_logs', 0)}, "
      f"watch_expansion={counts.get('watch_expansion_proposals', 0)}, "
      f"watch_draft={counts.get('watch_profile_drafts', 0)}, "
      f"next_cycle_plan={counts.get('next_cycle_search_plans', 0)}, "
      f"next_cycle_pack={counts.get('next_cycle_web_signal_packs', 0)}, "
      f"operation_status={counts.get('operation_status_snapshots', 0)}, "
      f"release_pack={counts.get('live_release_packs', 0)}"
    )
    st.caption(f"active storage root: `{inventory.get('active_storage_root')}`")

    runtime = build_operation_cycle_status(project_root).get("runtime_flags") or {}
    st.markdown(
      render_info_box(
        f"runtime: external_api={'OFF' if runtime.get('disable_external_api') else 'ON'}, "
        f"email={'OFF' if runtime.get('disable_email_send') else 'ON'}, "
        f"scheduler={'OFF' if runtime.get('disable_scheduler') else 'ON'}"
      ),
      unsafe_allow_html=True,
    )

    release_note = st.text_area(
      "release note（任意）",
      value="",
      height=80,
      key=f"{key_prefix}_release_note",
      placeholder="今回の共有で補足したい点（secret は入力しないでください）",
    )

    if st.button("共有パックを作成", key=f"{key_prefix}_create", type="primary"):
      pack, saved_paths, error = build_and_save_live_beta_release_pack(
        project_root,
        release_note=release_note.strip() or None,
      )
      st.session_state[f"{key_prefix}_pack"] = pack
      st.session_state[f"{key_prefix}_saved_paths"] = saved_paths
      st.session_state[f"{key_prefix}_error"] = error

    pack: dict[str, Any] | None = st.session_state.get(f"{key_prefix}_pack")
    saved_paths: dict[str, str] | None = st.session_state.get(f"{key_prefix}_saved_paths")
    error: str | None = st.session_state.get(f"{key_prefix}_error")

    if error:
      st.error(error)
    if saved_paths:
      st.success("共有パックを保存しました。")
      st.markdown(f"- json: `{saved_paths.get('json')}`")
      st.markdown(f"- markdown: `{saved_paths.get('markdown')}`")
      st.markdown(f"- text: `{saved_paths.get('text')}`")
      if saved_paths.get("zip"):
        st.markdown(f"- zip: `{saved_paths.get('zip')}`")

    if pack:
      with st.expander("stakeholder share message preview", expanded=False):
        st.text(str(pack.get("stakeholder_share_message") or ""))
      with st.expander("3分デモ台本 preview", expanded=False):
        st.text(str(pack.get("three_min_demo_script") or ""))
      md_preview = None
      if saved_paths and saved_paths.get("markdown"):
        md_path = Path(saved_paths["markdown"])
        if md_path.exists():
          md_preview = md_path.read_text(encoding="utf-8")
      with st.expander("markdown preview", expanded=False):
        if md_preview:
          st.markdown(md_preview)
        else:
          st.markdown(render_live_beta_release_pack_markdown(pack))
