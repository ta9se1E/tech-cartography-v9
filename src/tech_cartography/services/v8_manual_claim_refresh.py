"""v8 Manual Claim Refresh service (Phase 27J)."""

from __future__ import annotations

import hashlib
from pathlib import Path

from tech_cartography.runtime.v8_manual_claim_injection_schema import (
  MANUAL_CLAIM_SAFETY_NOTICES,
  V8ManualClaimInjectionResult,
  V8ManualClaimRefreshReport,
)
from tech_cartography.runtime.v8_sources_schema import utc_now_iso
from tech_cartography.services.v8_case_validation_pack import build_case_validation_report
from tech_cartography.services.v8_claim_map import build_claim_map
from tech_cartography.services.v8_claim_map_export import export_claim_map
from tech_cartography.services.v8_evidence_map import build_evidence_map
from tech_cartography.services.v8_evidence_map_export import export_evidence_map
from tech_cartography.services.v8_fixed_point_observation import build_observation_loop_report
from tech_cartography.services.v8_fixed_point_observation_export import export_observation_loop
from tech_cartography.services.v8_gap_next_actions import build_gap_next_actions_report
from tech_cartography.services.v8_gap_next_actions_export import export_gap_next_actions
from tech_cartography.services.v8_manual_claim_injection import claim_text_loaded_in_csv
from tech_cartography.services.v8_patent_shortlist import build_patent_shortlist
from tech_cartography.services.v8_patent_shortlist_export import export_patent_shortlist
from tech_cartography.services.v8_sources_table import project_root_from_here


def _report_id(case_id: str, publication_number: str) -> str:
  digest = hashlib.sha256(f"{case_id}|{publication_number}|refresh".encode()).hexdigest()[:12]
  return f"{case_id}:manual_refresh:{digest}"


def _resolve_post_injection_readiness(*, loaded: int, not_loaded: int, base_readiness: str) -> str:
  if loaded > 0 and not_loaded > 0:
    return "partial_claim_loaded"
  if not_loaded > 0:
    return "needs_claim_text"
  if base_readiness in {"needs_manual_review", "warning"}:
    return "needs_manual_review"
  return base_readiness if base_readiness != "needs_claim_text" else "partial_claim_loaded"


def refresh_after_manual_claim(
  *,
  case_id: str,
  publication_number: str,
  claim_no: str = "1",
  top_n: int = 5,
  project_root: Path | str | None = None,
  injection_result: V8ManualClaimInjectionResult | None = None,
) -> V8ManualClaimRefreshReport:
  """Regenerate downstream artifacts after user-provided claim text is saved. No external API calls."""
  root = Path(project_root or project_root_from_here())
  pub = publication_number.strip()
  cno = (claim_no or "1").strip()

  loaded, _ = claim_text_loaded_in_csv(case_id, pub, cno, project_root=root)
  if not loaded:
    raise ValueError(
      f"claims_input.csv に {pub} claim {cno} の claim 本文がありません。"
      " 先に手動投入してください。"
    )

  before_claim = build_claim_map(case_id=case_id, publication_number=pub, project_root=root)
  before_evidence = build_evidence_map(case_id=case_id, publication_number=pub, project_root=root)
  before_validation = build_case_validation_report(case_id, project_root=root, ensure_artifacts=False)
  before_readiness = _resolve_post_injection_readiness(
    loaded=before_claim.loaded_claim_count,
    not_loaded=before_claim.not_loaded_claim_count,
    base_readiness=before_validation.readiness_for_demo,
  )

  artifact_paths: list[str] = []

  shortlist = build_patent_shortlist(case_id=case_id, top_n=top_n, project_root=root)
  shortlist_exp = export_patent_shortlist(shortlist, project_root=root)
  artifact_paths.append(shortlist_exp.output_dir)

  claim_map = build_claim_map(case_id=case_id, publication_number=pub, project_root=root)
  claim_exp = export_claim_map(claim_map, project_root=root)
  artifact_paths.append(claim_exp.output_dir)

  evidence_map = build_evidence_map(case_id=case_id, publication_number=pub, project_root=root)
  evidence_exp = export_evidence_map(evidence_map, project_root=root)
  artifact_paths.append(evidence_exp.output_dir)

  gap_report = build_gap_next_actions_report(case_id=case_id, publication_number=pub, project_root=root)
  gap_exp = export_gap_next_actions(gap_report, project_root=root)
  artifact_paths.append(gap_exp.output_dir)

  obs_report = build_observation_loop_report(case_id=case_id, publication_number=pub, project_root=root)
  obs_exp = export_observation_loop(obs_report, project_root=root)
  artifact_paths.append(obs_exp.output_dir)

  after_validation = build_case_validation_report(case_id, project_root=root, ensure_artifacts=False)
  after_readiness = _resolve_post_injection_readiness(
    loaded=claim_map.loaded_claim_count,
    not_loaded=claim_map.not_loaded_claim_count,
    base_readiness=after_validation.readiness_for_demo,
  )

  remaining: list[str] = []
  if claim_map.not_loaded_claim_count > 0:
    remaining.append(f"claim 本文未取得: {claim_map.not_loaded_claim_count} claims")
  if evidence_map.claim_text_required_count > 0:
    remaining.append(f"claim_text_required: {evidence_map.claim_text_required_count}")
  if evidence_map.missing_evidence_count > 0:
    remaining.append(f"missing_evidence: {evidence_map.missing_evidence_count}")

  next_actions = [a.action_title for a in gap_report.top_3_actions[:3]]
  if not next_actions:
    next_actions = ["残りの claim 本文を一次情報から投入"]

  claim_map_summary = (
    f"{claim_map.claim_count} claims / loaded {claim_map.loaded_claim_count} / "
    f"not_loaded {claim_map.not_loaded_claim_count}"
  )
  evidence_map_summary = (
    f"{evidence_map.link_count} links / claim_text_required {evidence_map.claim_text_required_count} / "
    f"missing {evidence_map.missing_evidence_count} — supporting evidence candidate (not proof)"
  )
  gap_summary = (
    f"{gap_report.gap_count} gaps / Top3 {len(gap_report.top_3_actions)} — "
    f"claim_text_required={gap_report.count_by_gap_type.get('claim_text_required', 0)}"
  )
  fp_summary = (
    f"loop_status={obs_report.loop_status} / no_email_send / no_scheduler_start / "
    f"tasks={len(obs_report.top_3_next_cycle_tasks)}"
  )

  return V8ManualClaimRefreshReport(
    report_id=_report_id(case_id, pub),
    case_id=case_id,
    publication_number=pub,
    generated_at=utc_now_iso(),
    claim_injection_result=injection_result,
    claim_map_summary=claim_map_summary,
    evidence_map_summary=evidence_map_summary,
    gap_next_actions_summary=gap_summary,
    fixed_point_observation_summary=fp_summary,
    validation_readiness_before=before_readiness,
    validation_readiness_after=after_readiness,
    claim_text_required_count_before=before_evidence.claim_text_required_count,
    claim_text_required_count_after=evidence_map.claim_text_required_count,
    artifact_paths=artifact_paths,
    remaining_blocking_issues=remaining or ["（なし）"],
    next_human_actions=next_actions,
    warnings=list(MANUAL_CLAIM_SAFETY_NOTICES[:4]),
    candidate_information_only=True,
    human_review_required=True,
    no_legal_judgement=True,
    no_email_send=True,
    no_scheduler_start=True,
  )
