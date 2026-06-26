"""v8 Demo Polish service (Phase 27L)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from tech_cartography.runtime.v8_demo_polish_schema import (
  DEMO_POLISH_SAFETY_NOTICES,
  V8DemoPolishReport,
  V8DemoStoryCard,
  V8EvidenceDemoStatus,
  V8GapDemoStatus,
)
from tech_cartography.runtime.v8_sources_schema import utc_now_iso
from tech_cartography.services.v8_claim_input_loader import load_claims_input_csv
from tech_cartography.services.v8_claim_map_export import find_latest_claim_map_dir
from tech_cartography.services.v8_evidence_map import build_evidence_map
from tech_cartography.services.v8_evidence_map_export import find_latest_evidence_map_dir
from tech_cartography.services.v8_fixed_point_observation import build_observation_loop_report
from tech_cartography.services.v8_fixed_point_observation_export import find_latest_fixed_point_observation_dir
from tech_cartography.services.v8_gap_next_actions import build_gap_next_actions_report
from tech_cartography.services.v8_gap_next_actions_export import find_latest_gap_next_actions_dir
from tech_cartography.services.v8_large_candidate_shortlist import (
  find_latest_large_manifest,
  find_latest_large_shortlist_dir,
  load_top5_publications,
)
from tech_cartography.services.v8_manual_claim_refresh_export import find_latest_manual_claim_refresh_dir
from tech_cartography.services.v8_patent_shortlist import build_patent_shortlist
from tech_cartography.services.v8_patent_shortlist_export import find_latest_patent_shortlist_dir
from tech_cartography.services.v8_sources_table import project_root_from_here

LOADED_CLAIM_STATUSES = frozenset({"manual_input", "loaded", "csv_imported", "artifact_imported"})


def _report_id(case_id: str) -> str:
  digest = hashlib.sha256(f"{case_id}|demo_polish".encode()).hexdigest()[:12]
  return f"{case_id}:demo_polish:{digest}"


def _status_id(case_id: str, suffix: str) -> str:
  digest = hashlib.sha256(f"{case_id}|{suffix}".encode()).hexdigest()[:12]
  return f"{case_id}:demo_status:{suffix}:{digest}"


def _card_id(case_id: str, card_type: str) -> str:
  digest = hashlib.sha256(f"{case_id}|{card_type}".encode()).hexdigest()[:12]
  return f"{case_id}:story:{card_type}:{digest}"


def _resolve_claim_text_status(links: list, claim_rows: list) -> str:
  statuses = {getattr(l, "claim_text_status", "unknown") for l in links}
  loaded_rows = sum(1 for r in claim_rows if r.has_loaded_text())
  not_loaded_rows = sum(1 for r in claim_rows if not r.has_loaded_text())
  if not statuses and not claim_rows:
    return "unknown"
  if statuses <= {"not_loaded"} and loaded_rows == 0:
    return "not_loaded"
  if statuses <= LOADED_CLAIM_STATUSES and not_loaded_rows == 0:
    return "manual_input" if "manual_input" in statuses else "loaded"
  if loaded_rows > 0 and not_loaded_rows > 0:
    return "mixed"
  if "manual_input" in statuses:
    return "manual_input"
  if "loaded" in statuses or loaded_rows > 0:
    return "loaded"
  return "unknown"


def _large_candidate_summary(case_id: str, root: Path) -> tuple[str, list[str]]:
  trace: list[str] = []
  manifest_path = find_latest_large_manifest(case_id, root)
  shortlist_dir = find_latest_large_shortlist_dir(case_id, root)
  top5 = load_top5_publications(case_id, root)
  population = 0
  top100 = top20 = 0
  if manifest_path and manifest_path.exists():
    trace.append(str(manifest_path))
    try:
      meta = json.loads(manifest_path.read_text(encoding="utf-8"))
      population = int(meta.get("population_count") or meta.get("deduped_count") or 0)
      top100 = int(meta.get("top100_count") or 0)
      top20 = int(meta.get("top20_count") or 0)
    except (json.JSONDecodeError, TypeError, ValueError):
      pass
  if shortlist_dir:
    trace.append(str(shortlist_dir))
  summary = (
    f"Large Candidate: population≈{population or '—'} → Top100={top100 or '—'} → "
    f"Top20={top20 or '—'} → Top5={len(top5)}"
  )
  if top5:
    summary += f" ({', '.join(top5[:5])})"
  return summary, trace


def _build_evidence_demo_status(
  *,
  case_id: str,
  publication_number: str,
  patent_title: str,
  root: Path,
) -> V8EvidenceDemoStatus:
  evidence_map = build_evidence_map(
    case_id=case_id,
    publication_number=publication_number or None,
    project_root=root,
    include_unloaded_claim_gaps=True,
  )
  claim_rows, _ = load_claims_input_csv(case_id, project_root=root)
  links = evidence_map.links

  manual_count = sum(1 for l in links if l.claim_text_status in LOADED_CLAIM_STATUSES)
  paper_count = sum(
    1 for l in links
    if l.support_type == "paper_support_candidate" or l.source_type == "paper"
  )
  web_count = sum(
    1 for l in links
    if l.support_type == "web_signal_candidate" or l.source_type == "web"
  )
  company_count = sum(
    1 for l in links
    if l.support_type == "company_signal_candidate" or l.source_type == "company"
  )
  patent_count = sum(1 for l in links if l.source_type == "patent")
  review_count = sum(1 for l in links if l.human_review_required)

  strongest = ""
  candidates = [
    l for l in links
    if l.support_type not in {"claim_text_required", "missing_evidence", "unknown"}
    and l.source_title
  ]
  if candidates:
    best = max(candidates, key=lambda l: len(l.matched_terms))
    strongest = (
      f"{best.support_type} / {best.source_type}: {best.source_title[:60]} "
      f"(candidate, not proof)"
    )

  weakest = ""
  if evidence_map.claim_text_required_count > 0:
    weakest = f"claim_text_required={evidence_map.claim_text_required_count} — claim 本文未投入"
  elif evidence_map.missing_evidence_count > 0:
    weakest = f"missing_evidence={evidence_map.missing_evidence_count}"

  next_verify = ""
  if evidence_map.next_actions:
    next_verify = "; ".join(evidence_map.next_actions[:3])
  elif evidence_map.claim_text_required_count > 0:
    next_verify = "claim 本文を一次情報から投入"
  else:
    next_verify = "実施例 / paper / 一次情報を人手確認"

  claim_status = _resolve_claim_text_status(links, claim_rows)
  warnings: list[str] = []
  if claim_status == "not_loaded":
    warnings.append("claim 本文未投入 — Evidence Map は claim_text_required 中心")
  if manual_count > 0:
    warnings.append("manual_input claim あり — candidate 扱いは変わらない")

  return V8EvidenceDemoStatus(
    status_id=_status_id(case_id, "evidence"),
    case_id=case_id,
    publication_number=publication_number,
    patent_title=patent_title,
    claim_text_status=claim_status,
    claim_text_required_count=evidence_map.claim_text_required_count,
    manual_claim_count=manual_count,
    evidence_link_count=evidence_map.link_count,
    paper_candidate_count=paper_count,
    web_candidate_count=web_count,
    company_candidate_count=company_count,
    patent_candidate_count=patent_count,
    missing_evidence_count=evidence_map.missing_evidence_count,
    needs_human_review_count=review_count,
    strongest_candidate_summary=strongest or "（候補なし — claim 投入後に再確認）",
    weakest_point_summary=weakest or "（大きな gap なし — 人手確認は継続）",
    next_verification_summary=next_verify,
    warnings=warnings,
  )


def _build_gap_demo_status(
  *,
  case_id: str,
  publication_number: str,
  evidence_status: V8EvidenceDemoStatus,
  root: Path,
) -> V8GapDemoStatus:
  gap_report = build_gap_next_actions_report(
    case_id=case_id,
    publication_number=publication_number or None,
    project_root=root,
  )
  counts = gap_report.count_by_gap_type
  top_types = sorted(counts.keys(), key=lambda k: -counts[k])[:5]
  top_actions = [a.action_title for a in gap_report.top_3_actions[:3]]

  before_after = ""
  if evidence_status.claim_text_status == "not_loaded":
    before_after = "before: claim本文取得 → after: 実施例確認 / paper確認（claim投入後）"
  elif evidence_status.claim_text_status in {"manual_input", "loaded", "mixed"}:
    before_after = (
      "claim本文投入済み — 次は実施例確認 / paper evidence確認 / 一次情報確認"
    )

  return V8GapDemoStatus(
    status_id=_status_id(case_id, "gap"),
    case_id=case_id,
    publication_number=publication_number,
    gap_count=gap_report.gap_count,
    top_gap_types=top_types,
    top_3_next_actions=top_actions,
    claim_text_gap_count=counts.get("claim_text_required", 0),
    example_support_gap_count=counts.get("example_support_missing", 0),
    paper_support_gap_count=counts.get("paper_support_missing", 0),
    source_url_gap_count=counts.get("source_url_missing", 0),
    web_company_only_gap_count=counts.get("web_or_company_only", 0),
    before_after_summary=before_after,
    next_human_action_summary="; ".join(top_actions) if top_actions else "Gap を人手確認",
  )


def _build_story_cards(
  *,
  case_id: str,
  large_summary: str,
  evidence: V8EvidenceDemoStatus,
  gap: V8GapDemoStatus,
  obs_summary: str,
) -> list[V8DemoStoryCard]:
  return [
    V8DemoStoryCard(
      card_id=_card_id(case_id, "population_to_top5"),
      case_id=case_id,
      card_title="1000件母集団 → Top5 深掘り",
      card_subtitle="Large Candidate staged shortlist",
      card_type="population_to_top5",
      key_message="1000件規模の候補母集団から Top100 → Top20 → Top5 を選抜し、Top5 のみ Deep Dive します。",
      supporting_metrics={"top5_focus": "Deep Dive only Top5"},
      action_hint=large_summary,
      display_priority=1,
    ),
    V8DemoStoryCard(
      card_id=_card_id(case_id, "claim_status"),
      case_id=case_id,
      card_title="Claim 本文ステータス",
      card_subtitle=f"status={evidence.claim_text_status}",
      card_type="claim_status",
      key_message=(
        "claim 本文未投入は claim_text_required。"
        " 手動投入済みは Claim Map / Evidence Map が具体化します（candidate のみ）。"
      ),
      supporting_metrics={
        "claim_text_required_count": evidence.claim_text_required_count,
        "manual_claim_count": evidence.manual_claim_count,
      },
      action_hint="Claim Map タブで一次情報から claim 本文を投入",
      display_priority=2,
    ),
    V8DemoStoryCard(
      card_id=_card_id(case_id, "evidence_candidates"),
      case_id=case_id,
      card_title="Supporting Evidence Candidate",
      card_subtitle="Evidence Map is not proof",
      card_type="evidence_candidates",
      key_message="paper / web / company は裏付け候補であり、証明ではありません。",
      supporting_metrics={
        "paper_candidate_count": evidence.paper_candidate_count,
        "web_candidate_count": evidence.web_candidate_count,
        "company_candidate_count": evidence.company_candidate_count,
        "evidence_link_count": evidence.evidence_link_count,
      },
      caution_text="実施例本文・論文本文を読んだことにはしません。",
      display_priority=3,
    ),
    V8DemoStoryCard(
      card_id=_card_id(case_id, "evidence_gaps"),
      case_id=case_id,
      card_title="Evidence Gaps",
      card_subtitle="Gap is not invalidity / weakness",
      card_type="evidence_gaps",
      key_message="Gap は未確認事項であり、特許の弱点・無効性・侵害可能性ではありません。",
      supporting_metrics={
        "gap_count": gap.gap_count,
        "claim_text_gap_count": gap.claim_text_gap_count,
        "missing_evidence_count": evidence.missing_evidence_count,
      },
      action_hint=gap.before_after_summary,
      display_priority=4,
    ),
    V8DemoStoryCard(
      card_id=_card_id(case_id, "next_actions"),
      case_id=case_id,
      card_title="Top 3 Next Actions",
      card_subtitle="人間の確認作業",
      card_type="next_actions",
      key_message="Next Action は法的判断ではなく、人間が次に確認する技術調査タスクです。",
      supporting_metrics={"action_count": len(gap.top_3_next_actions)},
      action_hint="; ".join(gap.top_3_next_actions[:3]),
      display_priority=5,
    ),
    V8DemoStoryCard(
      card_id=_card_id(case_id, "observation_loop"),
      case_id=case_id,
      card_title="定点観測ループ",
      card_subtitle="no_email_send / no_scheduler_start",
      card_type="observation_loop",
      key_message=obs_summary,
      action_hint="Watch Profile 更新案 → Scheduler plan → Email Digest plan（本 Phase では実行しない）",
      display_priority=6,
    ),
    V8DemoStoryCard(
      card_id=_card_id(case_id, "caveat"),
      case_id=case_id,
      card_title="注意事項",
      card_type="caveat",
      key_message="candidate information only / human review required",
      caution_text="; ".join(DEMO_POLISH_SAFETY_NOTICES[:4]),
      display_priority=99,
    ),
  ]


def _demo_narrative(
  *,
  case_id: str,
  large_summary: str,
  evidence: V8EvidenceDemoStatus,
  gap: V8GapDemoStatus,
) -> str:
  lines = [
    f"## Demo Narrative — {case_id}",
    "",
    f"- {large_summary}",
    "- この案件では、1000件規模の候補母集団から Top5 を選抜しました。",
    f"- Top5 の claim ステータス: {evidence.claim_text_status}。"
    f" claim_text_required={evidence.claim_text_required_count}。",
    "- claim 本文が手動投入された場合、Claim Map と Evidence Map はより具体的になります。",
    "- ただし、paper / web / company は裏付け候補であり、証明ではありません（Evidence Map is not proof）。",
    f"- Gap={gap.gap_count} — Gap is not invalidity / weakness。",
    "- 次に人間が確認すべきこと: claim 本文、特許実施例、論文 Evidence、一次情報。",
    "- 実施例本文・論文本文を読んだことにはしません。",
  ]
  return "\n".join(lines)


def _collect_artifact_trace(case_id: str, root: Path, extra: list[str]) -> list[str]:
  trace: list[str] = list(extra)
  for finder, _label in (
    (find_latest_large_shortlist_dir, "large"),
    (find_latest_patent_shortlist_dir, "shortlist"),
    (find_latest_claim_map_dir, "claim_map"),
    (find_latest_evidence_map_dir, "evidence_map"),
    (find_latest_gap_next_actions_dir, "gap"),
    (find_latest_fixed_point_observation_dir, "observation"),
    (find_latest_manual_claim_refresh_dir, "manual_refresh"),
  ):
    try:
      if finder is find_latest_manual_claim_refresh_dir:
        path = finder(root)
      else:
        path = finder(case_id, root)
    except TypeError:
      path = finder(root)
    if path:
      trace.append(str(path))
  return list(dict.fromkeys(trace))


def build_demo_polish_report(
  *,
  case_id: str,
  publication_number: str | None = None,
  project_root: Path | str | None = None,
) -> V8DemoPolishReport:
  """Summarize Evidence Map / Gap / observation loop for demo presentation. No external API calls."""
  root = Path(project_root or project_root_from_here())
  pub = (publication_number or "").strip()
  top5 = load_top5_publications(case_id, root)
  if not pub and top5:
    pub = top5[0]

  shortlist = build_patent_shortlist(case_id=case_id, top_n=5, project_root=root)
  patent_title = ""
  if pub:
    for candidate in shortlist.patent_candidates:
      if candidate.publication_number == pub:
        patent_title = candidate.title
        break

  large_summary, large_trace = _large_candidate_summary(case_id, root)
  shortlist_summary = (
    f"Patent Shortlist Top5: {shortlist.count} candidates / "
    f"deep_dive={', '.join(top5[:5]) if top5 else '—'}"
  )

  evidence_status = _build_evidence_demo_status(
    case_id=case_id,
    publication_number=pub,
    patent_title=patent_title,
    root=root,
  )
  gap_status = _build_gap_demo_status(
    case_id=case_id,
    publication_number=pub,
    evidence_status=evidence_status,
    root=root,
  )

  obs_report = build_observation_loop_report(
    case_id=case_id,
    publication_number=pub or None,
    project_root=root,
  )
  obs_summary = (
    f"loop_status={obs_report.loop_status}; "
    f"tasks={len(obs_report.top_3_next_cycle_tasks)}; "
    f"no_email_send={obs_report.no_email_send}; "
    f"no_scheduler_start={obs_report.no_scheduler_start}"
  )

  story_cards = _build_story_cards(
    case_id=case_id,
    large_summary=large_summary,
    evidence=evidence_status,
    gap=gap_status,
    obs_summary=obs_summary,
  )
  narrative = _demo_narrative(
    case_id=case_id,
    large_summary=large_summary,
    evidence=evidence_status,
    gap=gap_status,
  )

  before_after = gap_status.before_after_summary
  if evidence_status.manual_claim_count > 0 and evidence_status.claim_text_required_count == 0:
    before_after = "claim 投入後: claim_text_required 解消 → 実施例 / paper 確認へ"

  remaining: list[str] = []
  if evidence_status.claim_text_required_count > 0:
    remaining.append(f"claim_text_required: {evidence_status.claim_text_required_count}")
  if evidence_status.missing_evidence_count > 0:
    remaining.append(f"missing_evidence: {evidence_status.missing_evidence_count}")
  if gap_status.gap_count > 0:
    remaining.append(f"gaps: {gap_status.gap_count}")
  if not remaining:
    remaining.append("人手確認は継続 — candidate は proof ではない")

  recommended_steps = [
    "入力タブで 1000件候補 CSV を取り込む",
    "Sources一覧で母集団を確認",
    "読むべき特許で Top100 → Top20 → Top5 を確認",
    "Claim Map で claim 本文状態を確認・必要なら手動投入",
    "Evidence Map で supporting evidence candidate を確認",
    "Gap / Next Actions で未確認事項と Top 3 Actions を確認",
    "定点観測で次回タスクと Digest 計画を確認",
    "Export で Demo Polish Pack を出力",
  ]

  artifact_trace = _collect_artifact_trace(case_id, root, large_trace)
  warnings = list(DEMO_POLISH_SAFETY_NOTICES[:3])

  return V8DemoPolishReport(
    report_id=_report_id(case_id),
    case_id=case_id,
    publication_number=pub,
    generated_at=utc_now_iso(),
    large_candidate_summary=large_summary,
    patent_shortlist_summary=shortlist_summary,
    evidence_demo_status=evidence_status,
    gap_demo_status=gap_status,
    story_cards=sorted(story_cards, key=lambda c: c.display_priority),
    demo_narrative=narrative,
    before_after_claim_status=before_after,
    recommended_demo_steps=recommended_steps,
    remaining_limitations=remaining,
    artifact_trace=artifact_trace,
    candidate_information_only=True,
    human_review_required=True,
    supporting_evidence_candidate_only=True,
    evidence_map_not_proof=True,
    gap_is_not_invalidity=True,
    no_legal_judgement=True,
    no_email_send=True,
    no_scheduler_start=True,
    warnings=warnings,
  )
