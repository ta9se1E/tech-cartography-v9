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
from tech_cartography.validation.theme_validation import ThemeValidationCase
from tech_cartography.ui.easy_japanese_ui import (
  DEMO_DEEP_DIVE_PUBLICATION,
  discover_demo_artifacts,
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
  render_demo_story_cards,
  render_evidence_validation_summary,
  render_evidence_map_demo_section,
  render_evidence_map_synthesis_card,
  normalize_dataframe_row,
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
from tech_cartography.ui.theme_validation_ui import (
  STATE_THEME_VALIDATION_CASE,
  render_analyst_input_execution_section,
  render_theme_validation_intro_card,
  render_theme_validation_section,
)
from tech_cartography.ui.demo_safe_ui import (
  format_display_path,
  get_ui_mode,
  is_analyst_view,
  is_demo_view,
  is_developer_view,
  render_usage_notices_expander,
  tab_ids_for_ui_mode,
  tab_labels_for_ui_mode,
)
from tech_cartography.ui.analyst_mode_ui import (
  ANALYST_EMPTY_ARTIFACT_MESSAGE,
  ANALYST_INPUT_KEY_PREFIX,
  analyst_has_evidence_outputs,
  analyst_has_market_outputs,
  case_from_session_widgets,
  compute_analyst_workflow_snapshot,
  load_analyst_evidence_bundle,
  preferred_analyst_publication,
)
from tech_cartography.ui.label_renderer import POLISHED_EVIDENCE_GAPS, POLISHED_NEXT_ACTIONS
from tech_cartography.ui.japanese_labels import (
  explain_cost_guard_status,
  explain_fulltext_scope,
  translate_fulltext_scope,
)
from tech_cartography.ui.user_settings_view import render_user_settings_tab
from tech_cartography.ui.evidence_map_demo import (
  load_demo_evidence_map_artifacts,
  render_demo_evidence_tab,
  render_demo_mode_banner,
  render_demo_start_tab,
  render_evidence_map_report,
  render_market_signal_demo_notice,
)
from tech_cartography.ui.reproducibility_smoke_ui import (
  load_reproducibility_smoke_artifacts,
  render_reproducibility_smoke_section,
)
from tech_cartography.ui.web_signal_review_ui import (
  load_web_signal_review_artifacts,
  render_web_signal_review_section,
)
from tech_cartography.ui.strategic_watch_ui import (
  load_strategic_watch_artifacts,
  render_strategic_watch_section,
)
from tech_cartography.ui.delivery_ui import load_delivery_artifacts, render_delivery_section
from tech_cartography.ui.report_tab_ui import (
  render_compressed_report_tab,
  render_developer_report_expander,
)
from tech_cartography.ui.streamlit_session import (
  DISPLAY_MODE_OPTIONS,
  STATE_CURRENT_USER,
  STATE_DISPLAY_MODE,
  STATE_DEMO_MODE,
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


def _resolve_analyst_case() -> ThemeValidationCase | None:
  import streamlit as st

  cached = st.session_state.get(STATE_THEME_VALIDATION_CASE)
  if isinstance(cached, ThemeValidationCase) and cached.theme_name.strip():
    return cached
  return case_from_session_widgets(key_prefix=ANALYST_INPUT_KEY_PREFIX)


def _tab_start(
  user: dict[str, Any],
  watch: dict[str, Any],
  manifest: dict[str, Any] | None,
  *,
  debug_mode: bool = False,
  demo_mode: bool = False,
  demo_artifacts: Any = None,
  repro_artifacts: Any = None,
) -> None:
  if demo_mode and demo_artifacts is not None:
    render_demo_start_tab(demo_artifacts)
    return
  if is_analyst_view():
    st.markdown(
      render_info_box(
        "本番実行では、まず『入力・実行』タブでテーマとseed公報を入力します。"
        "成果物が生成された後は、技術の裏取り、企業・市場シグナル、レポートの順に確認してください。"
      ),
      unsafe_allow_html=True,
    )
  elif is_developer_view():
    render_theme_validation_intro_card()
  st.markdown(render_demo_story_cards(), unsafe_allow_html=True)
  st.markdown(render_ok_box("このアプリでできること: 特許候補の整理、全文確認計画、技術の裏取り候補の確認"), unsafe_allow_html=True)
  st.markdown(render_watch_profile_card(watch), unsafe_allow_html=True)
  weekly = "ON" if user.get("weekly_email_enabled") else "OFF"
  st.caption(f"週次メール設定: {weekly}（送信は行いません。設定タブで変更できます）")
  if manifest:
    acquisition = _load_json_artifact(manifest, "acquisition_policy_summary_json")
    weekly_md = _load_text_artifact(manifest, "weekly_digest_preview_md")
    weekly_json = _load_json_artifact(manifest, "weekly_digest_preview_json")
    st.markdown(render_acquisition_policy_summary(acquisition), unsafe_allow_html=True)
    st.markdown(render_weekly_digest_preview_block(weekly_json, weekly_md), unsafe_allow_html=True)
    if debug_mode and is_developer_view():
      internal_summary = _load_json_artifact(manifest, "internal_cost_summary_json")
      ledger = (internal_summary or {}).get("ledger_summary")
      if ledger:
        st.markdown(render_cost_ledger_debug(ledger), unsafe_allow_html=True)
    if is_developer_view():
      with st.expander("実行状況の詳細"):
        stage_rows = summarize_stage_statuses(manifest)
        if stage_rows:
          render_small_table(pd.DataFrame(stage_rows)[["段階", "状態", "説明"]])
  elif is_analyst_view() or is_developer_view():
    st.info("本番実行タブでテーマを入力してください。" if is_analyst_view() else "run を読み込むには開発者向けモードが必要です。")

  render_usage_notices_expander(key="start_usage_notices", expanded=False)


def _tab_patents(manifest: dict[str, Any], display_mode: str) -> None:
  st.markdown(render_info_box("中国候補を除外しているわけではありません。US全文候補と戦略監視候補は別枠です。"), unsafe_allow_html=True)

  delivery_artifacts = load_delivery_artifacts(PROJECT_ROOT, publication_number=DEMO_DEEP_DIVE_PUBLICATION)
  st.divider()
  render_delivery_section(
    delivery_artifacts,
    compact_overview=True,
    key_prefix="start_delivery",
    developer_mode=is_developer_view(),
  )
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
        row_dict = normalize_dataframe_row(row.to_dict())
        try:
          notice_html = render_fulltext_availability_notice(row_dict)
          if notice_html:
            st.markdown(notice_html, unsafe_allow_html=True)
        except Exception as exc:
          st.warning(f"全文確認情報の表示中に問題が発生しました: {exc}")
          if debug_mode:
            st.write(row_dict)
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


def _tab_evidence(
  manifest: dict[str, Any] | None,
  *,
  demo_artifacts: Any = None,
  repro_artifacts: Any = None,
) -> None:
  if demo_artifacts is not None:
    render_demo_evidence_tab(demo_artifacts, developer_mode=is_developer_view())
    return
  if is_analyst_view():
    case = _resolve_analyst_case()
    if not case or not analyst_has_evidence_outputs(case, PROJECT_ROOT):
      st.info(ANALYST_EMPTY_ARTIFACT_MESSAGE)
      return
    publication = preferred_analyst_publication(case, PROJECT_ROOT)
    if not publication:
      st.info(ANALYST_EMPTY_ARTIFACT_MESSAGE)
      return
    bundle = load_analyst_evidence_bundle(PROJECT_ROOT, publication)
    st.caption("論文候補は supporting evidence candidate です。FTO・侵害・有効性判断ではありません。")
    st.caption(f"表示中 seed: {publication}")
    if not bundle.get("synthesis"):
      st.info(ANALYST_EMPTY_ARTIFACT_MESSAGE)
      return
    st.subheader("Evidence Map")
    st.markdown(
      render_evidence_map_demo_section(
        bundle.get("synthesis"),
        selected_papers=bundle.get("selected_papers"),
        claim_links=bundle.get("claim_links"),
        excluded_papers=bundle.get("excluded_papers"),
        artifact_status=bundle.get("artifact_status"),
      ),
      unsafe_allow_html=True,
    )
    if bundle.get("selected_papers"):
      with st.expander("Selected Evidence Papers"):
        render_small_table(pd.DataFrame(bundle["selected_papers"]).head(20))
    if bundle.get("claim_links"):
      st.markdown(
        render_claim_paper_candidate_map_card(bundle["claim_links"]),
        unsafe_allow_html=True,
      )
    st.markdown("### 確認ギャップと次アクション")
    for gap in POLISHED_EVIDENCE_GAPS:
      st.markdown(f"- {gap}")
    for action in POLISHED_NEXT_ACTIONS:
      st.markdown(f"- {action}")
    return
  if not manifest:
    st.info("実行結果を読み込んでください。")
    return

  st.caption("Paper候補は supporting evidence candidate です。最終判断には専門家レビューが必要です。")

  demo_bundle = _load_demo_evidence_bundle(manifest, PROJECT_ROOT)
  st.subheader("Evidence Map")
  st.markdown(
    render_evidence_map_demo_section(
      demo_bundle.get("synthesis"),
      selected_papers=demo_bundle.get("selected_papers"),
      claim_links=demo_bundle.get("claim_links"),
      excluded_papers=demo_bundle.get("excluded_papers"),
      artifact_status=demo_bundle.get("artifact_status"),
    ),
    unsafe_allow_html=True,
  )

  ev_summary = _load_json_artifact(manifest, "evidence_validation_summary_json")
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

  with st.expander("Evidence Validation / OpenAlex 詳細", expanded=False):
    st.markdown(render_evidence_validation_summary(ev_summary), unsafe_allow_html=True)

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
    if claim_links_df.empty and demo_bundle.get("claim_links"):
      claim_links_df = pd.DataFrame(demo_bundle["claim_links"])
    if not claim_links_df.empty:
      st.markdown(
        render_claim_paper_candidate_map_card(claim_links_df.to_dict(orient="records")),
        unsafe_allow_html=True,
      )
      with st.expander("Claim × Paper Candidate Links（表）"):
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

    ev_map = demo_bundle.get("synthesis") or _load_json_artifact(manifest, "evidence_map_synthesis_json")
    if not ev_map and ev_summary and isinstance(ev_summary.get("evidence_map_synthesis"), dict):
      ev_map = ev_summary["evidence_map_synthesis"]
    if ev_map:
      st.markdown(render_evidence_map_synthesis_card(ev_map), unsafe_allow_html=True)

    selected_df = _load_csv_artifact(manifest, "selected_evidence_papers_csv")
    if selected_df.empty and demo_bundle.get("selected_papers"):
      selected_df = pd.DataFrame(demo_bundle["selected_papers"])
    if not selected_df.empty:
      with st.expander("Selected Evidence Papers（表）"):
        render_small_table(selected_df.head(20))

    relevance_md = _artifact_path(manifest, "paper_candidate_relevance_report_md")
    if not relevance_md or not relevance_md.exists():
      fallback_rel = PROJECT_ROOT / "outputs/openalex_limited_execution/paper_candidate_relevance_report.md"
      if fallback_rel.exists():
        relevance_md = fallback_rel
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

    ev_map_md = _artifact_path(manifest, "evidence_map_synthesis_md")
    if not ev_map_md or not ev_map_md.exists():
      fallback_md = PROJECT_ROOT / "outputs/evidence_map_synthesis" / DEMO_DEEP_DIVE_PUBLICATION / "evidence_map_synthesis.md"
      if fallback_md.exists():
        ev_map_md = fallback_md
    if ev_map_md and ev_map_md.exists():
      with st.expander("Evidence Map Synthesis Report"):
        st.markdown(ev_map_md.read_text(encoding="utf-8"))

    ev_map_items_df = _load_csv_artifact(manifest, "evidence_map_items_csv")
    if ev_map_items_df.empty:
      fallback_items = PROJECT_ROOT / "outputs/evidence_map_synthesis" / DEMO_DEEP_DIVE_PUBLICATION / "evidence_map_items.csv"
      if fallback_items.exists():
        ev_map_items_df = pd.DataFrame(_load_csv_path(fallback_items))
    if not ev_map_items_df.empty:
      with st.expander("Evidence Map Items"):
        render_small_table(ev_map_items_df.head(50))


def _tab_market(manifest: dict[str, Any] | None, *, demo_mode: bool = False) -> None:
  if not demo_mode:
    from tech_cartography.services.live_web_signal_pack import load_latest_live_web_signal_pack
    from tech_cartography.ui.live_web_signal_pack_ui import render_live_web_signal_candidates_section

    render_live_web_signal_candidates_section(project_root=PROJECT_ROOT)

  if is_analyst_view() and not demo_mode:
    case = _resolve_analyst_case()
    has_case_outputs = bool(case and analyst_has_market_outputs(case, PROJECT_ROOT))
    has_live_pack = load_latest_live_web_signal_pack(PROJECT_ROOT) is not None if not demo_mode else False
    if not has_case_outputs:
      if not has_live_pack:
        st.info(ANALYST_EMPTY_ARTIFACT_MESSAGE)
      return
    publication = preferred_analyst_publication(case, PROJECT_ROOT) or case.seed_publication_numbers[0]
    render_market_signal_demo_notice()
    web_review_artifacts = load_web_signal_review_artifacts(PROJECT_ROOT)
    render_web_signal_review_section(web_review_artifacts, developer_mode=False)
    st.divider()
    strategic_watch_artifacts = load_strategic_watch_artifacts(
      PROJECT_ROOT,
      publication_number=publication,
    )
    render_strategic_watch_section(strategic_watch_artifacts, developer_mode=is_developer_view())
    return
  if demo_mode:
    render_market_signal_demo_notice()

  web_review_artifacts = load_web_signal_review_artifacts(PROJECT_ROOT)
  render_web_signal_review_section(web_review_artifacts, developer_mode=is_developer_view())

  st.divider()
  strategic_watch_artifacts = load_strategic_watch_artifacts(PROJECT_ROOT, publication_number=DEMO_DEEP_DIVE_PUBLICATION)
  render_strategic_watch_section(strategic_watch_artifacts, developer_mode=is_developer_view())

  if not manifest:
    if not demo_mode:
      st.divider()
      st.info("パイプライン manifest の Web signal CSV は未読み込みです。上記 Review Pack を優先して確認してください。")
    return

  if not demo_mode:
    st.divider()
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
      with st.expander("Web Signal (Pipeline Manifest)"):
        render_small_table(web_df.head(20))
    if not business_df.empty:
      with st.expander("Business Summary"):
        render_small_table(business_df.head(20))
  elif not demo_mode:
    st.info("manifest 内の Web signal CSV はまだありません。Review Pack を上で確認してください。")

  if not company_df.empty:
    with st.expander("Company Watch"):
      render_small_table(company_df.head(15))


def _tab_analyst_input() -> None:
  render_analyst_input_execution_section(key_prefix=ANALYST_INPUT_KEY_PREFIX)


def _tab_theme_validation() -> None:
  render_theme_validation_section(key_prefix="theme_validation_tab")


def _tab_reports_core_validation_summary_links(*, developer_mode: bool = False) -> None:
  if not developer_mode:
    return
  core_root = PROJECT_ROOT / "outputs" / "validation" / "core_validation"
  summary_md = core_root / "cross_theme_core_validation_summary.md"
  freeze_md = core_root / "freeze_readiness_judgement.md"
  reviewer_md = core_root / "reviewer_response_notes.md"
  st.markdown("**Core Validation Summary（Phase 24.4B — 開発者向け）**")
  st.caption(f"保存先: `{format_display_path(core_root, project_root=PROJECT_ROOT)}`")
  if not summary_md.exists() and not freeze_md.exists() and not reviewer_md.exists():
    st.info(
      "Core Validation Summary はまだ生成されていません。"
      "`python scripts/build_core_validation_summary.py` で生成できます。"
    )
    return
  for label, path in (
    ("cross_theme_core_validation_summary.md", summary_md),
    ("freeze_readiness_judgement.md", freeze_md),
    ("reviewer_response_notes.md", reviewer_md),
  ):
    if path.exists():
      with st.expander(label, expanded=label == "cross_theme_core_validation_summary.md"):
        st.markdown(render_markdown_preview(path.read_text(encoding="utf-8")))
        st.caption(format_display_path(path, project_root=PROJECT_ROOT))


def _tab_reports_final_validation_summary_links(*, developer_mode: bool = False) -> None:
  if not developer_mode:
    return
  final_root = PROJECT_ROOT / "outputs" / "validation" / "final_validation"
  summary_md = final_root / "final_end_to_end_validation_summary.md"
  freeze_md = final_root / "freeze_readiness_final.md"
  reviewer_md = final_root / "reviewer_response_final.md"
  summary_json = final_root / "final_end_to_end_validation_summary.json"
  seed_csv = final_root / "seed_end_to_end_status.csv"
  st.markdown("**Final End-to-End Validation Summary（Phase 24.4D — 開発者向け）**")
  st.caption(f"保存先: `{format_display_path(final_root, project_root=PROJECT_ROOT)}`")
  if (
    not summary_md.exists()
    and not freeze_md.exists()
    and not reviewer_md.exists()
    and not summary_json.exists()
    and not seed_csv.exists()
  ):
    st.info(
      "Final Validation Summary はまだ生成されていません。"
      "`python scripts/build_final_validation_summary.py` で生成できます。"
    )
    return
  for label, path in (
    ("final_end_to_end_validation_summary.md", summary_md),
    ("freeze_readiness_final.md", freeze_md),
    ("reviewer_response_final.md", reviewer_md),
    ("final_end_to_end_validation_summary.json", summary_json),
    ("seed_end_to_end_status.csv", seed_csv),
  ):
    if path.exists():
      with st.expander(label, expanded=label == "final_end_to_end_validation_summary.md"):
        if path.suffix == ".json":
          st.code(path.read_text(encoding="utf-8")[:6000], language="json")
        elif path.suffix == ".csv":
          st.code(path.read_text(encoding="utf-8")[:4000], language="text")
        else:
          st.markdown(render_markdown_preview(path.read_text(encoding="utf-8")))
        st.caption(format_display_path(path, project_root=PROJECT_ROOT))


def _tab_reports_theme_validation_links(*, developer_mode: bool = False) -> None:
  if not developer_mode:
    return
  validation_root = PROJECT_ROOT / "outputs" / "validation" / "theme_validation"
  st.markdown("**Theme Validation Reports（開発者向け）**")
  st.caption(f"保存先: `{format_display_path(validation_root, project_root=PROJECT_ROOT)}`")
  if not validation_root.exists():
    st.info("保存済みの theme validation report はまだありません。")
    return

  found = False
  for theme_dir in sorted(validation_root.iterdir()):
    if not theme_dir.is_dir():
      continue
    report_md = theme_dir / "theme_validation_report.md"
    report_json = theme_dir / "theme_validation_result.json"
    if report_md.exists() or report_json.exists():
      found = True
      with st.expander(f"Theme validation: {theme_dir.name}", expanded=False):
        if report_md.exists():
          st.markdown(render_markdown_preview(report_md.read_text(encoding="utf-8")))
          st.caption(format_display_path(report_md, project_root=PROJECT_ROOT))
        if report_json.exists():
          st.caption(f"JSON: {format_display_path(report_json, project_root=PROJECT_ROOT)}")
  if not found:
    st.info("保存済みの theme validation report はまだありません。")


def _tab_reports(
  manifest: dict[str, Any] | None,
  *,
  demo_artifacts: Any = None,
  repro_artifacts: Any = None,
  developer_mode: bool = False,
) -> None:
  if demo_artifacts is None:
    from tech_cartography.ui.live_digest_preview_ui import render_live_digest_preview_reports_section
    from tech_cartography.ui.live_watch_expansion_ui import render_watch_profile_draft_reports_section

    render_live_digest_preview_reports_section(project_root=PROJECT_ROOT)
    render_watch_profile_draft_reports_section(project_root=PROJECT_ROOT)
    from tech_cartography.ui.live_next_cycle_search_ui import render_live_next_cycle_search_reports_section

    render_live_next_cycle_search_reports_section(project_root=PROJECT_ROOT)
  if is_analyst_view() and demo_artifacts is None:
    case = _resolve_analyst_case()
    snapshot = compute_analyst_workflow_snapshot(case, project_root=PROJECT_ROOT)
    if not snapshot.has_viewable_outputs:
      st.info(ANALYST_EMPTY_ARTIFACT_MESSAGE)
      return
  delivery_artifacts = load_delivery_artifacts(PROJECT_ROOT, publication_number=DEMO_DEEP_DIVE_PUBLICATION)
  render_compressed_report_tab(
    project_root=PROJECT_ROOT,
    delivery_artifacts=delivery_artifacts,
    demo_artifacts=demo_artifacts,
    key_prefix="reports_brief",
  )

  def _full_evidence_report() -> None:
    if demo_artifacts is not None:
      render_evidence_map_report(demo_artifacts)
      return
    if not manifest:
      st.info("パイプライン manifest レポートは未読み込みです。")
      return
    reports = [
      ("carbon_fiber_evidence_map_report_md", "Carbon Fiber Evidence Map"),
      ("evidence_map_synthesis_md", "Evidence Map Synthesis"),
      ("final_report_md", "Synthesis Report"),
    ]
    for key, label in reports:
      md = _load_text_artifact(manifest, key)
      if md:
        with st.expander(label, expanded=False):
          st.markdown(render_markdown_preview(md[:8000]))

  def _repro_section() -> None:
    if repro_artifacts is not None:
      render_reproducibility_smoke_section(repro_artifacts)

  render_developer_report_expander(
    project_root=PROJECT_ROOT,
    delivery_artifacts=delivery_artifacts,
    developer_mode=developer_mode,
    render_core_validation_links=_tab_reports_core_validation_summary_links,
    render_final_validation_links=_tab_reports_final_validation_summary_links,
    render_theme_validation_links=_tab_reports_theme_validation_links,
    render_full_evidence_report=_full_evidence_report,
    render_repro_section=_repro_section,
    key_prefix="reports_dev",
  )


def _main_tab_labels(*, ui_mode: str | None = None) -> list[str]:
  return tab_labels_for_ui_mode(ui_mode)


def _render_tab_by_id(
  tab_id: str,
  *,
  user: dict[str, Any],
  watch: dict[str, Any],
  manifest: dict[str, Any] | None,
  display_mode: str,
  debug_mode: bool,
  demo_mode: bool,
  demo_artifacts: Any,
  repro_artifacts: Any,
  developer_mode: bool,
) -> None:
  if tab_id == "start":
    _tab_start(
      user,
      watch,
      manifest,
      debug_mode=debug_mode,
      demo_mode=demo_mode,
      demo_artifacts=demo_artifacts,
      repro_artifacts=repro_artifacts,
    )
  elif tab_id == "patents":
    if manifest:
      _tab_patents(manifest, display_mode)
    else:
      st.info("特許候補を表示するには run を読み込んでください（開発者向けモード）。")
  elif tab_id == "fulltext":
    if manifest:
      _tab_fulltext(manifest, display_mode, debug_mode=debug_mode and developer_mode)
    else:
      st.info("全文確認を表示するには run を読み込んでください（開発者向けモード）。")
  elif tab_id == "evidence":
    _tab_evidence(
      manifest,
      demo_artifacts=demo_artifacts if demo_mode else None,
      repro_artifacts=repro_artifacts if demo_mode else None,
    )
  elif tab_id == "market":
    _tab_market(manifest, demo_mode=demo_mode)
  elif tab_id == "analyst_input":
    _tab_analyst_input()
  elif tab_id == "theme_validation":
    _tab_theme_validation()
  elif tab_id == "reports":
    _tab_reports(
      manifest,
      demo_artifacts=demo_artifacts if demo_mode else None,
      repro_artifacts=repro_artifacts if demo_mode else None,
      developer_mode=developer_mode,
    )
  elif tab_id == "settings":
    render_user_settings_tab(
      user,
      current_run_id=(manifest or {}).get("run_id"),
      developer_mode=developer_mode,
    )


def render_tabbed_easy_app(
  user: dict[str, Any],
  *,
  pipeline_root: str | None = None,
  run_id: str = "",
  display_mode: str = "かんたん表示",
) -> None:
  st.markdown(inject_easy_ui_css(), unsafe_allow_html=True)
  watch = get_active_watch_profile(user["user_id"])
  ui_mode = get_ui_mode()
  developer_mode = is_developer_view()
  demo_mode = is_demo_view() or bool(st.session_state.get(STATE_DEMO_MODE))
  st.markdown(
    render_main_title("Tech Cartography v7", "炭素繊維 技術地図 — 特許・論文・企業情報から、読むべき技術候補を整理します"),
    unsafe_allow_html=True,
  )
  header_cols = st.columns([2, 2, 2])
  with header_cols[0]:
    st.markdown(render_user_badge(user), unsafe_allow_html=True)
  with header_cols[1]:
    theme_text = str(watch.get("theme", ""))
    watch_label = f"Watch: {theme_text[:40]}…" if len(theme_text) > 40 else f"Watch: {theme_text}"
    st.caption(watch_label)
  with header_cols[2]:
    if developer_mode:
      st.caption(f"run_id: {run_id or user.get('last_run_id') or '未選択'}")

  root = pipeline_root or default_pipeline_root()
  demo_artifacts = load_demo_evidence_map_artifacts(PROJECT_ROOT) if demo_mode else None
  repro_artifacts = (
    load_reproducibility_smoke_artifacts(PROJECT_ROOT)
    if demo_mode and developer_mode
    else None
  )
  if demo_mode and demo_artifacts is not None:
    render_demo_mode_banner(demo_artifacts)

  manifest = None if demo_mode else _resolve_manifest(user, root, run_id)
  debug_mode = bool(st.session_state.get("tc_debug_mode", False))
  if manifest and manifest.get("run_id"):
    rid = str(manifest["run_id"])
    if st.session_state.get(STATE_SAVED_RUN_ID) != rid:
      set_last_run_id(user["user_id"], rid)
      st.session_state[STATE_SAVED_RUN_ID] = rid
      refreshed = dict(user)
      refreshed["last_run_id"] = rid
      st.session_state[STATE_CURRENT_USER] = refreshed

  tab_ids = tab_ids_for_ui_mode(ui_mode)
  tab_labels = tab_labels_for_ui_mode(ui_mode)
  tabs = st.tabs(tab_labels)
  for tab_id, tab in zip(tab_ids, tabs, strict=True):
    with tab:
      _render_tab_by_id(
        tab_id,
        user=user,
        watch=watch,
        manifest=manifest,
        display_mode=display_mode,
        debug_mode=debug_mode,
        demo_mode=demo_mode,
        demo_artifacts=demo_artifacts,
        repro_artifacts=repro_artifacts,
        developer_mode=developer_mode,
      )

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
  if is_developer_view():
    st.sidebar.checkbox("デバッグモード（開発者向け cost ledger）", key="tc_debug_mode", value=False)
  render_tabbed_easy_app(user, pipeline_root=pipeline_root, run_id=run_id, display_mode=display_mode)


# Backward-compatible alias used by app.py import
DEFAULT_PIPELINE_ROOT = default_pipeline_root()
PROJECT_ROOT = Path(__file__).resolve().parents[3]


def _load_json_path(path: Path) -> dict[str, Any] | None:
  if not path.exists():
    return None
  try:
    data = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, dict) else None
  except json.JSONDecodeError:
    return None


def _load_csv_path(path: Path) -> list[dict[str, Any]]:
  if not path.exists():
    return []
  try:
    return load_records_csv(str(path))
  except Exception:
    return []


def _load_demo_evidence_bundle(
  manifest: dict[str, Any] | None,
  project_root: Path,
) -> dict[str, Any]:
  ev_map = _load_json_artifact(manifest, "evidence_map_synthesis_json") if manifest else None
  if not ev_map:
    ev_map = _load_json_path(
      project_root / "outputs/evidence_map_synthesis" / DEMO_DEEP_DIVE_PUBLICATION / "evidence_map_synthesis.json",
    )
  if not ev_map and manifest:
    ev_summary = _load_json_artifact(manifest, "evidence_validation_summary_json")
    if ev_summary and isinstance(ev_summary.get("evidence_map_synthesis"), dict):
      ev_map = ev_summary["evidence_map_synthesis"]

  selected = _load_csv_artifact(manifest, "selected_evidence_papers_csv") if manifest else pd.DataFrame()
  selected_rows = selected.to_dict(orient="records") if not selected.empty else []
  if not selected_rows:
    selected_rows = _load_csv_path(project_root / "outputs/openalex_limited_execution/selected_evidence_papers.csv")

  claim_links_df = _load_csv_artifact(manifest, "claim_paper_candidate_links_csv") if manifest else pd.DataFrame()
  claim_links = claim_links_df.to_dict(orient="records") if not claim_links_df.empty else []
  if not claim_links:
    claim_links = _load_csv_path(project_root / "outputs/openalex_limited_execution/claim_paper_candidate_links.csv")

  excluded: list[dict[str, Any]] = []
  relevance_path = project_root / "outputs/openalex_limited_execution/paper_candidate_relevance.csv"
  if relevance_path.exists():
    for row in _load_csv_path(relevance_path):
      if row.get("relevance_bucket") in {"broad_composite_background", "likely_off_topic"}:
        excluded.append(row)

  return {
    "synthesis": ev_map,
    "selected_papers": selected_rows,
    "claim_links": claim_links,
    "excluded_papers": excluded,
    "artifact_status": discover_demo_artifacts(project_root),
  }
