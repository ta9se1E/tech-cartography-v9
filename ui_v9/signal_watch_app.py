"""Streamlit entry for the lightweight Tech Cartography v9 signal watch UI."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
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
from services_v9.patent_bigquery_query import (
  build_patent_bigquery_preview,
  execute_patent_bigquery_retrieval,
  run_patent_bigquery_dry_run,
  save_patent_dry_run_artifacts,
  save_patent_retrieval_artifacts,
)
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
from services_v9.review_state import apply_reviews_to_signals
from services_v9.global_web_plan_schema import DEFAULT_GLOBAL_WEB_INTENTS, load_global_web_country_profiles
from services_v9.search_plan import DEFAULT_SOURCE_LIMITS, build_unified_search_plan, summarize_search_plan_ja, validate_search_plan
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
STATE_REVIEWS_BY_SIGNAL_ID = "reviews_by_signal_id"
STATE_SEARCH_PLAN_DATA = "state_search_plan_data"
STATE_SEARCH_PLAN_STATUS_MESSAGE = "state_search_plan_status_message"
STATE_SEARCH_PLAN_FORCE_REGENERATE = "state_search_plan_force_regenerate"
STATE_PATENT_BIGQUERY_MESSAGE = "state_patent_bigquery_message"
STATE_PATENT_BIGQUERY_DRY_RUN = "state_patent_bigquery_dry_run"
STATE_PATENT_BIGQUERY_APPROVED_QUERY_IDS = "state_patent_bigquery_approved_query_ids"
STATE_PATENT_RETRIEVAL_RESULT = "state_patent_retrieval_result"
STATE_PATENT_RETRIEVAL_MESSAGE = "state_patent_retrieval_message"

UI_SEARCH_TOTAL_LIMIT_KEY = "ui_search_total_limit"
UI_SEARCH_PATENT_LIMIT_KEY = "ui_search_patent_limit"
UI_SEARCH_PAPER_LIMIT_KEY = "ui_search_paper_limit"
UI_SEARCH_WEB_LIMIT_KEY = "ui_search_web_limit"
UI_SEARCH_COMPANY_LIMIT_KEY = "ui_search_company_limit"
UI_SEARCH_TIME_RANGE_KEY = "ui_search_time_range"
UI_SEARCH_WEB_HIGH_MAX_KEY = "ui_search_web_high_max_results"
UI_SEARCH_WEB_MEDIUM_MAX_KEY = "ui_search_web_medium_max_results"
UI_SEARCH_WEB_LOW_MAX_KEY = "ui_search_web_low_max_results"
UI_SEARCH_COMPANY_HIGH_MAX_KEY = "ui_search_company_high_max_results"
UI_SEARCH_COMPANY_MEDIUM_MAX_KEY = "ui_search_company_medium_max_results"
UI_SEARCH_COMPANY_LOW_MAX_KEY = "ui_search_company_low_max_results"
UI_MANUAL_QUERY_SOURCE_KEY = "ui_manual_query_source"
UI_MANUAL_QUERY_STRATEGY_KEY = "ui_manual_query_strategy"
UI_MANUAL_QUERY_LANGUAGE_KEY = "ui_manual_query_language"
UI_MANUAL_QUERY_TEXT_KEY = "ui_manual_query_text"
UI_MANUAL_QUERY_COUNTRY_KEY = "ui_manual_query_country"
UI_MANUAL_QUERY_INTENT_KEY = "ui_manual_query_intent"
UI_MANUAL_QUERY_BUCKET_KEY = "ui_manual_query_bucket"
UI_MANUAL_QUERY_PRIORITY_KEY = "ui_manual_query_priority"
UI_MANUAL_QUERY_LOCAL_KEY = "ui_manual_query_local"
UI_MANUAL_QUERY_FALLBACK_KEY = "ui_manual_query_fallback"
UI_MANUAL_QUERY_MAX_RESULTS_KEY = "ui_manual_query_max_results"
UI_PATENT_BIGQUERY_QUERY_ID_KEY = "ui_patent_bigquery_query_id"
UI_PATENT_BIGQUERY_MAX_RESULTS_KEY = "ui_patent_bigquery_max_results"


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
  st.session_state.setdefault(STATE_REVIEWS_BY_SIGNAL_ID, {})
  st.session_state.setdefault(STATE_PATENT_BIGQUERY_DRY_RUN, {})
  st.session_state.setdefault(STATE_PATENT_BIGQUERY_APPROVED_QUERY_IDS, [])
  if UI_THEME_NAME_KEY not in st.session_state:
    _set_profile_widgets(profile_dict)
  _ensure_search_plan_widget_defaults(profile_dict)


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


def _stable_signal_id(signal: dict[str, object], index: int = 0) -> str:
  signal_id = str(signal.get("id", "") or "").strip()
  if signal_id:
    return signal_id

  parts = [
    str(signal.get("title", "") or "").strip(),
    str(signal.get("type", "") or "").strip(),
    str(signal.get("source_url", "") or "").strip(),
    str(signal.get("source_name", "") or "").strip(),
    str(signal.get("published_date", "") or "").strip(),
    str(signal.get("summary", "") or "").strip(),
    " | ".join(str(item).strip() for item in signal.get("tags", []) if str(item).strip()),
    " | ".join(str(item).strip() for item in signal.get("companies", []) if str(item).strip()),
  ]
  raw_key = "||".join(parts)
  if not raw_key.strip():
    raw_key = f"signal-index-{index}"
  digest = hashlib.sha256(raw_key.encode("utf-8")).hexdigest()[:12]
  return f"generated_{digest}"


def _prepare_display_signal_dicts(
  signal_dicts: list[dict[str, object]],
  watch_profile_dict: dict[str, object],
  reviews_by_signal_id: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
  ensured_ids: list[dict[str, object]] = []
  for index, signal in enumerate(signal_dicts):
    copied_signal = dict(signal)
    copied_signal["id"] = _stable_signal_id(copied_signal, index=index)
    ensured_ids.append(copied_signal)

  reviewed_signals = apply_reviews_to_signals(ensured_ids, reviews_by_signal_id)
  return attach_score_explanations(reviewed_signals, watch_profile_dict)


def _prepare_reviewed_signal_dicts(
  signal_dicts: list[dict[str, object]],
  watch_profile_dict: dict[str, object],
  reviews_by_signal_id: dict[str, dict[str, object]],
) -> list[dict[str, object]]:
  reviewed_display_signals = _prepare_display_signal_dicts(
    signal_dicts,
    watch_profile_dict,
    reviews_by_signal_id,
  )
  cleaned_signals: list[dict[str, object]] = []
  for signal in reviewed_display_signals:
    cleaned_signal = dict(signal)
    cleaned_signal.pop("score_explanation", None)
    cleaned_signals.append(cleaned_signal)
  return cleaned_signals


def _stable_payload_signature(payload: object) -> str:
  serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
  return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def _country_enabled_key(country_code: str) -> str:
  return f"ui_search_country_enabled_{country_code}"


def _country_priority_key(country_code: str) -> str:
  return f"ui_search_country_priority_{country_code}"


def _country_official_key(country_code: str) -> str:
  return f"ui_search_country_official_{country_code}"


def _country_fallback_key(country_code: str) -> str:
  return f"ui_search_country_fallback_{country_code}"


def _intent_enabled_key(intent: str) -> str:
  return f"ui_search_intent_enabled_{intent}"


def _default_search_plan_settings(profile_dict: dict[str, object]) -> dict[str, object]:
  countries_in_profile = {
    str(item or "").strip().upper()
    for item in list(profile_dict.get("countries", []))
    if str(item or "").strip()
  }
  all_country_profiles = load_global_web_country_profiles()
  enable_all = not countries_in_profile
  country_settings = {
    str(item["country_region_code"]): {
      "enabled": enable_all or str(item["country_region_code"]) in countries_in_profile,
      "priority": int(item.get("priority", 0) or 0),
      "official_source_priority": bool(item.get("official_source_priority", False)),
      "english_fallback_enabled": bool(item.get("english_fallback_enabled", False)),
    }
    for item in all_country_profiles
  }
  return {
    "total_limit": 1000,
    "source_limits": dict(DEFAULT_SOURCE_LIMITS),
    "global_web": {
      "time_range": "12m",
      "country_settings": country_settings,
      "intent_settings": {intent: True for intent in DEFAULT_GLOBAL_WEB_INTENTS},
      "max_results": {
        "web_high": 10,
        "web_medium": 4,
        "web_low": 2,
        "company_high": 5,
        "company_medium": 4,
        "company_low": 2,
      },
    },
  }


def _ensure_search_plan_widget_defaults(profile_dict: dict[str, object]) -> None:
  defaults = _default_search_plan_settings(profile_dict)
  source_limits = dict(defaults["source_limits"])
  global_web = dict(defaults["global_web"])
  max_results = dict(global_web["max_results"])
  st.session_state.setdefault(UI_SEARCH_TOTAL_LIMIT_KEY, int(defaults["total_limit"]))
  st.session_state.setdefault(UI_SEARCH_PATENT_LIMIT_KEY, int(source_limits["patent"]))
  st.session_state.setdefault(UI_SEARCH_PAPER_LIMIT_KEY, int(source_limits["paper"]))
  st.session_state.setdefault(UI_SEARCH_WEB_LIMIT_KEY, int(source_limits["web"]))
  st.session_state.setdefault(UI_SEARCH_COMPANY_LIMIT_KEY, int(source_limits["company"]))
  st.session_state.setdefault(UI_SEARCH_TIME_RANGE_KEY, str(global_web["time_range"]))
  st.session_state.setdefault(UI_SEARCH_WEB_HIGH_MAX_KEY, int(max_results["web_high"]))
  st.session_state.setdefault(UI_SEARCH_WEB_MEDIUM_MAX_KEY, int(max_results["web_medium"]))
  st.session_state.setdefault(UI_SEARCH_WEB_LOW_MAX_KEY, int(max_results["web_low"]))
  st.session_state.setdefault(UI_SEARCH_COMPANY_HIGH_MAX_KEY, int(max_results["company_high"]))
  st.session_state.setdefault(UI_SEARCH_COMPANY_MEDIUM_MAX_KEY, int(max_results["company_medium"]))
  st.session_state.setdefault(UI_SEARCH_COMPANY_LOW_MAX_KEY, int(max_results["company_low"]))

  for country_code, settings in dict(global_web["country_settings"]).items():
    st.session_state.setdefault(_country_enabled_key(country_code), bool(settings["enabled"]))
    st.session_state.setdefault(_country_priority_key(country_code), int(settings["priority"]))
    st.session_state.setdefault(_country_official_key(country_code), bool(settings["official_source_priority"]))
    st.session_state.setdefault(_country_fallback_key(country_code), bool(settings["english_fallback_enabled"]))

  for intent, enabled in dict(global_web["intent_settings"]).items():
    st.session_state.setdefault(_intent_enabled_key(intent), bool(enabled))

  st.session_state.setdefault(UI_MANUAL_QUERY_SOURCE_KEY, "patent")
  st.session_state.setdefault(UI_MANUAL_QUERY_STRATEGY_KEY, "manual")
  st.session_state.setdefault(UI_MANUAL_QUERY_LANGUAGE_KEY, "ja")
  st.session_state.setdefault(UI_MANUAL_QUERY_TEXT_KEY, "")
  st.session_state.setdefault(UI_MANUAL_QUERY_COUNTRY_KEY, "JP")
  st.session_state.setdefault(UI_MANUAL_QUERY_INTENT_KEY, "research_development")
  st.session_state.setdefault(UI_MANUAL_QUERY_BUCKET_KEY, "web")
  st.session_state.setdefault(UI_MANUAL_QUERY_PRIORITY_KEY, "high")
  st.session_state.setdefault(UI_MANUAL_QUERY_LOCAL_KEY, "")
  st.session_state.setdefault(UI_MANUAL_QUERY_FALLBACK_KEY, "")
  st.session_state.setdefault(UI_MANUAL_QUERY_MAX_RESULTS_KEY, 10)


def _build_search_plan_settings_from_session() -> dict[str, object]:
  country_settings = {}
  for profile in load_global_web_country_profiles():
    code = str(profile["country_region_code"])
    country_settings[code] = {
      "enabled": bool(st.session_state.get(_country_enabled_key(code), True)),
      "priority": int(st.session_state.get(_country_priority_key(code), int(profile.get("priority", 0) or 0)) or 0),
      "official_source_priority": bool(st.session_state.get(_country_official_key(code), bool(profile.get("official_source_priority", False)))),
      "english_fallback_enabled": bool(st.session_state.get(_country_fallback_key(code), bool(profile.get("english_fallback_enabled", False)))),
    }

  intent_settings = {
    intent: bool(st.session_state.get(_intent_enabled_key(intent), True))
    for intent in DEFAULT_GLOBAL_WEB_INTENTS
  }

  return {
    "total_limit": int(st.session_state.get(UI_SEARCH_TOTAL_LIMIT_KEY, 1000) or 1000),
    "source_limits": {
      "patent": int(st.session_state.get(UI_SEARCH_PATENT_LIMIT_KEY, DEFAULT_SOURCE_LIMITS["patent"]) or 0),
      "paper": int(st.session_state.get(UI_SEARCH_PAPER_LIMIT_KEY, DEFAULT_SOURCE_LIMITS["paper"]) or 0),
      "web": int(st.session_state.get(UI_SEARCH_WEB_LIMIT_KEY, DEFAULT_SOURCE_LIMITS["web"]) or 0),
      "company": int(st.session_state.get(UI_SEARCH_COMPANY_LIMIT_KEY, DEFAULT_SOURCE_LIMITS["company"]) or 0),
    },
    "global_web": {
      "time_range": str(st.session_state.get(UI_SEARCH_TIME_RANGE_KEY, "12m") or "12m"),
      "country_settings": country_settings,
      "intent_settings": intent_settings,
      "max_results": {
        "web_high": int(st.session_state.get(UI_SEARCH_WEB_HIGH_MAX_KEY, 10) or 10),
        "web_medium": int(st.session_state.get(UI_SEARCH_WEB_MEDIUM_MAX_KEY, 4) or 4),
        "web_low": int(st.session_state.get(UI_SEARCH_WEB_LOW_MAX_KEY, 2) or 2),
        "company_high": int(st.session_state.get(UI_SEARCH_COMPANY_HIGH_MAX_KEY, 5) or 5),
        "company_medium": int(st.session_state.get(UI_SEARCH_COMPANY_MEDIUM_MAX_KEY, 4) or 4),
        "company_low": int(st.session_state.get(UI_SEARCH_COMPANY_LOW_MAX_KEY, 2) or 2),
      },
    },
  }


def _normalize_manual_query(raw_query: dict[str, object]) -> dict[str, object]:
  query = dict(raw_query)
  query_id = str(query.get("query_id", "") or "").strip()
  if not query_id:
    seed = {
      "source": query.get("source"),
      "query_text": query.get("query_text"),
      "query_local": query.get("query_local"),
      "country_region_code": query.get("country_region_code"),
      "web_intent": query.get("web_intent"),
    }
    query_id = f"manual_{_stable_payload_signature(seed)[:12]}"
  normalized = {
    "query_id": query_id,
    "origin": "manual",
    "source": str(query.get("source", "patent") or "patent"),
    "language": str(query.get("language", "ja") or "ja"),
    "strategy": str(query.get("strategy", "manual") or "manual"),
    "query_text": str(query.get("query_text", "") or "").strip(),
    "country_region_code": str(query.get("country_region_code", "") or "").strip().upper(),
    "web_intent": str(query.get("web_intent", "") or "").strip(),
    "result_bucket": str(query.get("result_bucket", "web") or "web"),
    "priority": str(query.get("priority", "high") or "high"),
    "enabled": bool(query.get("enabled", True)),
    "query_local": str(query.get("query_local", "") or "").strip(),
    "query_english_fallback": str(query.get("query_english_fallback", "") or "").strip(),
    "local_query_generation_mode": str(query.get("local_query_generation_mode", "manual") or "manual"),
    "fallback_execution_mode": str(query.get("fallback_execution_mode", "manual_optional") or "manual_optional"),
    "provider_primary": str(query.get("provider_primary", "manual_input") or "manual_input"),
    "provider_fallback": str(query.get("provider_fallback", "") or "").strip(),
    "verification_provider": str(query.get("verification_provider", "manual_verification_queue") or "manual_verification_queue"),
    "search_depth": str(query.get("search_depth", "discovery") or "discovery"),
    "max_results": int(query.get("max_results", 10) or 10),
    "generated_from": list(query.get("generated_from", ["manual"])) if isinstance(query.get("generated_from"), list) else ["manual"],
    "exclude_terms": list(query.get("exclude_terms", [])) if isinstance(query.get("exclude_terms"), list) else [],
    "dedupe_key": str(query.get("dedupe_key", "") or "").strip(),
    "duplicate_of": str(query.get("duplicate_of", "") or "").strip() or None,
  }
  if not normalized["dedupe_key"]:
    dedupe_seed = {
      "source": normalized["source"],
      "query_text": normalized["query_text"],
      "query_local": normalized["query_local"],
      "country_region_code": normalized["country_region_code"],
      "web_intent": normalized["web_intent"],
    }
    normalized["dedupe_key"] = _stable_payload_signature(dedupe_seed)[:16]
  return normalized


def _manual_queries_by_source(manual_queries: list[dict[str, object]]) -> dict[str, list[dict[str, object]]]:
  grouped = {source: [] for source in ["patent", "paper", "web", "company", "global_web"]}
  for query in manual_queries:
    source = str(query.get("source", "patent") or "patent")
    grouped.setdefault(source, []).append(query)
  return grouped


def _validate_manual_queries(manual_queries: list[dict[str, object]]) -> list[str]:
  errors: list[str] = []
  seen_ids: set[str] = set()
  for query in manual_queries:
    query_id = str(query.get("query_id", "") or "").strip()
    if not query_id:
      errors.append("手動queryに query_id がありません。")
      continue
    if query_id in seen_ids:
      errors.append(f"手動query {query_id} が重複しています。")
    seen_ids.add(query_id)
    source = str(query.get("source", "") or "").strip()
    if source == "global_web":
      if not str(query.get("query_local", "") or "").strip():
        errors.append(f"{query_id} の query_local が空です。")
    else:
      if not str(query.get("query_text", "") or "").strip():
        errors.append(f"{query_id} の query_text が空です。")
  return errors


def _build_search_plan_view(
  profile_dict: dict[str, object],
  settings: dict[str, object],
  manual_queries: list[dict[str, object]],
) -> dict[str, object]:
  normalized_manual_queries = [_normalize_manual_query(item) for item in manual_queries]
  plan = build_unified_search_plan(
    profile_dict,
    total_limit=int(settings["total_limit"]),
    source_limits=dict(settings["source_limits"]),
    global_web_options=dict(settings["global_web"]),
  )
  validation_errors = validate_search_plan(plan) + _validate_manual_queries(normalized_manual_queries)
  manual_by_source = _manual_queries_by_source(normalized_manual_queries)
  global_web_plan = dict(plan.get("global_web_plan", {}) or {})
  summary = {
    "plan_summary_text": summarize_search_plan_ja(plan),
    "country_coverage": list(global_web_plan.get("country_coverage", [])),
    "discovery_query_count": sum(
      len(source_plan.get("queries", []) or [])
      for source_plan in dict(plan.get("plans", {})).values()
      if isinstance(source_plan, dict)
    ) + len(global_web_plan.get("queries", []) or []) + len(normalized_manual_queries),
    "verification_planned_count": int(global_web_plan.get("verification_planned_count", 0) or 0) + sum(
      int(query.get("max_results", 0) or 0)
      for query in manual_by_source.get("global_web", [])
      if bool(query.get("enabled", True))
    ),
    "translation_planned_count": int(global_web_plan.get("translation_planned_count", 0) or 0) + sum(
      1
      for query in manual_by_source.get("global_web", [])
      if str(query.get("local_query_generation_mode", "") or "") == "translation_pending"
    ),
    "provider_routing": list(global_web_plan.get("provider_routing", [])),
    "validation_errors": validation_errors,
  }
  return {
    "plan": plan,
    "manual_queries": normalized_manual_queries,
    "generated_at": datetime.now().isoformat(timespec="seconds"),
    "profile_signature": _stable_payload_signature(profile_dict),
    "settings_signature": _stable_payload_signature(settings),
    "summary": summary,
  }


def _refresh_search_plan_state(
  profile_dict: dict[str, object],
  *,
  manual_queries: list[dict[str, object]] | None = None,
  status_message: str | None = None,
) -> dict[str, object]:
  current_settings = _build_search_plan_settings_from_session()
  existing = dict(st.session_state.get(STATE_SEARCH_PLAN_DATA, {}) or {})
  view = _build_search_plan_view(
    profile_dict,
    current_settings,
    manual_queries if manual_queries is not None else list(existing.get("manual_queries", [])),
  )
  st.session_state[STATE_SEARCH_PLAN_DATA] = view
  if status_message is not None:
    st.session_state[STATE_SEARCH_PLAN_STATUS_MESSAGE] = status_message
  return view


def _build_manual_query_from_session() -> tuple[dict[str, object] | None, str | None]:
  source = str(st.session_state.get(UI_MANUAL_QUERY_SOURCE_KEY, "patent") or "patent")
  strategy = str(st.session_state.get(UI_MANUAL_QUERY_STRATEGY_KEY, "manual") or "manual").strip() or "manual"
  if source == "global_web":
    query_local = str(st.session_state.get(UI_MANUAL_QUERY_LOCAL_KEY, "") or "").strip()
    if not query_local:
      return None, "Global Web の手動queryには query_local が必要です。"
    return {
      "source": "global_web",
      "strategy": strategy,
      "country_region_code": str(st.session_state.get(UI_MANUAL_QUERY_COUNTRY_KEY, "JP") or "JP").strip().upper(),
      "web_intent": str(st.session_state.get(UI_MANUAL_QUERY_INTENT_KEY, "research_development") or "research_development"),
      "result_bucket": str(st.session_state.get(UI_MANUAL_QUERY_BUCKET_KEY, "web") or "web"),
      "priority": str(st.session_state.get(UI_MANUAL_QUERY_PRIORITY_KEY, "high") or "high"),
      "enabled": True,
      "query_local": query_local,
      "query_english_fallback": str(st.session_state.get(UI_MANUAL_QUERY_FALLBACK_KEY, "") or "").strip(),
      "local_query_generation_mode": "manual",
      "fallback_execution_mode": "manual_optional",
      "provider_primary": "manual_input",
      "provider_fallback": "manual_input",
      "verification_provider": "manual_verification_queue",
      "search_depth": "discovery",
      "max_results": int(st.session_state.get(UI_MANUAL_QUERY_MAX_RESULTS_KEY, 10) or 10),
      "generated_from": ["manual"],
      "exclude_terms": [],
    }, None

  query_text = str(st.session_state.get(UI_MANUAL_QUERY_TEXT_KEY, "") or "").strip()
  if not query_text:
    return None, "手動queryには検索文字列が必要です。"
  return {
    "source": source,
    "language": str(st.session_state.get(UI_MANUAL_QUERY_LANGUAGE_KEY, "ja") or "ja"),
    "strategy": strategy,
    "query_text": query_text,
    "enabled": True,
    "generated_from": ["manual"],
    "exclude_terms": [],
  }, None


def _ensure_patent_bigquery_widget_defaults(search_plan_state: dict[str, object]) -> None:
  patent_queries = list(dict(search_plan_state.get("plan", {}) or {}).get("plans", {}).get("patent", {}).get("queries", []) or [])
  if patent_queries:
    first_query_id = str(patent_queries[0].get("query_id", "") or "")
    if first_query_id:
      st.session_state.setdefault(UI_PATENT_BIGQUERY_QUERY_ID_KEY, first_query_id)
  patent_limit = int(
    dict(search_plan_state.get("plan", {}) or {}).get("plans", {}).get("patent", {}).get("limit", 100) or 100
  )
  st.session_state.setdefault(UI_PATENT_BIGQUERY_MAX_RESULTS_KEY, min(max(patent_limit, 1), 1000))


def _build_patent_bigquery_ui_state(
  search_plan_state: dict[str, object],
  watch_profile_dict: dict[str, object],
) -> dict[str, object]:
  _ensure_patent_bigquery_widget_defaults(search_plan_state)
  plan = dict(search_plan_state.get("plan", {}) or {})
  preview = build_patent_bigquery_preview(
    plan,
    watch_profile_dict,
    selected_query_id=str(st.session_state.get(UI_PATENT_BIGQUERY_QUERY_ID_KEY, "") or ""),
    time_range=str(st.session_state.get(UI_SEARCH_TIME_RANGE_KEY, "12m") or "12m"),
    max_results=int(st.session_state.get(UI_PATENT_BIGQUERY_MAX_RESULTS_KEY, 100) or 100),
  )
  selected_query_id = str(preview.get("selected_query_id", "") or "")
  dry_run_map = dict(st.session_state.get(STATE_PATENT_BIGQUERY_DRY_RUN, {}) or {})
  approved_query_ids = set(str(item) for item in list(st.session_state.get(STATE_PATENT_BIGQUERY_APPROVED_QUERY_IDS, []) or []))
  return {
    "preview": preview,
    "dry_run_result": dict(dry_run_map.get(selected_query_id, {}) or {}),
    "approved": selected_query_id in approved_query_ids,
    "approved_query_ids": sorted(approved_query_ids),
    "retrieval_result": dict(st.session_state.get(STATE_PATENT_RETRIEVAL_RESULT, {}) or {}),
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
  _refresh_search_plan_state(profile_dict, status_message="監視プロファイル保存に合わせて検索計画を再生成しました。")
  st.rerun()


def _load_profile_into_widgets(default_profile: dict[str, object]) -> None:
  profile_dict = load_watch_profile(default_profile=default_profile)
  st.session_state[STATE_PENDING_PROFILE] = profile_dict
  st.session_state[STATE_PROFILE_MESSAGE] = "保存済み監視プロファイルを読み込みました。"
  st.session_state[STATE_SEARCH_PLAN_FORCE_REGENERATE] = True
  st.rerun()


def _apply_suggestions_and_rerun(profile_dict: dict[str, object], suggestions: list[str]) -> None:
  updated = apply_watch_profile_suggestions(WatchProfile.from_dict(profile_dict), suggestions)
  st.session_state[STATE_PENDING_PROFILE] = updated.to_dict()
  st.session_state[STATE_PROFILE_MESSAGE] = "監視プロファイルにデモ提案を反映しました。"
  st.session_state[STATE_SEARCH_PLAN_FORCE_REGENERATE] = True
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
  current_search_plan_settings = _build_search_plan_settings_from_session()
  current_profile_signature = _stable_payload_signature(watch_profile_dict)
  current_settings_signature = _stable_payload_signature(current_search_plan_settings)
  existing_search_plan_state = dict(st.session_state.get(STATE_SEARCH_PLAN_DATA, {}) or {})
  force_regenerate = bool(st.session_state.pop(STATE_SEARCH_PLAN_FORCE_REGENERATE, False))
  if (
    force_regenerate
    or not existing_search_plan_state
    or not existing_search_plan_state.get("plan")
  ):
    existing_search_plan_state = _refresh_search_plan_state(
      watch_profile_dict,
      status_message=str(st.session_state.get(STATE_SEARCH_PLAN_STATUS_MESSAGE, "") or "") or None,
    )
  search_plan_state = dict(existing_search_plan_state)
  search_plan_state["profile_signature_changed"] = (
    str(search_plan_state.get("profile_signature", "") or "") != current_profile_signature
  )
  search_plan_state["settings_signature_changed"] = (
    str(search_plan_state.get("settings_signature", "") or "") != current_settings_signature
  )
  search_plan_state["stale"] = bool(
    search_plan_state["profile_signature_changed"] or search_plan_state["settings_signature_changed"]
  )
  st.session_state[STATE_SEARCH_PLAN_DATA] = search_plan_state
  patent_bigquery_state = _build_patent_bigquery_ui_state(search_plan_state, watch_profile_dict)
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
  reviews_by_signal_id = dict(st.session_state.get(STATE_REVIEWS_BY_SIGNAL_ID, {}) or {})

  snapshot_labels, snapshot_map, history_rows = _build_snapshot_history()
  previous_snapshot_payload = st.session_state.get(STATE_PREVIOUS_SNAPSHOT)
  compare_enabled = bool(st.session_state.get(STATE_COMPARE_ENABLED, False))

  diff_result = None
  if compare_enabled and previous_snapshot_payload:
    current_signal_dicts = apply_snapshot_status(current_signal_dicts, previous_snapshot_payload.get("signals", []))
    diff_result = compare_snapshots(previous_snapshot_payload.get("signals", []), current_signal_dicts)

  display_signal_dicts = _prepare_display_signal_dicts(current_signal_dicts, watch_profile_dict, reviews_by_signal_id)
  signals = sorted(
    [Signal.from_dict(item) for item in display_signal_dicts],
    key=lambda item: (item.score, item.published_date, item.title),
    reverse=True,
  )
  suggestions = suggest_watch_profile_updates(signals, watch_profile)
  drift = compute_theme_drift_alert(signals, watch_profile)
  source_rows = build_source_rows(signals)
  operation_rows = build_operation_status_rows()
  csv_text = signals_to_csv(signals)

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
    theme_events = render_theme_setup_tab(
      profile_summary,
      search_plan_state,
      st.session_state.get(STATE_PROFILE_MESSAGE),
      st.session_state.get(STATE_SEARCH_PLAN_STATUS_MESSAGE),
    )
  with tabs[1]:
    source_events = render_sources_tab(
      source_rows,
      operation_rows,
      source_info,
      csv_template_text,
      json_template_text,
      search_plan_state,
      st.session_state.get(STATE_SEARCH_PLAN_STATUS_MESSAGE),
      patent_bigquery_state,
      st.session_state.get(STATE_PATENT_BIGQUERY_MESSAGE),
      st.session_state.get(STATE_PATENT_RETRIEVAL_MESSAGE),
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
      display_signal_dicts,
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
  latest_reviews_by_signal_id = dict(st.session_state.get(STATE_REVIEWS_BY_SIGNAL_ID, {}) or {})
  latest_reviewed_signals = _prepare_reviewed_signal_dicts(
    current_signal_dicts,
    watch_profile_dict,
    latest_reviews_by_signal_id,
  )
  latest_digest_signals = _prepare_display_signal_dicts(
    current_signal_dicts,
    watch_profile_dict,
    latest_reviews_by_signal_id,
  )
  markdown_text = build_weekly_digest_markdown(
    signals,
    watch_profile,
    data_source=str(source_info["label"]),
    loaded_count=int(source_info["loaded_count"]),
    reviewed_signals=latest_digest_signals,
  )
  json_text = signals_to_json(
    latest_reviewed_signals,
    watch_profile,
    data_source=str(source_info["label"]),
    loaded_count=int(source_info["loaded_count"]),
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

  if theme_events.get("regenerate_search_plan") or source_events.get("regenerate_search_plan"):
    _refresh_search_plan_state(
      watch_profile_dict,
      status_message="検索計画を再生成しました。外部検索はまだOFFのままです。",
    )
    st.rerun()

  if source_events.get("add_manual_query"):
    manual_query, error_message = _build_manual_query_from_session()
    if error_message:
      st.session_state[STATE_SEARCH_PLAN_STATUS_MESSAGE] = error_message
    else:
      existing_manual_queries = list(search_plan_state.get("manual_queries", []))
      existing_manual_queries.append(dict(manual_query or {}))
      _refresh_search_plan_state(
        watch_profile_dict,
        manual_queries=existing_manual_queries,
        status_message="手動queryを追加しました。自動生成queryは保持されています。",
      )
    st.rerun()

  delete_manual_query_ids = list(source_events.get("delete_manual_query_ids", []))
  if delete_manual_query_ids:
    updated_manual_queries = [
      query
      for query in list(search_plan_state.get("manual_queries", []))
      if str(query.get("query_id", "") or "") not in set(delete_manual_query_ids)
    ]
    _refresh_search_plan_state(
      watch_profile_dict,
      manual_queries=updated_manual_queries,
      status_message="手動queryを削除しました。",
    )
    st.rerun()

  if source_events.get("run_patent_dry_run"):
    dry_run_result = run_patent_bigquery_dry_run(dict(patent_bigquery_state.get("preview", {}) or {}))
    current_dry_run_map = dict(st.session_state.get(STATE_PATENT_BIGQUERY_DRY_RUN, {}) or {})
    query_id = str(dict(patent_bigquery_state.get("preview", {}) or {}).get("selected_query_id", "") or "")
    if query_id:
      current_dry_run_map[query_id] = dry_run_result
    st.session_state[STATE_PATENT_BIGQUERY_DRY_RUN] = current_dry_run_map
    artifact_paths = save_patent_dry_run_artifacts(dict(patent_bigquery_state.get("preview", {}) or {}), dry_run_result)
    st.session_state[STATE_PATENT_BIGQUERY_MESSAGE] = (
      f"特許BigQuery dry-run結果を保存しました: {artifact_paths['dry_run_json']} "
      f"(SQL: {artifact_paths['sql']}, validation: {artifact_paths['validation_csv']})"
    )
    st.rerun()

  if source_events.get("approve_patent_query"):
    query_id = str(dict(patent_bigquery_state.get("preview", {}) or {}).get("selected_query_id", "") or "")
    dry_run_result = dict(patent_bigquery_state.get("dry_run_result", {}) or {})
    if not query_id or str(dry_run_result.get("dry_run_status", "") or "") != "ok" or bool(dry_run_result.get("would_be_blocked_by_max_bytes", False)):
      st.session_state[STATE_PATENT_RETRIEVAL_MESSAGE] = "dry-run 成功済みかつ費用上限内の query だけ承認できます。"
    else:
      approved_query_ids = set(str(item) for item in list(st.session_state.get(STATE_PATENT_BIGQUERY_APPROVED_QUERY_IDS, []) or []))
      approved_query_ids.add(query_id)
      st.session_state[STATE_PATENT_BIGQUERY_APPROVED_QUERY_IDS] = sorted(approved_query_ids)
      st.session_state[STATE_PATENT_RETRIEVAL_MESSAGE] = f"query `{query_id}` を実行承認しました。"
    st.rerun()

  if source_events.get("run_patent_retrieval"):
    query_id = str(dict(patent_bigquery_state.get("preview", {}) or {}).get("selected_query_id", "") or "")
    approved_query_ids = set(str(item) for item in list(st.session_state.get(STATE_PATENT_BIGQUERY_APPROVED_QUERY_IDS, []) or []))
    dry_run_result = dict(patent_bigquery_state.get("dry_run_result", {}) or {})
    retrieval_result = execute_patent_bigquery_retrieval(
      dict(patent_bigquery_state.get("preview", {}) or {}),
      dry_run_result,
      approved=(query_id in approved_query_ids),
    )
    st.session_state[STATE_PATENT_RETRIEVAL_RESULT] = retrieval_result
    artifact_paths = save_patent_retrieval_artifacts(
      dict(patent_bigquery_state.get("preview", {}) or {}),
      dry_run_result,
      retrieval_result,
    )
    st.session_state[STATE_PATENT_RETRIEVAL_MESSAGE] = (
      f"特許候補 staging を保存しました: {artifact_paths['staged_json']} / {artifact_paths['staged_csv']} "
      f"(log: {artifact_paths['retrieval_log_json']})"
    )
    st.rerun()

  if signal_events["save_snapshot"]:
    path = save_snapshot(
      signals=latest_reviewed_signals,
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
        signals=latest_reviewed_signals,
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

