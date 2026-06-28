"""Demo flow / Weekly Watch / Export readiness (Phase 27S.7)."""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

from tech_cartography.runtime.v8_demo_flow_export_schema import (
  DEMO_FLOW_SAFETY_NOTICES,
  READINESS_STATUS_DEMO_OFF,
  READINESS_STATUS_READY,
  READINESS_STATUS_REMAINING,
  SUBMISSION_DEMO_PUB,
  DemoExportBundleResult,
  EvidenceAwareWatchContext,
  SubmissionDemoReadinessItem,
)
from tech_cartography.runtime.v8_sources_schema import utc_now_iso
from tech_cartography.services.v8_claim_example_binding import find_latest_claim_example_links_dir
from tech_cartography.services.v8_claim_input_loader import load_claims_input_csv
from tech_cartography.services.v8_evidence_gap_next_actions import (
  build_evidence_aware_gap_report,
  build_top3_next_actions_from_evidence_gaps,
  evidence_aware_gap_primary_available,
  find_latest_evidence_aware_gap_dir,
  is_evidence_aware_gap_pack,
)
from tech_cartography.services.v8_patent_shortlist_export import find_latest_patent_shortlist_dir
from tech_cartography.services.v8_sources_table import project_root_from_here
from tech_cartography.services.v8_top5_pdf_pipeline_status import build_top5_pdf_pipeline_status

LOCAL_DEMO_EXPORT_SUBDIR = "local_v8_demo_export_bundle"


def _project_root(project_root: Path | str | None) -> Path:
  return Path(project_root) if project_root else Path(project_root_from_here())


def _read_text(path: Path) -> str:
  if path.exists():
    return path.read_text(encoding="utf-8")
  return ""


def _status_for_pipeline_pub(case_id: str, pub: str, root: Path) -> dict[str, object]:
  statuses = build_top5_pdf_pipeline_status(case_id, root, root / "outputs")
  for s in statuses:
    if s.publication_number == pub:
      return {
        "pipeline_status_label": s.pipeline_status_label,
        "evidence_ready_for_review": s.evidence_ready_for_review,
        "vision_ocr_text_extracted": s.vision_ocr_text_extracted,
        "example_facts_extracted": s.example_facts_extracted,
        "claim_example_links_generated": s.claim_example_links_generated,
        "evidence_aware_gaps_generated": s.evidence_aware_gaps_generated,
        "next_action": s.next_action,
      }
  return {}


def build_submission_demo_readiness(
  case_id: str,
  *,
  project_root: Path | str | None = None,
) -> list[SubmissionDemoReadinessItem]:
  root = _project_root(project_root)
  items: list[SubmissionDemoReadinessItem] = []

  shortlist_dir = find_latest_patent_shortlist_dir(case_id, root)
  items.append(SubmissionDemoReadinessItem(
    label="Top5 selection",
    status=READINESS_STATUS_READY if shortlist_dir else READINESS_STATUS_REMAINING,
    detail=str(shortlist_dir) if shortlist_dir else "Patent shortlist artifact missing",
  ))

  claim_rows, _ = load_claims_input_csv(case_id, project_root=root)
  loaded = sum(1 for r in claim_rows if r.has_loaded_text())
  items.append(SubmissionDemoReadinessItem(
    label="Claims loaded",
    status=READINESS_STATUS_READY if loaded > 0 else READINESS_STATUS_REMAINING,
    detail=f"{loaded} claims with text" if loaded else "claims_input.csv missing or empty",
  ))

  pub_status = _status_for_pipeline_pub(case_id, SUBMISSION_DEMO_PUB, root)
  ocr_ready = bool(pub_status.get("vision_ocr_text_extracted"))
  items.append(SubmissionDemoReadinessItem(
    label=f"{SUBMISSION_DEMO_PUB} OCR",
    status=READINESS_STATUS_READY if ocr_ready else READINESS_STATUS_REMAINING,
    detail=str(pub_status.get("next_action") or "OCR pending"),
  ))

  facts_ready = bool(pub_status.get("example_facts_extracted"))
  items.append(SubmissionDemoReadinessItem(
    label=f"{SUBMISSION_DEMO_PUB} example facts",
    status=READINESS_STATUS_READY if facts_ready else READINESS_STATUS_REMAINING,
    detail="example facts extracted" if facts_ready else "example facts pending",
  ))

  bind_dir = find_latest_claim_example_links_dir(case_id, root)
  bind_ready = bool(bind_dir and (bind_dir / "claim_example_links.csv").exists())
  items.append(SubmissionDemoReadinessItem(
    label="Claim-example evidence detail",
    status=READINESS_STATUS_READY if bind_ready else READINESS_STATUS_REMAINING,
    detail=str(bind_dir) if bind_ready else "claim_example_links.csv missing",
  ))

  ev_gap_ready = evidence_aware_gap_primary_available(case_id, root)
  gap_dir = find_latest_evidence_aware_gap_dir(case_id, root)
  items.append(SubmissionDemoReadinessItem(
    label="Evidence-aware Gap",
    status=READINESS_STATUS_READY if ev_gap_ready else READINESS_STATUS_REMAINING,
    detail=str(gap_dir) if gap_dir else "Generate evidence-aware Gap from Claim-Example binding",
  ))

  watch_ready = bool(gap_dir and (gap_dir / "watch_profile_update_proposal.md").exists())
  items.append(SubmissionDemoReadinessItem(
    label="Weekly Watch preview",
    status=READINESS_STATUS_READY if watch_ready else READINESS_STATUS_REMAINING,
    detail="watch_profile_update_proposal.md available" if watch_ready else "Generate evidence-aware Gap first",
  ))

  bundle_dir = find_latest_demo_export_bundle_dir(case_id, root)
  items.append(SubmissionDemoReadinessItem(
    label="Export bundle",
    status=READINESS_STATUS_READY if bundle_dir else READINESS_STATUS_REMAINING,
    detail=str(bundle_dir) if bundle_dir else "Generate Demo Export Bundle from Export tab",
  ))

  items.append(SubmissionDemoReadinessItem(
    label="Email sending",
    status=READINESS_STATUS_DEMO_OFF,
    detail="demo OFF / not sent — normal for Judge Mode",
  ))
  items.append(SubmissionDemoReadinessItem(
    label="Scheduler",
    status=READINESS_STATUS_DEMO_OFF,
    detail="demo OFF / not started — normal for Judge Mode",
  ))

  return items


def load_evidence_aware_watch_context(
  case_id: str,
  *,
  project_root: Path | str | None = None,
) -> EvidenceAwareWatchContext | None:
  root = _project_root(project_root)
  gap_dir = find_latest_evidence_aware_gap_dir(case_id, root)
  if not gap_dir or not is_evidence_aware_gap_pack(gap_dir):
    return None

  bind_dir = find_latest_claim_example_links_dir(case_id, root)
  watch_path = gap_dir / "watch_profile_update_proposal.md"
  digest_path = gap_dir / "digest_summary.md"
  checklist_path = gap_dir / "human_review_checklist.md"
  gap_csv = gap_dir / "gap_next_actions.csv"

  report = build_evidence_aware_gap_report(case_id, project_root=root)
  top3 = build_top3_next_actions_from_evidence_gaps(report) if report.gaps else []
  watch_text = _read_text(watch_path)
  digest_text = _read_text(digest_path)

  bullets: list[str] = []
  for line in watch_text.splitlines():
    stripped = line.strip()
    if stripped.startswith("- "):
      bullets.append(stripped[2:])

  subject = f"[Digest preview] {case_id} — Evidence-aware Gap review tasks (not sent)"
  if report.summaries:
    ready = sum(s.ready_for_human_review_count for s in report.summaries)
    if ready:
      subject = f"[Digest preview] {case_id} — {ready} review-ready claim gaps (not sent)"

  ctx = EvidenceAwareWatchContext(
    case_id=case_id,
    gap_output_dir=str(gap_dir),
    claim_example_links_dir=str(bind_dir) if bind_dir else "",
    watch_profile_path=str(watch_path) if watch_path.exists() else "",
    digest_summary_path=str(digest_path) if digest_path.exists() else "",
    human_review_checklist_path=str(checklist_path) if checklist_path.exists() else "",
    gap_next_actions_csv=str(gap_csv) if gap_csv.exists() else "",
    digest_subject_draft=subject,
    digest_preview_text=digest_text,
    watch_profile_text=watch_text,
    top3_action_titles=[a.action_title for a in top3],
    watch_proposal_bullets=bullets[:10],
    email_sent=False,
    scheduler_started=False,
    demo_mode=True,
  )
  if not watch_path.exists():
    ctx.warnings.append("watch_profile_update_proposal.md missing — re-generate evidence-aware Gap")
  if not digest_path.exists():
    ctx.warnings.append("digest_summary.md missing — re-generate evidence-aware Gap")
  return ctx


def get_demo_export_bundle_dir(project_root: Path | str | None = None) -> Path:
  root = _project_root(project_root)
  return root / "outputs" / LOCAL_DEMO_EXPORT_SUBDIR


def find_latest_demo_export_bundle_dir(
  case_id: str | None = None,
  project_root: Path | str | None = None,
) -> Path | None:
  base = get_demo_export_bundle_dir(project_root)
  if not base.is_dir():
    return None
  candidates = [
    p for p in base.iterdir()
    if p.is_dir() and (case_id is None or p.name.startswith(f"{case_id}_"))
  ]
  if not candidates:
    return None
  return max(candidates, key=lambda p: p.stat().st_mtime)


def _demo_summary_md(case_id: str, ctx: EvidenceAwareWatchContext | None, readiness: list[SubmissionDemoReadinessItem]) -> str:
  lines = [
    f"# Demo Summary — {case_id}",
    "",
    "Evidence-aware Gap / Next Actions を中心とした提出デモサマリーです。",
    "Evidenceは裏取り候補、Gapは未確認事項です。",
    "",
    "## Demo readiness",
  ]
  for item in readiness:
    lines.append(f"- **{item.label}**: {item.status} — {item.detail}")
  if ctx:
    lines.extend([
      "",
      "## Evidence-aware Gap output",
      f"- gap dir: {ctx.gap_output_dir}",
      f"- claim-example links: {ctx.claim_example_links_dir or '(missing)'}",
      "",
      "## Top 3 Next Actions (Evidence-aware)",
    ])
    for idx, title in enumerate(ctx.top3_action_titles, start=1):
      lines.append(f"{idx}. {title}")
  lines.extend(["", "## Safety", *[f"- {n}" for n in DEMO_FLOW_SAFETY_NOTICES]])
  return "\n".join(lines)


def _artifact_trace_md(case_id: str, sources: list[tuple[str, Path | None]]) -> str:
  lines = [f"# Demo Artifact Trace — {case_id}", ""]
  for label, path in sources:
    lines.append(f"- **{label}**: {path if path and path.exists() else '(missing)'}")
  return "\n".join(lines)


def export_demo_flow_bundle(
  case_id: str,
  *,
  project_root: Path | str | None = None,
) -> DemoExportBundleResult:
  root = _project_root(project_root)
  stamp = utc_now_iso().replace(":", "").replace("-", "").replace("+00:00", "Z")
  digest = hashlib.sha256(f"{case_id}|demo_export|{stamp}".encode()).hexdigest()[:8]
  out_dir = get_demo_export_bundle_dir(root) / f"{case_id}_{stamp}_{digest}"
  out_dir.mkdir(parents=True, exist_ok=True)

  gap_dir = find_latest_evidence_aware_gap_dir(case_id, root)
  bind_dir = find_latest_claim_example_links_dir(case_id, root)
  shortlist_dir = find_latest_patent_shortlist_dir(case_id, root)
  ctx = load_evidence_aware_watch_context(case_id, project_root=root)
  readiness = build_submission_demo_readiness(case_id, project_root=root)

  copied: list[str] = []
  warnings: list[str] = []
  sources: list[tuple[str, Path | None]] = [
    ("evidence_aware_gap_dir", gap_dir),
    ("claim_example_links_dir", bind_dir),
    ("patent_shortlist_dir", shortlist_dir),
  ]

  def _copy_if_exists(src: Path | None, dest_name: str) -> None:
    if src and src.exists():
      dest = out_dir / dest_name
      shutil.copy2(src, dest)
      copied.append(dest_name)

  if bind_dir:
    _copy_if_exists(bind_dir / "claim_example_links.csv", "latest_claim_example_links.csv")
    _copy_if_exists(bind_dir / "claim_example_binding_summary.csv", "latest_claim_example_binding_summary.csv")
  else:
    warnings.append("claim_example_links.csv not found")

  if gap_dir:
    _copy_if_exists(gap_dir / "gap_next_actions.csv", "latest_gap_next_actions.csv")
    _copy_if_exists(gap_dir / "gap_next_actions_summary.csv", "latest_gap_next_actions_summary.csv")
    _copy_if_exists(gap_dir / "human_review_checklist.md", "human_review_checklist.md")
    _copy_if_exists(gap_dir / "watch_profile_update_proposal.md", "watch_profile_update_proposal.md")
    _copy_if_exists(gap_dir / "digest_summary.md", "digest_summary.md")
  else:
    warnings.append("evidence-aware gap output not found")

  if shortlist_dir:
    for name in ("patent_shortlist_top5.csv", "patent_shortlist.csv"):
      _copy_if_exists(shortlist_dir / name, f"latest_{name}")

  summary_path = out_dir / "demo_summary.md"
  trace_path = out_dir / "demo_artifact_trace.md"
  summary_path.write_text(_demo_summary_md(case_id, ctx, readiness), encoding="utf-8")
  trace_path.write_text(_artifact_trace_md(case_id, sources), encoding="utf-8")
  copied.extend(["demo_summary.md", "demo_artifact_trace.md"])

  manifest = {
    "case_id": case_id,
    "generated_at": utc_now_iso(),
    "generation_method": "demo_flow_export_phase27s7",
    "output_dir": str(out_dir),
    "files": copied,
    "source_paths": {label: str(p) if p else "" for label, p in sources},
    "warnings": warnings,
    "safety_notices": list(DEMO_FLOW_SAFETY_NOTICES),
    "email_sent": False,
    "scheduler_started": False,
  }
  (out_dir / "demo_export_manifest.json").write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2),
    encoding="utf-8",
  )
  copied.append("demo_export_manifest.json")

  return DemoExportBundleResult(
    case_id=case_id,
    output_dir=str(out_dir),
    files=copied,
    source_paths=[str(p) for _, p in sources if p],
    warnings=warnings,
  )
