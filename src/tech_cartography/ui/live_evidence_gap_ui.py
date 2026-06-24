"""Evidence Gap UI (Phase 25V)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from tech_cartography.auth.basic_auth import is_login_required
from tech_cartography.runtime.user_context import resolve_user_context
from tech_cartography.services.live_evidence_gap_builder import (
  load_latest_evidence_gap_artifact,
  run_live_evidence_gap_build,
)
from tech_cartography.services.live_watch_profile_manager import get_active_watch_profile
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_warning_box
from tech_cartography.ui.login_ui import can_use_admin_features, get_auth_role, is_app_authenticated


def should_show_live_evidence_gap_ui() -> bool:
  return is_login_required() and can_use_admin_features()


def render_live_evidence_gap_section(
  *,
  project_root: Path | str,
  key_prefix: str = "live_evidence_gap",
) -> None:
  if not should_show_live_evidence_gap_ui():
    return

  active, active_path = get_active_watch_profile(project_root)
  user_context = resolve_user_context()
  latest = load_latest_evidence_gap_artifact(project_root)

  with st.expander("Evidence Gap（Strategic Watch）", expanded=False):
    st.markdown(
      render_caution_box(
        "候補情報の境界を構造化します。確定事実・法的判断ではありません。"
        " 外部API・メール・Schedulerは実行しません。"
      ),
      unsafe_allow_html=True,
    )

    if not active:
      st.markdown(render_warning_box("active Watch Profile がありません。gap は skipped 扱いで生成できます。"), unsafe_allow_html=True)
    else:
      st.caption(f"active profile: {active_path}")

    if latest:
      st.caption(f"latest artifact: {latest.get('source_artifact_paths')}")
      st.markdown(f"**gap_count:** {len(latest.get('evidence_gaps') or [])}")

    if st.button("Evidence Gap を生成", key=f"{key_prefix}_build", type="primary"):
      result = run_live_evidence_gap_build(
        output_root=project_root,
        login_required=is_login_required(),
        is_authenticated=is_app_authenticated(),
        auth_role=get_auth_role(),
        user_context=user_context,
      )
      st.session_state[f"{key_prefix}_last_result"] = result

    last: dict[str, Any] | None = st.session_state.get(f"{key_prefix}_last_result")
    payload = (last or {}).get("payload") or latest
    if not payload:
      return

    if last:
      if last.get("ok"):
        st.success(str(last.get("message")))
      else:
        st.warning(str(last.get("message")))

    gaps = payload.get("evidence_gaps") or []
    if gaps:
      st.markdown("**Evidence Gaps**")
      rows = [
        {
          "gap_id": g.get("gap_id"),
          "urgency": g.get("urgency"),
          "observation": g.get("observation"),
          "support_level": g.get("support_level"),
          "owner": g.get("recommended_owner"),
        }
        for g in gaps
      ]
      st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    actions = payload.get("next_verification_actions") or []
    if actions:
      st.markdown("**Next Verification Actions**")
      for index, action in enumerate(actions, start=1):
        st.markdown(f"{index}. [{action.get('urgency')}] {action.get('action')} ({action.get('recommended_owner')})")

    st.markdown("**What Not To Conclude**")
    for item in payload.get("what_not_to_conclude") or []:
      st.markdown(f"- {item}")

    saved = (last or {}).get("saved_paths") or {}
    for label, path in saved.items():
      st.caption(f"saved ({label}): {path}")

    st.markdown(render_info_box(str(payload.get("caution_summary") or "")), unsafe_allow_html=True)
