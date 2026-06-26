"""Weekly Decision Cockpit UI (Phase 25W)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from tech_cartography.auth.basic_auth import is_login_required
from tech_cartography.runtime.user_context import resolve_user_context
from tech_cartography.services.live_weekly_decision_cockpit import (
  READING_ORDER,
  build_weekly_decision_cockpit_payload,
  load_latest_weekly_decision_cockpit,
  run_live_weekly_decision_cockpit_build,
)
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_warning_box
from tech_cartography.ui.login_ui import can_use_admin_features, get_auth_role, is_app_authenticated


def should_show_weekly_decision_cockpit_ui() -> bool:
  return is_login_required()


def render_live_weekly_decision_cockpit_section(
  *,
  project_root: Path | str,
  key_prefix: str = "live_weekly_decision_cockpit",
  expanded: bool = True,
) -> None:
  if not should_show_weekly_decision_cockpit_ui():
    return

  user_context = resolve_user_context()
  is_admin = can_use_admin_features()
  latest_saved = load_latest_weekly_decision_cockpit(project_root)
  live_preview = build_weekly_decision_cockpit_payload(project_root, user_context=user_context)

  with st.expander("今週の判断 — Weekly Decision Cockpit", expanded=expanded):
    st.markdown(
      render_caution_box(
        "<strong>候補情報であり確定事実ではありません。</strong> "
        "FTO、侵害、有効性判断ではありません。"
        " 外部API・メール・Schedulerは実行しません。"
      ),
      unsafe_allow_html=True,
    )

    st.markdown("**週30分で見る順番**")
    for step in READING_ORDER:
      st.markdown(f"- {step}")

    payload = live_preview
    st.markdown(f"### 1. 今週の確認対象テーマ")
    st.markdown(f"**{payload.get('theme_name')}**")
    profile = payload.get("active_watch_profile_summary") or {}
    if profile.get("exists"):
      st.caption(f"active profile: {profile.get('path')}")
    else:
      st.markdown(render_warning_box("active Watch Profile がありません。"), unsafe_allow_html=True)

    st.markdown("### 2. 今週の変化候補")
    for item in payload.get("weekly_change_candidates") or []:
      st.markdown(f"- {item}")

    st.markdown("### 3. Evidence Gap Top 3")
    gaps = payload.get("top_evidence_gaps") or []
    if gaps:
      st.dataframe(
        pd.DataFrame(
          [
            {
              "urgency": g.get("urgency"),
              "observation": g.get("observation"),
              "next": g.get("next_verification_action"),
            }
            for g in gaps
          ],
        ),
        width="stretch",
        hide_index=True,
      )
    else:
      st.caption("Evidence Gap artifact がありません。詳細タブで生成してください。")

    st.markdown("### 4. Next Verification Actions Top 3")
    for index, action in enumerate(payload.get("next_verification_actions") or [], start=1):
      owner = action.get("recommended_owner") or action.get("owner")
      st.markdown(f"{index}. [{action.get('urgency')}] {action.get('action')} — {owner}")

    st.markdown("### 5. What Not To Conclude")
    for item in payload.get("what_not_to_conclude") or []:
      st.markdown(f"- {item}")

    st.markdown("### 6. Source Coverage")
    st.json(payload.get("source_coverage") or {})

    st.markdown("### 7. 最新 artifact 参照")
    for label, path in (payload.get("latest_artifact_paths") or {}).items():
      if path:
        st.caption(f"{label}: {path}")

    st.markdown("### 8. 次に見るべき情報")
    st.markdown(render_info_box(str(payload.get("next_recommended_action") or "")), unsafe_allow_html=True)
    st.caption(f"readiness_level: {payload.get('readiness_level')}")

    st.markdown("**詳細機能へ**")
    st.caption("Digest Preview / Web Signal / Evidence Gap / Run History は各 expander またはタブで確認できます。")

    if is_admin:
      if st.button("Cockpit を保存", key=f"{key_prefix}_save", type="primary"):
        result = run_live_weekly_decision_cockpit_build(
          output_root=project_root,
          login_required=is_login_required(),
          is_authenticated=is_app_authenticated(),
          auth_role=get_auth_role(),
          user_context=user_context,
        )
        st.session_state[f"{key_prefix}_last_result"] = result
    else:
      st.caption("保存は admin のみ可能です（閲覧は全ログインユーザー）。")

    last: dict[str, Any] | None = st.session_state.get(f"{key_prefix}_last_result")
    if last:
      if last.get("ok"):
        st.success(str(last.get("message")))
      else:
        st.warning(str(last.get("message")))
    elif latest_saved:
      st.caption(f"saved cockpit: {latest_saved.get('generated_at')}")
