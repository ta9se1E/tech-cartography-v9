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
  c1, c2, c3, c4, c5 = st.columns(5)
  c1.metric("gap_count", report.gap_count)
  c2.metric("action_count", report.action_count)
  c3.metric("claim_text_required", report.count_by_gap_type.get("claim_text_required", 0))
  c4.metric("example_support_missing", report.count_by_gap_type.get("example_support_missing", 0))
  c5.metric("paper_support_missing", report.count_by_gap_type.get("paper_support_missing", 0))
  c6, c7, c8 = st.columns(3)
  c6.metric("web_or_company_only", report.count_by_gap_type.get("web_or_company_only", 0))
  c7.metric("needs_human_review", sum(1 for g in report.gaps if g.human_review_required))
  c8.metric("source_url_missing", report.count_by_gap_type.get("source_url_missing", 0))


def _render_top_actions(actions: list[V8NextVerificationAction]) -> None:
  if not actions:
    st.caption("Top 3 Next Actions は未生成です。")
    return
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


def _render_gap_table(gaps: list[V8EvidenceGapRecord]) -> None:
  if not gaps:
    st.caption("Gap はありません。")
    return
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
    for g in gaps
  ]
  st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)


def _render_single_report(
  report: V8GapNextActionsReport,
  export_info: dict[str, Any],
  *,
  key_suffix: str,
) -> None:
  _render_metrics(report)
  st.markdown("#### Top 3 Next Actions")
  _render_top_actions(report.top_3_actions)
  st.markdown("#### Gap table")
  _render_gap_table(report.gaps)

  gap_options = [f"{g.gap_type} — {g.gap_title} ({g.claim_no})" for g in report.gaps]
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
  st.caption(f"export dir: {export_info.get('output_dir', '')}")


def render_v8_gap_next_actions_tab(*, project_root: Path | str) -> None:
  root = Path(project_root)
  state = get_v8_input_state()
  default_case = str(state.get("selected_case_id") or st.session_state.get(STATE_V8_SELECTED_CASE) or "").strip()
  default_pub = str(st.session_state.get(STATE_V8_SELECTED_PUBLICATION) or "").strip()

  st.markdown("### Gap / Next Actions")
  st.markdown(
    render_caution_box(
      "<strong>Gap は未確認事項であり、特許の弱点・無効性・侵害可能性ではありません。</strong> "
      "Next Action は人間が次に確認する技術調査タスクであり、法的判断ではありません。"
      " candidate information only / human review required。"
      " FTO、侵害、有効性判断ではありません。"
      " 外部API・メール送信・Scheduler 起動はこのタブでは行いません。"
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
  claim_dir = find_latest_claim_map_dir(active_case, root)
  shortlist_dir = find_latest_patent_shortlist_dir(active_case, root)
  if ev_dir:
    st.caption(f"Evidence Map artifact: {ev_dir}")
    import json
    manifest = ev_dir / "evidence_map_manifest.json"
    if manifest.exists():
      meta = json.loads(manifest.read_text(encoding="utf-8"))
      st.caption(
        f"missing_evidence_count={meta.get('missing_evidence_count', 0)} / "
        f"claim_text_required_count={meta.get('claim_text_required_count', 0)}"
      )
  else:
    st.caption("Evidence Map 未生成 — 「Evidence Map」タブで Generate してください。")
  if claim_dir:
    st.caption(f"Claim Map artifact: {claim_dir}")
  if shortlist_dir:
    st.caption(f"Patent Shortlist artifact: {shortlist_dir}")

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
        _render_single_report(report, bundle.get("export") or {}, key_suffix=cid)
  else:
    report = _report_from_dict(cached["report"])
    _render_single_report(report, cached.get("export") or {}, key_suffix="single")

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
      f"「{V8_TAB_LABELS['fixed_point_observation']}」で定点観測ループ（Phase27H）へ進んでください。"
    ),
    unsafe_allow_html=True,
  )
