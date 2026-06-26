"""v8 Fixed Point Observation loop builder (Phase 27H)."""

from __future__ import annotations

import hashlib
from collections import Counter, defaultdict
from typing import Any

from tech_cartography.runtime.v8_fixed_point_observation_schema import (
  OBSERVATION_LOOP_SAFETY_NOTICES,
  V8EmailDigestPlan,
  V8ObservationCycleInput,
  V8ObservationLoopReport,
  V8SchedulerFollowupPlan,
  V8WatchProfileUpdateProposal,
)
from tech_cartography.runtime.v8_gap_next_actions_schema import V8GapNextActionsReport, V8NextVerificationAction
from tech_cartography.runtime.v8_sources_schema import utc_now_iso
from tech_cartography.services.v8_claim_map_export import find_latest_claim_map_dir
from tech_cartography.services.v8_evidence_map_export import find_latest_evidence_map_dir
from tech_cartography.services.v8_export_package import get_v8_export_packages_dir
from tech_cartography.services.v8_gap_next_actions import build_gap_next_actions_report
from tech_cartography.services.v8_gap_next_actions_export import find_latest_gap_next_actions_dir
from tech_cartography.services.v8_patent_shortlist_export import find_latest_patent_shortlist_dir
from tech_cartography.services.v8_sources_table import load_case_profile, project_root_from_here

ACTION_TO_PROPOSAL_TYPE: dict[str, str] = {
  "load_claim_text": "add_claim_loading_task",
  "check_patent_examples": "add_example_review_task",
  "expand_paper_search": "add_paper_search_task",
  "check_paper_source": "add_paper_search_task",
  "check_company_primary_source": "add_company_source_review_task",
  "narrow_watch_profile": "narrow_keywords",
  "expand_watch_profile": "expand_keywords",
  "add_exclusion_keywords": "add_exclusion_keywords",
}

ACTION_TO_SCHEDULER_STEP: dict[str, str] = {
  "load_claim_text": "load_claim_text",
  "check_patent_examples": "check_examples",
  "check_paper_source": "update_sources",
  "check_company_primary_source": "update_sources",
  "expand_paper_search": "update_sources",
}


def _report_id(case_id: str, publication_number: str) -> str:
  digest = hashlib.sha256(f"{case_id}|{publication_number}|observation_loop".encode()).hexdigest()[:12]
  return f"{case_id}:observation_loop:{digest}"


def _proposal_id(case_id: str, proposal_type: str) -> str:
  digest = hashlib.sha256(f"{case_id}|{proposal_type}".encode()).hexdigest()[:12]
  return f"{case_id}:watch_proposal:{digest}"


def _scheduler_plan_id(case_id: str) -> str:
  digest = hashlib.sha256(f"{case_id}|scheduler_plan".encode()).hexdigest()[:12]
  return f"{case_id}:scheduler_plan:{digest}"


def _digest_plan_id(case_id: str) -> str:
  digest = hashlib.sha256(f"{case_id}|digest_plan".encode()).hexdigest()[:12]
  return f"{case_id}:digest_plan:{digest}"


def _collect_source_paths(case_id: str, root: Any) -> dict[str, list[str]]:
  paths: dict[str, list[str]] = {
    "gap": [],
    "evidence_map": [],
    "claim_map": [],
    "patent_shortlist": [],
    "sources": [],
  }
  gap_dir = find_latest_gap_next_actions_dir(case_id, root)
  if gap_dir and gap_dir.exists():
    paths["gap"].append(str(gap_dir))
  ev_dir = find_latest_evidence_map_dir(case_id, root)
  if ev_dir and ev_dir.exists():
    paths["evidence_map"].append(str(ev_dir))
  claim_dir = find_latest_claim_map_dir(case_id, root)
  if claim_dir and claim_dir.exists():
    paths["claim_map"].append(str(claim_dir))
  shortlist_dir = find_latest_patent_shortlist_dir(case_id, root)
  if shortlist_dir and shortlist_dir.exists():
    paths["patent_shortlist"].append(str(shortlist_dir))
  sources_root = get_v8_export_packages_dir(root)
  if sources_root.is_dir():
    for p in sorted(sources_root.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
      if p.is_dir() and p.name.startswith(f"{case_id}_"):
        paths["sources"].append(str(p))
        break
  return paths


def _build_watch_proposals(
  gap_report: V8GapNextActionsReport,
  *,
  case_id: str,
) -> list[V8WatchProfileUpdateProposal]:
  proposals: list[V8WatchProfileUpdateProposal] = []
  action_counts = Counter(a.action_type for a in gap_report.next_actions)
  gap_type_counts = gap_report.count_by_gap_type

  if action_counts.get("load_claim_text", 0) > 0 or gap_type_counts.get("claim_text_required", 0) > 0:
    gap_ids = [g.gap_id for g in gap_report.gaps if g.gap_type == "claim_text_required"]
    action_ids = [a.action_id for a in gap_report.next_actions if a.action_type == "load_claim_text"]
    proposals.append(V8WatchProfileUpdateProposal(
      proposal_id=_proposal_id(case_id, "add_claim_loading_task"),
      case_id=case_id,
      proposal_type="add_claim_loading_task",
      proposed_items=["claims_input.csv に claim 本文を追加", "次回タスクに claim 本文取得を追加"],
      reason=f"claim_text_required が {gap_type_counts.get('claim_text_required', 0)} 件",
      source_gap_ids=gap_ids[:5],
      source_action_ids=action_ids[:5],
      priority_label="high",
      caution_flags=["pending_human_review", "no_auto_watch_profile_update"],
    ))

  if action_counts.get("check_patent_examples", 0) > 0:
    proposals.append(V8WatchProfileUpdateProposal(
      proposal_id=_proposal_id(case_id, "add_example_review_task"),
      case_id=case_id,
      proposal_type="add_example_review_task",
      proposed_items=["特許 description / examples の実施例確認を次回タスクに追加"],
      reason=f"check_patent_examples が {action_counts.get('check_patent_examples', 0)} 件",
      source_action_ids=[a.action_id for a in gap_report.next_actions if a.action_type == "check_patent_examples"][:5],
      priority_label="high",
      caution_flags=["pending_human_review"],
    ))

  paper_count = action_counts.get("check_paper_source", 0) + action_counts.get("expand_paper_search", 0)
  if paper_count > 0 or gap_type_counts.get("paper_support_missing", 0) > 0:
    proposals.append(V8WatchProfileUpdateProposal(
      proposal_id=_proposal_id(case_id, "add_paper_search_task"),
      case_id=case_id,
      proposal_type="add_paper_search_task",
      proposed_items=["paper search keywords を Watch Profile に追加"],
      reason=f"paper_support_missing / paper actions が {paper_count + gap_type_counts.get('paper_support_missing', 0)} 件",
      priority_label="medium",
      caution_flags=["pending_human_review"],
    ))

  if action_counts.get("check_company_primary_source", 0) > 0 or gap_type_counts.get("web_or_company_only", 0) > 0:
    proposals.append(V8WatchProfileUpdateProposal(
      proposal_id=_proposal_id(case_id, "add_company_source_review_task"),
      case_id=case_id,
      proposal_type="add_company_source_review_task",
      proposed_items=["company source verification を次回定点観測タスクに追加"],
      reason="web/company 候補の一次情報確認が必要",
      priority_label="medium",
      caution_flags=["candidate_information_only", "pending_human_review"],
    ))

  axes: dict[str, int] = defaultdict(int)
  for gap in gap_report.gaps:
    for ax in gap.technical_axis_labels:
      if ax and ax != "unknown":
        axes[ax] += 1
  if axes:
    top_axis = max(axes, key=axes.get)  # type: ignore[arg-type]
    proposals.append(V8WatchProfileUpdateProposal(
      proposal_id=_proposal_id(case_id, "focus_axis"),
      case_id=case_id,
      proposal_type="focus_axis",
      proposed_items=[f"重点 technical_axis: {top_axis}"],
      reason=f"technical_axis '{top_axis}' が {axes[top_axis]} 件の Gap に関連",
      affected_claim_axes=[top_axis],
      priority_label="medium",
      caution_flags=["pending_human_review"],
    ))

  weak_count = gap_type_counts.get("evidence_link_weak", 0) + gap_type_counts.get("web_or_company_only", 0)
  if weak_count >= 2:
    proposals.append(V8WatchProfileUpdateProposal(
      proposal_id=_proposal_id(case_id, "add_exclusion_keywords"),
      case_id=case_id,
      proposal_type="add_exclusion_keywords",
      proposed_items=["ノイズ source_type の除外キーワード縮小候補を検討"],
      reason=f"弱い候補 / web-only が {weak_count} 件",
      priority_label="low",
      caution_flags=["pending_human_review"],
    ))

  if not proposals:
    proposals.append(V8WatchProfileUpdateProposal(
      proposal_id=_proposal_id(case_id, "keep_current_scope"),
      case_id=case_id,
      proposal_type="keep_current_scope",
      proposed_items=["現行 Watch Profile スコープを維持"],
      reason="追加タスクが少ない — 現行スコープを維持",
      priority_label="low",
      review_status="not_applicable",
      caution_flags=["keep_current_scope"],
    ))

  return proposals


def _build_scheduler_plan(
  gap_report: V8GapNextActionsReport,
  *,
  case_id: str,
) -> V8SchedulerFollowupPlan:
  steps: list[str] = []
  blocked: list[str] = []
  required_inputs: list[str] = []

  has_claim_required = gap_report.count_by_gap_type.get("claim_text_required", 0) > 0
  if has_claim_required:
    steps.append("load_claim_text")
    required_inputs.append("claims_input.csv に claim 本文を人手追加")

  for action in gap_report.top_3_actions:
    step = ACTION_TO_SCHEDULER_STEP.get(action.action_type)
    if step and step not in steps:
      steps.append(step)

  pipeline = [
    "update_sources",
    "regenerate_patent_shortlist",
    "regenerate_claim_map",
    "regenerate_evidence_map",
    "regenerate_gap_next_actions",
    "create_digest_preview",
  ]
  for step in pipeline:
    if step not in steps:
      steps.append(step)

  steps.append("send_email_after_approval")
  blocked.append("send_email_after_approval — 本 Phase では実送信しない")

  if has_claim_required:
    blocked.extend([
      "regenerate_claim_map — claim 本文取得前は深い分析が制限される",
      "regenerate_evidence_map — claim 本文取得前は深い分析が制限される",
    ])

  return V8SchedulerFollowupPlan(
    scheduler_plan_id=_scheduler_plan_id(case_id),
    case_id=case_id,
    schedule_mode="dry_run_only",
    planned_cycle_label="next_manual_cycle",
    planned_steps=steps,
    blocked_steps=blocked,
    required_human_inputs=required_inputs,
    scheduler_followup_hint="次回 Scheduler 定点観測で Gap 再確認（本 Phase では起動しない）",
    scheduler_enabled=False,
    no_scheduler_start=True,
    caution_flags=["no_scheduler_start", "dry_run_only", "human_approval_required"],
  )


def _build_email_digest_plan(
  gap_report: V8GapNextActionsReport,
  proposals: list[V8WatchProfileUpdateProposal],
  *,
  case_id: str,
) -> V8EmailDigestPlan:
  top_lines = [
    f"{a.action_rank}. {a.action_title} ({a.target_publication_number})"
    for a in gap_report.top_3_actions[:3]
  ]
  watch_lines = [f"- [{p.proposal_type}] {', '.join(p.proposed_items[:2])}" for p in proposals[:3]]
  subject = f"[PatentScout v8] Evidence Gap {gap_report.gap_count}件 — {case_id}（プレビュー）"
  digest_body = "\n".join([
    f"未確認 Gap 数: {gap_report.gap_count}",
    f"Top 3 Next Actions:",
    *[f"  {line}" for line in top_lines],
    "",
    "次回 Watch Profile 更新候補:",
    *watch_lines,
    "",
    "candidate information only — Web/company は候補扱い",
    "FTO / 侵害 / 有効性 / 法的結論は行いません。",
    "本メールはプレビューです — 送信はしません。",
  ])
  return V8EmailDigestPlan(
    digest_plan_id=_digest_plan_id(case_id),
    case_id=case_id,
    digest_mode="preview_only",
    subject_draft=subject,
    digest_summary=digest_body,
    top_3_actions_summary="\n".join(top_lines),
    watch_profile_update_summary="\n".join(watch_lines),
    evidence_gap_change_summary=f"gap_count={gap_report.gap_count}; types={gap_report.count_by_gap_type}",
    recipient_group_label="approved_members",
    email_digest_hint="人手承認後にメール Digest 送信（本 Phase では送信しない）",
    email_send_enabled=False,
    no_email_send=True,
    caution_flags=["preview_only", "no_email_send", "no_legal_judgement", "candidate_information_only"],
  )


def _resolve_loop_status(
  gap_report: V8GapNextActionsReport | None,
  source_paths: dict[str, list[str]],
) -> str:
  if not gap_report:
    return "incomplete_inputs"
  if not source_paths.get("gap"):
    return "incomplete_inputs"
  if gap_report.count_by_gap_type.get("claim_text_required", 0) >= 1:
    return "blocked_by_claim_text_required"
  if gap_report.digest_summary.strip():
    return "ready_for_digest_preview"
  if gap_report.gap_count >= 1:
    return "ready_for_next_cycle_plan"
  return "ready_for_human_review"


def _top_cycle_tasks(gap_report: V8GapNextActionsReport) -> list[str]:
  tasks: list[str] = []
  for action in gap_report.top_3_actions[:3]:
    tasks.append(f"{action.action_rank}. [{action.action_type}] {action.action_title} — {action.expected_output}")
  return tasks


def build_observation_loop_report(
  *,
  case_id: str,
  publication_number: str | None = None,
  project_root: Any = None,
  gap_report: V8GapNextActionsReport | None = None,
) -> V8ObservationLoopReport:
  root = project_root or project_root_from_here()
  profile = load_case_profile(case_id, root) or {}
  del profile

  warnings: list[str] = list(OBSERVATION_LOOP_SAFETY_NOTICES[:3])
  source_paths = _collect_source_paths(case_id, root)

  if gap_report is None:
    gap_report = build_gap_next_actions_report(
      case_id=case_id,
      publication_number=publication_number,
      project_root=root,
    )

  pub = (publication_number or gap_report.publication_number or "all").strip() or "all"
  proposals = _build_watch_proposals(gap_report, case_id=case_id)
  scheduler_plan = _build_scheduler_plan(gap_report, case_id=case_id)
  email_plan = _build_email_digest_plan(gap_report, proposals, case_id=case_id)
  loop_status = _resolve_loop_status(gap_report, source_paths)

  all_source_paths: list[str] = []
  for key in ("gap", "evidence_map", "claim_map", "patent_shortlist", "sources"):
    all_source_paths.extend(source_paths.get(key, []))

  artifact_trace = [
    f"gap_next_actions: {source_paths['gap'][0]}" if source_paths["gap"] else "gap_next_actions: (missing)",
    f"evidence_map: {source_paths['evidence_map'][0]}" if source_paths["evidence_map"] else "evidence_map: (missing)",
    f"claim_map: {source_paths['claim_map'][0]}" if source_paths["claim_map"] else "claim_map: (missing)",
    f"patent_shortlist: {source_paths['patent_shortlist'][0]}" if source_paths["patent_shortlist"] else "patent_shortlist: (missing)",
  ]

  cycle_input = V8ObservationCycleInput(
    cycle_id=_report_id(case_id, pub),
    case_id=case_id,
    publication_number=pub,
    generated_at=utc_now_iso(),
    source_gap_next_actions_paths=source_paths["gap"],
    source_evidence_map_paths=source_paths["evidence_map"],
    source_claim_map_paths=source_paths["claim_map"],
    source_patent_shortlist_paths=source_paths["patent_shortlist"],
    source_sources_paths=source_paths["sources"],
    current_gap_count=gap_report.gap_count,
    current_top_actions=[a.action_title for a in gap_report.top_3_actions],
    current_watch_profile_update_proposal=gap_report.watch_profile_update_proposal,
    current_digest_summary=gap_report.digest_summary,
  )
  del cycle_input

  state_summary = (
    f"Gap {gap_report.gap_count}件 / Actions {gap_report.action_count}件 / "
    f"loop_status={loop_status} / claim_text_required={gap_report.count_by_gap_type.get('claim_text_required', 0)}"
  )
  what_changed = (
    f"次回サイクルで確認すべき: {', '.join(gap_report.count_by_gap_type.keys()) or 'なし'}。"
    " Watch Profile 更新案は人手承認待ち。"
  )

  return V8ObservationLoopReport(
    report_id=_report_id(case_id, pub),
    case_id=case_id,
    publication_number=pub,
    generated_at=utc_now_iso(),
    loop_status=loop_status,
    current_state_summary=state_summary,
    what_changed_or_needs_change=what_changed,
    watch_profile_update_proposals=proposals,
    scheduler_followup_plan=scheduler_plan,
    email_digest_plan=email_plan,
    top_3_next_cycle_tasks=_top_cycle_tasks(gap_report),
    artifact_trace=artifact_trace,
    source_artifact_paths=all_source_paths,
    warnings=warnings,
    candidate_information_only=True,
    human_review_required=True,
    no_legal_judgement=True,
    no_email_send=True,
    no_scheduler_start=True,
  )
