"""Streamlit entry for the lightweight Tech Cartography v9 signal watch UI."""

from __future__ import annotations

import json

import streamlit as st

from services_v9.demo_data import (
  build_operation_status_rows,
  build_source_rows,
  load_demo_signals_payload,
  load_demo_watch_profile_payload,
)
from services_v9.digest_export import build_weekly_digest_markdown, signals_to_csv, signals_to_json
from services_v9.signal_models import Signal, WatchProfile
from services_v9.signal_scoring import enrich_signals, suggest_watch_profile_updates
from ui_v9.tabs import (
  V9_TAB_LABELS,
  render_digest_export_tab,
  render_notice,
  render_sources_tab,
  render_theme_setup_tab,
  render_top_signals_tab,
  render_watch_profile_tab,
  render_weekly_updates_tab,
)

DEFAULT_THEME = "PAN系炭素繊維のサイジング、表面処理、界面接着、ストランド引張弾性率"
DEFAULT_GOAL = "毎週のTop Signalsと差分だけを軽く確認したい"


@st.cache_data(show_spinner=False)
def load_demo_bundle() -> tuple[list[dict[str, object]], dict[str, object]]:
  return load_demo_signals_payload(), load_demo_watch_profile_payload()


def _init_session_state(watch_profile: WatchProfile) -> None:
  st.session_state.setdefault("v9_theme", watch_profile.theme or DEFAULT_THEME)
  st.session_state.setdefault("v9_watch_goal", DEFAULT_GOAL)
  st.session_state.setdefault("v9_demo_mode", True)


def _build_ui_watch_profile(base_profile: WatchProfile) -> WatchProfile:
  return WatchProfile(
    theme=str(st.session_state.get("v9_theme", base_profile.theme or DEFAULT_THEME)),
    include_keywords=list(base_profile.include_keywords),
    exclude_keywords=list(base_profile.exclude_keywords),
    target_companies=list(base_profile.target_companies),
    source_types=list(base_profile.source_types),
    countries=list(base_profile.countries),
    cadence=base_profile.cadence,
    priority_rules=list(base_profile.priority_rules),
  )


def run_app() -> None:
  st.set_page_config(
    page_title="Tech Cartography v9",
    layout="wide",
    initial_sidebar_state="collapsed",
  )

  raw_signals, raw_profile = load_demo_bundle()
  base_profile = WatchProfile.from_dict(raw_profile)
  _init_session_state(base_profile)
  watch_profile = _build_ui_watch_profile(base_profile)
  signals = enrich_signals([Signal.from_dict(item) for item in raw_signals])
  suggestions = suggest_watch_profile_updates(signals, watch_profile)
  source_rows = build_source_rows(signals)
  operation_rows = build_operation_status_rows()
  markdown_text = build_weekly_digest_markdown(signals, watch_profile)
  csv_text = signals_to_csv(signals)
  json_text = signals_to_json(signals, watch_profile)

  st.title("Tech Cartography v9")
  st.caption("Lightweight R&D Signal Watch Agent")
  render_notice()
  st.caption(
    "Demo mode is local-only. No BigQuery, OpenAlex, web search, OCR, PDF scan, scheduler, "
    "or external API call runs at startup."
  )
  st.caption(f"Watch goal: {st.session_state.get('v9_watch_goal', DEFAULT_GOAL)}")

  tabs = st.tabs(V9_TAB_LABELS)
  with tabs[0]:
    render_theme_setup_tab(watch_profile)
  with tabs[1]:
    render_sources_tab(source_rows, operation_rows)
  with tabs[2]:
    render_top_signals_tab(signals)
  with tabs[3]:
    render_weekly_updates_tab(signals, watch_profile)
  with tabs[4]:
    render_watch_profile_tab(watch_profile, suggestions)
  with tabs[5]:
    render_digest_export_tab(markdown_text, csv_text, json_text)

  with st.expander("Demo Payload Preview"):
    st.code(json.dumps({"signals": raw_signals[:2], "watch_profile": raw_profile}, ensure_ascii=False, indent=2))
