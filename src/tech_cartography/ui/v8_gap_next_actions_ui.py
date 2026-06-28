"""v8 Gap / Next Actions tab (Phase 27G)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from tech_cartography.runtime.v8_gap_next_actions_schema import (
  GAP_NEXT_ACTIONS_SAFETY_NOTICES,
  GAP_NEXT_PHASES,
  V8EvidenceGapRecord,
  V8GapNextActionsReport,
  V8NextVerificationAction,
)
from tech_cartography.services.v8_claim_map_export import find_latest_claim_map_dir
from tech_cartography.services.v8_evidence_map_export import find_latest_evidence_map_dir
from tech_cartography.services.v8_gap_next_actions import build_gap_next_actions_report
from tech_cartography.services.v8_gap_next_actions_export import (
  export_gap_next_actions,
  find_latest_gap_next_actions_dir,
  gap_next_actions_to_markdown,
  gaps_to_csv_text,
)
from tech_cartography.services.v8_patent_shortlist import build_patent_shortlist
from tech_cartography.services.v8_patent_shortlist_export import find_latest_patent_shortlist_dir
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_next_action_box, render_warning_box
from tech_cartography.ui.v8_demo_flow_ui import render_demo_flow_banner
from tech_cartography.ui.v8_executive_summary_ui import (
  render_gap_executive_summary,
  render_gap_how_to_read_section,
)
from tech_cartography.ui.v8_google_patents_links_ui import render_google_patents_caution
from tech_cartography.ui.v8_judge_mode_ui import render_judge_conclusion_card, render_judge_next_tab_hint
from tech_cartography.ui.v8_input_ui import get_v8_input_state
from tech_cartography.ui.v8_tab_config import (
  STATE_V8_SELECTED_CASE,
  STATE_V8_SELECTED_PUBLICATION,
  V8_CASE_SAMPLES,
  V8_TAB_LABELS,
)

STATE_V8_GAP_NEXT_ACTIONS = "v8_gap_next_actions"


def _case_options() -> list[tuple[str, str]]:
  return [("all", "All cases")] + [(s["case_id"], s["label"]) for s in V8_CASE_SAMPLES]


def _report_from_dict(data: dict[str, Any]) -> V8GapNextActionsReport:
  return V8GapNextActionsReport(
    report_id=data["report_id"],
    case_id=data["case_id"],
    publication_number=data["publication_number"],
    generated_at=data["generated_at"],
    gaps=[V8EvidenceGapRecord.from_dict(g) for g in data.get("gaps", [])],
    next_actions=[V8NextVerificationAction.from_dict(a) for a in data.get("next_actions", [])],
    top_3_actions=[V8NextVerificationAction.from_dict(a) for a in data.get("top_3_actions", [])],
    gap_count=data.get("gap_count", 0),
    action_count=data.get("action_count", 0),
    count_by_gap_type=data.get("count_by_gap_type", {}),
    count_by_action_type=data.get("count_by_action_type", {}),
    count_by_urgency=data.get("count_by_urgency", {}),
    source_artifact_paths=data.get("source_artifact_paths", []),
    evidence_map_artifact_paths=data.get("evidence_map_artifact_paths", []),
    watch_profile_update_proposal=data.get("watch_profile_update_proposal", ""),
    digest_summary=data.get("digest_summary", ""),
    warnings=data.get("warnings", []),
    candidate_information_only=data.get("candidate_information_only", True),
    human_review_required=data.get("human_review_required", True),
    no_legal_judgement=data.get("no_legal_judgement", True),
  )


def _render_metrics(report: V8GapNextActionsReport) -> None:
  review_count = sum(1 for g in report.gaps if g.human_review_required)
  c1, c2, c3, c4 = st.columns(4)
  c1.metric("gap_count", report.gap_count)
  c2.metric("claim_text_required", report.count_by_gap_type.get("claim_text_required", 0))
  c3.metric("example_support_missing", report.count_by_gap_type.get("example_support_missing", 0))
  c4.metric("paper_support_missing", report.count_by_gap_type.get("paper_support_missing", 0))
  c5, c6 = st.columns(2)
  c5.metric("web_or_company_only", report.count_by_gap_type.get("web_or_company_only", 0))
  c6.metric("needs_human_review", review_count)


def _render_top_action_cards(actions: list[V8NextVerificationAction]) -> None:
  if not actions:
    st.caption("Top 3 Next Actions は未生成です。")
    return
  for action in actions[:3]:
    st.markdown(
      render_info_box(
        f"<strong>#{action.action_rank} {action.action_title}</strong><br>"
        f"type: {action.action_type} / effort: {action.estimated_effort_label} / "
        f"owner: {action.owner_suggestion}<br>"
        f"expected_output: {action.expected_output}"
      ),
      unsafe_allow_html=True,
    )


def _render_top_actions(actions: list[V8NextVerificationAction]) -> None:
  if not actions:
    st.caption("Top 3 Next Actions は未生成です。")
    return
  _render_top_action_cards(actions)
  rows = [
    {
      "rank": a.action_rank,
      "action_type": a.action_type,
      "action_title": a.action_title,
      "target_publication_number": a.target_publication_number,
      "expected_output": a.expected_output,
      "effort": a.estimated_effort_label,
      "owner": a.owner_suggestion,
    }
    for a in actions
  ]
  st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
  for action in actions:
    with st.expander(f"#{action.action_rank} {action.action_title}", expanded=action.action_rank == 1):
      st.markdown(f"**action_type:** {action.action_type}")
      st.markdown(f"**description:** {action.action_description}")
      st.markdown(f"**priority_reason:** {action.priority_reason}")
      st.markdown(f"**watch_profile_update_hint:** {action.watch_profile_update_hint}")
      st.markdown(f"**scheduler_followup_hint:** {action.scheduler_followup_hint}")
      st.markdown(f"**email_digest_hint:** {action.email_digest_hint}")


def _render_gap_table(gaps: list[V8EvidenceGapRecord], *, artifact_generated: bool = True, preview_limit: int = 20) -> None:
  if not gaps:
    if artifact_generated:
      st.caption("Gap は0件です（artifact 生成済み — true zero）。")
    else:
      st.caption("Gap artifact は未生成です — これは0件ではなく artifact missing です。")
    return
  st.caption(f"Gap total: {len(gaps)} — 先頭 {min(preview_limit, len(gaps))} 件を表示")
  rows = [
    {
      "gap_type": g.gap_type,
      "gap_title": g.gap_title,
      "severity": g.severity_label,
      "urgency": g.urgency_label,
      "confidence": g.confidence_label,
      "claim_no": g.claim_no,
      "publication_number": g.publication_number,
      "human_review": g.human_review_required,
    }
    for g in gaps[:preview_limit]
  ]
  st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
  if len(gaps) > preview_limit:
    st.caption(f"残り {len(gaps) - preview_limit} 件 — 全件は CSV ダウンロードを利用")


def _render_single_report(
  report: V8GapNextActionsReport,
  export_info: dict[str, Any],
  *,
  key_suffix: str,
) -> None:
  render_gap_how_to_read_section(report=report)

  ex_missing = report.count_by_gap_type.get("example_support_missing", 0)
  if ex_missing > 0:
    st.markdown(
      render_info_box(
        "<strong>実施例裏取り（example_support_missing）</strong><br>"
        f"{ex_missing} 件の未確認事項があります。"
        " 実施例裏取りを進めるには、Top5公報PDFの description / examples 本文が必要です。"
        f" 「{V8_TAB_LABELS['patent_shortlist']}」でGoogle Patentsリンクを開き、"
        f" PDFを取得して「{V8_TAB_LABELS['input']}」にアップロードしてください。"
        " Gapは弱点ではなく未確認事項、Evidence Mapは証明ではなく裏取り候補です。"
        " このPhaseではPDF本文解析はまだ行いません。"
      ),
      unsafe_allow_html=True,
    )
    render_google_patents_caution()

  st.caption("artifact missing と true zero を区別 — Gap artifact 未生成時は gap_count=0 と表示しません")
  refresh_cached = st.session_state.get("v8_manual_claim_refresh_result")
  if isinstance(refresh_cached, dict):
    rpt = refresh_cached.get("report") or {}
    if rpt.get("case_id") == report.case_id:
      before = rpt.get("claim_text_required_count_before")
      after = rpt.get("claim_text_required_count_after")
      if before is not None and after is not None:
        st.markdown(
          render_info_box(
            f"<strong>claim投入後の変化 (Phase27K)</strong> — "
            f"claim_text_required: {before} → {after}。"
            " 次アクションが claim取得 から example/paper 確認へ進む場合があります。"
            " Gap は未確認事項であり、特許の弱点ではありません。"
          ),
          unsafe_allow_html=True,
        )
  else:
    st.caption("Manual Claim Refresh 結果はまだありません — Claim Map タブで保存後 refresh してください。")

  st.markdown("#### Top 3 Next Actions（最優先）")
  _render_top_actions(report.top_3_actions)

  with st.expander(f"Gap 一覧・詳細（全{report.gap_count}件）", expanded=False):
    with st.expander("gap_type 別詳細メトリクス", expanded=False):
      _render_metrics(report)
    if report.count_by_gap_type:
      st.markdown("**gap_type 別 count:**")
      for gap_type, count in sorted(report.count_by_gap_type.items(), key=lambda x: -x[1]):
        st.caption(f"- {gap_type}: {count}")

    st.markdown("#### Remaining Limitations")
    limitations: list[str] = []
    if report.count_by_gap_type.get("claim_text_required", 0) > 0:
      limitations.append("claim 本文未取得 — claim_text_required")
    if report.count_by_gap_type.get("example_support_missing", 0) > 0:
      limitations.append("特許実施例の人手確認が必要（本文は未読）")
    if report.count_by_gap_type.get("paper_support_missing", 0) > 0:
      limitations.append("論文 Evidence の人手確認が必要（本文は未読）")
    if not limitations:
      limitations.append("大きな blocking gap なし — candidate は proof ではない")
    for lim in limitations:
      st.caption(f"- {lim}")

    st.markdown("#### Gap table（preview）")
    _render_gap_table(report.gaps, preview_limit=20)

    gap_options = [f"{g.gap_type} — {g.gap_title} ({g.claim_no})" for g in report.gaps[:20]]
    if gap_options:
      selected_gap_label = st.selectbox("Gap 詳細", gap_options, key=f"v8_gap_detail_{key_suffix}")
      idx = gap_options.index(selected_gap_label)
      gap = report.gaps[idx]
      st.markdown(f"**why_it_matters:** {gap.why_it_matters}")
      st.markdown(f"**related_source_titles:** {', '.join(gap.related_source_titles) or '—'}")
      st.caption(f"source_evidence_links: {', '.join(gap.source_evidence_links)}")

    action_options = [f"#{a.action_rank} {a.action_title}" for a in report.next_actions[:10]]
    if action_options:
      selected_action = st.selectbox("Action 詳細", action_options, key=f"v8_action_detail_{key_suffix}")
      aidx = action_options.index(selected_action)
      action = report.next_actions[aidx]
      st.markdown(f"**expected_output:** {action.expected_output}")
      st.markdown(f"**next_step_command_hint:** {action.next_step_command_hint}")

  st.markdown("#### Watch Profile / Digest / Artifact trace")
  with st.expander("定点観測の詳細（Watch Profile / Digest / Artifact trace）", expanded=False):
    st.markdown("#### Watch Profile update proposal")
    st.markdown(report.watch_profile_update_proposal)
    st.markdown("#### Digest summary")
    st.markdown(report.digest_summary)
    st.markdown("#### Artifact trace")
    for path in report.source_artifact_paths:
      st.caption(path)
    for path in report.evidence_map_artifact_paths:
      st.caption(f"evidence_map: {path}")

  st.markdown("#### ダウンロード")
  st.download_button(
    "CSV", gaps_to_csv_text(report.gaps).encode("utf-8"),
    f"gap_next_actions_{report.case_id}.csv", "text/csv", key=f"v8_gap_dl_csv_{key_suffix}",
  )
  st.download_button(
    "Markdown", gap_next_actions_to_markdown(report).encode("utf-8"),
    f"gap_next_actions_{report.case_id}.md", "text/markdown", key=f"v8_gap_dl_md_{key_suffix}",
  )
  xlsx_path = Path(str(export_info.get("xlsx_path", "")))
  if xlsx_path.exists():
    st.download_button(
      "Excel", xlsx_path.read_bytes(), xlsx_path.name,
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      key=f"v8_gap_dl_xlsx_{key_suffix}",
    )
  watch_path = Path(str(export_info.get("watch_profile_proposal_path", "")))
  if watch_path.exists():
    st.download_button(
      "watch_profile_update_proposal.md", watch_path.read_bytes(), watch_path.name,
      "text/markdown", key=f"v8_gap_dl_watch_{key_suffix}",
    )
  digest_path = Path(str(export_info.get("digest_summary_path", "")))
  if digest_path.exists():
    st.download_button(
      "digest_summary.md", digest_path.read_bytes(), digest_path.name,
      "text/markdown", key=f"v8_gap_dl_digest_{key_suffix}",
    )
  with st.expander("export dir（開発者向け）", expanded=False):
    st.caption(f"export dir: {export_info.get('output_dir', '')}")


def render_v8_gap_next_actions_tab(*, project_root: Path | str) -> None:
  root = Path(project_root)
  render_judge_conclusion_card("gap_next_actions")
  render_judge_next_tab_hint("gap_next_actions")

  state = get_v8_input_state()
  default_case = str(state.get("selected_case_id") or st.session_state.get(STATE_V8_SELECTED_CASE) or "").strip()
  default_pub = str(st.session_state.get(STATE_V8_SELECTED_PUBLICATION) or "").strip()

  st.markdown("### Gap / Next Actions｜未確認事項")
  with st.expander("詳細ガイド・注意事項", expanded=False):
    render_demo_flow_banner(
      project_root=root,
      current_tab="gap_next_actions",
      tab_purpose="Gapは未確認事項 — 弱点・無効理由・侵害リスクではない",
      next_tab_key="fixed_point_observation",
    )
    st.markdown(
      render_info_box(
        "<strong>Gapの見方</strong><br>"
        "• Gap は<strong>未確認事項</strong> — 弱点・無効理由・侵害リスクではありません。<br>"
        "• Next Action は人間が次に確認する技術調査タスクです。"
      ),
      unsafe_allow_html=True,
    )
    st.markdown(
      render_caution_box(
        "<strong>Gap は特許の弱点ではなく、次に確認すべき未確認事項です。</strong> "
        " Next Action は人間が次に確認する技術調査タスクであり、法的判断ではありません。"
        " FTO、侵害、有効性判断は行いません。"
      ),
      unsafe_allow_html=True,
    )
    for notice in GAP_NEXT_ACTIONS_SAFETY_NOTICES[:4]:
      st.caption(notice)

  case_options = _case_options()
  case_ids = [c for c, _ in case_options]
  labels = {c: label for c, label in case_options}
  default_idx = case_ids.index(default_case) if default_case in case_ids else 0

  col1, col2 = st.columns(2)
  with col1:
    selected_case = st.selectbox(
      "案件",
      options=case_ids,
      index=default_idx,
      format_func=lambda cid: labels[cid],
      key="v8_gap_case",
    )
  active_case = case_ids[1] if selected_case == "all" else selected_case
  if selected_case != "all":
    st.session_state[STATE_V8_SELECTED_CASE] = selected_case

  shortlist = build_patent_shortlist(case_id=active_case, top_n=5, project_root=root)
  pub_options = ["（Shortlist 全件）"] + [p.publication_number for p in shortlist.patent_candidates]
  default_pub_idx = pub_options.index(default_pub) if default_pub in pub_options else 0
  with col2:
    selected_pub_label = st.selectbox(
      "特許（Evidence Map / Claim Map / Shortlist）",
      options=pub_options,
      index=default_pub_idx,
      key="v8_gap_pub",
    )
  publication_number = None if selected_pub_label == "（Shortlist 全件）" else selected_pub_label
  if publication_number:
    st.session_state[STATE_V8_SELECTED_PUBLICATION] = publication_number

  ev_dir = find_latest_evidence_map_dir(active_case, root)
  if ev_dir:
    with st.expander("artifact参照（開発者向け）", expanded=False):
      st.caption(f"Evidence Map artifact: {ev_dir}")
      import json
      manifest = ev_dir / "evidence_map_manifest.json"
      if manifest.exists():
        meta = json.loads(manifest.read_text(encoding="utf-8"))
        st.caption(f"missing_evidence_count={meta.get('missing_evidence_count', 0)}")
  else:
    st.caption("Evidence Map 未生成 — 「Evidence Map」タブで Generate してください。")

  refresh = st.button("Generate / Refresh Gap & Next Actions", key="v8_gap_refresh", type="primary")

  cache_key = f"{selected_case}:{publication_number}"
  if refresh or st.session_state.get("v8_gap_cache_key") != cache_key:
    if selected_case == "all":
      bundles: dict[str, dict] = {}
      for sample in V8_CASE_SAMPLES:
        cid = sample["case_id"]
        report = build_gap_next_actions_report(case_id=cid, project_root=root)
        export_result = export_gap_next_actions(report, project_root=root)
        bundles[cid] = {"report": report.to_dict(), "export": export_result.to_dict()}
      st.session_state[STATE_V8_GAP_NEXT_ACTIONS] = {"mode": "all", "bundles": bundles}
    else:
      report = build_gap_next_actions_report(
        case_id=selected_case,
        publication_number=publication_number,
        project_root=root,
      )
      export_result = export_gap_next_actions(report, project_root=root)
      st.session_state[STATE_V8_GAP_NEXT_ACTIONS] = {
        "mode": "single",
        "report": report.to_dict(),
        "export": export_result.to_dict(),
      }
    st.session_state["v8_gap_cache_key"] = cache_key

  cached = st.session_state.get(STATE_V8_GAP_NEXT_ACTIONS)
  if not cached:
    render_gap_executive_summary(None)
    render_gap_how_to_read_section()
    with st.expander("latest export（開発者向け）", expanded=False):
      latest_dir = find_latest_gap_next_actions_dir(active_case if selected_case != "all" else None, root)
      if latest_dir:
        st.caption(f"latest export: {latest_dir}")
    st.info("「Generate / Refresh Gap & Next Actions」を押してください。")
    st.markdown(
      render_next_action_box(f"先に「{V8_TAB_LABELS['evidence_map']}」で Evidence Map を生成してください。"),
      unsafe_allow_html=True,
    )
    return

  if cached.get("mode") == "all":
    bundles = cached.get("bundles") or {}
    for sample in V8_CASE_SAMPLES:
      cid = sample["case_id"]
      bundle = bundles.get(cid)
      if not bundle:
        continue
      report = _report_from_dict(bundle["report"])
      with st.expander(f"{sample['label']} — {report.gap_count} gaps / {report.action_count} actions", expanded=cid == active_case):
        render_gap_executive_summary(report)
        _render_single_report(report, bundle.get("export") or {}, key_suffix=cid)
  else:
    report = _report_from_dict(cached["report"])
    render_gap_executive_summary(report)
    _render_single_report(report, cached.get("export") or {}, key_suffix="single")

  with st.expander("次 Phase への接続（詳細）", expanded=False):
    st.markdown("#### 次 Phase への接続")
    for phase in GAP_NEXT_PHASES:
      st.markdown(f"- {phase}")
    st.markdown(
      render_info_box(
        "Watch Profile update proposal / Digest summary は定点観測ループ（"
        f"「{V8_TAB_LABELS['fixed_point_observation']}」）へ引き継がれます。"
        " 人手承認後に Watch Profile 反映・次回 Scheduler・メール Digest へ接続します。"
      ),
      unsafe_allow_html=True,
    )

  st.markdown(
    render_next_action_box(
      f"次: 「{V8_TAB_LABELS['fixed_point_observation']}」で定点観測ループを確認。"
      " 次回タスク / Digest 計画 / Scheduler plan（デモではメール送信・Scheduler起動はOFF）へ進んでください。"
    ),
    unsafe_allow_html=True,
  )
