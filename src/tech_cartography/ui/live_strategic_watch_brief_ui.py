"""Strategic Watch Brief UI (Phase 25V)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import streamlit as st

from tech_cartography.auth.basic_auth import is_login_required
from tech_cartography.runtime.user_context import resolve_user_context
from tech_cartography.services.live_strategic_watch_brief import (
  load_latest_strategic_watch_brief,
  render_strategic_watch_brief_markdown,
  run_live_strategic_watch_brief_build,
)
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box
from tech_cartography.ui.login_ui import can_use_admin_features, get_auth_role, is_app_authenticated


def should_show_live_strategic_watch_brief_ui() -> bool:
  return is_login_required() and can_use_admin_features()


def render_live_strategic_watch_brief_section(
  *,
  project_root: Path | str,
  key_prefix: str = "live_strategic_watch_brief",
) -> None:
  if not should_show_live_strategic_watch_brief_ui():
    return

  user_context = resolve_user_context()
  latest = load_latest_strategic_watch_brief(project_root)

  with st.expander("Strategic Watch Brief（週30分）", expanded=False):
    st.markdown(
      render_caution_box(
        "週次の確認用ブリーフです。候補情報であり確定事実ではありません。"
        " FTO、侵害、有効性判断ではありません。"
        " 外部API・メール・Schedulerは実行しません。"
      ),
      unsafe_allow_html=True,
    )

    if latest:
      st.caption(f"latest brief theme: {latest.get('theme_name')}")
      for path in latest.get("source_artifact_paths") or []:
        st.caption(f"source: {path}")

    if st.button("Strategic Watch Brief を生成", key=f"{key_prefix}_build", type="primary"):
      result = run_live_strategic_watch_brief_build(
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
      st.markdown(render_info_box("Brief 未生成 — Evidence Gap 生成後に作成できます。"), unsafe_allow_html=True)
      return

    if last:
      if last.get("ok"):
        st.success(str(last.get("message")))
      else:
        st.warning(str(last.get("message")))

    st.markdown(render_strategic_watch_brief_markdown(payload))

    saved = (last or {}).get("saved_paths") or {}
    for label, path in saved.items():
      st.caption(f"saved ({label}): {path}")
