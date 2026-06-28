"""v8 fixed-point observation tab (Phase 27H)."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd
import streamlit as st

from tech_cartography.auth.basic_auth import is_login_required
from tech_cartography.runtime.user_context import resolve_user_context
from tech_cartography.runtime.v8_fixed_point_observation_schema import (
  OBSERVATION_LOOP_SAFETY_NOTICES,
  V8EmailDigestPlan,
  V8ObservationLoopReport,
  V8SchedulerFollowupPlan,
  V8WatchProfileUpdateProposal,
)
from tech_cartography.services.live_run_history import list_run_history_entries
from tech_cartography.services.live_watch_profile_manager import describe_watch_profile_status, get_active_watch_profile
from tech_cartography.services.v8_claim_map_export import find_latest_claim_map_dir
from tech_cartography.services.v8_evidence_map_export import find_latest_evidence_map_dir
from tech_cartography.services.v8_fixed_point_observation import build_observation_loop_report
from tech_cartography.services.v8_fixed_point_observation_export import (
  export_observation_loop,
  find_latest_fixed_point_observation_dir,
  observation_loop_to_markdown,
)
from tech_cartography.services.v8_evidence_gap_next_actions import (
  evidence_aware_gap_primary_available,
  find_latest_evidence_aware_gap_dir,
)
from tech_cartography.services.v8_gap_next_actions_export import find_latest_gap_next_actions_dir
from tech_cartography.services.v8_patent_shortlist import build_patent_shortlist
from tech_cartography.services.v8_patent_shortlist_export import find_latest_patent_shortlist_dir
from tech_cartography.ui.easy_japanese_ui import render_caution_box, render_info_box, render_next_action_box, render_warning_box
from tech_cartography.ui.live_run_history_ui import render_run_history_section
from tech_cartography.ui.live_watch_expansion_ui import render_live_watch_expansion_section
from tech_cartography.ui.login_ui import can_use_admin_features
from tech_cartography.ui.v8_demo_flow_ui import render_demo_flow_banner
from tech_cartography.ui.v8_executive_summary_ui import render_watch_executive_summary
from tech_cartography.ui.v8_evidence_aware_watch_ui import render_evidence_aware_watch_section
from tech_cartography.ui.v8_judge_mode_ui import render_judge_conclusion_card, render_judge_next_tab_hint
from tech_cartography.ui.v8_input_ui import get_v8_input_state
from tech_cartography.ui.v8_tab_config import (
  STATE_V8_SELECTED_CASE,
  STATE_V8_SELECTED_PUBLICATION,
  V8_CASE_SAMPLES,
  V8_TAB_LABELS,
)

STATE_V8_OBSERVATION_LOOP = "v8_observation_loop"


def _case_options() -> list[tuple[str, str]]:
  return [("all", "All cases")] + [(s["case_id"], s["label"]) for s in V8_CASE_SAMPLES]


def _report_from_dict(data: dict[str, Any]) -> V8ObservationLoopReport:
  sched_data = data.get("scheduler_followup_plan")
  email_data = data.get("email_digest_plan")
  return V8ObservationLoopReport(
    report_id=data["report_id"],
    case_id=data["case_id"],
    publication_number=data["publication_number"],
    generated_at=data["generated_at"],
    loop_status=data.get("loop_status", ""),
    current_state_summary=data.get("current_state_summary", ""),
    what_changed_or_needs_change=data.get("what_changed_or_needs_change", ""),
    watch_profile_update_proposals=[
      V8WatchProfileUpdateProposal.from_dict(p) for p in data.get("watch_profile_update_proposals", [])
    ],
    scheduler_followup_plan=V8SchedulerFollowupPlan.from_dict(sched_data) if sched_data else None,
    email_digest_plan=V8EmailDigestPlan.from_dict(email_data) if email_data else None,
    top_3_next_cycle_tasks=data.get("top_3_next_cycle_tasks", []),
    artifact_trace=data.get("artifact_trace", []),
    source_artifact_paths=data.get("source_artifact_paths", []),
    export_paths=data.get("export_paths", []),
    warnings=data.get("warnings", []),
    candidate_information_only=data.get("candidate_information_only", True),
    human_review_required=data.get("human_review_required", True),
    no_legal_judgement=data.get("no_legal_judgement", True),
    no_email_send=data.get("no_email_send", True),
    no_scheduler_start=data.get("no_scheduler_start", True),
  )


def _render_metrics(report: V8ObservationLoopReport) -> None:
  c1, c2, c3, c4 = st.columns(4)
  c1.metric("loop_status", report.loop_status)
  c2.metric("top_action_count", len(report.top_3_next_cycle_tasks))
  c3.metric("watch_proposals", len(report.watch_profile_update_proposals))
  sched = report.scheduler_followup_plan
  c4.metric("human_inputs", len(sched.required_human_inputs) if sched else 0)


def _render_single_report(
  report: V8ObservationLoopReport,
  export_info: dict[str, Any],
  *,
  key_suffix: str,
) -> None:
  _render_metrics(report)
  st.markdown(f"**current_state_summary:** {report.current_state_summary}")

  refresh_cached = st.session_state.get("v8_manual_claim_refresh_result")
  if isinstance(refresh_cached, dict):
    rpt = refresh_cached.get("report") or {}
    if rpt.get("case_id") == report.case_id:
      st.markdown(
        render_info_box(
          "<strong>claim投入後の次回タスク変化 (Phase27K)</strong><br>"
          "before: claim本文取得 / load_claim_text<br>"
          "after: 実施例確認 / paper evidence確認 / property data確認<br>"
          "メール送信: デモではOFF / Scheduler起動: デモではOFF — 機能は必須として保持。"
        ),
        unsafe_allow_html=True,
      )

  st.markdown("#### Top 3 Next Cycle Tasks")
  for task in report.top_3_next_cycle_tasks:
    st.markdown(f"- {task}")

  st.markdown("#### Watch Profile Update Proposal")
  if report.watch_profile_update_proposals:
    rows = [
      {
        "proposal_type": p.proposal_type,
        "proposed_items": "; ".join(p.proposed_items[:3]),
        "reason": p.reason[:80],
        "priority_label": p.priority_label,
        "review_status": p.review_status,
      }
      for p in report.watch_profile_update_proposals
    ]
    st.dataframe(pd.DataFrame(rows), width="stretch", hide_index=True)
    st.caption("Watch Profile 更新案は自動反映しません — 人手承認が必要です。")
  else:
    st.caption("提案なし")

  with st.expander("Scheduler / Email Digest 詳細", expanded=False):
    st.markdown("#### Scheduler Follow-up Plan")
    sched = report.scheduler_followup_plan
    if sched:
      st.markdown(f"- **schedule_mode:** {sched.schedule_mode}")
      st.markdown(f"- **planned_steps:** {', '.join(sched.planned_steps)}")
      if sched.blocked_steps:
        st.markdown(f"- **blocked_steps:** {', '.join(sched.blocked_steps)}")
      if sched.required_human_inputs:
        st.markdown(f"- **required_human_inputs:** {', '.join(sched.required_human_inputs)}")
      st.caption(sched.scheduler_followup_hint)
      st.caption("Scheduler起動: デモではOFF")
    else:
      st.caption("Scheduler plan 未生成")

    st.markdown("#### Email Digest Plan")
    email = report.email_digest_plan
    if email:
      st.markdown(f"- **digest_mode:** {email.digest_mode}")
      st.markdown(f"- **subject_draft:** {email.subject_draft}")
      st.caption("メール送信: デモではOFF")
      with st.expander("digest_summary", expanded=False):
        st.markdown(email.digest_summary)
      st.caption(email.email_digest_hint)
    else:
      st.caption("Email digest plan 未生成")

  st.markdown("#### Artifact Trace")
  with st.expander("Artifact trace（開発者向け）", expanded=False):
    for trace in report.artifact_trace:
      st.caption(trace)
    for path in report.source_artifact_paths:
      st.caption(f"source: {path}")

  st.markdown("#### ダウンロード")
  st.download_button(
    "fixed_point_observation.md",
    observation_loop_to_markdown(report).encode("utf-8"),
    f"fixed_point_observation_{report.case_id}.md",
    "text/markdown",
    key=f"v8_fp_dl_md_{key_suffix}",
  )
  for label, key in (
    ("watch_profile_update_proposal.md", "watch_profile_proposal_path"),
    ("scheduler_followup_plan.md", "scheduler_plan_path"),
    ("email_digest_plan.md", "email_digest_plan_path"),
  ):
    path = Path(str(export_info.get(key, "")))
    if path.exists():
      st.download_button(label, path.read_bytes(), path.name, "text/markdown", key=f"v8_fp_dl_{key}_{key_suffix}")
  xlsx_path = Path(str(export_info.get("xlsx_path", "")))
  if xlsx_path.exists():
    st.download_button(
      "Excel", xlsx_path.read_bytes(), xlsx_path.name,
      "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
      key=f"v8_fp_dl_xlsx_{key_suffix}",
    )
  manifest_path = Path(str(export_info.get("manifest_path", "")))
  if manifest_path.exists():
    st.download_button(
      "manifest.json", manifest_path.read_bytes(), manifest_path.name,
      "application/json", key=f"v8_fp_dl_manifest_{key_suffix}",
    )
  with st.expander("export dir（開発者向け）", expanded=False):
    st.caption(f"export dir: {export_info.get('output_dir', '')}")

def render_v8_fixed_point_observation_tab(*, project_root: Path | str) -> None:
  root = Path(project_root)
  render_judge_conclusion_card("fixed_point_observation")
  render_judge_next_tab_hint("fixed_point_observation")

  state = get_v8_input_state()
  default_case = str(state.get("selected_case_id") or st.session_state.get(STATE_V8_SELECTED_CASE) or "").strip()
  default_pub = str(st.session_state.get(STATE_V8_SELECTED_PUBLICATION) or "").strip()

  st.markdown("### 定点観測｜Weekly Watch")
  render_watch_executive_summary()
  with st.expander("詳細ガイド・メール/Scheduler 注意", expanded=False):
    render_demo_flow_banner(
      project_root=root,
      current_tab="fixed_point_observation",
      tab_purpose="定点観測ループ — Digest preview（メール/Scheduler OFF）",
      next_tab_key="export",
    )
    st.markdown(
      render_info_box(
        "<strong>定点観測で回る流れ</strong><br>"
        "1. 今回の Top5 深掘り結果<br>"
        "2. 今回の Evidence Gap（未確認事項）<br>"
        "3. 次回 Watch Profile 更新案（人手承認後）<br>"
        "4. Scheduler Follow-up Plan（起動OFF）<br>"
        "5. Email Digest Plan（送信OFF）<br>"
        "メール送信と Scheduler は必須機能として残しますが、本デモでは実行しません。"
      ),
      unsafe_allow_html=True,
    )
    st.markdown(
      render_info_box(
        "<strong>メール送信</strong>と<strong>Scheduler</strong>は定点観測の必須機能です（デフォルト OFF、機能は保持）。"
        " 本タブでは計画・提案・プレビューのみ — 送信・起動はしません。"
        f" SMTP / Scheduler 本番設定は「{V8_TAB_LABELS['admin_settings']}」へ。"
      ),
      unsafe_allow_html=True,
    )
    for notice in OBSERVATION_LOOP_SAFETY_NOTICES[:4]:
      st.caption(notice)

  watch_status = describe_watch_profile_status(root)
  active, active_path = get_active_watch_profile(root)
  with st.expander("Active Watch Profile（閲覧）", expanded=False):
    if active:
      st.markdown(f"- **theme**: {active.get('theme', '')}")
      st.markdown(f"- **keywords**: {', '.join(active.get('keywords') or [])}")
      st.caption(f"path: {active_path}")
    else:
      st.caption("active Watch Profile なし")
    st.caption(f"status: {watch_status.get('watch_profile_status')}")

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
      key="v8_fp_case",
    )
  active_case = case_ids[1] if selected_case == "all" else selected_case
  if selected_case != "all":
    st.session_state[STATE_V8_SELECTED_CASE] = selected_case

  shortlist = build_patent_shortlist(case_id=active_case, top_n=5, project_root=root)
  pub_options = ["（Shortlist 全件）"] + [p.publication_number for p in shortlist.patent_candidates]
  default_pub_idx = pub_options.index(default_pub) if default_pub in pub_options else 0
  with col2:
    selected_pub_label = st.selectbox(
      "特許（Gap / Evidence / Claim / Shortlist）",
      options=pub_options,
      index=default_pub_idx,
      key="v8_fp_pub",
    )
  publication_number = None if selected_pub_label == "（Shortlist 全件）" else selected_pub_label
  if publication_number:
    st.session_state[STATE_V8_SELECTED_PUBLICATION] = publication_number

  if selected_case != "all":
    render_evidence_aware_watch_section(active_case, root, key_prefix="v8_fp_ev_watch")
    st.divider()

  gap_dir = find_latest_evidence_aware_gap_dir(active_case, root)
  legacy_gap_dir = find_latest_gap_next_actions_dir(active_case, root)
  if not gap_dir or not evidence_aware_gap_primary_available(active_case, root):
    st.caption(
      "Evidence-aware Gap 未生成 — "
      f"「{V8_TAB_LABELS['gap_next_actions']}」タブで Generate Gap / Next Actions from Claim-Example Evidence を実行してください。"
    )
  with st.expander("artifact参照（開発者向け）", expanded=False):
    if gap_dir:
      st.caption(f"Evidence-aware Gap artifact: {gap_dir}")
    if legacy_gap_dir and legacy_gap_dir != gap_dir:
      st.caption(f"Legacy Gap artifact: {legacy_gap_dir}")
    for finder, label in (
      (find_latest_evidence_map_dir, "Evidence Map"),
      (find_latest_claim_map_dir, "Claim Map"),
      (find_latest_patent_shortlist_dir, "Patent Shortlist"),
    ):
      p = finder(active_case, root)
      if p:
        st.caption(f"{label}: {p}")

  refresh = st.button(
    "Generate / Refresh Fixed Point Observation Loop",
    key="v8_fp_refresh",
    type="primary",
  )

  cache_key = f"{selected_case}:{publication_number}"
  if refresh or st.session_state.get("v8_fp_cache_key") != cache_key:
    if selected_case == "all":
      bundles: dict[str, dict] = {}
      for sample in V8_CASE_SAMPLES:
        cid = sample["case_id"]
        report = build_observation_loop_report(case_id=cid, project_root=root)
        export_result = export_observation_loop(report, project_root=root)
        bundles[cid] = {"report": report.to_dict(), "export": export_result.to_dict()}
      st.session_state[STATE_V8_OBSERVATION_LOOP] = {"mode": "all", "bundles": bundles}
    else:
      report = build_observation_loop_report(
        case_id=selected_case,
        publication_number=publication_number,
        project_root=root,
      )
      export_result = export_observation_loop(report, project_root=root)
      st.session_state[STATE_V8_OBSERVATION_LOOP] = {
        "mode": "single",
        "report": report.to_dict(),
        "export": export_result.to_dict(),
      }
    st.session_state["v8_fp_cache_key"] = cache_key

  cached = st.session_state.get(STATE_V8_OBSERVATION_LOOP)
  if not cached:
    with st.expander("latest export（開発者向け）", expanded=False):
      latest = find_latest_fixed_point_observation_dir(active_case if selected_case != "all" else None, root)
      if latest:
        st.caption(f"latest export: {latest}")

  with st.expander("Legacy Fixed Point Observation Loop（Evidence Mapベース）", expanded=False):
    if not cached:
      st.info("「Generate / Refresh Fixed Point Observation Loop」を押してください（Legacy observation loop）。")
      st.caption("Evidence-aware Watch preview は上記セクションが主参照です。")
    else:
      st.caption("以下は Evidence Map ベースの従来ループです。")
      if cached.get("mode") == "all":
        bundles = cached.get("bundles") or {}
        for sample in V8_CASE_SAMPLES:
          cid = sample["case_id"]
          bundle = bundles.get(cid)
          if not bundle:
            continue
          report = _report_from_dict(bundle["report"])
          with st.expander(
            f"{sample['label']} — {report.loop_status}",
            expanded=cid == active_case,
          ):
            _render_single_report(report, bundle.get("export") or {}, key_suffix=cid)
      else:
        report = _report_from_dict(cached["report"])
        _render_single_report(report, cached.get("export") or {}, key_suffix="single")

  st.markdown("#### Scope Feedback / Run History")
  st.caption("検索範囲の拡張・縮小は Scope Expansion で人間承認。Watch Profile は自動更新しません。")
  if can_use_admin_features() and is_login_required():
    render_live_watch_expansion_section(project_root=root, key_prefix="v8_fixed_point_scope")
    render_run_history_section(project_root=root, key_prefix="v8_fixed_point_run_history", expanded=False)
  else:
    st.markdown(render_info_box("Scope Feedback / Run History の詳細は管理者設定で操作します。"), unsafe_allow_html=True)

  history = list_run_history_entries(root, limit=3, viewer_user_context=resolve_user_context())
  if history:
    st.caption("直近 Run History:")
    for entry in history:
      st.caption(f"- {entry.get('run_id')} / {entry.get('action_type')}")

  st.markdown(
    render_caution_box(
      "このタブでは Scheduler 起動・メール送信・Watch Profile 自動更新は行いません。"
      f" 詳細設定は「{V8_TAB_LABELS['admin_settings']}」を参照。"
      " FTO / 侵害 / 有効性判断ではありません。"
    ),
    unsafe_allow_html=True,
  )

  st.markdown(
    render_info_box(
      f"「{V8_TAB_LABELS['gap_next_actions']}」に戻るか、"
      f"「{V8_TAB_LABELS['export']}」で成果物をダウンロードできます。"
    ),
    unsafe_allow_html=True,
  )
