"""v8 Gap / Next Actions builder (Phase 27G)."""

from __future__ import annotations

import hashlib
from collections import defaultdict
from typing import Any

from tech_cartography.runtime.v8_evidence_map_schema import V8EvidenceLink, V8EvidenceMap
from tech_cartography.runtime.v8_gap_next_actions_schema import (
  GAP_NEXT_ACTIONS_SAFETY_NOTICES,
  V8EvidenceGapRecord,
  V8GapNextActionsReport,
  V8NextVerificationAction,
)
from tech_cartography.runtime.v8_sources_schema import utc_now_iso
from tech_cartography.services.v8_claim_map_export import find_latest_claim_map_dir
from tech_cartography.services.v8_evidence_map import build_evidence_map
from tech_cartography.services.v8_evidence_map_export import find_latest_evidence_map_dir
from tech_cartography.services.v8_patent_shortlist_export import find_latest_patent_shortlist_dir
from tech_cartography.services.v8_sources_table import load_case_profile, project_root_from_here

GAP_TYPE_PRIORITY: dict[str, int] = {
  "claim_text_required": 100,
  "example_support_missing": 90,
  "paper_support_missing": 80,
  "property_data_missing": 75,
  "process_condition_missing": 75,
  "structure_characterization_missing": 70,
  "needs_primary_source_review": 65,
  "source_url_missing": 60,
  "web_or_company_only": 55,
  "evidence_link_weak": 40,
  "unknown": 10,
}

ACTION_TYPE_FOR_GAP: dict[str, str] = {
  "claim_text_required": "load_claim_text",
  "example_support_missing": "check_patent_examples",
  "paper_support_missing": "check_paper_source",
  "property_data_missing": "check_property_data",
  "process_condition_missing": "check_process_conditions",
  "structure_characterization_missing": "check_paper_source",
  "web_or_company_only": "check_company_primary_source",
  "source_url_missing": "check_company_primary_source",
  "needs_primary_source_review": "check_company_primary_source",
  "evidence_link_weak": "check_paper_source",
  "unknown": "unknown",
}

EVIDENCE_NEEDED_GAP_MAP: dict[str, str] = {
  "example_support": "example_support_missing",
  "paper_support": "paper_support_missing",
  "property_data_support": "property_data_missing",
  "process_condition_support": "process_condition_missing",
  "structure_characterization_support": "structure_characterization_missing",
  "claim_text_loading_required": "claim_text_required",
}


def _gap_id(case_id: str, claim_id: str, gap_type: str) -> str:
  digest = hashlib.sha256(f"{case_id}|{claim_id}|{gap_type}".encode()).hexdigest()[:12]
  return f"{case_id}:gap:{digest}"


def _action_id(case_id: str, gap_id: str, action_type: str) -> str:
  digest = hashlib.sha256(f"{case_id}|{gap_id}|{action_type}".encode()).hexdigest()[:12]
  return f"{case_id}:action:{digest}"


def _report_id(case_id: str, publication_number: str) -> str:
  digest = hashlib.sha256(f"{case_id}|{publication_number}|gap_report".encode()).hexdigest()[:12]
  return f"{case_id}:gap_report:{digest}"


def _count_by(items: list, attr: str) -> dict[str, int]:
  counts: dict[str, int] = {}
  for item in items:
    val = getattr(item, attr, "unknown") or "unknown"
    counts[val] = counts.get(val, 0) + 1
  return counts


def _is_gap_link(link: V8EvidenceLink) -> bool:
  if link.support_type == "claim_text_required":
    return True
  if link.support_level in {"missing", "needs_human_review", "weak_candidate", "not_assessed"}:
    return True
  if link.source_type in {"web", "company"}:
    return True
  return bool(not link.source_url.strip() and link.source_id)


def _classify_gap_from_link(link: V8EvidenceLink) -> str:
  if link.support_type == "claim_text_required":
    return "claim_text_required"
  if link.support_level == "missing":
    for needed in link.evidence_needed:
      mapped = EVIDENCE_NEEDED_GAP_MAP.get(needed)
      if mapped:
        return mapped
  if not link.source_url.strip() and link.source_id:
    return "source_url_missing"
  if link.source_type in {"web", "company"}:
    return "web_or_company_only"
  if link.support_level in {"weak_candidate", "not_assessed"}:
    return "evidence_link_weak"
  if link.human_review_required and link.support_level == "needs_human_review":
    return "needs_primary_source_review"
  return "unknown"


def _gap_title(gap_type: str) -> str:
  titles = {
    "claim_text_required": "請求項本文が未取得",
    "example_support_missing": "実施例裏取りが未確認",
    "paper_support_missing": "論文Evidenceが不足",
    "property_data_missing": "物性データ裏取りが未確認",
    "process_condition_missing": "プロセス条件裏取りが未確認",
    "structure_characterization_missing": "構造解析Evidenceが未確認",
    "web_or_company_only": "Web/company候補のみ",
    "source_url_missing": "source URLが不足",
    "needs_primary_source_review": "一次情報の人手確認が必要",
    "evidence_link_weak": "裏取り候補リンクが弱い",
  }
  return titles.get(gap_type, f"未確認Gap ({gap_type})")


def _severity(gap_type: str) -> str:
  if gap_type in {"claim_text_required", "example_support_missing"}:
    return "high"
  if gap_type in {"paper_support_missing", "process_condition_missing", "property_data_missing"}:
    return "medium"
  return "low"


def _urgency(gap_type: str) -> str:
  if gap_type == "claim_text_required":
    return "now"
  if gap_type in {"example_support_missing", "paper_support_missing"}:
    return "next_cycle"
  return "later"


def _build_gap(link: V8EvidenceLink, gap_type: str, *, case_id: str) -> V8EvidenceGapRecord:
  gid = _gap_id(case_id, link.claim_id, gap_type)
  return V8EvidenceGapRecord(
    gap_id=gid,
    case_id=case_id,
    publication_number=link.publication_number,
    patent_title="",
    claim_id=link.claim_id,
    claim_no=link.claim_no,
    primary_axis=link.primary_axis,
    technical_axis_labels=list(link.technical_axis_labels),
    gap_type=gap_type,
    gap_title=_gap_title(gap_type),
    gap_description=link.evidence_gap or f"Evidence Map link indicates {gap_type}",
    why_it_matters=(
      f"未確認のため Claim/Evidence 分析を深められません（{gap_type}）。"
      " 特許の弱点・無効性ではありません。"
    ),
    source_evidence_links=[link.evidence_link_id],
    related_source_ids=[link.source_id] if link.source_id else [],
    related_source_titles=[link.source_title] if link.source_title else [],
    related_evidence_needed=list(link.evidence_needed),
    severity_label=_severity(gap_type),
    urgency_label=_urgency(gap_type),
    confidence_label="high" if gap_type == "claim_text_required" else "medium",
    human_review_required=True,
    candidate_information_only=link.candidate_information_only,
    caution_flags=[
      "gap_not_invalidity_conclusion",
      "human_verification_task",
      "no_legal_judgement",
    ],
    next_action_id="",
  )


def _build_action_from_gap(gap: V8EvidenceGapRecord, *, rank: int) -> V8NextVerificationAction:
  action_type = ACTION_TYPE_FOR_GAP.get(gap.gap_type, "unknown")
  aid = _action_id(gap.case_id, gap.gap_id, action_type)
  gap.next_action_id = aid

  titles = {
    "load_claim_text": "対象特許の claim 本文を取得する",
    "check_patent_examples": "特許 description / examples の実施例を確認する",
    "check_paper_source": "該当技術軸に関する論文 Evidence を確認する",
    "check_property_data": "物性データの一次 source を確認する",
    "check_process_conditions": "プロセス条件の一次 source を確認する",
    "check_company_primary_source": "Web/company signal の一次情報を確認する",
    "needs_primary_source_review": "source URL または一次資料を補完する",
    "expand_paper_search": "論文検索範囲を広げる",
  }
  outputs = {
    "load_claim_text": "claims_input.csv に claim_text を追加",
    "check_patent_examples": "実施例条件・物性値・比較例の有無を記録",
    "check_paper_source": "paper source を Sources 一覧へ追加",
    "check_property_data": "物性データ source を Sources 一覧へ追加",
    "check_process_conditions": "プロセス条件 source を Sources 一覧へ追加",
    "check_company_primary_source": "企業ページ・製品資料の出典確認",
    "needs_primary_source_review": "URL または artifact path を Sources 一覧に追加",
    "expand_paper_search": "paper search keywords を Watch Profile に追加",
  }
  effort = {
    "load_claim_text": "medium",
    "check_patent_examples": "deep",
    "check_paper_source": "medium",
    "check_company_primary_source": "quick",
    "needs_primary_source_review": "quick",
  }

  return V8NextVerificationAction(
    action_id=aid,
    case_id=gap.case_id,
    action_rank=rank,
    action_type=action_type,
    action_title=titles.get(action_type, gap.gap_title),
    action_description=gap.gap_description,
    target_publication_number=gap.publication_number,
    target_claim_no=gap.claim_no,
    target_source_id=gap.related_source_ids[0] if gap.related_source_ids else "",
    target_source_title=gap.related_source_titles[0] if gap.related_source_titles else "",
    expected_output=outputs.get(action_type, "人手確認結果を記録"),
    estimated_effort_label=effort.get(action_type, "unknown"),
    priority_reason=f"gap_type={gap.gap_type}; severity={gap.severity_label}; urgency={gap.urgency_label}",
    owner_suggestion="researcher" if action_type == "load_claim_text" else "engineer",
    next_step_command_hint=f"cases/{gap.case_id}/claims_input.csv を更新",
    watch_profile_update_hint=_watch_hint_for_gap(gap.gap_type),
    scheduler_followup_hint="次回 Scheduler 定点観測で Gap 再確認",
    email_digest_hint=f"Digest: {gap.gap_title} — {gap.publication_number} claim {gap.claim_no}",
    caution_flags=[
      "next_action_human_verification_task",
      "not_legal_judgement",
      "gap_not_invalidity_conclusion",
    ],
    human_review_required=True,
  )


def _watch_hint_for_gap(gap_type: str) -> str:
  hints = {
    "claim_text_required": "次回タスクに claim 本文取得を追加",
    "paper_support_missing": "paper search keywords を Watch Profile に追加",
    "web_or_company_only": "company source verification を次回タスクに追加",
    "source_url_missing": "source URL 補完を次回タスクに追加",
    "example_support_missing": "特許実施例確認を重点軸に追加",
  }
  return hints.get(gap_type, "technical_axis の重点化を検討")


def _build_watch_profile_proposal(gaps: list[V8EvidenceGapRecord], *, case_id: str) -> str:
  lines = [f"# Watch Profile Update Proposal — {case_id}", ""]
  by_type = _count_by(gaps, "gap_type")
  if by_type.get("claim_text_required", 0) > 0:
    lines.append("- 次回タスク: 対象特許の claim 本文取得（claims_input.csv 更新）")
  if by_type.get("paper_support_missing", 0) > 0:
    lines.append("- paper search keywords を Watch Profile に追加（論文検索範囲拡大）")
  if by_type.get("web_or_company_only", 0) > 0:
    lines.append("- company source verification を次回定点観測タスクに追加")
  if by_type.get("source_url_missing", 0) > 0:
    lines.append("- source URL 補完を Sources 一覧更新タスクに追加")
  axes: dict[str, int] = defaultdict(int)
  for g in gaps:
    for ax in g.technical_axis_labels:
      axes[ax] += 1
  if axes:
    top_axis = max(axes, key=axes.get)  # type: ignore[arg-type]
    lines.append(f"- 重点 technical_axis: {top_axis}")
  lines.append("- ノイズ source_type が多い場合は除外キーワード縮小候補を検討")
  lines.append("")
  lines.append("※ 人手承認後に Watch Profile へ反映。本 Phase では自動更新しません。")
  return "\n".join(lines)


def _build_digest_summary(
  report: V8GapNextActionsReport,
  top_actions: list[V8NextVerificationAction],
) -> str:
  lines = [
    f"# Digest Summary — {report.case_id}",
    "",
    f"- 未確認 Gap 数: {report.gap_count}",
    f"- Next Actions 数: {report.action_count}",
    "",
    "## Top 3 Next Actions",
  ]
  for action in top_actions[:3]:
    lines.append(f"{action.action_rank}. {action.action_title} ({action.target_publication_number})")
  lines.extend([
    "",
    "## 次回定点観測で追う軸",
    f"- claim_text_required: {report.count_by_gap_type.get('claim_text_required', 0)}",
    f"- paper_support_missing: {report.count_by_gap_type.get('paper_support_missing', 0)}",
    "",
    "## メール Digest 用短文（送信はしません）",
    f"Evidence Gap {report.gap_count}件。優先: "
    + (top_actions[0].action_title if top_actions else "（なし）"),
    "",
    "Web Signal / company source は candidate information only。",
  ])
  return "\n".join(lines)


def _collect_artifact_paths(case_id: str, root: Any) -> tuple[list[str], list[str]]:
  paths: list[str] = []
  ev_paths: list[str] = []
  ev_dir = find_latest_evidence_map_dir(case_id, root)
  if ev_dir and ev_dir.exists():
    paths.append(str(ev_dir))
    ev_paths.append(str(ev_dir))
  claim_dir = find_latest_claim_map_dir(case_id, root)
  if claim_dir and claim_dir.exists():
    paths.append(str(claim_dir))
  shortlist_dir = find_latest_patent_shortlist_dir(case_id, root)
  if shortlist_dir and shortlist_dir.exists():
    paths.append(str(shortlist_dir))
  return paths, ev_paths


def build_gap_next_actions_report(
  *,
  case_id: str,
  publication_number: str | None = None,
  project_root: Any = None,
  evidence_map: V8EvidenceMap | None = None,
) -> V8GapNextActionsReport:
  root = project_root or project_root_from_here()
  profile = load_case_profile(case_id, root) or {}
  del profile

  warnings: list[str] = list(GAP_NEXT_ACTIONS_SAFETY_NOTICES[:2])
  artifact_paths, ev_paths = _collect_artifact_paths(case_id, root)

  if evidence_map is None:
    evidence_map = build_evidence_map(
      case_id=case_id,
      publication_number=publication_number,
      project_root=root,
    )

  pub_filter = (publication_number or "").strip()
  links = evidence_map.links
  if pub_filter:
    links = [l for l in links if l.publication_number == pub_filter]

  seen_gap_keys: set[tuple[str, str]] = set()
  gaps: list[V8EvidenceGapRecord] = []

  for link in links:
    if not _is_gap_link(link):
      continue
    gap_type = _classify_gap_from_link(link)
    key = (link.claim_id, gap_type)
    if key in seen_gap_keys:
      continue
    seen_gap_keys.add(key)
    gaps.append(_build_gap(link, gap_type, case_id=case_id))

  gaps.sort(key=lambda g: -GAP_TYPE_PRIORITY.get(g.gap_type, 0))

  actions: list[V8NextVerificationAction] = []
  for rank, gap in enumerate(gaps, start=1):
    actions.append(_build_action_from_gap(gap, rank=rank))

  actions.sort(
    key=lambda a: -GAP_TYPE_PRIORITY.get(
      next((g.gap_type for g in gaps if g.next_action_id == a.action_id), "unknown"),
      0,
    ),
  )
  for i, action in enumerate(actions, start=1):
    action.action_rank = i

  top_3 = actions[:3]
  primary_pub = pub_filter or evidence_map.publication_number or "all"

  report = V8GapNextActionsReport(
    report_id=_report_id(case_id, primary_pub),
    case_id=case_id,
    publication_number=primary_pub,
    generated_at=utc_now_iso(),
    gaps=gaps,
    next_actions=actions,
    top_3_actions=top_3,
    gap_count=len(gaps),
    action_count=len(actions),
    count_by_gap_type=_count_by(gaps, "gap_type"),
    count_by_action_type=_count_by(actions, "action_type"),
    count_by_urgency=_count_by(gaps, "urgency_label"),
    source_artifact_paths=artifact_paths,
    evidence_map_artifact_paths=ev_paths,
    watch_profile_update_proposal=_build_watch_profile_proposal(gaps, case_id=case_id),
    digest_summary="",
    warnings=warnings,
    candidate_information_only=True,
    human_review_required=True,
    no_legal_judgement=True,
  )
  report.digest_summary = _build_digest_summary(report, top_3)
  return report
