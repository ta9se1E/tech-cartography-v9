"""v8 Demo Readiness service (Phase 27M)."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

from tech_cartography.runtime.v8_demo_readiness_schema import (
  DEMO_READINESS_SAFETY_NOTICES,
  V8CaseDemoReadiness,
  V8DemoReadinessReport,
  V8DemoStepStatus,
)
from tech_cartography.runtime.v8_sources_schema import utc_now_iso
from tech_cartography.services.v8_claim_input_loader import load_claims_input_csv
from tech_cartography.services.v8_claim_map_export import find_latest_claim_map_dir
from tech_cartography.services.v8_demo_polish_export import find_latest_demo_polish_dir
from tech_cartography.services.v8_evidence_map_export import find_latest_evidence_map_dir
from tech_cartography.services.v8_export_package import get_v8_export_packages_dir
from tech_cartography.services.v8_fixed_point_observation_export import find_latest_fixed_point_observation_dir
from tech_cartography.services.v8_gap_next_actions_export import find_latest_gap_next_actions_dir
from tech_cartography.services.v8_large_candidate_shortlist import find_latest_large_shortlist_dir
from tech_cartography.services.v8_sources_table import load_case_profile, project_root_from_here
from tech_cartography.ui.v8_tab_config import V8_CASE_SAMPLES, V8_TAB_LABELS

LOADED_CLAIM_STATUSES = frozenset({"manual_input", "loaded", "csv_imported", "artifact_imported"})

RECOMMENDED_DEMO_FLOW: tuple[str, ...] = (
  "1. Case を選ぶ",
  "2. 入力タブで 1000件 CSV を取り込む",
  "3. Sources一覧で母集団を見る",
  "4. 読むべき特許で Top100 → Top20 → Top5 を生成",
  "5. Claim Map で claim 状態を確認",
  "6. 必要なら claim 本文を1件手動投入",
  "7. Evidence Map で supporting evidence candidate を見る",
  "8. Gap / Next Actions で未確認事項を見る",
  "9. 定点観測で次回タスクを見る",
  "10. Export で Demo Pack を出す",
)

STEP_TO_TAB: dict[str, str] = {
  "input": "input",
  "sources": "sources",
  "large_candidate_import": "input",
  "large_candidate_shortlist": "patent_shortlist",
  "ranking_explanation": "patent_shortlist",
  "claim_map": "claim_map",
  "manual_claim_injection": "claim_map",
  "evidence_map": "evidence_map",
  "gap_next_actions": "gap_next_actions",
  "fixed_point_observation": "fixed_point_observation",
  "demo_polish_pack": "export",
  "export": "export",
}


def _report_id() -> str:
  digest = hashlib.sha256(f"demo_readiness|{utc_now_iso()}".encode()).hexdigest()[:12]
  return f"demo_readiness:{digest}"


def _step_id(case_id: str, step_name: str) -> str:
  digest = hashlib.sha256(f"{case_id}|{step_name}".encode()).hexdigest()[:8]
  return f"{case_id}:{step_name}:{digest}"


def _count_csv_rows(path: Path) -> int:
  if not path.exists():
    return 0
  try:
    with path.open(encoding="utf-8", newline="") as handle:
      reader = csv.reader(handle)
      next(reader, None)
      return sum(1 for _ in reader)
  except (OSError, csv.Error):
    return 0


def _read_manifest_counts(path: Path, *keys: str) -> dict[str, int]:
  if not path.exists():
    return {}
  try:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {k: int(data[k]) for k in keys if k in data and data[k] is not None}
  except (json.JSONDecodeError, TypeError, ValueError, OSError):
    return {}


def _make_step(
  *,
  case_id: str,
  step_name: str,
  status: str,
  display_label: str,
  summary: str,
  artifact_paths: list[str] | None = None,
  primary_artifact_exists: bool = False,
  key_counts: dict[str, str | int] | None = None,
  next_user_action: str = "",
  next_button_hint: str = "",
  warnings: list[str] | None = None,
  blocking_issues: list[str] | None = None,
) -> V8DemoStepStatus:
  tab_key = STEP_TO_TAB.get(step_name, "intro")
  return V8DemoStepStatus(
    step_id=_step_id(case_id, step_name),
    case_id=case_id,
    step_name=step_name,
    status=status,
    display_label=display_label,
    summary=summary,
    artifact_paths=artifact_paths or [],
    primary_artifact_exists=primary_artifact_exists,
    key_counts=key_counts or {},
    next_user_action=next_user_action,
    next_tab=V8_TAB_LABELS.get(tab_key, tab_key),
    next_button_hint=next_button_hint,
    warnings=warnings or [],
    blocking_issues=blocking_issues or [],
  )


def _artifact_missing_summary(step_label: str) -> str:
  return f"artifact missing — {step_label} 未生成（true zero ではありません）"


def assess_case_demo_readiness(
  case_id: str,
  *,
  project_root: Path | str | None = None,
) -> V8CaseDemoReadiness:
  """Assess demo readiness for one case. Distinguishes artifact missing vs true zero."""
  root = Path(project_root or project_root_from_here())
  profile = load_case_profile(case_id, root) or {}
  case_name = str(profile.get("case_name") or case_id)
  trace: list[str] = []
  steps: list[V8DemoStepStatus] = []
  caveats: list[str] = list(DEMO_READINESS_SAFETY_NOTICES[:2])

  case_dir = root / "cases" / case_id
  large_csv = case_dir / "source_candidates_large.csv"
  large_deduped = case_dir / "source_candidates_large_deduped.csv"
  sources_csv = case_dir / "source_candidates.csv"
  claims_csv = case_dir / "claims_input.csv"

  large_count: int | None = None
  if large_csv.exists():
    large_count = _count_csv_rows(large_csv)
    trace.append(str(large_csv))
    lc_status = "ready" if large_count > 0 else "warning"
    lc_summary = f"source_candidates_large.csv: {large_count} rows"
    if large_count < 100:
      caveats.append(f"{case_id}: large candidate {large_count} rows — fixture or partial import")
    steps.append(_make_step(
      case_id=case_id,
      step_name="large_candidate_import",
      status=lc_status,
      display_label="Large Candidate CSV",
      summary=lc_summary,
      artifact_paths=[str(large_csv)],
      primary_artifact_exists=True,
      key_counts={"large_candidate_count": large_count},
      next_user_action=(
        "入力タブで CSV/Excel を取り込む" if large_count == 0
        else f"Sources一覧タブへ — {large_count}件母集団"
      ),
      next_button_hint="Import Large Candidate File",
    ))
  else:
    steps.append(_make_step(
      case_id=case_id,
      step_name="large_candidate_import",
      status="not_generated",
      display_label="Large Candidate CSV",
      summary=_artifact_missing_summary("Large Candidate CSV"),
      primary_artifact_exists=False,
      key_counts={"artifact_status": "artifact_missing"},
      next_user_action="入力タブで 1000件候補 CSV/Excel を取り込む",
      next_button_hint="Import Large Candidate File",
      blocking_issues=["source_candidates_large.csv がありません"],
    ))

  if sources_csv.exists():
    src_count = _count_csv_rows(sources_csv)
    trace.append(str(sources_csv))
    steps.append(_make_step(
      case_id=case_id,
      step_name="sources",
      status="ready" if src_count > 0 else "warning",
      display_label="Sources一覧",
      summary=f"source_candidates.csv: {src_count} rows",
      artifact_paths=[str(sources_csv)],
      primary_artifact_exists=True,
      key_counts={"source_count": src_count},
      next_user_action="読むべき特許タブへ",
    ))
  else:
    steps.append(_make_step(
      case_id=case_id,
      step_name="sources",
      status="needs_previous_step",
      display_label="Sources一覧",
      summary=_artifact_missing_summary("Sources CSV"),
      next_user_action="入力タブで Large Candidate を取り込む",
    ))

  steps.append(_make_step(
    case_id=case_id,
    step_name="input",
    status="ready" if large_csv.exists() or sources_csv.exists() else "missing",
    display_label="入力",
    summary="Case 選択と CSV 取込",
    next_user_action="Case を選び CSV を取り込む" if not large_csv.exists() else "Sources一覧へ",
  ))

  shortlist_dir = find_latest_large_shortlist_dir(case_id, root)
  top100_count: int | None = None
  top20_count: int | None = None
  top5_count: int | None = None
  if shortlist_dir and shortlist_dir.is_dir():
    trace.append(str(shortlist_dir))
    top100_path = shortlist_dir / "large_candidate_top100.csv"
    top20_path = shortlist_dir / "large_candidate_top20.csv"
    top5_path = shortlist_dir / "large_candidate_top5.csv"
    manifest_path = shortlist_dir / "large_candidate_shortlist_manifest.json"
    manifest_counts = _read_manifest_counts(
      manifest_path,
      "top100_count", "top20_count", "top5_count", "population_count",
    )
    top100_count = manifest_counts.get("top100_count") or (_count_csv_rows(top100_path) if top100_path.exists() else None)
    top20_count = manifest_counts.get("top20_count") or (_count_csv_rows(top20_path) if top20_path.exists() else None)
    top5_count = manifest_counts.get("top5_count") or (_count_csv_rows(top5_path) if top5_path.exists() else None)
    has_top5 = top5_path.exists() or (top5_count or 0) > 0
    sl_status = "ready" if has_top5 else "warning"
    steps.append(_make_step(
      case_id=case_id,
      step_name="large_candidate_shortlist",
      status=sl_status,
      display_label="Top100 / Top20 / Top5",
      summary=(
        f"Top100={top100_count if top100_count is not None else '—'} / "
        f"Top20={top20_count if top20_count is not None else '—'} / "
        f"Top5={top5_count if top5_count is not None else '—'}"
      ),
      artifact_paths=[str(shortlist_dir)],
      primary_artifact_exists=True,
      key_counts={
        "top100_count": top100_count if top100_count is not None else "—",
        "top20_count": top20_count if top20_count is not None else "—",
        "top5_count": top5_count if top5_count is not None else "—",
      },
      next_user_action="Claim Map タブへ" if has_top5 else "読むべき特許タブで Top100/Top20/Top5 を生成",
      next_button_hint="Generate Large Candidate Shortlist",
    ))

    ranking_md = shortlist_dir / "ranking_explanation.md"
    ranking_json = shortlist_dir / "ranking_explanation.json"
    if ranking_md.exists() or ranking_json.exists():
      steps.append(_make_step(
        case_id=case_id,
        step_name="ranking_explanation",
        status="ready",
        display_label="Ranking Explanation",
        summary="ranking_explanation artifact あり",
        artifact_paths=[str(p) for p in (ranking_md, ranking_json) if p.exists()],
        primary_artifact_exists=True,
        next_user_action="Claim Map タブへ",
      ))
    else:
      steps.append(_make_step(
        case_id=case_id,
        step_name="ranking_explanation",
        status="not_generated",
        display_label="Ranking Explanation",
        summary=_artifact_missing_summary("Ranking Explanation"),
        next_user_action="読むべき特許タブで Large Candidate shortlist を再生成",
        next_button_hint="Generate Large Candidate Shortlist",
      ))
  else:
    steps.append(_make_step(
      case_id=case_id,
      step_name="large_candidate_shortlist",
      status="not_generated",
      display_label="Top100 / Top20 / Top5",
      summary=_artifact_missing_summary("Large Candidate Shortlist"),
      primary_artifact_exists=False,
      key_counts={"artifact_status": "artifact_missing"},
      next_user_action="読むべき特許タブで Top100 / Top20 / Top5 を生成",
      next_button_hint="Generate Large Candidate Shortlist",
      blocking_issues=["Large Candidate shortlist 未生成"],
    ))
    steps.append(_make_step(
      case_id=case_id,
      step_name="ranking_explanation",
      status="needs_previous_step",
      display_label="Ranking Explanation",
      summary="shortlist 未生成のため ranking explanation も未生成",
      next_user_action="先に Top100/Top20/Top5 を生成",
    ))

  claim_map_dir = find_latest_claim_map_dir(case_id, root)
  claim_rows, _ = load_claims_input_csv(case_id, project_root=root)
  manual_count = sum(1 for r in claim_rows if r.has_loaded_text())
  not_loaded_count = sum(1 for r in claim_rows if not r.has_loaded_text())

  if claim_map_dir:
    trace.append(str(claim_map_dir))
    steps.append(_make_step(
      case_id=case_id,
      step_name="claim_map",
      status="ready",
      display_label="Claim Map",
      summary=f"Claim Map artifact あり — claims_input {len(claim_rows)} rows",
      artifact_paths=[str(claim_map_dir)],
      primary_artifact_exists=True,
      key_counts={"claim_rows": len(claim_rows), "not_loaded": not_loaded_count},
      next_user_action="Evidence Map タブへ",
      next_button_hint="Generate / Refresh Claim Map",
    ))
  elif claims_csv.exists():
    steps.append(_make_step(
      case_id=case_id,
      step_name="claim_map",
      status="not_generated",
      display_label="Claim Map",
      summary=_artifact_missing_summary("Claim Map export"),
      primary_artifact_exists=False,
      key_counts={"claim_rows": len(claim_rows), "artifact_status": "artifact_missing"},
      next_user_action="Claim Map タブで Generate / Refresh",
      next_button_hint="Generate / Refresh Claim Map",
    ))
  else:
    steps.append(_make_step(
      case_id=case_id,
      step_name="claim_map",
      status="needs_previous_step",
      display_label="Claim Map",
      summary="claims_input.csv なし — 先に Top5 shortlist を生成",
      next_user_action="読むべき特許 → Claim Map の順",
    ))

  if manual_count > 0:
    mc_status = "ready"
    mc_summary = f"manual_input/loaded claim: {manual_count} 件"
  elif claims_csv.exists() or claim_rows:
    mc_status = "warning"
    mc_summary = "claim 本文未投入 — デモ継続可能だが warning（Top5の1件投入推奨）"
    caveats.append(f"{case_id}: manual claim 未投入 — claim_text_required のまま")
  else:
    mc_status = "needs_previous_step"
    mc_summary = "claims_input 未確認"
  steps.append(_make_step(
    case_id=case_id,
    step_name="manual_claim_injection",
    status=mc_status,
    display_label="Manual Claim",
    summary=mc_summary,
    artifact_paths=[str(claims_csv)] if claims_csv.exists() else [],
    primary_artifact_exists=claims_csv.exists(),
    key_counts={
      "manual_claim_count": manual_count if claim_rows else "artifact_missing",
      "not_loaded_claims": not_loaded_count if claim_rows else "—",
    },
    next_user_action=(
      "Claim Map タブで Top5 の1件だけ claim 本文を手動投入"
      if manual_count == 0 else "Evidence Map タブへ"
    ),
    next_button_hint="claims_input.csvへ保存",
  ))

  ev_dir = find_latest_evidence_map_dir(case_id, root)
  evidence_link_count: int | None = None
  claim_text_required_count: int | None = None
  if ev_dir:
    trace.append(str(ev_dir))
    manifest = ev_dir / "evidence_map_manifest.json"
    counts = _read_manifest_counts(
      manifest,
      "link_count", "claim_text_required_count", "missing_evidence_count",
    )
    evidence_link_count = counts.get("link_count")
    claim_text_required_count = counts.get("claim_text_required_count")
    if evidence_link_count is not None:
      ev_status = "ready" if evidence_link_count > 0 else "warning"
      ev_summary = f"Evidence Map artifact あり — links={evidence_link_count} (true zero では artifact 由来)"
      if evidence_link_count == 0:
        ev_summary += " — 件数0（artifact 生成済み）"
    else:
      ev_status = "warning"
      ev_summary = "Evidence Map artifact あり — manifest から件数未取得"
    steps.append(_make_step(
      case_id=case_id,
      step_name="evidence_map",
      status=ev_status,
      display_label="Evidence Map",
      summary=ev_summary,
      artifact_paths=[str(ev_dir)],
      primary_artifact_exists=True,
      key_counts={
        "evidence_link_count": evidence_link_count if evidence_link_count is not None else "—",
        "claim_text_required_count": claim_text_required_count if claim_text_required_count is not None else "—",
      },
      next_user_action="Gap / Next Actions タブへ",
      next_button_hint="Generate / Refresh Evidence Map",
    ))
  else:
    steps.append(_make_step(
      case_id=case_id,
      step_name="evidence_map",
      status="not_generated",
      display_label="Evidence Map",
      summary=_artifact_missing_summary("Evidence Map"),
      primary_artifact_exists=False,
      key_counts={"evidence_link_count": "artifact_missing", "artifact_status": "not_generated"},
      next_user_action="Evidence Map タブで Generate / Refresh",
      next_button_hint="Generate / Refresh Evidence Map",
      blocking_issues=["Evidence Map artifact 未生成 — 0件表示はしない"],
    ))

  gap_dir = find_latest_gap_next_actions_dir(case_id, root)
  gap_count: int | None = None
  if gap_dir:
    trace.append(str(gap_dir))
    manifest = gap_dir / "gap_next_actions_manifest.json"
    counts = _read_manifest_counts(manifest, "gap_count", "action_count")
    gap_count = counts.get("gap_count")
    if gap_count is not None:
      gap_status = "ready" if gap_count >= 0 else "warning"
      gap_summary = f"Gap artifact あり — gaps={gap_count}"
      if gap_count == 0:
        gap_summary += " (true zero — artifact 生成済み)"
    else:
      gap_status = "warning"
      gap_summary = "Gap artifact あり"
    steps.append(_make_step(
      case_id=case_id,
      step_name="gap_next_actions",
      status=gap_status,
      display_label="Gap / Next Actions",
      summary=gap_summary,
      artifact_paths=[str(gap_dir)],
      primary_artifact_exists=True,
      key_counts={"gap_count": gap_count if gap_count is not None else "—"},
      next_user_action="定点観測タブへ",
      next_button_hint="Generate / Refresh Gap & Next Actions",
    ))
  else:
    steps.append(_make_step(
      case_id=case_id,
      step_name="gap_next_actions",
      status="not_generated",
      display_label="Gap / Next Actions",
      summary=_artifact_missing_summary("Gap / Next Actions"),
      primary_artifact_exists=False,
      key_counts={"gap_count": "artifact_missing"},
      next_user_action="Gap / Next Actions タブで Generate / Refresh",
      blocking_issues=["Gap artifact 未生成 — gap_count=0 と表示しない"],
    ))

  fp_dir = find_latest_fixed_point_observation_dir(case_id, root)
  if fp_dir:
    trace.append(str(fp_dir))
    steps.append(_make_step(
      case_id=case_id,
      step_name="fixed_point_observation",
      status="ready",
      display_label="定点観測",
      summary="Fixed Point Observation artifact あり — no_email_send / no_scheduler_start",
      artifact_paths=[str(fp_dir)],
      primary_artifact_exists=True,
      key_counts={"no_email_send": True, "no_scheduler_start": True},
      next_user_action="Export タブへ",
      next_button_hint="Generate / Refresh Fixed Point Observation",
    ))
  else:
    steps.append(_make_step(
      case_id=case_id,
      step_name="fixed_point_observation",
      status="not_generated",
      display_label="定点観測",
      summary=_artifact_missing_summary("Fixed Point Observation"),
      next_user_action="定点観測タブで Generate / Refresh",
    ))

  polish_dir = find_latest_demo_polish_dir(case_id, root)
  demo_polish_exists = bool(polish_dir and (polish_dir / "demo_polish_report.json").exists())
  if demo_polish_exists:
    trace.append(str(polish_dir))
    steps.append(_make_step(
      case_id=case_id,
      step_name="demo_polish_pack",
      status="ready",
      display_label="Demo Polish Pack",
      summary="demo_polish_report あり",
      artifact_paths=[str(polish_dir)],
      primary_artifact_exists=True,
      next_user_action="Export で Demo Readiness Pack を生成",
    ))
  else:
    steps.append(_make_step(
      case_id=case_id,
      step_name="demo_polish_pack",
      status="not_generated",
      display_label="Demo Polish Pack",
      summary=_artifact_missing_summary("Demo Polish Pack"),
      next_user_action="Export タブで Demo Polish Pack を生成",
      next_button_hint="Generate Demo Polish Pack",
    ))

  export_root = get_v8_export_packages_dir(root)
  export_exists = export_root.is_dir() and any(export_root.iterdir()) if export_root.exists() else False
  steps.append(_make_step(
    case_id=case_id,
    step_name="export",
    status="ready" if export_exists else "warning",
    display_label="Export",
    summary="Export Package あり" if export_exists else "Export Package 未生成 — warning",
    artifact_paths=[str(export_root)] if export_exists else [],
    primary_artifact_exists=export_exists,
    next_user_action="Demo Readiness Pack を生成して提出準備",
    next_button_hint="Generate Demo Readiness Pack",
  ))

  ready_steps = sum(1 for s in steps if s.status == "ready")
  total_steps = len(steps)
  next_actions = [s.next_user_action for s in steps if s.status in {"not_generated", "missing", "needs_previous_step", "warning"} and s.next_user_action][:3]

  if not large_csv.exists():
    overall = "needs_large_candidate_csv"
  elif not shortlist_dir:
    overall = "needs_shortlist"
  elif manual_count == 0 and not_loaded_count > 0:
    overall = "needs_claim_text"
  elif not ev_dir or not gap_dir:
    overall = "needs_evidence_refresh"
  elif ready_steps >= total_steps - 2:
    overall = "demo_ready"
  elif ready_steps >= total_steps // 2:
    overall = "ready_with_warnings"
  else:
    overall = "not_ready"

  current_step = next(
    (s.display_label for s in steps if s.status in {"not_generated", "missing", "needs_previous_step"}),
    steps[-1].display_label if steps else "入力",
  )

  return V8CaseDemoReadiness(
    case_id=case_id,
    case_name=case_name,
    generated_at=utc_now_iso(),
    overall_status=overall,
    current_recommended_step=current_step,
    completed_step_count=ready_steps,
    total_step_count=total_steps,
    step_statuses=steps,
    large_candidate_count=large_count,
    top100_count=top100_count,
    top20_count=top20_count,
    top5_count=top5_count,
    manual_claim_count=manual_count if claim_rows else None,
    claim_text_required_count=claim_text_required_count,
    evidence_link_count=evidence_link_count if ev_dir else None,
    gap_count=gap_count if gap_dir else None,
    demo_polish_pack_exists=demo_polish_exists,
    export_pack_exists=export_exists,
    recommended_demo_flow=list(RECOMMENDED_DEMO_FLOW),
    next_3_user_actions=next_actions,
    caveats=caveats,
    artifact_trace=trace,
  )


def build_demo_readiness_report(
  *,
  project_root: Path | str | None = None,
) -> V8DemoReadinessReport:
  """Build three-case demo readiness report. No external API calls."""
  root = Path(project_root or project_root_from_here())
  cases = [assess_case_demo_readiness(case_id, project_root=root) for case_id, _ in (
    (s["case_id"], s["label"]) for s in V8_CASE_SAMPLES
  )]

  ready_count = sum(1 for c in cases if c.overall_status == "demo_ready")
  warning_count = sum(1 for c in cases if c.overall_status == "ready_with_warnings")
  not_ready_count = len(cases) - ready_count - warning_count

  if ready_count == len(cases):
    overall = "demo_ready"
  elif ready_count + warning_count > 0:
    overall = "ready_with_warnings"
  else:
    overall = "not_ready"

  action_counts: dict[str, int] = {}
  for case in cases:
    for action in case.next_3_user_actions:
      action_counts[action] = action_counts.get(action, 0) + 1
  common_actions = [a for a, _ in sorted(action_counts.items(), key=lambda x: -x[1])][:5]

  operator_checklist = [
    "Case を1つ選び、入力タブから開始",
    "Large Candidate CSV 投入済みか確認（artifact missing と true zero を区別）",
    "Top100 → Top20 → Top5 生成済みか確認",
    "Claim Map / Evidence Map / Gap artifact 生成済みか確認",
    "claim 本文1件投入でデモ見栄え改善（任意）",
    "Demo Polish Pack / Demo Readiness Pack を Export",
    "Cloud Build / Cloud Run はまだ実行しない",
  ]
  cloud_checklist = [
    "3案件すべて demo_ready または ready_with_warnings",
    "artifact missing が blocking になっていないか確認",
    "secret が Export に含まれていないこと",
    "no_email_send / no_scheduler_start 設定確認",
    "README_v8_LOCAL_FIRST.md の Cloud 手順を確認",
    "Phase27N で Cloud Run v8 反映準備",
  ]

  trace: list[str] = []
  for case in cases:
    trace.extend(case.artifact_trace)

  return V8DemoReadinessReport(
    report_id=_report_id(),
    generated_at=utc_now_iso(),
    cases=cases,
    overall_status=overall,
    ready_case_count=ready_count,
    warning_case_count=warning_count,
    not_ready_case_count=not_ready_count,
    common_next_actions=common_actions or ["入力タブで Case を選び CSV を取り込む"],
    demo_operator_checklist=operator_checklist,
    cloud_preparation_checklist=cloud_checklist,
    artifact_trace=list(dict.fromkeys(trace)),
    warnings=list(DEMO_READINESS_SAFETY_NOTICES[:3]),
  )
