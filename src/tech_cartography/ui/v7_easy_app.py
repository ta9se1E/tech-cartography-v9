"""Easy Japanese Streamlit app for Tech Cartography v7 pipeline results."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from tech_cartography.orchestration.latest_outputs import read_latest_run_pointer
from tech_cartography.reports.project_export import load_records_csv
from tech_cartography.ui.easy_japanese_ui import (
  inject_easy_ui_css,
  prepare_patent_display_df,
  render_caveat_footer,
  render_fulltext_vs_watch_notice,
  render_info_box,
  render_metric_cards,
  render_patent_card,
  render_step_header,
  render_strategic_watch_card,
  render_success_box,
  render_top5_fulltext_card,
  render_warning_box,
  summarize_stage_statuses,
)

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_PIPELINE_ROOT = PROJECT_ROOT / "outputs" / "pipeline_runs"


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


def _resolve_run_dir(run_id: str, pipeline_root: Path) -> Path:
  return pipeline_root / run_id


def _next_commands(manifest: dict[str, Any]) -> list[str]:
  commands = manifest.get("config", {}).get("next_recommended_commands") or []
  return [str(cmd) for cmd in commands if cmd]


def render_easy_japanese_app() -> None:
  st.markdown(inject_easy_ui_css(), unsafe_allow_html=True)
  st.markdown('<div class="tc-easy-title">Tech Cartography v7 かんたん技術地図</div>', unsafe_allow_html=True)
  st.markdown(
    '<div class="tc-easy-subtitle">特許・論文・企業情報から、読むべき技術候補を整理します</div>',
    unsafe_allow_html=True,
  )

  with st.sidebar:
    st.header("設定")
    pipeline_root = st.text_input("実行結果フォルダ", value=str(DEFAULT_PIPELINE_ROOT))
    run_id = st.text_input("run_id", value="")
    if st.button("latest_run から読み込む"):
      pointer = read_latest_run_pointer(pipeline_root)
      if pointer and pointer.get("run_id"):
        st.session_state["easy_run_id"] = pointer["run_id"]
        st.session_state["easy_manifest_path"] = pointer.get("manifest_path", "")
        st.success(f"最新 run: {pointer['run_id']}")
      else:
        st.warning("latest_run.json が見つかりません。")
    if st.session_state.get("easy_run_id"):
      run_id = st.session_state["easy_run_id"]
    display_mode = st.radio("表示モード", ["かんたん表示", "詳細表示"], index=0)
    st.markdown(render_warning_box(
      "BigQuery・OpenAlex・全文取得は有料/外部実行の可能性があります。"
      "本画面は結果の整理用であり、法的判断は行いません。",
    ), unsafe_allow_html=True)

  manifest_data: dict[str, Any] | None = None
  manifest_path = st.session_state.get("easy_manifest_path")
  if manifest_path:
    manifest_data = _load_manifest(manifest_path)
  elif run_id:
    candidate = _resolve_run_dir(run_id, Path(pipeline_root)) / "run_manifest.json"
    manifest_data = _load_manifest(candidate)

  if not manifest_data:
    st.markdown(render_info_box(
      "実行結果を選んでください。sidebar で run_id を入力するか、"
      "「latest_run から読み込む」を押してください。",
    ), unsafe_allow_html=True)
    st.markdown(render_caveat_footer(), unsafe_allow_html=True)
    return

  # Step 1: 実行状況
  st.markdown(
    render_step_header(1, "実行状況", "パイプライン各段階の状態と、次に実行すべきコマンドを確認します"),
    unsafe_allow_html=True,
  )
  stage_rows = summarize_stage_statuses(manifest_data)
  if stage_rows:
    st.dataframe(pd.DataFrame(stage_rows)[["段階", "状態", "説明"]], use_container_width=True, hide_index=True)
  else:
    st.info("ステージ情報がありません。")

  commands = _next_commands(manifest_data)
  if commands:
    st.markdown(render_info_box("次に実行すべきコマンド例:"), unsafe_allow_html=True)
    for cmd in commands:
      st.code(cmd)

  # Step 2: 特許候補
  st.markdown(
    render_step_header(2, "特許候補をさがす", "分類・優先度付けされた特許候補を確認します"),
    unsafe_allow_html=True,
  )
  ranked_df = _load_csv_artifact(manifest_data, "ranked_patents_csv")
  top20_df = _load_csv_artifact(manifest_data, "top20_patents_csv")
  if ranked_df.empty and not top20_df.empty:
    ranked_df = top20_df

  metrics = [
    {"label": "ランク付け件数", "value": len(ranked_df)},
    {"label": "Top20件数", "value": len(top20_df)},
  ]
  if not top20_df.empty and "primary_cluster_id" in top20_df.columns:
    metrics.append({"label": "技術分類数", "value": top20_df["primary_cluster_id"].nunique()})
  if not top20_df.empty and "country" in top20_df.columns:
    metrics.append({"label": "国数", "value": top20_df["country"].nunique()})
  st.markdown(render_metric_cards(metrics), unsafe_allow_html=True)

  if not top20_df.empty:
    display_df = prepare_patent_display_df(top20_df)
    if display_mode == "かんたん表示":
      st.subheader("読むべき特許候補（Top20）")
      for _, row in top20_df.head(20).iterrows():
        st.markdown(render_patent_card(row.to_dict()), unsafe_allow_html=True)
    else:
      st.subheader("Top20（日本語列名）")
      st.dataframe(display_df, use_container_width=True, hide_index=True)
    if "primary_cluster_id" in top20_df.columns:
      st.caption("技術分類別件数")
      st.dataframe(top20_df["primary_cluster_id"].value_counts().reset_index(), hide_index=True)
    if "country" in top20_df.columns:
      st.caption("国別件数")
      st.dataframe(top20_df["country"].value_counts().reset_index(), hide_index=True)
    if "assignee" in top20_df.columns:
      st.caption("出願人別件数")
      st.dataframe(top20_df["assignee"].fillna("不明").value_counts().head(10).reset_index(), hide_index=True)
  else:
    st.warning("Top20 の成果物がまだありません。technology_clustering_ranking を実行してください。")

  # Step 3: 全文確認候補 + 戦略監視候補
  st.markdown(
    render_step_header(3, "読むべき特許を選ぶ", "全文取得候補と戦略監視候補を分けて確認します"),
    unsafe_allow_html=True,
  )
  st.markdown(render_fulltext_vs_watch_notice(), unsafe_allow_html=True)

  top5_df = _load_csv_artifact(manifest_data, "top5_fulltext_candidates_csv")
  watch_df = _load_csv_artifact(manifest_data, "strategic_watch_candidates_csv")
  country_watch_df = _load_csv_artifact(manifest_data, "country_watch_summary_csv")
  company_watch_df = _load_csv_artifact(manifest_data, "company_watch_summary_csv")

  st.subheader("A. 全文を取りに行きやすい候補（US中心）")
  if not top5_df.empty:
    st.markdown(render_success_box(f"全文を確認できそうな特許: {len(top5_df)} 件"), unsafe_allow_html=True)
    caveat = str(top5_df.iloc[0].get("caveat_japanese", ""))
    if caveat:
      st.markdown(render_info_box(caveat), unsafe_allow_html=True)
    for _, row in top5_df.iterrows():
      st.markdown(render_top5_fulltext_card(row.to_dict()), unsafe_allow_html=True)
    if display_mode == "詳細表示":
      st.dataframe(prepare_patent_display_df(top5_df), use_container_width=True, hide_index=True)
  else:
    st.info("Top5 全文候補がまだありません。")

  st.subheader("B. 戦略監視すべき候補（中国・EP・JP含む）")
  if not watch_df.empty:
    cn_count = 0
    if "country" in watch_df.columns:
      cn_count = int((watch_df["country"].astype(str).str.upper() == "CN").sum())
    st.markdown(
      render_info_box(
        f"戦略監視候補: {len(watch_df)} 件（中国候補: {cn_count} 件）。"
        "中国候補を除外しているわけではありません。",
      ),
      unsafe_allow_html=True,
    )
    for _, row in watch_df.head(15).iterrows():
      st.markdown(render_strategic_watch_card(row.to_dict()), unsafe_allow_html=True)
    if display_mode == "詳細表示":
      st.dataframe(prepare_patent_display_df(watch_df), use_container_width=True, hide_index=True)
    if not country_watch_df.empty:
      st.caption("国別監視サマリー")
      st.dataframe(country_watch_df, use_container_width=True, hide_index=True)
    if not company_watch_df.empty:
      st.caption("企業別監視サマリー")
      st.dataframe(company_watch_df.head(15), use_container_width=True, hide_index=True)
  else:
    st.info("Strategic Watch 候補がまだありません。clustering を再実行してください。")

  # Step 4: 技術の裏取り
  st.markdown(
    render_step_header(4, "技術の裏取りを見る", "請求項・論文による裏取り候補を確認します"),
    unsafe_allow_html=True,
  )
  technical_md = _load_text_artifact(manifest_data, "technical_view_report_md")
  claim_md = _load_text_artifact(manifest_data, "claim_element_report_md")
  if technical_md or claim_md:
    st.markdown(render_info_box("技術の裏取り候補があります。これは断定ではなく、追加確認が必要です。"), unsafe_allow_html=True)
    if claim_md:
      with st.expander("請求項要素レポート"):
        st.markdown(claim_md)
    if technical_md:
      with st.expander("技術評価レポート"):
        st.markdown(technical_md)
  else:
    st.warning("まだ実行していません。次は Full Text / Claim Element を実行してください。")

  # Step 5: 企業の動き
  st.markdown(
    render_step_header(5, "企業の動きを見る", "Webシグナルや事業化候補を確認します"),
    unsafe_allow_html=True,
  )
  web_df = _load_csv_artifact(manifest_data, "web_signal_patent_links_csv")
  business_df = _load_csv_artifact(manifest_data, "patent_business_summary_csv")
  if not web_df.empty or not business_df.empty:
    st.markdown(render_info_box("企業の動きの候補があります。市場断定ではありません。"), unsafe_allow_html=True)
    if not web_df.empty:
      st.dataframe(web_df.head(20), use_container_width=True, hide_index=True)
    if not business_df.empty:
      st.dataframe(business_df.head(20), use_container_width=True, hide_index=True)
  else:
    st.info("Web signal CSVを追加すると表示できます。")

  # Step 6: まとめ
  st.markdown(
    render_step_header(6, "まとめレポート", "統合レポートで全体像を確認します"),
    unsafe_allow_html=True,
  )
  synthesis_md = _load_text_artifact(manifest_data, "final_report_md") or _load_text_artifact(
    manifest_data,
    "carbon_fiber_evidence_map_v1_md",
  )
  if synthesis_md:
    st.markdown(synthesis_md)
  else:
    st.info("まだ統合レポートはありません。")

  # Step 7: 次にやること
  st.markdown(
    render_step_header(7, "次にやること", "現在の run 状態から推奨アクションを確認します"),
    unsafe_allow_html=True,
  )
  recommendations: list[str] = []
  if top20_df.empty:
    recommendations.append("まず technology_clustering_ranking を完了させて Top20 を確認してください。")
  elif top5_df.empty:
    recommendations.append("Top20 確認後、fulltext_collection 段階へ進んでください。")
  else:
    recommendations.append("Top5 全文候補（US）と Strategic Watch 候補（中国・EP・JP含む）を確認してください。")
  if web_df.empty:
    recommendations.append("企業動向を見る場合は Web signal CSV テンプレートを埋めてください。")
  if not synthesis_md:
    recommendations.append("統合レポートが未作成なら synthesis_report 段階を実行してください。")
  for item in recommendations:
    st.markdown(f"- {item}")
  if commands:
    st.code(commands[0])

  st.markdown(render_caveat_footer(), unsafe_allow_html=True)
