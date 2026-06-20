"""Analyst (production run) mode UI helpers (Phase 24.5D)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tech_cartography.validation.end_to_end_chain import EndToEndChainConfig, inspect_end_to_end_status
from tech_cartography.validation.final_validation_summary import (
  build_final_validation_summary,
  save_final_validation_summary_pack,
)
from tech_cartography.validation.seed_progress import inspect_seed_progress_many
from tech_cartography.validation.theme_validation import ThemeValidationCase, parse_keyword_text

PAN_PRECURSOR_THEME_PRESET: dict[str, Any] = {
  "theme_id": "pan_precursor_surface_internal_defects",
  "theme_name": "PAN系炭素繊維前駆体の表面・内部欠陥制御",
  "description": (
    "PAN前駆体の表面・内部欠陥を制御する紡糸・耐炎化・乾燥工程に関する検証テーマです。"
  ),
  "core_keywords": [
    "PAN",
    "carbon fiber",
    "precursor",
    "surface defect",
    "internal defect",
  ],
  "application_keywords": ["CFRP", "hydrogen tank", "pressure vessel"],
  "material_process_keywords": [
    "dry-jet wet spinning",
    "stabilization",
    "carbonization",
    "spinning dope",
  ],
  "exclude_keywords": ["medical film", "photography"],
  "seed_publication_numbers": [
    "JP2022090764A",
    "JP2023163084A",
    "JP2018084002A",
  ],
}

ANALYST_INPUT_KEY_PREFIX = "analyst_input_tab"

ANALYST_WORKFLOW_STEPS: tuple[tuple[str, str], ...] = (
  ("theme_input", "Step 1: テーマを入力する"),
  ("seed_input", "Step 2: seed公報を入力する"),
  ("manual_claims", "Step 3: Manual Claimsを保存する"),
  ("evidence_map", "Step 4: Evidence Map skeletonを生成する"),
  ("paper_web", "Step 5: Paper / Web候補を取得する"),
  ("link_watch_digest", "Step 6: Link Candidate / Strategic Watch / Digestを生成する"),
  ("view_results", "Step 7: 結果を見る"),
)

ANALYST_PROGRESS_LABELS: tuple[str, ...] = (
  "テーマ入力",
  "Seed確認",
  "Manual Claims",
  "Evidence Map",
  "Paper/Web",
  "Link/Watch/Digest",
  "Final Validation",
)

STEP_STATUS_DONE = "完了"
STEP_STATUS_NEXT = "次にやる"
STEP_STATUS_PENDING = "未実行"
STEP_STATUS_REVIEW = "要確認"
STEP_STATUS_API_CONSENT = "外部API同意が必要"

ANALYST_EMPTY_ARTIFACT_MESSAGE = (
  "まだ生成されていません。入力・実行タブで先に実行してください"
)

FINAL_VALIDATION_JSON = (
  Path("outputs") / "validation" / "final_validation" / "final_end_to_end_validation_summary.json"
)


@dataclass(frozen=True)
class AnalystStepStatus:
  step_id: str
  label: str
  status: str


@dataclass(frozen=True)
class AnalystWorkflowSnapshot:
  steps: tuple[AnalystStepStatus, ...]
  progress_lines: tuple[str, ...]
  next_action: str
  has_viewable_outputs: bool


def _keywords_to_text(keywords: list[str]) -> str:
  return ", ".join(keywords)


def pan_theme_session_state_updates(*, key_prefix: str = ANALYST_INPUT_KEY_PREFIX) -> dict[str, str]:
  preset = PAN_PRECURSOR_THEME_PRESET
  return {
    f"{key_prefix}_theme_name": str(preset["theme_name"]),
    f"{key_prefix}_theme_id": str(preset["theme_id"]),
    f"{key_prefix}_description": str(preset["description"]),
    f"{key_prefix}_core_keywords": _keywords_to_text(list(preset["core_keywords"])),
    f"{key_prefix}_application_keywords": _keywords_to_text(list(preset["application_keywords"])),
    f"{key_prefix}_material_keywords": _keywords_to_text(list(preset["material_process_keywords"])),
    f"{key_prefix}_exclude_keywords": _keywords_to_text(list(preset["exclude_keywords"])),
    f"{key_prefix}_seed_publications": _keywords_to_text(list(preset["seed_publication_numbers"])),
  }


def _final_validation_exists(project_root: Path) -> bool:
  return (project_root / FINAL_VALIDATION_JSON).exists()


def _stage_pass(status: str) -> bool:
  return status in {"pass", "actual_data", "query_plan_ready", "preview_ready"}


def compute_analyst_workflow_snapshot(
  case: ThemeValidationCase | None,
  *,
  project_root: Path,
) -> AnalystWorkflowSnapshot:
  if case is None or not case.theme_name.strip() or case.theme_name.strip() == "（テーマ名未入力）":
    steps = _build_step_statuses(
      theme_done=False,
      seed_done=False,
      manual_done=False,
      manual_partial=False,
      evidence_done=False,
      paper_done=False,
      paper_needs_api=False,
      chain_done=False,
      chain_needs_api=False,
      view_ready=False,
    )
    return AnalystWorkflowSnapshot(
      steps=steps,
      progress_lines=_progress_lines_from_steps(steps),
      next_action="テーマ名とコアキーワードを入力してください",
      has_viewable_outputs=False,
    )

  seeds = list(case.seed_publication_numbers)
  progress = inspect_seed_progress_many(seeds, project_root) if seeds else []
  manual_saved = sum(1 for item in progress if item.manual_claims_status == "saved")
  manual_partial = 0 < manual_saved < len(seeds) if seeds else False
  manual_done = bool(seeds) and manual_saved == len(seeds)
  evidence_saved = sum(
    1 for item in progress if item.evidence_map_status in {"skeleton_exists", "full_map_exists"}
  )
  evidence_done = bool(seeds) and evidence_saved == len(seeds)

  e2e = None
  if seeds:
    config = EndToEndChainConfig(
      theme_id=case.theme_id,
      theme_name=case.theme_name,
      publication_numbers=seeds,
      output_root=str(project_root),
      allow_external_api=False,
      dry_run=True,
    )
    e2e = inspect_end_to_end_status(config)

  paper_done = False
  paper_needs_api = False
  chain_done = False
  chain_needs_api = False
  if e2e and e2e.seed_statuses:
    paper_done = all(
      _stage_pass(seed.stage4_paper_candidates) for seed in e2e.seed_statuses
    )
    paper_needs_api = any(
      seed.stage4_paper_candidates == "external_api_required" for seed in e2e.seed_statuses
    )
    chain_done = all(
      _stage_pass(seed.stage6_link_candidates)
      and _stage_pass(seed.stage7_strategic_watch)
      and _stage_pass(seed.stage8_digest)
      for seed in e2e.seed_statuses
    )
    chain_needs_api = any(
      seed.stage5_web_signals == "external_api_required"
      or seed.stage4_paper_candidates == "external_api_required"
      for seed in e2e.seed_statuses
    )

  final_done = _final_validation_exists(project_root)
  view_ready = evidence_done or final_done

  steps = _build_step_statuses(
    theme_done=True,
    seed_done=bool(seeds),
    manual_done=manual_done,
    manual_partial=manual_partial,
    evidence_done=evidence_done,
    paper_done=paper_done,
    paper_needs_api=paper_needs_api and not paper_done,
    chain_done=chain_done,
    chain_needs_api=chain_needs_api and not chain_done,
    view_ready=view_ready and (final_done or (manual_done and evidence_done)),
  )

  next_action = _derive_next_action(
    seeds=seeds,
    manual_done=manual_done,
    evidence_done=evidence_done,
    paper_done=paper_done,
    chain_done=chain_done,
    final_done=final_done,
    view_ready=view_ready,
  )
  return AnalystWorkflowSnapshot(
    steps=steps,
    progress_lines=_progress_lines_from_steps(steps),
    next_action=next_action,
    has_viewable_outputs=view_ready,
  )


def _build_step_statuses(
  *,
  theme_done: bool,
  seed_done: bool,
  manual_done: bool,
  manual_partial: bool,
  evidence_done: bool,
  paper_done: bool,
  paper_needs_api: bool,
  chain_done: bool,
  chain_needs_api: bool,
  view_ready: bool,
) -> tuple[AnalystStepStatus, ...]:
  flags = [
    theme_done,
    seed_done,
    manual_done,
    evidence_done,
    paper_done,
    chain_done,
    view_ready,
  ]
  statuses: list[str] = []
  next_assigned = False
  specialized = [
    None,
    None,
    STEP_STATUS_REVIEW if manual_partial else None,
    None,
    STEP_STATUS_API_CONSENT if paper_needs_api else None,
    STEP_STATUS_API_CONSENT if chain_needs_api else None,
    None,
  ]
  for index, (step_id, label) in enumerate(ANALYST_WORKFLOW_STEPS):
    done = flags[index]
    if done:
      statuses.append(STEP_STATUS_DONE)
      continue
    if specialized[index]:
      statuses.append(specialized[index])
      if not next_assigned:
        next_assigned = True
      continue
    if not next_assigned:
      statuses.append(STEP_STATUS_NEXT)
      next_assigned = True
    else:
      statuses.append(STEP_STATUS_PENDING)
  return tuple(
    AnalystStepStatus(step_id=step_id, label=label, status=status)
    for (step_id, label), status in zip(ANALYST_WORKFLOW_STEPS, statuses, strict=True)
  )


def _progress_lines_from_steps(steps: tuple[AnalystStepStatus, ...]) -> tuple[str, ...]:
  labels = list(ANALYST_PROGRESS_LABELS)
  lines: list[str] = []
  for label, step in zip(labels, steps, strict=True):
    marker = "✓" if step.status == STEP_STATUS_DONE else "·"
    lines.append(f"{marker} {label}")
  return tuple(lines)


def _derive_next_action(
  *,
  seeds: list[str],
  manual_done: bool,
  evidence_done: bool,
  paper_done: bool,
  chain_done: bool,
  final_done: bool,
  view_ready: bool,
) -> str:
  if not seeds:
    return "seed公報を入力してください"
  if not manual_done:
    return "Manual Claimsを保存してください"
  if not evidence_done:
    return "Evidence Map skeletonを生成してください"
  if not paper_done:
    return "Paper/Web候補を取得してください"
  if not chain_done:
    return "Link/Watch/Digestを生成してください"
  if not final_done:
    return "Final Validation Summaryを生成してください"
  if view_ready:
    return "レポートを確認してください"
  return "入力・実行タブでテーマとseed公報を入力してください"


def build_final_validation_from_case(
  case: ThemeValidationCase,
  *,
  project_root: Path,
) -> dict[str, Path]:
  summary = build_final_validation_summary(
    project_root=project_root,
    theme_id=case.theme_id,
    theme_name=case.theme_name,
    seed_publications=case.seed_publication_numbers,
  )
  out_dir = project_root / "outputs" / "validation" / "final_validation"
  paths = save_final_validation_summary_pack(summary, out_dir)
  return paths


def case_from_session_widgets(
  *,
  key_prefix: str = ANALYST_INPUT_KEY_PREFIX,
  session_state: dict[str, Any] | None = None,
) -> ThemeValidationCase | None:
  import streamlit as st

  from tech_cartography.validation.theme_validation import build_theme_id

  state = session_state if session_state is not None else st.session_state
  theme_name = str(state.get(f"{key_prefix}_theme_name", "") or "").strip()
  if not theme_name:
    return None
  core_text = str(state.get(f"{key_prefix}_core_keywords", "") or "")
  theme_id_value = str(state.get(f"{key_prefix}_theme_id", "") or "").strip()
  theme_id = build_theme_id(
    theme_name,
    theme_id_override=theme_id_value,
    core_keywords=parse_keyword_text(core_text),
  )
  return ThemeValidationCase(
    theme_id=theme_id,
    theme_name=theme_name,
    description=str(state.get(f"{key_prefix}_description", "") or "").strip(),
    core_keywords=parse_keyword_text(core_text),
    application_keywords=parse_keyword_text(str(state.get(f"{key_prefix}_application_keywords", "") or "")),
    material_or_process_keywords=parse_keyword_text(str(state.get(f"{key_prefix}_material_keywords", "") or "")),
    exclude_keywords=parse_keyword_text(str(state.get(f"{key_prefix}_exclude_keywords", "") or "")),
    seed_publication_numbers=parse_keyword_text(str(state.get(f"{key_prefix}_seed_publications", "") or "")),
    validation_goal="analyst_mode_ui",
  )


def analyst_has_evidence_outputs(case: ThemeValidationCase, project_root: Path) -> bool:
  if not case.seed_publication_numbers:
    return False
  progress = inspect_seed_progress_many(case.seed_publication_numbers, project_root)
  return any(item.evidence_map_status in {"skeleton_exists", "full_map_exists"} for item in progress)


def preferred_analyst_publication(case: ThemeValidationCase, project_root: Path) -> str | None:
  if not case.seed_publication_numbers:
    return None
  progress = inspect_seed_progress_many(case.seed_publication_numbers, project_root)
  from tech_cartography.validation.seed_progress import preferred_publication_for_evidence_map

  return preferred_publication_for_evidence_map(progress) or case.seed_publication_numbers[0]


def analyst_has_market_outputs(case: ThemeValidationCase, project_root: Path) -> bool:
  if not case.seed_publication_numbers:
    return False
  for pub in case.seed_publication_numbers:
    watch = project_root / "outputs" / "strategic_watch_briefs" / pub / "strategic_watch_brief.md"
    web = project_root / "outputs" / "web_signals" / f"{case.theme_id}_{pub}" / "web_signals.csv"
    review = project_root / "outputs" / "web_signals" / f"{case.theme_id}_{pub}" / "web_signal_review_pack.json"
    if watch.exists() or web.exists() or review.exists():
      return True
  return False


def load_analyst_evidence_bundle(project_root: Path, publication_number: str) -> dict[str, Any]:
  import json

  ev_dir = project_root / "outputs" / "evidence_map_synthesis" / publication_number
  synthesis = None
  for name in ("evidence_map_synthesis.json", "evidence_map_skeleton.json"):
    path = ev_dir / name
    if path.exists():
      try:
        synthesis = json.loads(path.read_text(encoding="utf-8"))
      except (json.JSONDecodeError, OSError):
        synthesis = None
      if synthesis:
        break

  selected_rows: list[dict[str, Any]] = []
  paper_dir = project_root / "outputs" / "paper_candidates" / publication_number
  selected_csv = paper_dir / "selected_evidence_papers.csv"
  if selected_csv.exists():
    from tech_cartography.reports.project_export import load_records_csv

    selected_rows = load_records_csv(str(selected_csv))

  claim_links: list[dict[str, Any]] = []
  links_csv = project_root / "outputs" / "openalex_limited_execution" / "claim_paper_candidate_links.csv"
  if links_csv.exists():
    from tech_cartography.reports.project_export import load_records_csv

    for row in load_records_csv(str(links_csv)):
      if str(row.get("publication_number", "")).strip() == publication_number:
        claim_links.append(row)

  return {
    "publication_number": publication_number,
    "synthesis": synthesis,
    "selected_papers": selected_rows,
    "claim_links": claim_links,
    "excluded_papers": [],
    "artifact_status": {},
  }

