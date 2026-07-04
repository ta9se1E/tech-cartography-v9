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
from services_v9.email_delivery import (
  build_digest_email_preview,
  load_email_delivery_config,
  run_email_delivery_dry_run,
  save_email_delivery_log,
  send_digest_email_self_only,
)
from services_v9.paper_openalex_retrieval import (
  build_openalex_paper_preview,
  execute_openalex_paper_retrieval,
  save_openalex_paper_retrieval_artifacts,
)
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
from services_v9.retrieval_run_store import (
  build_retrieval_run_manifest,
  find_latest_compatible_manifest,
  load_candidates_from_manifest,
  save_retrieval_run_manifest,
  stable_payload_signature,
)
from services_v9.global_web_plan_schema import DEFAULT_GLOBAL_WEB_INTENTS, load_global_web_country_profiles
from services_v9.search_plan import DEFAULT_SOURCE_LIMITS, build_unified_search_plan, summarize_search_plan_ja, validate_search_plan
from services_v9.score_explainer import attach_score_explanations
from services_v9.signal_loader import (
  enrich_signals_with_profile,
  load_signals_from_csv_text,
  load_signals_from_json_text,
)
from services_v9.signal_integration import apply_signal_change_tracking, integrate_multi_source_signals
from services_v9.signal_models import Signal, WatchProfile
from services_v9.signal_scoring import (
  apply_watch_profile_suggestions,
  compute_theme_drift_alert,
  enrich_signals,
  suggest_watch_profile_updates,
)
from services_v9.signal_template import build_csv_template, build_json_template
from services_v9.snapshot_diff import apply_snapshot_status, compare_snapshots
from services_v9.web_company_retrieval import (
  build_global_web_retrieval_preview,
  execute_global_web_retrieval,
  save_global_web_retrieval_artifacts,
)
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
UI_EMAIL_CONFIRM_SEND_KEY = "ui_email_confirm_send"

STATE_PENDING_PROFILE = "state_pending_watch_profile"
STATE_PROFILE_MESSAGE = "state_profile_status_message"
STATE_SNAPSHOT_MESSAGE = "state_snapshot_status_message"
STATE_COMPARE_MESSAGE = "state_compare_status_message"
STATE_DIGEST_MESSAGE = "state_digest_status_message"
STATE_EMAIL_DELIVERY_MESSAGE = "state_email_delivery_message"
STATE_EMAIL_DRY_RUN_RESULT = "state_email_dry_run_result"
STATE_EMAIL_SEND_RESULT = "state_email_send_result"
STATE_EMAIL_LAST_SENT_DIGEST_SHA = "state_email_last_sent_digest_sha"
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
STATE_PAPER_RETRIEVAL_RESULT = "state_paper_retrieval_result"
STATE_PAPER_RETRIEVAL_MESSAGE = "state_paper_retrieval_message"
STATE_GLOBAL_WEB_RETRIEVAL_RESULT = "state_global_web_retrieval_result"
STATE_GLOBAL_WEB_RETRIEVAL_MESSAGE = "state_global_web_retrieval_message"
STATE_RETRIEVAL_SOURCE_RUNS = "state_retrieval_source_runs"
STATE_RETRIEVAL_ACTIVE_SOURCE = "state_retrieval_active_source"
STATE_RETRIEVAL_LOADED_CANDIDATES = "state_retrieval_loaded_candidates"
STATE_RETRIEVAL_LOADED_MANIFEST = "state_retrieval_loaded_manifest"
STATE_RETRIEVAL_MANIFEST_SUMMARY = "state_retrieval_manifest_summary"
STATE_RETRIEVAL_MANIFEST_MESSAGE = "state_retrieval_manifest_message"
STATE_PENDING_DATA_SOURCE_MODE = "state_pending_data_source_mode"

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
UI_PAPER_OPENALEX_QUERY_ID_KEY = "ui_paper_openalex_query_id"
UI_PAPER_OPENALEX_MAX_RESULTS_KEY = "ui_paper_openalex_max_results"
UI_GLOBAL_WEB_MAX_QUERIES_KEY = "ui_global_web_max_queries"
UI_GLOBAL_WEB_VERIFICATION_LIMIT_KEY = "ui_global_web_verification_limit"
UI_GLOBAL_WEB_SUMMARY_TOP_N_KEY = "ui_global_web_summary_top_n"


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


def _apply_pending_data_source_mode_if_any() -> None:
  pending_mode = str(st.session_state.pop(STATE_PENDING_DATA_SOURCE_MODE, "") or "").strip()
  if pending_mode:
    st.session_state[UI_DATA_SOURCE_MODE_KEY] = pending_mode


def _init_session_state(profile_dict: dict[str, object]) -> None:
  st.session_state.setdefault(UI_DEMO_KEY, True)
  st.session_state.setdefault(UI_SNAPSHOT_NOTE_KEY, "")
  st.session_state.setdefault(UI_EMAIL_CONFIRM_SEND_KEY, False)
  st.session_state.setdefault(STATE_COMPARE_ENABLED, False)
  st.session_state.setdefault(UI_DATA_SOURCE_MODE_KEY, "demo")
  st.session_state.setdefault(STATE_REVIEWS_BY_SIGNAL_ID, {})
  st.session_state.setdefault(STATE_PATENT_BIGQUERY_DRY_RUN, {})
  st.session_state.setdefault(STATE_PATENT_BIGQUERY_APPROVED_QUERY_IDS, [])
  st.session_state.setdefault(STATE_PAPER_RETRIEVAL_RESULT, {})
  st.session_state.setdefault(STATE_GLOBAL_WEB_RETRIEVAL_RESULT, {})
  st.session_state.setdefault(STATE_RETRIEVAL_SOURCE_RUNS, {})
  st.session_state.setdefault(STATE_RETRIEVAL_ACTIVE_SOURCE, "session_runs")
  st.session_state.setdefault(STATE_RETRIEVAL_LOADED_CANDIDATES, {})
  st.session_state.setdefault(STATE_RETRIEVAL_LOADED_MANIFEST, {})
  st.session_state.setdefault(STATE_RETRIEVAL_MANIFEST_SUMMARY, {})
  st.session_state.setdefault(STATE_EMAIL_DRY_RUN_RESULT, {})
  st.session_state.setdefault(STATE_EMAIL_SEND_RESULT, {})
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

  source_payload: dict[str, object] | None = None

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
          source_payload = {
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
        else:
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
          source_payload = {
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
        else:
          warnings.append("JSONから有効なシグナルを読み込めなかったため、デモデータを表示します。")

  if mode == "retrieval_saved":
    active_source = str(st.session_state.get(STATE_RETRIEVAL_ACTIVE_SOURCE, "session_runs") or "session_runs")
    retrieval_rows = _loaded_retrieval_rows_by_source() if active_source == "saved_manifest" else _session_retrieval_rows_by_source()
    patent_rows = list(retrieval_rows.get("patent", []) or [])
    paper_rows = list(retrieval_rows.get("paper", []) or [])
    web_company_rows = list(retrieval_rows.get("web_company", []) or [])
    if not patent_rows and not paper_rows and not web_company_rows:
      warnings.append("取得済みデータモードですが、統合対象の取得済み候補がありません。")
      return {
        "requested_mode": mode,
        "mode": "retrieval_saved",
        "label": data_source_mode_label_ja("retrieval_saved"),
        "signals": [],
        "loaded_count": 0,
        "warnings": warnings,
        "provisional_scoring": True,
        "template_csv_path": str(SAMPLE_UPLOAD_CSV_PATH),
        "template_json_path": str(SAMPLE_UPLOAD_JSON_PATH),
        "integration_summary": {},
      }
    integrated = integrate_multi_source_signals(
      base_signals=[],
      watch_profile=watch_profile_dict,
      patent_rows=patent_rows,
      paper_rows=paper_rows,
      web_company_rows=web_company_rows,
      max_items=1000,
      ranking_limit=100,
    )
    integration_mode_parts = []
    if patent_rows:
      integration_mode_parts.append("patent")
    if paper_rows:
      integration_mode_parts.append("paper")
    if web_company_rows:
      integration_mode_parts.append("web/company")
    source_label = "保存済みmanifest" if active_source == "saved_manifest" else "現セッション取得結果"
    return {
      "requested_mode": mode,
      "mode": "retrieval_saved",
      "label": data_source_mode_label_ja("retrieval_saved"),
      "signals": list(integrated.get("signals", []) or []),
      "loaded_count": int(integrated.get("ranked_count", 0) or 0),
      "warnings": warnings + [f"{source_label}から既存の統合処理を再実行しました。デモ/CSV/JSONは混在していません。"],
      "provisional_scoring": True,
      "template_csv_path": str(SAMPLE_UPLOAD_CSV_PATH),
      "template_json_path": str(SAMPLE_UPLOAD_JSON_PATH),
      "integration_summary": {
        "integration_run_id": str(integrated.get("integration_run_id", "") or ""),
        "raw_count": int(integrated.get("raw_count", 0) or 0),
        "capped_count": int(integrated.get("capped_count", 0) or 0),
        "deduped_count": int(integrated.get("deduped_count", 0) or 0),
        "ranked_count": int(integrated.get("ranked_count", 0) or 0),
        "active_sources": integration_mode_parts,
        "top_by_source": dict(integrated.get("top_by_source", {}) or {}),
        "data_origin": "retrieval_artifact",
        "retrieval_source_kind": active_source,
      },
    }

  if source_payload is None:
    source_payload = {
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
  return source_payload


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
  return stable_payload_signature(payload)


def _set_current_retrieval_source_run(source_type: str, result: dict[str, object], artifact_dir: Path) -> None:
  source_runs = dict(st.session_state.get(STATE_RETRIEVAL_SOURCE_RUNS, {}) or {})
  rows = list(dict(result or {}).get("rows", []) or [])
  source_runs[source_type] = {
    "run_id": str(dict(result or {}).get("retrieval_run_id", "") or "").strip(),
    "artifact_dir": str(Path(artifact_dir).resolve().relative_to(Path(__file__).resolve().parents[1])),
    "status": str(dict(result or {}).get("provider_status", "failed") or "failed"),
    "candidate_count": len(rows),
    "data_origin": "retrieval_artifact",
  }
  st.session_state[STATE_RETRIEVAL_SOURCE_RUNS] = source_runs
  st.session_state[STATE_RETRIEVAL_ACTIVE_SOURCE] = "session_runs"


def _session_retrieval_rows_by_source() -> dict[str, list[dict[str, object]]]:
  return {
    "patent": list(dict(st.session_state.get(STATE_PATENT_RETRIEVAL_RESULT, {}) or {}).get("rows", []) or []),
    "paper": list(dict(st.session_state.get(STATE_PAPER_RETRIEVAL_RESULT, {}) or {}).get("rows", []) or []),
    "web_company": list(dict(st.session_state.get(STATE_GLOBAL_WEB_RETRIEVAL_RESULT, {}) or {}).get("rows", []) or []),
  }


def _loaded_retrieval_rows_by_source() -> dict[str, list[dict[str, object]]]:
  payload = dict(st.session_state.get(STATE_RETRIEVAL_LOADED_CANDIDATES, {}) or {})
  return {
    "patent": list(payload.get("patent", []) or []),
    "paper": list(payload.get("paper", []) or []),
    "web_company": list(payload.get("web_company", []) or []),
  }


def _build_retrieval_reload_ui_state(watch_profile_dict: dict[str, object]) -> dict[str, object]:
  current_signature = _stable_payload_signature(watch_profile_dict)
  current_runs = dict(st.session_state.get(STATE_RETRIEVAL_SOURCE_RUNS, {}) or {})
  manifest_summary = dict(st.session_state.get(STATE_RETRIEVAL_MANIFEST_SUMMARY, {}) or {})
  loaded_manifest = dict(st.session_state.get(STATE_RETRIEVAL_LOADED_MANIFEST, {}) or {})
  return {
    "watch_profile_signature": current_signature,
    "current_run_ids": {
      "patent": str(dict(current_runs.get("patent", {}) or {}).get("run_id", "") or ""),
      "paper": str(dict(current_runs.get("paper", {}) or {}).get("run_id", "") or ""),
      "web_company": str(dict(current_runs.get("web_company", {}) or {}).get("run_id", "") or ""),
    },
    "manifest_summary": manifest_summary,
    "loaded_manifest_id": str(loaded_manifest.get("manifest_id", "") or ""),
    "active_source": str(st.session_state.get(STATE_RETRIEVAL_ACTIVE_SOURCE, "session_runs") or "session_runs"),
  }


def _build_email_delivery_ui_state(
  *,
  markdown_text: str,
  source_info: dict[str, object],
  signals: list[dict[str, object]],
  watch_profile_dict: dict[str, object],
) -> dict[str, object]:
  config = load_email_delivery_config()
  preview = build_digest_email_preview(
    markdown_text,
    theme_name=str(watch_profile_dict.get("theme_name", "") or ""),
    data_source=str(source_info.get("label", "") or ""),
    signals=signals,
    data_source_mode=str(source_info.get("mode", "") or ""),
    watch_profile=watch_profile_dict,
  )
  dry_run_result = run_email_delivery_dry_run(preview, config)
  return {
    "config": config,
    "preview": preview,
    "dry_run_result": dry_run_result,
    "last_dry_run_result": dict(st.session_state.get(STATE_EMAIL_DRY_RUN_RESULT, {}) or {}),
    "last_send_result": dict(st.session_state.get(STATE_EMAIL_SEND_RESULT, {}) or {}),
    "last_sent_digest_sha": str(st.session_state.get(STATE_EMAIL_LAST_SENT_DIGEST_SHA, "") or ""),
  }


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


def _ensure_paper_openalex_widget_defaults(search_plan_state: dict[str, object]) -> None:
  paper_queries = list(dict(search_plan_state.get("plan", {}) or {}).get("plans", {}).get("paper", {}).get("queries", []) or [])
  if paper_queries:
    first_query_id = str(paper_queries[0].get("query_id", "") or "")
    if first_query_id:
      st.session_state.setdefault(UI_PAPER_OPENALEX_QUERY_ID_KEY, first_query_id)
  paper_limit = int(
    dict(search_plan_state.get("plan", {}) or {}).get("plans", {}).get("paper", {}).get("limit", 50) or 50
  )
  st.session_state.setdefault(UI_PAPER_OPENALEX_MAX_RESULTS_KEY, min(max(paper_limit, 1), 200))


def _build_paper_openalex_ui_state(
  search_plan_state: dict[str, object],
  watch_profile_dict: dict[str, object],
) -> dict[str, object]:
  _ensure_paper_openalex_widget_defaults(search_plan_state)
  plan = dict(search_plan_state.get("plan", {}) or {})
  preview = build_openalex_paper_preview(
    plan,
    watch_profile_dict,
    selected_query_id=str(st.session_state.get(UI_PAPER_OPENALEX_QUERY_ID_KEY, "") or ""),
    time_range=str(st.session_state.get(UI_SEARCH_TIME_RANGE_KEY, "12m") or "12m"),
    max_results=int(st.session_state.get(UI_PAPER_OPENALEX_MAX_RESULTS_KEY, 50) or 50),
  )
  return {
    "preview": preview,
    "retrieval_result": dict(st.session_state.get(STATE_PAPER_RETRIEVAL_RESULT, {}) or {}),
  }


def _ensure_global_web_retrieval_widget_defaults(search_plan_state: dict[str, object]) -> None:
  global_web_plan = dict(dict(search_plan_state.get("plan", {}) or {}).get("global_web_plan", {}) or {})
  enabled_count = int(global_web_plan.get("enabled_query_count", 0) or 0)
  st.session_state.setdefault(UI_GLOBAL_WEB_MAX_QUERIES_KEY, max(enabled_count, 1))
  st.session_state.setdefault(UI_GLOBAL_WEB_VERIFICATION_LIMIT_KEY, 40)
  st.session_state.setdefault(UI_GLOBAL_WEB_SUMMARY_TOP_N_KEY, 8)


def _build_global_web_retrieval_ui_state(search_plan_state: dict[str, object]) -> dict[str, object]:
  _ensure_global_web_retrieval_widget_defaults(search_plan_state)
  plan = dict(search_plan_state.get("plan", {}) or {})
  preview = build_global_web_retrieval_preview(
    plan,
    max_query_count=int(st.session_state.get(UI_GLOBAL_WEB_MAX_QUERIES_KEY, 1) or 1),
    verification_limit=int(st.session_state.get(UI_GLOBAL_WEB_VERIFICATION_LIMIT_KEY, 40) or 40),
    summary_top_n=int(st.session_state.get(UI_GLOBAL_WEB_SUMMARY_TOP_N_KEY, 8) or 8),
  )
  return {
    "preview": preview,
    "retrieval_result": dict(st.session_state.get(STATE_GLOBAL_WEB_RETRIEVAL_RESULT, {}) or {}),
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


def _build_operation_rows() -> list[dict[str, str]]:
  active_source = str(st.session_state.get(STATE_RETRIEVAL_ACTIVE_SOURCE, "session_runs") or "session_runs")
  if active_source == "saved_manifest":
    loaded_rows = _loaded_retrieval_rows_by_source()
    patent_mode = "loaded" if loaded_rows["patent"] else "off"
    paper_mode = "loaded" if loaded_rows["paper"] else "off"
    web_mode = "loaded" if loaded_rows["web_company"] else "off"
  else:
    patent_mode = "live" if bool(dict(st.session_state.get(STATE_PATENT_RETRIEVAL_RESULT, {}) or {}).get("rows")) else "off"
    paper_mode = "live" if bool(dict(st.session_state.get(STATE_PAPER_RETRIEVAL_RESULT, {}) or {}).get("rows")) else "off"
    web_mode = "live" if bool(dict(st.session_state.get(STATE_GLOBAL_WEB_RETRIEVAL_RESULT, {}) or {}).get("rows")) else "off"
  return build_operation_status_rows(
    bigquery_mode=patent_mode,
    openalex_mode=paper_mode,
    web_search_mode=web_mode,
    email_mode="off",
  )


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
  _apply_pending_data_source_mode_if_any()
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
  paper_openalex_state = _build_paper_openalex_ui_state(search_plan_state, watch_profile_dict)
  global_web_retrieval_state = _build_global_web_retrieval_ui_state(search_plan_state)
  retrieval_reload_state = _build_retrieval_reload_ui_state(watch_profile_dict)
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

  if previous_snapshot_payload:
    current_signal_dicts = apply_signal_change_tracking(
      current_signal_dicts,
      list(previous_snapshot_payload.get("signals", []) or []),
    )

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
  source_rows = build_source_rows(signals, data_source_mode=str(source_info.get("mode", "demo") or "demo"))
  operation_rows = _build_operation_rows()
  csv_text = signals_to_csv(signals)

  st.title("Tech Cartography v9")
  st.caption("軽量R&Dシグナル監視エージェント")
  render_notice()
  st.caption(
    "ローカルのデモデータ、アップロードされたCSV/JSON、または明示的に読込んだ取得済みartifactで動作します。"
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
      retrieval_reload_state,
      st.session_state.get(STATE_RETRIEVAL_MANIFEST_MESSAGE),
      st.session_state.get(STATE_SEARCH_PLAN_STATUS_MESSAGE),
      patent_bigquery_state,
      st.session_state.get(STATE_PATENT_BIGQUERY_MESSAGE),
      st.session_state.get(STATE_PATENT_RETRIEVAL_MESSAGE),
      paper_openalex_state,
      st.session_state.get(STATE_PAPER_RETRIEVAL_MESSAGE),
      global_web_retrieval_state,
      st.session_state.get(STATE_GLOBAL_WEB_RETRIEVAL_MESSAGE),
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
  email_delivery_state = _build_email_delivery_ui_state(
    markdown_text=markdown_text,
    source_info=source_info,
    signals=latest_reviewed_signals,
    watch_profile_dict=watch_profile_dict,
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
      email_delivery_state,
      st.session_state.get(STATE_EMAIL_DELIVERY_MESSAGE),
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

  if source_events.get("save_retrieval_manifest"):
    source_runs = dict(st.session_state.get(STATE_RETRIEVAL_SOURCE_RUNS, {}) or {})
    try:
      manifest = build_retrieval_run_manifest(watch_profile_dict, source_runs)
      manifest_path = save_retrieval_run_manifest(manifest)
    except ValueError as exc:
      st.session_state[STATE_RETRIEVAL_MANIFEST_MESSAGE] = f"保存できる取得済みrunがありません: {exc}"
    else:
      st.session_state[STATE_RETRIEVAL_MANIFEST_SUMMARY] = {
        "checked": True,
        "available": True,
        "manifest_id": str(manifest.get("manifest_id", "") or ""),
        "status": str(manifest.get("status", "") or ""),
        "candidate_count": int(manifest.get("total_candidate_count", 0) or 0),
      }
      st.session_state[STATE_RETRIEVAL_MANIFEST_MESSAGE] = (
        f"取得済みrun manifest を保存しました: `{manifest.get('manifest_id', '')}` ({manifest_path})"
      )
    st.rerun()

  if source_events.get("load_saved_retrieval_manifest"):
    manifest = find_latest_compatible_manifest(None, _stable_payload_signature(watch_profile_dict))
    if manifest is None:
      st.session_state[STATE_RETRIEVAL_MANIFEST_SUMMARY] = {
        "checked": True,
        "available": False,
        "manifest_id": "",
        "status": "none",
        "candidate_count": 0,
      }
      st.session_state[STATE_RETRIEVAL_MANIFEST_MESSAGE] = "現在のWatch Profileに一致する保存済み取得結果はありません。"
      st.rerun()
    loaded_bundle = load_candidates_from_manifest(manifest)
    st.session_state[STATE_RETRIEVAL_MANIFEST_SUMMARY] = {
      "checked": True,
      "available": True,
      "manifest_id": str(manifest.get("manifest_id", "") or ""),
      "status": str(loaded_bundle.get("status", manifest.get("status", "partial_success")) or "partial_success"),
      "candidate_count": int(loaded_bundle.get("total_candidate_count", 0) or 0),
    }
    if int(loaded_bundle.get("total_candidate_count", 0) or 0) <= 0:
      warning_text = " / ".join(str(item) for item in list(loaded_bundle.get("warnings", []) or []))
      st.session_state[STATE_RETRIEVAL_MANIFEST_MESSAGE] = (
        "一致manifestは見つかりましたが、読込可能な候補がありませんでした。"
        + (f" 警告: {warning_text}" if warning_text else "")
      )
      st.rerun()
    st.session_state[STATE_RETRIEVAL_LOADED_MANIFEST] = manifest
    st.session_state[STATE_RETRIEVAL_LOADED_CANDIDATES] = dict(loaded_bundle.get("candidates_by_source", {}) or {})
    st.session_state[STATE_RETRIEVAL_SOURCE_RUNS] = dict(loaded_bundle.get("source_runs", {}) or {})
    st.session_state[STATE_RETRIEVAL_ACTIVE_SOURCE] = "saved_manifest"
    st.session_state[STATE_PENDING_DATA_SOURCE_MODE] = "retrieval_saved"
    warning_text = " / ".join(str(item) for item in list(loaded_bundle.get("warnings", []) or []))
    st.session_state[STATE_RETRIEVAL_MANIFEST_MESSAGE] = (
      f"保存済み取得結果を読込みました: `{manifest.get('manifest_id', '')}`"
      + (f" (警告: {warning_text})" if warning_text else "")
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
    _set_current_retrieval_source_run("patent", retrieval_result, artifact_paths["run_dir"])
    st.rerun()

  if source_events.get("run_paper_retrieval"):
    paper_retrieval_result = execute_openalex_paper_retrieval(
      dict(paper_openalex_state.get("preview", {}) or {}),
    )
    st.session_state[STATE_PAPER_RETRIEVAL_RESULT] = paper_retrieval_result
    artifact_paths = save_openalex_paper_retrieval_artifacts(
      dict(paper_openalex_state.get("preview", {}) or {}),
      paper_retrieval_result,
    )
    st.session_state[STATE_PAPER_RETRIEVAL_MESSAGE] = (
      f"OpenAlex論文候補 staging を保存しました: {artifact_paths['staged_json']} / {artifact_paths['staged_csv']} "
      f"(log: {artifact_paths['provider_log_json']})"
    )
    _set_current_retrieval_source_run("paper", paper_retrieval_result, artifact_paths["run_dir"])
    st.rerun()

  if source_events.get("run_global_web_retrieval"):
    global_web_result = execute_global_web_retrieval(
      dict(global_web_retrieval_state.get("preview", {}) or {}),
    )
    st.session_state[STATE_GLOBAL_WEB_RETRIEVAL_RESULT] = global_web_result
    artifact_paths = save_global_web_retrieval_artifacts(
      dict(global_web_retrieval_state.get("preview", {}) or {}),
      global_web_result,
    )
    st.session_state[STATE_GLOBAL_WEB_RETRIEVAL_MESSAGE] = (
      f"Global Web / 企業候補 staging を保存しました: {artifact_paths['staged_json']} / "
      f"{artifact_paths['staged_csv']} (discovery: {artifact_paths['discovery_json']}, "
      f"verification: {artifact_paths['verification_json']})"
    )
    _set_current_retrieval_source_run("web_company", global_web_result, artifact_paths["run_dir"])
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

  if digest_events.get("run_email_delivery_dry_run"):
    dry_run_result = run_email_delivery_dry_run(
      dict(email_delivery_state.get("preview", {}) or {}),
      email_delivery_state["config"],
    )
    log_path = save_email_delivery_log(dry_run_result)
    st.session_state[STATE_EMAIL_DRY_RUN_RESULT] = dry_run_result
    st.session_state[STATE_EMAIL_DELIVERY_MESSAGE] = (
      f"メール dry-run を実行しました: status={dry_run_result.get('status', '')} (log: {log_path})"
    )
    st.rerun()

  if digest_events.get("send_email_self_only"):
    if not bool(st.session_state.get(UI_EMAIL_CONFIRM_SEND_KEY, False)):
      st.session_state[STATE_EMAIL_DELIVERY_MESSAGE] = "確認チェックボックスを選択した場合のみ self-only 送信できます。"
      st.rerun()
    preview = dict(email_delivery_state.get("preview", {}) or {})
    last_send_result = dict(st.session_state.get(STATE_EMAIL_SEND_RESULT, {}) or {})
    if (
      str(st.session_state.get(STATE_EMAIL_LAST_SENT_DIGEST_SHA, "") or "") == str(preview.get("digest_sha256", "") or "")
      and bool(last_send_result.get("send_succeeded", False))
    ):
      st.session_state[STATE_EMAIL_DELIVERY_MESSAGE] = "同一Previewの二重送信はブロックしました。内容を更新してから再送してください。"
      st.rerun()
    send_result = send_digest_email_self_only(preview, email_delivery_state["config"])
    log_path = save_email_delivery_log(send_result)
    st.session_state[STATE_EMAIL_SEND_RESULT] = send_result
    if bool(send_result.get("send_succeeded", False)):
      st.session_state[STATE_EMAIL_LAST_SENT_DIGEST_SHA] = str(preview.get("digest_sha256", "") or "")
      st.session_state[STATE_EMAIL_DELIVERY_MESSAGE] = f"self-only メール送信が完了しました (log: {log_path})"
    else:
      error_message = str(send_result.get("safe_error_message", "") or "self-only メール送信に失敗しました。")
      st.session_state[STATE_EMAIL_DELIVERY_MESSAGE] = f"{error_message} (log: {log_path})"
    st.rerun()

