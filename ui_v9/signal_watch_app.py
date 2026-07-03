"""Streamlit entry for the lightweight Tech Cartography v9 signal watch UI."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from services_v9.demo_data import (
  SAMPLE_UPLOAD_CSV_PATH,
  SAMPLE_UPLOAD_JSON_PATH,
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
from services_v9.query_preview import build_query_preview_bundle
from services_v9.score_explainer import attach_score_explanations
from services_v9.signal_loader import (
  enrich_signals_with_profile,
  load_signals_from_csv_text,
  load_signals_from_json_text,
)
from services_v9.signal_models import Signal, WatchProfile
from services_v9.signal_scoring import (
  apply_watch_profile_suggestions,
  compute_theme_drift_alert,
  enrich_signals,
  suggest_watch_profile_updates,
)
from services_v9.signal_template import build_csv_template, build_json_template
from services_v9.snapshot_diff import apply_snapshot_status, compare_snapshots
from services_v9.watch_profile_schema import build_profile_from_form, watch_profile_summary
from ui_v9.labels import data_source_mode_label_ja
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

UI_DEMO_KEY = "ui_demo_mode_input"
UI_THEME_NAME_KEY = "ui_theme_name_input"
UI_THEME_DESCRIPTION_KEY = "ui_theme_description_input"
UI_CORE_EN_KEY = "ui_core_en_input"
UI_CORE_JA_KEY = "ui_core_ja_input"
UI_APPLICATION_EN_KEY = "ui_application_en_input"
UI_APPLICATION_JA_KEY = "ui_application_ja_input"
UI_MATERIAL_PROCESS_EN_KEY = "ui_material_process_en_input"
UI_MATERIAL_PROCESS_JA_KEY = "ui_material_process_ja_input"
UI_EXCLUDE_EN_KEY = "ui_exclude_en_input"
UI_EXCLUDE_JA_KEY = "ui_exclude_ja_input"
UI_SEED_PUBLICATIONS_KEY = "ui_seed_publications_input"
UI_CANDIDATE_PUBLICATIONS_KEY = "ui_candidate_publications_input"
UI_TARGET_COMPANIES_KEY = "ui_target_companies_input"
UI_SOURCE_TYPES_KEY = "ui_source_types_input"
UI_COUNTRIES_KEY = "ui_countries_input"
UI_CADENCE_KEY = "ui_cadence_input"
UI_PRIORITY_RULES_KEY = "ui_priority_rules_input"
UI_SNAPSHOT_NOTE_KEY = "ui_snapshot_run_note"
UI_PREVIOUS_SNAPSHOT_CHOICE_KEY = "ui_previous_snapshot_choice"
UI_DATA_SOURCE_MODE_KEY = "ui_data_source_mode"
UI_CSV_UPLOAD_KEY = "ui_csv_upload"
UI_JSON_UPLOAD_KEY = "ui_json_upload"

STATE_PENDING_PROFILE = "state_pending_watch_profile"
STATE_PROFILE_MESSAGE = "state_profile_status_message"
STATE_SNAPSHOT_MESSAGE = "state_snapshot_status_message"
STATE_COMPARE_MESSAGE = "state_compare_status_message"
STATE_DIGEST_MESSAGE = "state_digest_status_message"
STATE_PREVIOUS_SNAPSHOT = "state_previous_snapshot_payload"
STATE_COMPARE_ENABLED = "state_compare_enabled"
STATE_LAST_SNAPSHOT_PATH = "state_last_snapshot_path"
STATE_LAST_SNAPSHOT_ID = "state_last_snapshot_id"
STATE_CURRENT_SOURCE_INFO = "state_current_source_info"
STATE_UPLOADED_SIGNALS = "state_uploaded_signals"
STATE_UPLOAD_WARNINGS = "state_upload_warnings"


@st.cache_data(show_spinner=False)
def load_demo_bundle() -> tuple[list[dict[str, object]], dict[str, object]]:
  return load_demo_signals_payload(), load_demo_watch_profile_payload()


def _join_lines(values: list[str]) -> str:
  return "\n".join(values)


def _set_profile_widgets(profile_dict: dict[str, object]) -> None:
  profile = WatchProfile.from_dict(profile_dict)
  st.session_state[UI_THEME_NAME_KEY] = profile.theme_name
  st.session_state[UI_THEME_DESCRIPTION_KEY] = profile.theme_description
  st.session_state[UI_CORE_EN_KEY] = _join_lines(profile.keywords.get("core_en", []))
  st.session_state[UI_CORE_JA_KEY] = _join_lines(profile.keywords.get("core_ja", []))
  st.session_state[UI_APPLICATION_EN_KEY] = _join_lines(profile.keywords.get("application_en", []))
  st.session_state[UI_APPLICATION_JA_KEY] = _join_lines(profile.keywords.get("application_ja", []))
  st.session_state[UI_MATERIAL_PROCESS_EN_KEY] = _join_lines(profile.keywords.get("material_process_en", []))
  st.session_state[UI_MATERIAL_PROCESS_JA_KEY] = _join_lines(profile.keywords.get("material_process_ja", []))
  st.session_state[UI_EXCLUDE_EN_KEY] = _join_lines(profile.keywords.get("exclude_en", []))
  st.session_state[UI_EXCLUDE_JA_KEY] = _join_lines(profile.keywords.get("exclude_ja", []))
  st.session_state[UI_SEED_PUBLICATIONS_KEY] = _join_lines(profile.seed_publications)
  st.session_state[UI_CANDIDATE_PUBLICATIONS_KEY] = _join_lines(profile.candidate_publications)
  st.session_state[UI_TARGET_COMPANIES_KEY] = _join_lines(profile.target_companies)
  st.session_state[UI_SOURCE_TYPES_KEY] = list(profile.source_types or ["patent", "paper", "web", "company"])
  st.session_state[UI_COUNTRIES_KEY] = ", ".join(profile.countries)
  st.session_state[UI_CADENCE_KEY] = profile.cadence or "weekly"
  st.session_state[UI_PRIORITY_RULES_KEY] = _join_lines(profile.priority_rules)


def _apply_pending_profile_if_any() -> None:
  payload = st.session_state.pop(STATE_PENDING_PROFILE, None)
  if not payload:
    return
  _set_profile_widgets(payload)


def _init_session_state(profile_dict: dict[str, object]) -> None:
  st.session_state.setdefault(UI_DEMO_KEY, True)
  st.session_state.setdefault(UI_SNAPSHOT_NOTE_KEY, "")
  st.session_state.setdefault(STATE_COMPARE_ENABLED, False)
  st.session_state.setdefault(UI_DATA_SOURCE_MODE_KEY, "demo")
  if UI_THEME_NAME_KEY not in st.session_state:
    _set_profile_widgets(profile_dict)


def _build_ui_watch_profile_dict() -> dict[str, object]:
  return build_profile_from_form(
    {
      "ui_theme_name_input": st.session_state.get(UI_THEME_NAME_KEY, ""),
      "ui_theme_description_input": st.session_state.get(UI_THEME_DESCRIPTION_KEY, ""),
      "ui_core_en_input": st.session_state.get(UI_CORE_EN_KEY, ""),
      "ui_core_ja_input": st.session_state.get(UI_CORE_JA_KEY, ""),
      "ui_application_en_input": st.session_state.get(UI_APPLICATION_EN_KEY, ""),
      "ui_application_ja_input": st.session_state.get(UI_APPLICATION_JA_KEY, ""),
      "ui_material_process_en_input": st.session_state.get(UI_MATERIAL_PROCESS_EN_KEY, ""),
      "ui_material_process_ja_input": st.session_state.get(UI_MATERIAL_PROCESS_JA_KEY, ""),
      "ui_exclude_en_input": st.session_state.get(UI_EXCLUDE_EN_KEY, ""),
      "ui_exclude_ja_input": st.session_state.get(UI_EXCLUDE_JA_KEY, ""),
      "ui_seed_publications_input": st.session_state.get(UI_SEED_PUBLICATIONS_KEY, ""),
      "ui_candidate_publications_input": st.session_state.get(UI_CANDIDATE_PUBLICATIONS_KEY, ""),
      "ui_target_companies_input": st.session_state.get(UI_TARGET_COMPANIES_KEY, ""),
      "ui_source_types_input": st.session_state.get(UI_SOURCE_TYPES_KEY, ["patent", "paper", "web", "company"]),
      "ui_countries_input": st.session_state.get(UI_COUNTRIES_KEY, ""),
      "ui_cadence_input": st.session_state.get(UI_CADENCE_KEY, "weekly"),
      "ui_priority_rules_input": st.session_state.get(UI_PRIORITY_RULES_KEY, ""),
    }
  )


def _decode_uploaded_text(uploaded_file) -> tuple[str | None, list[str]]:
  if uploaded_file is None:
    return None, []
  raw = uploaded_file.getvalue()
  for encoding in ("utf-8-sig", "utf-8", "cp932"):
    try:
      return raw.decode(encoding), []
    except UnicodeDecodeError:
      continue
  return None, ["アップロードファイルの文字コードを判定できませんでした。UTF-8 のCSV/JSONを使用してください。"]


def _resolve_current_signal_source(
  raw_demo_signals: list[dict[str, object]],
  watch_profile_dict: dict[str, object],
) -> dict[str, object]:
  mode = str(st.session_state.get(UI_DATA_SOURCE_MODE_KEY, "demo"))
  csv_file = st.session_state.get(UI_CSV_UPLOAD_KEY)
  json_file = st.session_state.get(UI_JSON_UPLOAD_KEY)

  demo_signals = [signal.to_dict() for signal in enrich_signals([Signal.from_dict(item) for item in raw_demo_signals])]
  warnings: list[str] = []

  if mode == "csv":
    if csv_file is None:
      warnings.append("CSVアップロードモードですが、まだCSVファイルが選択されていません。デモデータを表示します。")
    else:
      text, decode_warnings = _decode_uploaded_text(csv_file)
      warnings.extend(decode_warnings)
      if text is not None:
        records, load_warnings = load_signals_from_csv_text(text)
        prepared = sorted(
          enrich_signals_with_profile(records, watch_profile_dict),
          key=lambda item: (
            float(item.get("score", 0.0)),
            str(item.get("published_date", "")),
            str(item.get("title", "")),
          ),
          reverse=True,
        )
        warnings.extend(load_warnings)
        if prepared:
          return {
            "requested_mode": mode,
            "mode": "csv",
            "label": data_source_mode_label_ja("csv"),
            "signals": prepared,
            "loaded_count": len(prepared),
            "warnings": warnings,
            "provisional_scoring": True,
            "template_csv_path": str(SAMPLE_UPLOAD_CSV_PATH),
            "template_json_path": str(SAMPLE_UPLOAD_JSON_PATH),
          }
        warnings.append("CSVから有効なシグナルを読み込めなかったため、デモデータを表示します。")

  if mode == "json":
    if json_file is None:
      warnings.append("JSONアップロードモードですが、まだJSONファイルが選択されていません。デモデータを表示します。")
    else:
      text, decode_warnings = _decode_uploaded_text(json_file)
      warnings.extend(decode_warnings)
      if text is not None:
        records, load_warnings = load_signals_from_json_text(text)
        prepared = sorted(
          enrich_signals_with_profile(records, watch_profile_dict),
          key=lambda item: (
            float(item.get("score", 0.0)),
            str(item.get("published_date", "")),
            str(item.get("title", "")),
          ),
          reverse=True,
        )
        warnings.extend(load_warnings)
        if prepared:
          return {
            "requested_mode": mode,
            "mode": "json",
            "label": data_source_mode_label_ja("json"),
            "signals": prepared,
            "loaded_count": len(prepared),
            "warnings": warnings,
            "provisional_scoring": True,
            "template_csv_path": str(SAMPLE_UPLOAD_CSV_PATH),
            "template_json_path": str(SAMPLE_UPLOAD_JSON_PATH),
          }
        warnings.append("JSONから有効なシグナルを読み込めなかったため、デモデータを表示します。")

  return {
    "requested_mode": mode,
    "mode": "demo",
    "label": data_source_mode_label_ja("demo"),
    "signals": demo_signals,
    "loaded_count": len(demo_signals),
    "warnings": warnings,
    "provisional_scoring": False,
    "template_csv_path": str(SAMPLE_UPLOAD_CSV_PATH),
    "template_json_path": str(SAMPLE_UPLOAD_JSON_PATH),
  }


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


def _save_profile_and_rerun(profile_dict: dict[str, object]) -> None:
  path = save_watch_profile(profile_dict)
  st.session_state[STATE_PROFILE_MESSAGE] = f"監視プロファイルを保存しました: {path}"
  st.rerun()


def _load_profile_into_widgets(default_profile: dict[str, object]) -> None:
  profile_dict = load_watch_profile(default_profile=default_profile)
  st.session_state[STATE_PENDING_PROFILE] = profile_dict
  st.session_state[STATE_PROFILE_MESSAGE] = "保存済み監視プロファイルを読み込みました。"
  st.rerun()


def _apply_suggestions_and_rerun(profile_dict: dict[str, object], suggestions: list[str]) -> None:
  updated = apply_watch_profile_suggestions(WatchProfile.from_dict(profile_dict), suggestions)
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
  _apply_pending_profile_if_any()
  _init_session_state(raw_profile)
  watch_profile_dict = _build_ui_watch_profile_dict()
  watch_profile = WatchProfile.from_dict(watch_profile_dict)
  profile_summary = watch_profile_summary(watch_profile_dict)
  query_previews = build_query_preview_bundle(watch_profile_dict)
  csv_template_text = build_csv_template()
  json_template_text = build_json_template()
  source_info = _resolve_current_signal_source(raw_signals, watch_profile_dict)
  st.session_state[STATE_CURRENT_SOURCE_INFO] = source_info
  st.session_state[STATE_UPLOAD_WARNINGS] = list(source_info["warnings"])
  if source_info["mode"] in {"csv", "json"}:
    st.session_state[STATE_UPLOADED_SIGNALS] = list(source_info["signals"])
  else:
    st.session_state.pop(STATE_UPLOADED_SIGNALS, None)

  current_signal_dicts = list(source_info["signals"])

  snapshot_labels, snapshot_map, history_rows = _build_snapshot_history()
  previous_snapshot_payload = st.session_state.get(STATE_PREVIOUS_SNAPSHOT)
  compare_enabled = bool(st.session_state.get(STATE_COMPARE_ENABLED, False))

  diff_result = None
  if compare_enabled and previous_snapshot_payload:
    current_signal_dicts = apply_snapshot_status(current_signal_dicts, previous_snapshot_payload.get("signals", []))
    diff_result = compare_snapshots(previous_snapshot_payload.get("signals", []), current_signal_dicts)

  display_signal_dicts = attach_score_explanations(current_signal_dicts, watch_profile_dict)
  signals = sorted(
    [Signal.from_dict(item) for item in display_signal_dicts],
    key=lambda item: (item.score, item.published_date, item.title),
    reverse=True,
  )
  suggestions = suggest_watch_profile_updates(signals, watch_profile)
  drift = compute_theme_drift_alert(signals, watch_profile)
  source_rows = build_source_rows(signals)
  operation_rows = build_operation_status_rows()
  markdown_text = build_weekly_digest_markdown(
    signals,
    watch_profile,
    data_source=str(source_info["label"]),
    loaded_count=int(source_info["loaded_count"]),
  )
  csv_text = signals_to_csv(signals)
  json_text = signals_to_json(
    signals,
    watch_profile,
    data_source=str(source_info["label"]),
    loaded_count=int(source_info["loaded_count"]),
  )

  st.title("Tech Cartography v9")
  st.caption("軽量R&Dシグナル監視エージェント")
  render_notice()
  st.caption(
    "ローカルのデモデータまたはアップロードされたCSV/JSONのみで動作します。"
    "BigQuery、OpenAlex、Web検索、OCR、PDFスキャン、"
    "スケジューラ、外部APIは起動時に実行しません。"
  )

  tabs = st.tabs(V9_TAB_LABELS)
  with tabs[0]:
    theme_events = render_theme_setup_tab(profile_summary, st.session_state.get(STATE_PROFILE_MESSAGE))
  with tabs[1]:
    render_sources_tab(
      source_rows,
      operation_rows,
      source_info,
      csv_template_text,
      json_template_text,
    )
  with tabs[2]:
    signal_events = render_top_signals_tab(
      signals,
      display_signal_dicts,
      source_info,
      st.session_state.get(STATE_SNAPSHOT_MESSAGE),
    )
  with tabs[3]:
    weekly_events = render_weekly_updates_tab(
      signals,
      source_info,
      snapshot_labels,
      diff_result,
      drift,
      history_rows,
      previous_snapshot_payload,
      st.session_state.get(STATE_COMPARE_MESSAGE),
    )
  with tabs[4]:
    profile_events = render_watch_profile_tab(
      watch_profile,
      profile_summary,
      query_previews,
      suggestions,
      st.session_state.get(STATE_PROFILE_MESSAGE),
    )
  with tabs[5]:
    digest_events = render_digest_export_tab(
      markdown_text,
      csv_text,
      json_text,
      source_info,
      st.session_state.get(STATE_DIGEST_MESSAGE),
    )

  if theme_events["save_profile"] or profile_events["save_profile"]:
    _save_profile_and_rerun(watch_profile_dict)

  if theme_events["load_profile"] or profile_events["load_profile"]:
    _load_profile_into_widgets(raw_profile)

  if profile_events["apply_suggestions"]:
    _apply_suggestions_and_rerun(watch_profile_dict, suggestions)

  if signal_events["save_snapshot"]:
    path = save_snapshot(
      signals=[signal.to_dict() for signal in signals],
      watch_profile=watch_profile_dict,
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
        watch_profile=watch_profile_dict,
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

