"""Streamlit entry for the lightweight Tech Cartography v9 signal watch UI."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from services_v9.demo_data import (
  build_operation_status_rows,
  build_source_rows,
  load_demo_signals_payload,
  load_demo_watch_profile_payload,
)
from services_v9.digest_export import build_weekly_digest_markdown, signals_to_csv, signals_to_json
from services_v9.persistence import (
  ensure_v9_run_dirs,
  list_snapshots,
  load_snapshot,
  load_watch_profile,
  save_digest_files,
  save_snapshot,
  save_watch_profile,
)
from services_v9.signal_models import Signal, WatchProfile
from services_v9.signal_scoring import (
  apply_watch_profile_suggestions,
  compute_theme_drift_alert,
  enrich_signals,
  suggest_watch_profile_updates,
)
from services_v9.snapshot_diff import apply_snapshot_status, compare_snapshots
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
DEFAULT_GOAL = "毎週の注目シグナルと差分だけを軽く確認したい"

UI_THEME_KEY = "ui_theme_input"
UI_GOAL_KEY = "ui_watch_goal_input"
UI_DEMO_KEY = "ui_demo_mode_input"
UI_INCLUDE_KEY = "ui_include_keywords_input"
UI_EXCLUDE_KEY = "ui_exclude_keywords_input"
UI_TARGET_COMPANIES_KEY = "ui_target_companies_input"
UI_SOURCE_TYPES_KEY = "ui_source_types_input"
UI_COUNTRIES_KEY = "ui_countries_input"
UI_CADENCE_KEY = "ui_cadence_input"
UI_PRIORITY_RULES_KEY = "ui_priority_rules_input"
UI_SNAPSHOT_NOTE_KEY = "ui_snapshot_run_note"
UI_PREVIOUS_SNAPSHOT_CHOICE_KEY = "ui_previous_snapshot_choice"

STATE_PENDING_PROFILE = "state_pending_watch_profile"
STATE_PROFILE_MESSAGE = "state_profile_status_message"
STATE_SNAPSHOT_MESSAGE = "state_snapshot_status_message"
STATE_COMPARE_MESSAGE = "state_compare_status_message"
STATE_DIGEST_MESSAGE = "state_digest_status_message"
STATE_PREVIOUS_SNAPSHOT = "state_previous_snapshot_payload"
STATE_COMPARE_ENABLED = "state_compare_enabled"
STATE_LAST_SNAPSHOT_PATH = "state_last_snapshot_path"
STATE_LAST_SNAPSHOT_ID = "state_last_snapshot_id"


@st.cache_data(show_spinner=False)
def load_demo_bundle() -> tuple[list[dict[str, object]], dict[str, object]]:
  return load_demo_signals_payload(), load_demo_watch_profile_payload()


def _join_lines(values: list[str]) -> str:
  return "\n".join(values)


def _split_multiline(value: str) -> list[str]:
  items: list[str] = []
  for line in str(value or "").replace(",", "\n").splitlines():
    item = line.strip()
    if item:
      items.append(item)
  return items


def _set_profile_widgets(profile: WatchProfile) -> None:
  st.session_state[UI_THEME_KEY] = profile.theme or DEFAULT_THEME
  st.session_state[UI_INCLUDE_KEY] = _join_lines(profile.include_keywords)
  st.session_state[UI_EXCLUDE_KEY] = _join_lines(profile.exclude_keywords)
  st.session_state[UI_TARGET_COMPANIES_KEY] = _join_lines(profile.target_companies)
  st.session_state[UI_SOURCE_TYPES_KEY] = list(profile.source_types or ["patent", "paper", "web", "company"])
  st.session_state[UI_COUNTRIES_KEY] = ", ".join(profile.countries)
  st.session_state[UI_CADENCE_KEY] = profile.cadence or "Weekly"
  st.session_state[UI_PRIORITY_RULES_KEY] = _join_lines(profile.priority_rules)


def _apply_pending_profile_if_any() -> None:
  payload = st.session_state.pop(STATE_PENDING_PROFILE, None)
  if not payload:
    return
  _set_profile_widgets(WatchProfile.from_dict(payload))


def _init_session_state(watch_profile: WatchProfile) -> None:
  st.session_state.setdefault(UI_GOAL_KEY, DEFAULT_GOAL)
  st.session_state.setdefault(UI_DEMO_KEY, True)
  st.session_state.setdefault(UI_SNAPSHOT_NOTE_KEY, "")
  st.session_state.setdefault(STATE_COMPARE_ENABLED, False)
  if UI_THEME_KEY not in st.session_state:
    _set_profile_widgets(watch_profile)


def _build_ui_watch_profile() -> WatchProfile:
  return WatchProfile(
    theme=str(st.session_state.get(UI_THEME_KEY, DEFAULT_THEME)).strip() or DEFAULT_THEME,
    include_keywords=_split_multiline(str(st.session_state.get(UI_INCLUDE_KEY, ""))),
    exclude_keywords=_split_multiline(str(st.session_state.get(UI_EXCLUDE_KEY, ""))),
    target_companies=_split_multiline(str(st.session_state.get(UI_TARGET_COMPANIES_KEY, ""))),
    source_types=list(st.session_state.get(UI_SOURCE_TYPES_KEY, ["patent", "paper", "web", "company"])),
    countries=_split_multiline(str(st.session_state.get(UI_COUNTRIES_KEY, ""))),
    cadence=str(st.session_state.get(UI_CADENCE_KEY, "Weekly")),
    priority_rules=_split_multiline(str(st.session_state.get(UI_PRIORITY_RULES_KEY, ""))),
  )


def _build_snapshot_history() -> tuple[list[str], dict[str, Path], list[dict[str, str]]]:
  snapshot_labels: list[str] = []
  snapshot_map: dict[str, Path] = {}
  history_rows: list[dict[str, str]] = []

  for path in list_snapshots(limit=20):
    payload = load_snapshot(path)
    label = (
      f"{payload.get('snapshot_id', path.stem)} | "
      f"{payload.get('created_at', '')} | "
      f"メモ: {payload.get('run_note', '') or 'なし'}"
    )
    snapshot_labels.append(label)
    snapshot_map[label] = path
    history_rows.append(
      {
        "snapshot_id": str(payload.get("snapshot_id", path.stem)),
        "created_at": str(payload.get("created_at", "")),
        "run_note": str(payload.get("run_note", "")),
      }
    )
  return snapshot_labels, snapshot_map, history_rows


def _resolve_selected_snapshot(snapshot_map: dict[str, Path]) -> tuple[Path | None, dict | None]:
  selected_label = st.session_state.get(UI_PREVIOUS_SNAPSHOT_CHOICE_KEY, "")
  path = snapshot_map.get(str(selected_label))
  if path is None:
    return None, None
  return path, load_snapshot(path)


def _save_profile_and_rerun(profile: WatchProfile) -> None:
  path = save_watch_profile(profile.to_dict())
  st.session_state[STATE_PROFILE_MESSAGE] = f"監視プロファイルを保存しました: {path}"
  st.rerun()


def _load_profile_into_widgets(default_profile: WatchProfile) -> None:
  profile_dict = load_watch_profile(default_profile=default_profile.to_dict())
  st.session_state[STATE_PENDING_PROFILE] = profile_dict
  st.session_state[STATE_PROFILE_MESSAGE] = "保存済み監視プロファイルを読み込みました。"
  st.rerun()


def _apply_suggestions_and_rerun(profile: WatchProfile, suggestions: list[str]) -> None:
  updated = apply_watch_profile_suggestions(profile, suggestions)
  st.session_state[STATE_PENDING_PROFILE] = updated.to_dict()
  st.session_state[STATE_PROFILE_MESSAGE] = "監視プロファイルにデモ提案を反映しました。"
  st.rerun()


def run_app() -> None:
  st.set_page_config(
    page_title="Tech Cartography v9",
    layout="wide",
    initial_sidebar_state="collapsed",
  )

  ensure_v9_run_dirs()
  raw_signals, raw_profile = load_demo_bundle()
  base_profile = WatchProfile.from_dict(raw_profile)
  _apply_pending_profile_if_any()
  _init_session_state(base_profile)
  watch_profile = _build_ui_watch_profile()

  base_signals = enrich_signals([Signal.from_dict(item) for item in raw_signals])
  current_signal_dicts = [signal.to_dict() for signal in base_signals]

  snapshot_labels, snapshot_map, history_rows = _build_snapshot_history()
  previous_snapshot_payload = st.session_state.get(STATE_PREVIOUS_SNAPSHOT)
  compare_enabled = bool(st.session_state.get(STATE_COMPARE_ENABLED, False))

  diff_result = None
  if compare_enabled and previous_snapshot_payload:
    current_signal_dicts = apply_snapshot_status(current_signal_dicts, previous_snapshot_payload.get("signals", []))
    diff_result = compare_snapshots(previous_snapshot_payload.get("signals", []), current_signal_dicts)

  signals = enrich_signals([Signal.from_dict(item) for item in current_signal_dicts])
  suggestions = suggest_watch_profile_updates(signals, watch_profile)
  drift = compute_theme_drift_alert(signals, watch_profile)
  source_rows = build_source_rows(signals)
  operation_rows = build_operation_status_rows()
  markdown_text = build_weekly_digest_markdown(signals, watch_profile)
  csv_text = signals_to_csv(signals)
  json_text = signals_to_json(signals, watch_profile)

  st.title("Tech Cartography v9")
  st.caption("軽量R&Dシグナル監視エージェント")
  render_notice()
  st.caption(
    "ローカルのデモデータのみで動作します。BigQuery、OpenAlex、Web検索、OCR、PDFスキャン、"
    "スケジューラ、外部APIは起動時に実行しません。"
  )
  st.caption(f"現在の監視目的: {st.session_state.get(UI_GOAL_KEY, DEFAULT_GOAL)}")

  tabs = st.tabs(V9_TAB_LABELS)
  with tabs[0]:
    theme_events = render_theme_setup_tab(st.session_state.get(STATE_PROFILE_MESSAGE))
  with tabs[1]:
    render_sources_tab(source_rows, operation_rows)
  with tabs[2]:
    signal_events = render_top_signals_tab(signals, st.session_state.get(STATE_SNAPSHOT_MESSAGE))
  with tabs[3]:
    weekly_events = render_weekly_updates_tab(
      signals,
      snapshot_labels,
      diff_result,
      drift,
      history_rows,
      previous_snapshot_payload,
      st.session_state.get(STATE_COMPARE_MESSAGE),
    )
  with tabs[4]:
    profile_events = render_watch_profile_tab(watch_profile, suggestions, st.session_state.get(STATE_PROFILE_MESSAGE))
  with tabs[5]:
    digest_events = render_digest_export_tab(markdown_text, csv_text, json_text, st.session_state.get(STATE_DIGEST_MESSAGE))

  if theme_events["save_profile"] or profile_events["save_profile"]:
    _save_profile_and_rerun(watch_profile)

  if theme_events["load_profile"] or profile_events["load_profile"]:
    _load_profile_into_widgets(base_profile)

  if profile_events["apply_suggestions"]:
    _apply_suggestions_and_rerun(watch_profile, suggestions)

  if signal_events["save_snapshot"]:
    path = save_snapshot(
      signals=[signal.to_dict() for signal in signals],
      watch_profile=watch_profile.to_dict(),
      run_note=str(st.session_state.get(UI_SNAPSHOT_NOTE_KEY, "")).strip(),
    )
    payload = load_snapshot(path)
    st.session_state[STATE_LAST_SNAPSHOT_PATH] = str(path)
    st.session_state[STATE_LAST_SNAPSHOT_ID] = str(payload.get("snapshot_id", path.stem))
    st.session_state[STATE_SNAPSHOT_MESSAGE] = f"スナップショットを保存しました: {path}"
    st.rerun()

  if weekly_events["load_previous_snapshot"] or weekly_events["compare_snapshot"]:
    selected_path, selected_payload = _resolve_selected_snapshot(snapshot_map)
    if selected_path is None or selected_payload is None:
      st.session_state[STATE_COMPARE_MESSAGE] = "比較に使える前回スナップショットが見つかりません。"
      if weekly_events["compare_snapshot"]:
        st.session_state[STATE_COMPARE_ENABLED] = False
      st.rerun()
    st.session_state[STATE_PREVIOUS_SNAPSHOT] = selected_payload
    st.session_state[STATE_COMPARE_ENABLED] = bool(weekly_events["compare_snapshot"])
    action_text = "比較を実行しました" if weekly_events["compare_snapshot"] else "前回スナップショットを読み込みました"
    st.session_state[STATE_COMPARE_MESSAGE] = f"{action_text}: {selected_path}"
    st.rerun()

  if digest_events["save_digest_files"]:
    snapshot_id = str(st.session_state.get(STATE_LAST_SNAPSHOT_ID, "")).strip()
    auto_snapshot_note = str(st.session_state.get(UI_SNAPSHOT_NOTE_KEY, "")).strip()
    auto_snapshot_path = None
    if not snapshot_id:
      auto_snapshot_path = save_snapshot(
        signals=[signal.to_dict() for signal in signals],
        watch_profile=watch_profile.to_dict(),
        run_note=auto_snapshot_note or "digest export auto snapshot",
      )
      auto_snapshot_payload = load_snapshot(auto_snapshot_path)
      snapshot_id = str(auto_snapshot_payload.get("snapshot_id", auto_snapshot_path.stem))
      st.session_state[STATE_LAST_SNAPSHOT_PATH] = str(auto_snapshot_path)
      st.session_state[STATE_LAST_SNAPSHOT_ID] = snapshot_id
    saved_paths = save_digest_files(markdown_text, csv_text, json_text, snapshot_id=snapshot_id)
    message = (
      f"ダイジェストファイルを保存しました: {saved_paths['markdown']} / "
      f"{saved_paths['csv']} / {saved_paths['json']}"
    )
    if auto_snapshot_path is not None:
      message += f"（スナップショットも自動保存: {auto_snapshot_path}）"
    st.session_state[STATE_DIGEST_MESSAGE] = message
    st.rerun()

