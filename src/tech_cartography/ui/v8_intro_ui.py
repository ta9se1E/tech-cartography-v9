"""v8 intro tab (Phase 27B / 27M / 27N)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from tech_cartography.services.v8_cloud_run_readiness import build_cloud_run_readiness_report
from tech_cartography.services.v8_demo_readiness import build_demo_readiness_report
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box
from tech_cartography.ui.v8_demo_flow_ui import format_count_label
from tech_cartography.ui.v8_text_rendering import render_next_action_card
from tech_cartography.ui.v8_judge_mode_ui import (
  render_judge_conclusion_card,
  render_judge_next_tab_hint,
  render_judge_three_minute_guide,
)
from tech_cartography.ui.v8_tab_config import V8_STATUS_CAPTION, V8_TAB_LABELS

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def render_v8_intro_tab() -> None:
  render_judge_conclusion_card("intro")
  render_judge_three_minute_guide()
  render_judge_next_tab_hint("intro")

  with st.expander("詳細情報（Demo Readiness / Cloud Run / 開発者向け）", expanded=False):
    st.markdown("### Tech Cartography v8")
    st.markdown(
      render_info_box(
        "<strong>1000件規模の特許候補から読むべき特許を絞り込み、"
        "Claim / Evidence / Gap / Next Action を整理して、"
        "次回の定点観測へつなげる R&D Intelligence Agent</strong><br>"
        "FTO、侵害、有効性判断、法的結論は行いません。"
      ),
      unsafe_allow_html=True,
    )

    st.markdown("#### Case 1 実データ E2E")
    st.markdown(
      render_info_box(
        "<strong>Case 1 は1000件候補→Top5選抜→Top5全件35請求項投入済み。</strong>"
        " 1000件は母集団 — Top5 のみ Deep Dive。"
        " claim 本文は自動生成しません。"
      ),
      unsafe_allow_html=True,
    )
    n5_steps = [
      "実在 CSV を cases/case_01_pan_graphitization/large_candidates/case_01_bigquery_export_1000.csv に配置済み",
      "Import（入力タブまたは CLI）",
      "Top100 / Top20 / Top5 生成",
      "Top5 全件35請求項を manual_input として投入済み",
      "refresh（Claim Map 投入後 または CLI）",
      "Demo Polish Pack / Demo Readiness Pack 生成",
    ]
    for index, step in enumerate(n5_steps, start=1):
      st.markdown(f"{index}. {step}")
    st.markdown(
      render_next_action_card(
        "Case 1 次にやること",
        [
          "Case 1: Top5全件35請求項投入済み — Evidence Gap / 実施例確認へ",
          "Export タブで Demo Readiness Pack / 共有レポートを確認",
        ],
      ),
      unsafe_allow_html=True,
    )

    st.markdown("#### Demo Readiness Summary")
    try:
      report = build_demo_readiness_report(project_root=PROJECT_ROOT)
      st.markdown(f"- **overall_status**: {report.overall_status}")
      for case in report.cases:
        ev = format_count_label(case.evidence_link_count, artifact_label="evidence")
        gap = format_count_label(case.gap_count, artifact_label="gap")
        st.markdown(
          f"- **{case.case_id}**: {case.overall_status} — evidence={ev} / gap={gap}"
        )
    except Exception as exc:
      st.warning(f"Demo Readiness 取得エラー: {exc}")

    st.markdown("#### Cloud Run Readiness Summary")
    try:
      cr = build_cloud_run_readiness_report(project_root=PROJECT_ROOT)
      st.markdown(f"- **overall_status**: {cr.overall_status}")
      st.markdown(f"- **demo_data**: {cr.demo_data_status}")
    except Exception as exc:
      st.warning(f"Cloud Run Readiness 取得エラー: {exc}")

    st.caption(V8_STATUS_CAPTION)
