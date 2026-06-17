"""Tabbed Easy Japanese Streamlit app for Tech Cartography v7 (Phase 17)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from tech_cartography.manual.manual_fulltext_loader import get_manual_fulltext_status
from tech_cartography.orchestration.latest_outputs import read_latest_run_pointer
from tech_cartography.reports.project_export import load_records_csv
from tech_cartography.ui.easy_japanese_ui import (
  inject_easy_ui_css,
  prepare_patent_display_df,
  render_acquisition_policy_summary,
  render_fulltext_availability_notice,
  render_cost_ledger_debug,
  render_weekly_digest_preview_block,
  render_caveat_footer,
  render_caution_box,
  render_claims_paper_query_plan_card,
  render_claim_paper_candidate_map_card,
  render_evidence_validation_summary,
  render_openalex_limited_execution_card,
  render_paper_candidate_relevance_card,
  render_fulltext_execute_summary,
  render_fulltext_status_card,
  render_fulltext_vs_watch_notice,
  render_info_box,
  render_main_title,
  render_manual_checklist_notice,
  render_manual_fulltext_route_card,
  render_markdown_preview,
  render_metric_cards,
  render_next_action_box,
  render_ok_box,
  render_patent_card,
  render_small_table,
  render_status_card,
  render_strategic_watch_card,
  render_success_box,
  render_top5_fulltext_card,
  render_user_badge,
  render_watch_profile_card,
  render_warning_box,
  summarize_stage_statuses,
)
from tech_cartography.ui.japanese_labels import (
  explain_cost_guard_status,
  explain_fulltext_scope,
  explain_watch_profile,
  translate_fulltext_scope,
  translate_tab_name,
)
from tech_cartography.ui.user_settings_view import render_user_settings_tab
from tech_cartography.ui.streamlit_session import (
  DISPLAY_MODE_OPTIONS,
  STATE_CURRENT_USER,
  STATE_DISPLAY_MODE,
  STATE_MANIFEST_PATH,
  STATE_PIPELINE_ROOT,
  STATE_SAVED_RUN_ID,
  STATE_SELECTED_RUN_ID,
  default_pipeline_root,
)
from tech_cartography.users.user_store import set_last_run_id
from tech_cartography.users.watch_profile_store import get_active_watch_profile


def _load_manifest(path: str | Path) -> dict[str, Any] | None:
  manifest_path = Path(path)
  if not manifest_path.exists():
    return None
  data = json.loads(manifest_path.read_text(encoding="utf-8"))
  return data if isinstance(data, dict) else None


def _artifact_path(manifest: dict[str, Any], key: str) -> Path | None:
  final_outputs = manifest.get("final_outputs") or {}
  value = final_outputs.get(key)
  if value and Path(value).exists():
    return Path(value)
  for stage in manifest.get("stage_results", []):
    if not isinstance(stage, dict):
      continue
    outputs = stage.get("output_paths") or {}
    value = outputs.get(key)
    if value and Path(value).exists():
      return Path(value)
  return None


def _load_csv_artifact(manifest: dict[str, Any], key: str) -> pd.DataFrame:
  path = _artifact_path(manifest, key)
  if not path:
    return pd.DataFrame()
  try:
    return pd.DataFrame(load_records_csv(path))
  except Exception:
    return pd.DataFrame()


def _load_text_artifact(manifest: dict[str, Any], key: str) -> str:
  path = _artifact_path(manifest, key)
  if not path:
    return ""
  try:
    return path.read_text(encoding="utf-8")
  except Exception:
    return ""


def _load_json_artifact(manifest: dict[str, Any], key: str) -> dict[str, Any] | None:
  path = _artifact_path(manifest, key)
  if not path:
    return None
  try:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None
  except json.JSONDecodeError:
    return None


def _resolve_manifest(
  user: dict[str, Any],
  pipeline_root: str,
  run_id: str,
) -> dict[str, Any] | None:
  manifest_path = st.session_state.get(STATE_MANIFEST_PATH)
  if manifest_path:
    return _load_manifest(manifest_path)
  if run_id:
    candidate = Path(pipeline_root) / run_id / "run_manifest.json"
    return _load_manifest(candidate)
  saved_run = user.get("last_run_id")
  if saved_run:
    candidate = Path(pipeline_root) / saved_run / "run_manifest.json"
    manifest = _load_manifest(candidate)
    if manifest:
      return manifest
  pointer = read_latest_run_pointer(pipeline_root)
  if pointer and pointer.get("manifest_path"):
    return _load_manifest(pointer["manifest_path"])
  return None


def _tab_start(user: dict[str, Any], watch: dict[str, Any], manifest: dict[str, Any] | None, *, debug_mode: bool = False) -> None:
  st.markdown(render_ok_box("このアプリでできること: 特許候補の整理、全文確認計画、技術の裏取り候補の確認"), unsafe_allow_html=True)
  st.markdown(
    render_caution_box(
      "ご利用上の注意: 特許の有効性・侵害・FTOは判断しません。"
      "論文候補は裏取り候補であり証明ではありません。"
      "BigQuery/OpenAlexの実行はこの画面からは自動では行いません。"
    ),
    unsafe_allow_html=True,
  )
  st.markdown(render_watch_profile_card(watch), unsafe_allow_html=True)
  st.markdown(render_info_box(explain_watch_profile()), unsafe_allow_html=True)
  weekly = "ON" if user.get("weekly_email_enabled") else "OFF"
  st.markdown(
    render_info_box(
      f"週次メール設定: {weekly}（送信先: {user.get('email', '')}）。"
      "まだ送信は行いません。設定タブで変更できます。"
    ),
    unsafe_allow_html=True,
  )
  if manifest:
    acquisition = _load_json_artifact(manifest, "acquisition_policy_summary_json")
    weekly_md = _load_text_artifact(manifest, "weekly_digest_preview_md")
    weekly_json = _load_json_artifact(manifest, "weekly_digest_preview_json")
    st.markdown(render_acquisition_policy_summary(acquisition), unsafe_allow_html=True)
    st.markdown(render_weekly_digest_preview_block(weekly_json, weekly_md), unsafe_allow_html=True)
    if debug_mode:
      internal_summary = _load_json_artifact(manifest, "internal_cost_summary_json")
      ledger = (internal_summary or {}).get("ledger_summary")
      if ledger:
        st.markdown(render_cost_ledger_debug(ledger), unsafe_allow_html=True)
    with st.expander("実行状況の詳細"):
      stage_rows = summarize_stage_statuses(manifest)
      if stage_rows:
        render_small_table(pd.DataFrame(stage_rows)[["段階", "状態", "説明"]])
  else:
    st.info("sidebar で run_id を指定するか、「latest_run を読み込む」を押してください。")


def _tab_patents(manifest: dict[str, Any], display_mode: str) -> None:
  st.markdown(render_info_box("中国候補を除外しているわけではありません。US全文候補と戦略監視候補は別枠です。"), unsafe_allow_html=True)
  ranked_df = _load_csv_artifact(manifest, "ranked_patents_csv")
  top20_df = _load_csv_artifact(manifest, "top20_patents_csv")
  cluster_df = _load_csv_artifact(manifest, "cluster_summary_csv")
  watch_df = _load_csv_artifact(manifest, "strategic_watch_candidates_csv")
  company_df = _load_csv_artifact(manifest, "company_watch_summary_csv")

  metrics = [
    {"label": "ランク付け件数", "value": len(ranked_df)},
    {"label": "Top20", "value": len(top20_df)},
    {"label": "戦略監視", "value": len(watch_df)},
  ]
  st.markdown(render_metric_cards(metrics), unsafe_allow_html=True)

  if not top20_df.empty:
    with st.expander("Top20 特許候補", expanded=display_mode == "かんたん表示"):
      if display_mode == "かんたん表示":
        for _, row in top20_df.head(10).iterrows():
          st.markdown(render_patent_card(row.to_dict()), unsafe_allow_html=True)
      else:
        render_small_table(prepare_patent_display_df(top20_df))
  else:
    st.warning("Top20 の成果物がまだありません。")

  if not cluster_df.empty:
    with st.expander("技術クラスタサマリー"):
      render_small_table(cluster_df)
  if not company_df.empty:
    with st.expander("企業別監視サマリー"):
      render_small_table(company_df.head(15))

  if not watch_df.empty:
    st.subheader("戦略監視候補（中国・EP・JP含む）")
    cn_count = int((watch_df["country"].astype(str).str.upper() == "CN").sum()) if "country" in watch_df.columns else 0
    st.markdown(render_info_box(f"戦略監視: {len(watch_df)} 件（中国: {cn_count} 件）"), unsafe_allow_html=True)
    with st.expander("戦略監視候補一覧", expanded=False):
      for _, row in watch_df.head(10).iterrows():
        st.markdown(render_strategic_watch_card(row.to_dict()), unsafe_allow_html=True)


def _tab_fulltext(manifest: dict[str, Any], display_mode: str, *, debug_mode: bool = False) -> None:
  acquisition = _load_json_artifact(manifest, "acquisition_policy_summary_json")
  if acquisition:
    st.markdown(render_acquisition_policy_summary(acquisition), unsafe_allow_html=True)
  st.markdown(render_fulltext_vs_watch_notice(), unsafe_allow_html=True)
  st.markdown(render_info_box(explain_fulltext_scope("claims_only")), unsafe_allow_html=True)
  for scope in ("claims_only", "description_only", "claims_and_description"):
    st.caption(f"{translate_fulltext_scope(scope)}: {explain_fulltext_scope(scope)}")

  top5_df = _load_csv_artifact(manifest, "top5_fulltext_candidates_csv")
  records_df = _load_csv_artifact(manifest, "top5_fulltext_records_csv")
  ft_preview = _load_json_artifact(manifest, "fulltext_execute_preview_json")
  ft_summary = _load_json_artifact(manifest, "fulltext_retrieval_summary_json")
  probe_md = _load_text_artifact(manifest, "fulltext_availability_probe_md")
  execute_df = _load_csv_artifact(manifest, "fulltext_execute_results_csv")
  checklist_md = _load_text_artifact(manifest, "manual_fulltext_checklist_md")
  strategic_manual_df = _load_csv_artifact(manifest, "strategic_watch_manual_fulltext_required_csv")

  if ft_preview or ft_summary:
    st.markdown(render_fulltext_execute_summary(ft_preview, ft_summary), unsafe_allow_html=True)
    guard_status = ""
    if ft_preview and ft_preview.get("preview_targets"):
      guard_status = str(ft_preview["preview_targets"][0].get("cost_guard_status", ""))
    if guard_status:
      st.markdown(render_info_box(explain_cost_guard_status(guard_status)), unsafe_allow_html=True)

  if not top5_df.empty:
    st.subheader("US Top5 全文候補")
    with st.expander("US Top5 一覧", expanded=display_mode == "かんたん表示"):
      for _, row in top5_df.iterrows():
        st.markdown(render_top5_fulltext_card(row.to_dict()), unsafe_allow_html=True)
  else:
    st.info("Top5 全文候補がまだありません。")

  if probe_md:
    with st.expander("Fulltext Availability Probe", expanded=True):
      st.markdown(probe_md)

  if not records_df.empty:
    with st.expander("全文取得の実行状態"):
      for _, row in records_df.iterrows():
        row_dict = row.to_dict()
        st.markdown(render_fulltext_availability_notice(row_dict), unsafe_allow_html=True)
        st.markdown(render_fulltext_status_card(row_dict), unsafe_allow_html=True)
        pub = str(row_dict.get("publication_number") or "")
        bq_not_found = str(row_dict.get("retrieval_status") or "") in {
          "not_found",
          "manual_google_patents_recommended",
          "bigquery_fulltext_not_available",
          "skipped_known_not_found",
          "manual_route_recommended",
        }
        if pub and (bq_not_found or str(row_dict.get("retrieval_status") or "") in {"manual_claims_loaded", "manual_fulltext_loaded"}):
          manual_status = get_manual_fulltext_status(pub, "outputs/manual_fulltext_inputs")
          st.markdown(
            render_manual_fulltext_route_card(pub, manual_status, bigquery_not_found=bq_not_found),
            unsafe_allow_html=True,
          )

  if not execute_df.empty:
    with st.expander("fulltext_execute_results"):
      render_small_table(execute_df)

  if checklist_md:
    with st.expander("Manual Full Text Checklist"):
      st.markdown(checklist_md)

  if not strategic_manual_df.empty:
    st.subheader("CN/EP/JP 手動全文確認候補")
    render_small_table(prepare_patent_display_df(strategic_manual_df))
  elif not top5_df.empty:
    st.markdown(render_manual_checklist_notice(), unsafe_allow_html=True)

  if debug_mode:
    internal_summary = _load_json_artifact(manifest, "internal_cost_summary_json")
    ledger = (internal_summary or {}).get("ledger_summary")
    if ledger:
      with st.expander("開発者向け cost ledger（デバッグ）"):
        st.markdown(render_cost_ledger_debug(ledger), unsafe_allow_html=True)
        ledger_path = _artifact_path(manifest, "cost_ledger_csv")
        if ledger_path and ledger_path.exists():
          st.caption(f"ledger: {ledger_path}")


def _tab_evidence(manifest: dict[str, Any]) -> None:
  st.markdown(render_caution_box("論文候補は証明ではありません。専門家レビューが必要です。"), unsafe_allow_html=True)
  ev_summary = _load_json_artifact(manifest, "evidence_validation_summary_json")
  st.markdown(render_evidence_validation_summary(ev_summary), unsafe_allow_html=True)

  claims_plan_path = _artifact_path(manifest, "claims_paper_query_plan_md")
  claims_queries_df = _load_csv_artifact(manifest, "paper_query_candidates_from_claims_csv")
  records_df = _load_csv_artifact(manifest, "top5_fulltext_records_csv")
  manual_loaded = False
  if not records_df.empty and "retrieval_status" in records_df.columns:
    manual_loaded = records_df["retrieval_status"].astype(str).isin(
      {"manual_claims_loaded", "manual_fulltext_loaded"},
    ).any()

  claims_plan: dict[str, Any] = {}
  if ev_summary and isinstance(ev_summary.get("claims_paper_query_plan"), dict):
    claims_plan = ev_summary["claims_paper_query_plan"]
  elif not claims_queries_df.empty:
    claims_plan = {
      "total_queries": len(claims_queries_df),
      "openalex_mode": "plan_only",
      "confidence_levels": sorted(claims_queries_df["confidence"].dropna().unique().tolist())
      if "confidence" in claims_queries_df.columns
      else ["medium", "low"],
      "query_examples": claims_queries_df["query"].head(5).tolist() if "query" in claims_queries_df.columns else [],
      "queries": claims_queries_df.to_dict(orient="records"),
      "caveat_japanese": (
        claims_queries_df["caveat_japanese"].iloc[0]
        if "caveat_japanese" in claims_queries_df.columns and not claims_queries_df.empty
        else ""
      ),
    }

  claims_card = render_claims_paper_query_plan_card(claims_plan, manual_claims_loaded=manual_loaded)
  if claims_card:
    st.markdown(claims_card, unsafe_allow_html=True)

  openalex_summary = _load_json_artifact(manifest, "openalex_execution_summary_json")
  if openalex_summary:
    st.markdown(render_openalex_limited_execution_card(openalex_summary), unsafe_allow_html=True)
  elif ev_summary and isinstance(ev_summary.get("openalex_limited_execution"), dict):
    st.markdown(
      render_openalex_limited_execution_card(ev_summary["openalex_limited_execution"]),
      unsafe_allow_html=True,
    )

  claim_links_df = _load_csv_artifact(manifest, "claim_paper_candidate_links_csv")
  if not claim_links_df.empty:
    st.markdown(
      render_claim_paper_candidate_map_card(claim_links_df.to_dict(orient="records")),
      unsafe_allow_html=True,
    )
    with st.expander("Claim × Paper Candidate Links"):
      render_small_table(claim_links_df.head(50))
  elif ev_summary and isinstance(ev_summary.get("claim_paper_candidate_links"), dict):
    rep = ev_summary["claim_paper_candidate_links"].get("representative_links") or []
    if rep:
      st.markdown(render_claim_paper_candidate_map_card(rep), unsafe_allow_html=True)

  relevance_summary = None
  if ev_summary and isinstance(ev_summary.get("paper_candidate_relevance"), dict):
    relevance_summary = ev_summary["paper_candidate_relevance"]
  if relevance_summary:
    st.markdown(render_paper_candidate_relevance_card(relevance_summary), unsafe_allow_html=True)

  selected_df = _load_csv_artifact(manifest, "selected_evidence_papers_csv")
  if not selected_df.empty:
    with st.expander("Selected Evidence Papers"):
      render_small_table(selected_df.head(20))

  relevance_md = _artifact_path(manifest, "paper_candidate_relevance_report_md")
  if relevance_md and relevance_md.exists():
    with st.expander("Paper Candidate Relevance Report"):
      st.markdown(relevance_md.read_text(encoding="utf-8"))

  openalex_papers_df = _load_csv_artifact(manifest, "openalex_paper_records_csv")
  if not openalex_papers_df.empty:
    with st.expander("OpenAlex Paper Records"):
      render_small_table(openalex_papers_df.head(50))

  openalex_selected_df = _load_csv_artifact(manifest, "openalex_selected_queries_csv")
  if not openalex_selected_df.empty:
    with st.expander("OpenAlex Selected Queries"):
      render_small_table(openalex_selected_df.head(20))

  claim_df = _load_csv_artifact(manifest, "claim_elements_csv")
  paper_df = _load_csv_artifact(manifest, "paper_query_candidates_csv")
  if not claim_df.empty:
    with st.expander("Claim Elements"):
      render_small_table(claim_df.head(50))
  if not claims_queries_df.empty:
    with st.expander("Claims-based Paper Query Candidates"):
      render_small_table(claims_queries_df.head(50))
  elif not paper_df.empty:
    with st.expander("Paper Query Candidates"):
      render_small_table(paper_df.head(50))

  openalex_plan = _load_json_artifact(manifest, "openalex_query_plan_json")
  if openalex_plan:
    mode = openalex_plan.get("mode", "plan_only") if isinstance(openalex_plan, dict) else "plan_only"
    st.markdown(render_info_box(f"OpenAlex: {mode}（plan_only — 本実行はまだ任意）"), unsafe_allow_html=True)
  elif claims_plan:
    st.markdown(render_info_box("OpenAlex: plan_only（本実行はまだ任意）"), unsafe_allow_html=True)

  if claims_plan_path and claims_plan_path.exists():
    with st.expander("Claims Paper Query Plan"):
      st.markdown(claims_plan_path.read_text(encoding="utf-8"))

  quality_md = _artifact_path(manifest, "paper_query_quality_report_md")
  if quality_md and quality_md.exists():
    with st.expander("Paper Query Quality"):
      st.markdown(quality_md.read_text(encoding="utf-8"))


def _tab_market(manifest: dict[str, Any]) -> None:
  st.markdown(
    render_info_box(
      "Toray / Teijin / Zhongfu Shenying などの企業動向は、"
      "特許候補と併せて確認してください。自動Web検索はまだ行いません。"
    ),
    unsafe_allow_html=True,
  )
  web_df = _load_csv_artifact(manifest, "web_signal_patent_links_csv")
  business_df = _load_csv_artifact(manifest, "patent_business_summary_csv")
  company_df = _load_csv_artifact(manifest, "company_watch_summary_csv")

  if not web_df.empty or not business_df.empty:
    if not web_df.empty:
      with st.expander("Web Signal"):
        render_small_table(web_df.head(20))
    if not business_df.empty:
      with st.expander("Business Summary"):
        render_small_table(business_df.head(20))
  else:
    st.info("Web signal CSV を追加するとここに表示されます。テンプレートを埋めてパイプラインを実行してください。")

  if not company_df.empty:
    with st.expander("Company Watch"):
      render_small_table(company_df.head(15))


def _tab_reports(manifest: dict[str, Any]) -> None:
  reports = [
    ("carbon_fiber_evidence_map_report_md", "Carbon Fiber Evidence Map"),
    ("fulltext_evidence_report_md", "Full Text Evidence"),
    ("evidence_validation_report_md", "Evidence Validation"),
    ("final_report_md", "Synthesis Report"),
    ("carbon_fiber_evidence_map_v1_md", "Evidence Map v1"),
  ]
  found = False
  for key, label in reports:
    md = _load_text_artifact(manifest, key)
    if md:
      found = True
      with st.expander(label):
        st.markdown(render_markdown_preview(md))
        st.text_area(f"{label}（コピー用）", value=md[:4000], height=200, key=f"copy_{key}")
  if not found:
    st.info("レポートがまだありません。パイプラインを実行してください。")


def render_tabbed_easy_app(
  user: dict[str, Any],
  *,
  pipeline_root: str | None = None,
  run_id: str = "",
  display_mode: str = "かんたん表示",
) -> None:
  st.markdown(inject_easy_ui_css(), unsafe_allow_html=True)
  watch = get_active_watch_profile(user["user_id"])
  st.markdown(
    render_main_title("Tech Cartography v7", "炭素繊維 技術地図 — 特許・論文・企業情報から、読むべき技術候補を整理します"),
    unsafe_allow_html=True,
  )
  header_cols = st.columns([2, 2, 2])
  with header_cols[0]:
    st.markdown(render_user_badge(user), unsafe_allow_html=True)
  with header_cols[1]:
    st.caption(f"Watch: {watch.get('theme', '')[:40]}…" if len(str(watch.get("theme", ""))) > 40 else f"Watch: {watch.get('theme', '')}")
  with header_cols[2]:
    st.caption(f"run_id: {run_id or user.get('last_run_id') or '未選択'}")

  root = pipeline_root or default_pipeline_root()
  manifest = _resolve_manifest(user, root, run_id)
  debug_mode = bool(st.session_state.get("tc_debug_mode", False))
  if manifest and manifest.get("run_id"):
    rid = str(manifest["run_id"])
    if st.session_state.get(STATE_SAVED_RUN_ID) != rid:
      set_last_run_id(user["user_id"], rid)
      st.session_state[STATE_SAVED_RUN_ID] = rid
      refreshed = dict(user)
      refreshed["last_run_id"] = rid
      st.session_state[STATE_CURRENT_USER] = refreshed

  if not manifest:
    st.markdown(render_info_box("実行結果を読み込んでください。sidebar で run_id を指定するか latest_run を読み込みます。"), unsafe_allow_html=True)
    _tab_start(user, watch, None, debug_mode=debug_mode)
    st.markdown(render_caveat_footer(), unsafe_allow_html=True)
    return

  tabs = st.tabs(
    [
      translate_tab_name("start"),
      translate_tab_name("patents"),
      translate_tab_name("fulltext"),
      translate_tab_name("evidence"),
      translate_tab_name("market"),
      translate_tab_name("reports"),
      translate_tab_name("settings"),
    ],
  )
  with tabs[0]:
    _tab_start(user, watch, manifest, debug_mode=debug_mode)
  with tabs[1]:
    _tab_patents(manifest, display_mode)
  with tabs[2]:
    _tab_fulltext(manifest, display_mode, debug_mode=debug_mode)
  with tabs[3]:
    _tab_evidence(manifest)
  with tabs[4]:
    _tab_market(manifest)
  with tabs[5]:
    _tab_reports(manifest)
  with tabs[6]:
    render_user_settings_tab(user, current_run_id=manifest.get("run_id"))

  st.markdown(render_caveat_footer(), unsafe_allow_html=True)


def render_easy_japanese_app() -> None:
  """Backward-compatible entry for streamlit_app Expert mode switch."""
  user = st.session_state.get(STATE_CURRENT_USER)
  if not user:
    st.warning("ログインが必要です。app.py から起動してください。")
    return
  pipeline_root = st.session_state.get(STATE_PIPELINE_ROOT, default_pipeline_root())
  run_id = st.session_state.get(STATE_SELECTED_RUN_ID, "")
  display_mode = st.session_state.get(STATE_DISPLAY_MODE, DISPLAY_MODE_OPTIONS[0])
  st.sidebar.checkbox("デバッグモード（開発者向け cost ledger）", key="tc_debug_mode", value=False)
  render_tabbed_easy_app(user, pipeline_root=pipeline_root, run_id=run_id, display_mode=display_mode)


# Backward-compatible alias used by app.py import
DEFAULT_PIPELINE_ROOT = default_pipeline_root()
