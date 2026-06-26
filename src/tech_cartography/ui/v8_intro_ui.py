"""v8 intro tab (Phase 27B / 27M / 27N)."""

from __future__ import annotations

from pathlib import Path

import streamlit as st

from tech_cartography.services.v8_cloud_run_readiness import build_cloud_run_readiness_report
from tech_cartography.services.v8_demo_readiness import build_demo_readiness_report
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box
from tech_cartography.ui.v8_demo_flow_ui import format_count_label
from tech_cartography.ui.v8_text_rendering import render_next_action_card
from tech_cartography.ui.v8_tab_config import V8_STATUS_CAPTION, V8_TAB_LABELS

PROJECT_ROOT = Path(__file__).resolve().parents[3]


def render_v8_intro_tab() -> None:
  st.markdown("### Tech Cartography v8")
  st.markdown(
    render_info_box(
      "<strong>1000件規模の特許候補から読むべき特許を絞り込み、"
      "Claim / Evidence / Gap / Next Action を整理して、"
      "次回の定点観測へつなげる R&D Intelligence Agent</strong>"
    ),
    unsafe_allow_html=True,
  )

  st.markdown("#### Phase27N.5 — Case 1 実データ E2E（最優先）")
  st.markdown(
    render_info_box(
      "<strong>Cloud Run deploy 前に、Case 1 だけ実在特許 CSV で最後まで通す</strong>。"
      " 1000件は母集団 — Top5 のみ Deep Dive。"
      " claim 本文は自動生成しません。"
    ),
    unsafe_allow_html=True,
  )
  n5_steps = [
    "実在 CSV を cases/case_01_pan_graphitization/large_candidates/case_01_bigquery_export_1000.csv に配置",
    "Import（入力タブまたは CLI）",
    "Top100 / Top20 / Top5 生成",
    "Top5 から1件選び claim 本文を手動投入",
    "refresh（Claim Map 投入後 または CLI）",
    "Demo Polish Pack / Demo Readiness Pack 生成",
  ]
  for index, step in enumerate(n5_steps, start=1):
    st.markdown(f"{index}. {step}")
  st.markdown(
    render_next_action_card(
      "Case 1 次にやること",
      [
        "実在特許 CSV を配置（fixture/架空CSV不可）",
        "scripts/run_v8_one_case_demo_e2e_check.py を実行",
        "claim 未投入なら Claim Map タブで1件手動投入",
      ],
    ),
    unsafe_allow_html=True,
  )

  st.markdown("#### 最短デモ操作")
  demo_steps = [
    "Case を選ぶ",
    "入力タブで 1000件 CSV を取り込む",
    "Sources一覧で母集団を見る",
    "読むべき特許で Top100 → Top20 → Top5 を見る",
    "Claim Map で claim 状態を見る",
    "claim 本文があれば手動投入する（1件推奨）",
    "Evidence Map で supporting evidence candidate を見る",
    "Gap / Next Actions で未確認事項を見る",
    "定点観測で次回タスクを見る",
    "Export で Demo Pack を出す",
  ]
  for index, step in enumerate(demo_steps, start=1):
    st.markdown(f"{index}. {step}")

  st.markdown("#### デモで見せる順番")
  flow = [
    V8_TAB_LABELS["input"],
    V8_TAB_LABELS["sources"],
    V8_TAB_LABELS["patent_shortlist"],
    V8_TAB_LABELS["claim_map"],
    V8_TAB_LABELS["evidence_map"],
    V8_TAB_LABELS["gap_next_actions"],
    V8_TAB_LABELS["fixed_point_observation"],
    V8_TAB_LABELS["export"],
  ]
  st.caption(" → ".join(flow))

  st.markdown("#### Demo Readiness Summary (Phase27M)")
  try:
    report = build_demo_readiness_report(project_root=PROJECT_ROOT)
    st.markdown(f"- **overall_status**: {report.overall_status}")
    st.markdown(f"- **ready / warning / not_ready**: {report.ready_case_count} / {report.warning_case_count} / {report.not_ready_case_count}")
    for case in report.cases:
      ev = format_count_label(case.evidence_link_count, artifact_label="evidence")
      gap = format_count_label(case.gap_count, artifact_label="gap")
      st.markdown(
        f"- **{case.case_id}**: {case.overall_status} — "
        f"next={case.current_recommended_step} / evidence={ev} / gap={gap}"
      )
      not_gen = [s.display_label for s in case.step_statuses if s.status == "not_generated"]
      if not_gen:
        st.caption(f"  artifact missing: {', '.join(not_gen)}（true zero ではありません）")
    st.markdown(
      render_next_action_card("次にやること", report.common_next_actions[:3]),
      unsafe_allow_html=True,
    )
  except Exception as exc:
    st.warning(f"Demo Readiness 取得エラー: {exc}")

  st.markdown("#### Cloud Run Readiness Summary (Phase27N)")
  st.caption("今は **deploy 前チェックの段階** — Cloud Build / Cloud Run deploy はまだ実行しません。")
  try:
    cr = build_cloud_run_readiness_report(project_root=PROJECT_ROOT)
    st.markdown(f"- **overall_status**: {cr.overall_status}")
    st.markdown(f"- **app_entrypoint**: {cr.app_entrypoint_status}")
    st.markdown(f"- **streamlit_command**: {cr.streamlit_command_status}")
    st.markdown(f"- **demo_data**: {cr.demo_data_status}")
    if cr.known_blockers:
      st.markdown("- **known_blockers**:")
      for b in cr.known_blockers[:3]:
        st.caption(f"  - {b}")
    next_actions = [
      "Export タブで Cloud Run Readiness Pack を生成する",
    ]
    if cr.demo_data_status in {"not_ready", "needs_large_candidate_csv", "unknown"}:
      next_actions.append("Demo Readiness が not_ready なら、1ケース分の CSV 投入と Top5 生成を行う")
    next_actions.append("Phase27O まで Cloud Build / Cloud Run deploy を実行しない")
    st.markdown(
      render_next_action_card("次にやること (Cloud Run 準備)", next_actions),
      unsafe_allow_html=True,
    )
  except Exception as exc:
    st.warning(f"Cloud Run Readiness 取得エラー: {exc}")

  st.markdown(
    render_caution_box(
      "Cloud Build / Cloud Run deploy はこの Phase では実行しません。"
      " artifact 未生成は「0件」ではなく「未生成」と表示します。"
      " FTO・侵害・有効性判断は行いません。"
    ),
    unsafe_allow_html=True,
  )

  st.markdown("#### Phase27I — 3案件ローカル検証")
  st.markdown(
    render_info_box(
      "Export タブで<strong>3案件検証パック</strong>を作成し、"
      " Sources → Top特許 → Claim Map → Evidence Map → Gap → 定点観測 → Export "
      "の流れがローカルで成立するか確認します。"
    ),
    unsafe_allow_html=True,
  )

  st.markdown("#### 現在の開発状態")
  st.caption(V8_STATUS_CAPTION)

  st.markdown(
    render_next_action_card(
      "初めての方へ",
      f"「{V8_TAB_LABELS['input']}」タブから Case を選び、CSV を取り込んでください。",
    ),
    unsafe_allow_html=True,
  )
