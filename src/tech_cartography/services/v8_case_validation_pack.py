"""v8 Three Case Validation pack builder (Phase 27I)."""

from __future__ import annotations

import csv
import hashlib
import re
from collections import Counter
from pathlib import Path
from typing import Any

from tech_cartography.runtime.v8_case_validation_schema import (
  VALIDATION_SAFETY_NOTICES,
  VALIDATION_STEP_IDS,
  V8CaseValidationReport,
  V8CaseValidationStepResult,
  V8ThreeCaseValidationPack,
)
from tech_cartography.runtime.v8_sources_schema import utc_now_iso
from tech_cartography.services.v8_claim_map import build_claim_map
from tech_cartography.services.v8_claim_map_export import export_claim_map, find_latest_claim_map_dir
from tech_cartography.services.v8_evidence_map import build_evidence_map
from tech_cartography.services.v8_evidence_map_export import export_evidence_map, find_latest_evidence_map_dir
from tech_cartography.services.v8_fixed_point_observation import build_observation_loop_report
from tech_cartography.services.v8_fixed_point_observation_export import (
  export_observation_loop,
  find_latest_fixed_point_observation_dir,
)
from tech_cartography.services.v8_gap_next_actions import build_gap_next_actions_report
from tech_cartography.services.v8_gap_next_actions_export import export_gap_next_actions, find_latest_gap_next_actions_dir
from tech_cartography.services.v8_patent_shortlist import build_patent_shortlist
from tech_cartography.services.v8_patent_shortlist_export import export_patent_shortlist, find_latest_patent_shortlist_dir
from tech_cartography.services.v8_sources_repository import load_sources_table
from tech_cartography.services.v8_sources_table import load_case_profile, project_root_from_here
from tech_cartography.ui.v8_tab_config import V8_CASE_SAMPLES

CASE_IDS: tuple[str, ...] = tuple(s["case_id"] for s in V8_CASE_SAMPLES)

CSV_COLUMNS: tuple[str, ...] = (
  "type", "title", "organization", "year", "url", "publication_number",
  "source_status", "evidence_role", "case_id", "notes",
)

CLAIMS_COLUMNS: tuple[str, ...] = (
  "case_id", "publication_number", "patent_title", "claim_no", "claim_text",
  "claim_source_type", "claim_source_url", "claim_source_path", "notes",
)

FAKE_URL_RE = re.compile(
  r"10\.(0000|1234)/|example\.com|fake-doi|placeholder",
  re.IGNORECASE,
)

STEP_NAMES: dict[str, str] = {
  "sources": "Sources一覧",
  "patent_shortlist": "読むべき特許 Top N",
  "claim_map": "Claim Map",
  "evidence_map": "Evidence Map",
  "gap_next_actions": "Gap / Next Actions",
  "fixed_point_observation": "定点観測ループ",
  "export": "Export",
}


def _report_id(case_id: str) -> str:
  digest = hashlib.sha256(f"{case_id}|validation".encode()).hexdigest()[:12]
  return f"{case_id}:validation:{digest}"


def _pack_id() -> str:
  digest = hashlib.sha256(f"three_case|{utc_now_iso()}".encode()).hexdigest()[:12]
  return f"v8_three_case_validation:{digest}"


def _step(case_id: str, step_id: str, **kwargs: Any) -> V8CaseValidationStepResult:
  return V8CaseValidationStepResult(
    step_id=step_id,
    case_id=case_id,
    step_name=STEP_NAMES.get(step_id, step_id),
    **kwargs,
  )


def ensure_case_artifacts(case_id: str, *, project_root: Path | str) -> list[str]:
  """Generate local v8 artifacts if missing. No external API calls."""
  root = Path(project_root)
  generated: list[str] = []

  shortlist_dir = find_latest_patent_shortlist_dir(case_id, root)
  if not shortlist_dir:
    shortlist = build_patent_shortlist(case_id=case_id, top_n=5, project_root=root)
    exp = export_patent_shortlist(shortlist, project_root=root)
    generated.append(exp.output_dir)

  claim_dir = find_latest_claim_map_dir(case_id, root)
  if not claim_dir:
    claim_map = build_claim_map(case_id=case_id, project_root=root)
    exp = export_claim_map(claim_map, project_root=root)
    generated.append(exp.output_dir)

  ev_dir = find_latest_evidence_map_dir(case_id, root)
  if not ev_dir:
    emap = build_evidence_map(case_id=case_id, project_root=root)
    exp = export_evidence_map(emap, project_root=root)
    generated.append(exp.output_dir)

  gap_dir = find_latest_gap_next_actions_dir(case_id, root)
  if not gap_dir:
    gap_report = build_gap_next_actions_report(case_id=case_id, project_root=root)
    exp = export_gap_next_actions(gap_report, project_root=root)
    generated.append(exp.output_dir)

  fp_dir = find_latest_fixed_point_observation_dir(case_id, root)
  if not fp_dir:
    obs = build_observation_loop_report(case_id=case_id, project_root=root)
    exp = export_observation_loop(obs, project_root=root)
    generated.append(exp.output_dir)

  return generated


def _validate_sources(case_id: str, root: Path) -> V8CaseValidationStepResult:
  warnings: list[str] = []
  blocking: list[str] = []
  paths: list[str] = []
  counts: dict[str, int] = {}

  csv_path = root / "cases" / case_id / "source_candidates.csv"
  if not csv_path.exists():
    return _step(case_id, "sources", status="fail", summary="source_candidates.csv missing",
                   blocking_issues=["source_candidates.csv が存在しません"],
                   next_fix_hint="cases/<case_id>/source_candidates.csv を用意してください")

  paths.append(str(csv_path))
  with csv_path.open(encoding="utf-8", newline="") as handle:
    reader = csv.DictReader(handle)
    fieldnames = reader.fieldnames or []
    rows = list(reader)

  missing_cols = [c for c in CSV_COLUMNS if c not in fieldnames]
  if missing_cols:
    blocking.append(f"不足カラム: {', '.join(missing_cols)}")

  patent_rows = [r for r in rows if str(r.get("type") or "").lower() == "patent"]
  counts["source_total"] = len(rows)
  counts["patent_count"] = len(patent_rows)

  if len(patent_rows) < 5:
    blocking.append(f"patent source が {len(patent_rows)} 件（5件以上必要）")

  for row in rows:
    url = str(row.get("url") or "")
    if FAKE_URL_RE.search(url):
      blocking.append(f"fake-like URL: {url[:60]}")

  table = load_sources_table(case_id=case_id, project_root=root)
  counts["unified_sources"] = len(table.records)

  status = "fail" if blocking else ("warning" if warnings else "pass")
  return _step(
    case_id, "sources",
    status=status,
    summary=f"patent {len(patent_rows)}件 / unified {len(table.records)}件",
    required_output_exists=True,
    artifact_paths=paths,
    key_counts=counts,
    warnings=warnings + ["candidate_information_only — Web/company は候補扱い"],
    blocking_issues=blocking,
    next_fix_hint="source_candidates.csv に patent 5件以上を追加" if blocking else "",
  )


def _validate_patent_shortlist(case_id: str, root: Path) -> V8CaseValidationStepResult:
  blocking: list[str] = []
  warnings: list[str] = []
  paths: list[str] = []
  counts: dict[str, int] = {}

  shortlist = build_patent_shortlist(case_id=case_id, top_n=5, project_root=root)
  counts["shortlist_count"] = shortlist.count

  if shortlist.count < 3:
    blocking.append(f"Top N が {shortlist.count} 件（3件以上必要）")

  empty_why = [c for c in shortlist.patent_candidates if not c.why_read.strip()]
  if empty_why:
    warnings.append(f"why_read 空欄: {len(empty_why)} 件")

  empty_next = [c for c in shortlist.patent_candidates if not c.next_verification_action.strip()]
  if empty_next:
    warnings.append(f"next_verification_action 空欄: {len(empty_next)} 件")

  latest = find_latest_patent_shortlist_dir(case_id, root)
  if latest:
    paths.append(str(latest))

  status = "fail" if blocking else ("warning" if warnings else "pass")
  return _step(
    case_id, "patent_shortlist",
    status=status,
    summary=f"Top {shortlist.count} 候補（heuristic 読む優先度、法的判断ではない）",
    required_output_exists=shortlist.count >= 1,
    artifact_paths=paths,
    key_counts=counts,
    warnings=warnings,
    blocking_issues=blocking,
  )


def _validate_claim_map(case_id: str, root: Path) -> V8CaseValidationStepResult:
  blocking: list[str] = []
  warnings: list[str] = []
  paths: list[str] = []
  counts: dict[str, int] = {}

  claims_path = root / "cases" / case_id / "claims_input.csv"
  loaded: list[dict[str, str]] = []
  if not claims_path.exists():
    blocking.append("claims_input.csv がありません")
  else:
    paths.append(str(claims_path))
    with claims_path.open(encoding="utf-8", newline="") as handle:
      reader = csv.DictReader(handle)
      claim_rows = list(reader)
    counts["claims_input_rows"] = len(claim_rows)
    missing_cols = [c for c in CLAIMS_COLUMNS if c not in (reader.fieldnames or [])]
    if missing_cols:
      blocking.append(f"claims_input 不足カラム: {', '.join(missing_cols)}")
    loaded = [r for r in claim_rows if str(r.get("claim_text") or "").strip()]
    counts["claim_text_loaded"] = len(loaded)
    if not loaded:
      warnings.append("claim_text が全件空欄 — claim_text_status=not_loaded（正しい挙動）")

  claim_map = build_claim_map(case_id=case_id, project_root=root)
  counts["claim_map_count"] = claim_map.claim_count
  counts["not_loaded_count"] = claim_map.not_loaded_claim_count

  if claim_map.claim_count < 1:
    blocking.append("Claim Map が空です")

  if claim_map.not_loaded_claim_count > 0 and not loaded:
    warnings.append("架空 claim を生成していない — not_loaded として扱う")

  latest = find_latest_claim_map_dir(case_id, root)
  if latest:
    paths.append(str(latest))

  status = "fail" if blocking else "warning"
  return _step(
    case_id, "claim_map",
    status=status,
    summary=f"{claim_map.claim_count} claims / not_loaded {claim_map.not_loaded_claim_count}",
    required_output_exists=claim_map.claim_count >= 1,
    artifact_paths=paths,
    key_counts=counts,
    warnings=warnings,
    blocking_issues=blocking,
    next_fix_hint="claims_input.csv に claim 本文を人手追加" if claim_map.not_loaded_claim_count else "",
  )


def _validate_evidence_map(case_id: str, root: Path) -> V8CaseValidationStepResult:
  blocking: list[str] = []
  warnings: list[str] = []
  paths: list[str] = []

  emap = build_evidence_map(case_id=case_id, project_root=root)
  counts = {
    "link_count": emap.link_count,
    "claim_text_required_count": emap.claim_text_required_count,
    "missing_evidence_count": emap.missing_evidence_count,
  }

  if emap.link_count < 1:
    blocking.append("Evidence Map links が空")

  if emap.claim_text_required_count >= 1:
    warnings.append(f"claim_text_required: {emap.claim_text_required_count}（未確認扱い）")

  weak = [l for l in emap.links if l.source_type in {"web", "company"}]
  if weak:
    warnings.append(f"web/company candidate: {len(weak)} links")

  latest = find_latest_evidence_map_dir(case_id, root)
  if latest:
    paths.append(str(latest))

  status = "fail" if blocking else "warning"
  return _step(
    case_id, "evidence_map",
    status=status,
    summary=f"{emap.link_count} links — supporting evidence candidate（not proof）",
    required_output_exists=emap.link_count >= 1,
    artifact_paths=paths,
    key_counts=counts,
    warnings=warnings + ["Evidence Map is not proof"],
    blocking_issues=blocking,
  )


def _validate_gap_next_actions(case_id: str, root: Path) -> V8CaseValidationStepResult:
  blocking: list[str] = []
  warnings: list[str] = []
  paths: list[str] = []

  gap_report = build_gap_next_actions_report(case_id=case_id, project_root=root)
  counts = {
    "gap_count": gap_report.gap_count,
    "action_count": gap_report.action_count,
    "top_3_count": len(gap_report.top_3_actions),
  }

  if gap_report.gap_count < 1:
    blocking.append("Gap が空")

  if not gap_report.top_3_actions:
    blocking.append("Top 3 Next Actions が空")

  claim_gaps = gap_report.count_by_gap_type.get("claim_text_required", 0)
  if claim_gaps:
    warnings.append(f"claim_text_required: {claim_gaps}")

  load_actions = [a for a in gap_report.top_3_actions if a.action_type == "load_claim_text"]
  if claim_gaps and not load_actions:
    warnings.append("claim_text_required があるが load_claim_text action が Top3 にない")

  if not gap_report.watch_profile_update_proposal.strip():
    warnings.append("watch_profile_update_proposal が空")

  latest = find_latest_gap_next_actions_dir(case_id, root)
  if latest:
    paths.append(str(latest))

  status = "fail" if blocking else "warning"
  return _step(
    case_id, "gap_next_actions",
    status=status,
    summary=f"{gap_report.gap_count} gaps / Top3 actions {len(gap_report.top_3_actions)}",
    required_output_exists=gap_report.gap_count >= 1,
    artifact_paths=paths,
    key_counts=counts,
    warnings=warnings + ["Gap is not invalidity / weakness conclusion"],
    blocking_issues=blocking,
  )


def _validate_fixed_point_observation(case_id: str, root: Path) -> V8CaseValidationStepResult:
  blocking: list[str] = []
  warnings: list[str] = []
  paths: list[str] = []

  obs = build_observation_loop_report(case_id=case_id, project_root=root)
  counts = {"proposal_count": len(obs.watch_profile_update_proposals)}

  if not obs.watch_profile_update_proposals:
    warnings.append("Watch Profile proposals なし")

  sched = obs.scheduler_followup_plan
  if not sched:
    blocking.append("Scheduler plan なし")
  else:
    if not sched.no_scheduler_start:
      blocking.append("no_scheduler_start が false")
    if sched.schedule_mode != "dry_run_only":
      warnings.append(f"schedule_mode={sched.schedule_mode}")

  email = obs.email_digest_plan
  if not email:
    blocking.append("Email digest plan なし")
  else:
    if not email.no_email_send:
      blocking.append("no_email_send が false")
    if email.digest_mode != "preview_only":
      warnings.append(f"digest_mode={email.digest_mode}")

  latest = find_latest_fixed_point_observation_dir(case_id, root)
  if latest:
    paths.append(str(latest))

  status = "fail" if blocking else "warning"
  return _step(
    case_id, "fixed_point_observation",
    status=status,
    summary=f"loop_status={obs.loop_status} / no_email_send / no_scheduler_start",
    required_output_exists=bool(sched and email),
    artifact_paths=paths,
    key_counts=counts,
    warnings=warnings + ["Watch Profile 自動更新なし", "メール/Scheduler は必須機能として保持"],
    blocking_issues=blocking,
  )


def _validate_export_step(case_id: str, root: Path) -> V8CaseValidationStepResult:
  warnings: list[str] = []
  paths: list[str] = []
  finders = (
    find_latest_patent_shortlist_dir,
    find_latest_claim_map_dir,
    find_latest_evidence_map_dir,
    find_latest_gap_next_actions_dir,
    find_latest_fixed_point_observation_dir,
  )
  for finder in finders:
    p = finder(case_id, root)
    if p and p.exists():
      paths.append(str(p))
      manifest_candidates = list(p.glob("*manifest*.json"))
      for m in manifest_candidates:
        text = m.read_text(encoding="utf-8")
        if "smtp_password" in text.lower() or "tavily_api_key" in text.lower():
          warnings.append(f"secret-like string in {m.name}")
    else:
      warnings.append(f"{finder.__name__} — 未生成")

  counts = {"export_artifact_dirs": len(paths)}
  status = "warning" if warnings else "pass"
  return _step(
    case_id, "export",
    status=status,
    summary=f"{len(paths)} export artifact dirs collected",
    required_output_exists=len(paths) >= 3,
    artifact_paths=paths,
    key_counts=counts,
    warnings=warnings,
    blocking_issues=[],
  )


def _resolve_readiness(
  steps: list[V8CaseValidationStepResult],
  *,
  not_loaded_claims: int,
) -> str:
  if any(s.status == "fail" for s in steps):
    return "not_ready"
  if not_loaded_claims > 0:
    return "needs_claim_text"
  source_step = next((s for s in steps if s.step_id == "sources"), None)
  if source_step and source_step.key_counts.get("patent_count", 0) < 5:
    return "needs_more_sources"
  if any(s.status == "warning" for s in steps):
    return "needs_manual_review"
  return "ready"


def _overall_status(steps: list[V8CaseValidationStepResult], readiness: str) -> str:
  if any(s.status == "fail" for s in steps):
    return "fail"
  if readiness in {"not_ready", "needs_more_sources"}:
    return "fail"
  if readiness in {"needs_claim_text", "needs_manual_review"} or any(s.status == "warning" for s in steps):
    return "warning"
  return "pass"


def build_case_validation_report(
  case_id: str,
  *,
  project_root: Path | str | None = None,
  ensure_artifacts: bool = True,
) -> V8CaseValidationReport:
  root = Path(project_root or project_root_from_here())
  profile = load_case_profile(case_id, root) or {}
  case_name = str(profile.get("case_name") or case_id)

  if ensure_artifacts:
    ensure_case_artifacts(case_id, project_root=root)

  steps = [
    _validate_sources(case_id, root),
    _validate_patent_shortlist(case_id, root),
    _validate_claim_map(case_id, root),
    _validate_evidence_map(case_id, root),
    _validate_gap_next_actions(case_id, root),
    _validate_fixed_point_observation(case_id, root),
    _validate_export_step(case_id, root),
  ]

  claim_step = next(s for s in steps if s.step_id == "claim_map")
  not_loaded = claim_step.key_counts.get("not_loaded_count", 0)
  readiness = _resolve_readiness(steps, not_loaded_claims=not_loaded)
  overall = _overall_status(steps, readiness)

  gap_step = next(s for s in steps if s.step_id == "gap_next_actions")
  fp_step = next(s for s in steps if s.step_id == "fixed_point_observation")
  ev_step = next(s for s in steps if s.step_id == "evidence_map")
  src_step = next(s for s in steps if s.step_id == "sources")
  ps_step = next(s for s in steps if s.step_id == "patent_shortlist")
  exp_step = next(s for s in steps if s.step_id == "export")

  top_findings: list[str] = []
  if not_loaded:
    top_findings.append(f"claim 本文未取得: {not_loaded} claims（needs_claim_text）")
  if gap_step.key_counts.get("gap_count"):
    top_findings.append(f"Gap {gap_step.key_counts['gap_count']} 件 — Top3 Next Actions あり")

  limitations = [
    "claim 本文未取得のため Evidence Map は浅い",
    "Evidence Map は candidate のみ（not proof）",
  ]
  next_actions: list[str] = []
  gap_report = build_gap_next_actions_report(case_id=case_id, project_root=root)
  for action in gap_report.top_3_actions[:3]:
    next_actions.append(action.action_title)

  trace: list[str] = []
  for step in steps:
    for p in step.artifact_paths:
      trace.append(f"{step.step_id}: {p}")

  return V8CaseValidationReport(
    report_id=_report_id(case_id),
    case_id=case_id,
    case_name=case_name,
    generated_at=utc_now_iso(),
    overall_status=overall,
    step_results=steps,
    source_count=src_step.key_counts.get("source_total", 0),
    patent_shortlist_count=ps_step.key_counts.get("shortlist_count", 0),
    claim_map_count=claim_step.key_counts.get("claim_map_count", 0),
    evidence_link_count=ev_step.key_counts.get("link_count", 0),
    gap_count=gap_step.key_counts.get("gap_count", 0),
    next_action_count=gap_step.key_counts.get("action_count", 0),
    fixed_point_loop_status=fp_step.summary,
    export_artifact_count=exp_step.key_counts.get("export_artifact_dirs", 0),
    top_findings=top_findings,
    known_limitations=limitations,
    next_human_actions=next_actions,
    artifact_trace=trace,
    readiness_for_demo=readiness,
    warnings=list(VALIDATION_SAFETY_NOTICES[:3]),
    candidate_information_only=True,
    human_review_required=True,
    no_legal_judgement=True,
    no_email_send=True,
    no_scheduler_start=True,
  )


def build_three_case_validation_pack(
  *,
  project_root: Path | str | None = None,
  ensure_artifacts: bool = True,
) -> V8ThreeCaseValidationPack:
  root = Path(project_root or project_root_from_here())
  reports = [
    build_case_validation_report(cid, project_root=root, ensure_artifacts=ensure_artifacts)
    for cid in CASE_IDS
  ]

  readiness_counts = Counter(r.readiness_for_demo for r in reports)
  status_counts = Counter(r.overall_status for r in reports)

  blocking_counter: Counter[str] = Counter()
  for report in reports:
    for step in report.step_results:
      for issue in step.blocking_issues:
        blocking_counter[issue] += 1
    if report.readiness_for_demo == "needs_claim_text":
      blocking_counter["claim 本文未取得（全案件）"] += 1

  common_blocking = [issue for issue, count in blocking_counter.most_common() if count >= 1]
  if not common_blocking:
    common_blocking = ["（なし）"]

  action_counter: Counter[str] = Counter()
  for report in reports:
    for action in report.next_human_actions:
      action_counter[action] += 1
  common_actions = [a for a, _ in action_counter.most_common(5)]
  if not common_actions:
    common_actions = ["claims_input.csv に claim 本文を人手追加"]

  overall = "fail" if status_counts.get("fail", 0) else ("warning" if status_counts.get("warning", 0) else "pass")

  demo_summary = "\n".join([
    "# Demo Readiness Summary",
    "",
    f"- overall_status: {overall}",
    f"- total_cases: {len(reports)}",
    *[f"- {r.case_id}: {r.readiness_for_demo} ({r.overall_status})" for r in reports],
    "",
    "## 共通課題",
    *[f"- {b}" for b in common_blocking[:5]],
    "",
    "## 次の人手アクション",
    *[f"- {a}" for a in common_actions[:5]],
    "",
    "ready = デモ説明可能（技術的正しさ・特許的有効性ではない）",
    "needs_claim_text = claim 本文未取得が主要 blocking issue",
  ])

  cloud_summary = "\n".join([
    "# Cloud Readiness Summary",
    "",
    "Cloud Build / Cloud Run deploy はこの Phase では実行しません。",
    "",
    f"- overall_status: {overall}",
    "- ローカル検証パック生成済み",
    "- メール送信・Scheduler: 必須機能として保持（本 Phase では実行しない）",
    "- 次: Phase27L Cloud Run v8 反映準備",
    "",
    "## 案件別 readiness",
    *[f"- {r.case_id}: {r.readiness_for_demo}" for r in reports],
  ])

  cross = (
    f"{len(reports)} cases validated — "
    f"needs_claim_text={readiness_counts.get('needs_claim_text', 0)}, "
    f"warning={status_counts.get('warning', 0)}, fail={status_counts.get('fail', 0)}"
  )

  return V8ThreeCaseValidationPack(
    pack_id=_pack_id(),
    generated_at=utc_now_iso(),
    cases=reports,
    overall_status=overall,
    total_cases=len(reports),
    ready_case_count=readiness_counts.get("ready", 0),
    warning_case_count=status_counts.get("warning", 0) + readiness_counts.get("needs_claim_text", 0),
    fail_case_count=status_counts.get("fail", 0),
    cross_case_summary=cross,
    common_blocking_issues=common_blocking,
    common_next_actions=common_actions,
    demo_readiness_summary=demo_summary,
    cloud_readiness_summary=cloud_summary,
    safety_notice="; ".join(VALIDATION_SAFETY_NOTICES[:4]),
    no_legal_judgement=True,
    no_email_send=True,
    no_scheduler_start=True,
  )
