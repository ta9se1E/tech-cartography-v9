"""Structured research theme UI section (Phase 27Q.1)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from tech_cartography.runtime.v8_research_theme_schema import ResearchThemeProfile
from tech_cartography.services.v8_research_theme_defaults import (
  default_theme_for_case,
  load_research_theme_profile,
  save_research_theme_profile,
)
from tech_cartography.services.v8_research_theme_export import export_research_theme_profile
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box
from tech_cartography.ui.v8_tab_config import V8_CASE_SAMPLES

STATE_V8_RESEARCH_THEME = "v8_research_theme_profile"


def _split_lines(text: str) -> list[str]:
  parts: list[str] = []
  for line in text.replace(",", "\n").splitlines():
    item = line.strip()
    if item:
      parts.append(item)
  return parts


def _join_lines(items: list[str]) -> str:
  return "\n".join(items)


def get_research_theme_state(case_id: str, *, project_root: Path) -> ResearchThemeProfile:
  cached = st.session_state.get(STATE_V8_RESEARCH_THEME)
  if isinstance(cached, dict) and cached.get("case_id") == case_id:
    return ResearchThemeProfile.from_dict(cached)
  profile = load_research_theme_profile(case_id, project_root)
  st.session_state[STATE_V8_RESEARCH_THEME] = profile.to_dict()
  return profile


def render_research_theme_section(*, case_id: str, project_root: Path) -> ResearchThemeProfile:
  st.markdown("#### 研究テーマ設定 (Phase27Q.1)")
  st.markdown(
    render_info_box(
      "テーマ名・説明・キーワード群・除外キーワード・seed publication numbers を構造化して保存します。"
      " seed が空でも keyword_only で動作します。"
    ),
    unsafe_allow_html=True,
  )

  profile = get_research_theme_state(case_id, project_root=project_root)

  profile.theme_name = st.text_input("テーマ名", value=profile.theme_name, key="v8_theme_name")
  profile.theme_description = st.text_area(
    "テーマ説明",
    value=profile.theme_description,
    height=100,
    key="v8_theme_desc",
  )
  profile.core_keywords = _split_lines(
    st.text_area("コアキーワード（1行1件またはカンマ区切り）", value=_join_lines(profile.core_keywords), key="v8_theme_core"),
  )
  profile.application_keywords = _split_lines(
    st.text_area("用途キーワード", value=_join_lines(profile.application_keywords), key="v8_theme_app"),
  )
  profile.material_process_keywords = _split_lines(
    st.text_area("材料・プロセスキーワード", value=_join_lines(profile.material_process_keywords), key="v8_theme_mat"),
  )
  profile.exclude_keywords = _split_lines(
    st.text_area("除外キーワード", value=_join_lines(profile.exclude_keywords), key="v8_theme_excl"),
  )
  profile.seed_publication_numbers = _split_lines(
    st.text_area(
      "seed publication numbers（1行1件）",
      value=_join_lines(profile.seed_publication_numbers),
      key="v8_theme_seeds",
    ),
  )

  col1, col2, col3 = st.columns(3)
  with col1:
    profile.search_mode = st.selectbox(
      "search mode",
      options=["seed_and_keywords", "keyword_only", "seed_only"],
      index=["seed_and_keywords", "keyword_only", "seed_only"].index(profile.search_mode)
      if profile.search_mode in {"seed_and_keywords", "keyword_only", "seed_only"} else 0,
      key="v8_theme_search_mode",
    )
  with col2:
    profile.max_results = int(st.number_input("max results", min_value=1, max_value=1000, value=profile.max_results, key="v8_theme_max"))
  with col3:
    countries_text = st.text_input("countries（カンマ区切り）", value=",".join(profile.countries), key="v8_theme_countries")
  profile.countries = [c.strip().upper() for c in countries_text.split(",") if c.strip()]

  yr_col1, yr_col2 = st.columns(2)
  with yr_col1:
    yfrom = st.number_input("publication_year_from", min_value=1900, max_value=2100, value=profile.publication_year_from or 2000, key="v8_theme_yfrom")
    profile.publication_year_from = int(yfrom)
  with yr_col2:
    yto_raw = st.text_input("publication_year_to（空=上限なし）", value=str(profile.publication_year_to or ""), key="v8_theme_yto")
    profile.publication_year_to = int(yto_raw) if yto_raw.strip().isdigit() else None

  profile = ResearchThemeProfile.from_dict(profile.to_dict())

  if st.button("Research Theme Profile を保存", key="v8_theme_save", type="primary"):
    save_research_theme_profile(profile, project_root)
    export_path = export_research_theme_profile(profile, project_root)
    st.session_state[STATE_V8_RESEARCH_THEME] = profile.to_dict()
    st.success(f"保存しました — {export_path}")

  st.caption(f"resolved search_mode: {profile.search_mode}")
  if not profile.seed_publication_numbers:
    st.caption("seed なし — keyword_only にフォールバックします。")

  return profile
