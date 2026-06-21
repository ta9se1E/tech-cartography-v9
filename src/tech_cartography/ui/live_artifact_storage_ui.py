"""Admin Live Artifact Storage status UI (Phase 25H)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from tech_cartography.auth.basic_auth import is_login_required
from tech_cartography.runtime.live_artifact_paths import describe_live_artifact_storage
from tech_cartography.ui.easy_japanese_ui import render_info_box
from tech_cartography.ui.login_ui import can_use_admin_features


def should_show_live_artifact_storage_ui() -> bool:
  return is_login_required() and can_use_admin_features()


def render_live_artifact_storage_expander(
  *,
  project_root: Path | str,
  expanded: bool = False,
  key: str = "live_artifact_storage",
) -> None:
  if not should_show_live_artifact_storage_ui():
    return

  status = describe_live_artifact_storage(project_root)

  with st.expander("Live Artifact Storage（管理者向け）", expanded=expanded):
    st.markdown(
      render_info_box(
        "Live 成果物（Web Signal / Digest Preview / Email Send Log）の保存先です。"
        " Cloud Run では LIVE_OUTPUTS_ROOT に Cloud Storage mount を設定できます。"
        " Secret 値は表示しません。"
      ),
      unsafe_allow_html=True,
    )
    st.markdown(f"**LIVE_OUTPUTS_ROOT:** `{status['live_outputs_root_env']}`")
    st.markdown(f"**active storage root:** `{status['active_storage_root']}`")
    st.caption(f"env override: {'yes' if status['using_env_override'] else 'no (local fallback)'}")

    rows = [
      {"kind": "web_signal_dir", "path": status["web_signal_dir"], "writable": status["writable"]["web_signal_dir"]},
      {
        "kind": "digest_preview_dir",
        "path": status["digest_preview_dir"],
        "writable": status["writable"]["digest_preview_dir"],
      },
      {
        "kind": "email_send_log_dir",
        "path": status["email_send_log_dir"],
        "writable": status["writable"]["email_send_log_dir"],
      },
    ]
    st.dataframe(rows, use_container_width=True, hide_index=True)

    counts = status["artifact_counts"]
    st.markdown(
      "**latest artifact counts:** "
      f"web_signal_packs={counts['web_signal_packs']}, "
      f"digest_previews={counts['digest_previews']}, "
      f"email_send_logs={counts['email_send_logs']}"
    )

    for label, ok in status["writable"].items():
      if not ok:
        message = status["writable_messages"].get(label)
        if message:
          st.warning(message)
