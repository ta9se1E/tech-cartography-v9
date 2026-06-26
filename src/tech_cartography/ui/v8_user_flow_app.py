"""v8 user-flow Streamlit app (Phase 27B)."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

import streamlit as st

from tech_cartography.ui.demo_safe_ui import render_usage_notices_expander
from tech_cartography.ui.easy_japanese_ui import inject_easy_ui_css, render_caveat_footer, render_main_title, render_user_badge
from tech_cartography.ui.streamlit_session import default_pipeline_root
from tech_cartography.ui.v8_admin_settings_ui import render_v8_admin_settings_tab
from tech_cartography.ui.v8_claim_map_ui import render_v8_claim_map_tab
from tech_cartography.ui.v8_evidence_map_ui import render_v8_evidence_map_tab
from tech_cartography.ui.v8_export_ui import render_v8_export_tab
from tech_cartography.ui.v8_fixed_point_observation_ui import render_v8_fixed_point_observation_tab
from tech_cartography.ui.v8_gap_next_actions_ui import render_v8_gap_next_actions_tab
from tech_cartography.ui.v8_input_ui import render_v8_input_tab
from tech_cartography.ui.v8_intro_ui import render_v8_intro_tab
from tech_cartography.ui.v8_patent_shortlist_ui import render_v8_patent_shortlist_tab
from tech_cartography.ui.v8_sources_ui import render_v8_sources_tab
from tech_cartography.ui.v8_tab_config import V8_STATUS_CAPTION, V8_TAB_IDS, v8_tab_labels
from tech_cartography.users.watch_profile_store import get_active_watch_profile

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PIPELINE_ROOT = default_pipeline_root()

_TAB_RENDERERS: dict[str, Callable[..., None]] = {
  "intro": lambda **kwargs: render_v8_intro_tab(),
  "input": render_v8_input_tab,
  "sources": render_v8_sources_tab,
  "patent_shortlist": render_v8_patent_shortlist_tab,
  "claim_map": render_v8_claim_map_tab,
  "evidence_map": render_v8_evidence_map_tab,
  "gap_next_actions": render_v8_gap_next_actions_tab,
  "fixed_point_observation": render_v8_fixed_point_observation_tab,
  "export": render_v8_export_tab,
  "admin_settings": render_v8_admin_settings_tab,
}


def render_v8_user_flow_app(
  user: dict[str, Any],
  *,
  pipeline_root: str | None = None,
  run_id: str = "",
  display_mode: str = "かんたん表示",
) -> None:
  del run_id, display_mode
  st.markdown(inject_easy_ui_css(), unsafe_allow_html=True)
  watch = get_active_watch_profile(user["user_id"])
  root = pipeline_root or default_pipeline_root()

  st.markdown(
    render_main_title(
      "Tech Cartography v8",
      "Claim / Evidence / Gap / 定点観測 — 読むべき特許と次の一次確認を整理します",
    ),
    unsafe_allow_html=True,
  )
  header_cols = st.columns([2, 2])
  with header_cols[0]:
    st.markdown(render_user_badge(user), unsafe_allow_html=True)
  with header_cols[1]:
    theme_text = str(watch.get("theme", ""))
    watch_label = f"Watch: {theme_text[:40]}…" if len(theme_text) > 40 else f"Watch: {theme_text}"
    st.caption(watch_label)
    st.caption(V8_STATUS_CAPTION)

  tabs = st.tabs(v8_tab_labels())
  for tab_id, tab in zip(V8_TAB_IDS, tabs, strict=True):
    with tab:
      renderer = _TAB_RENDERERS[tab_id]
      if tab_id in {"intro"}:
        renderer()
      elif tab_id == "admin_settings":
        renderer(project_root=PROJECT_ROOT)
      else:
        renderer(project_root=PROJECT_ROOT)

  with st.sidebar:
    render_usage_notices_expander()

  st.markdown(render_caveat_footer(), unsafe_allow_html=True)
