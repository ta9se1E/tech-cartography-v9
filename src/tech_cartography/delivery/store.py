"""Persist Intelligence Delivery Hub outputs (Phase 24.0 / 24.1)."""

from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tech_cartography.delivery.digest_diff import (
  DigestDiff,
  WeeklyDigestSnapshot,
  build_digest_snapshot,
  compare_digest_snapshots,
  load_snapshot_file,
  save_digest_snapshot,
)
from tech_cartography.delivery.email_outbox import (
  EmailDraft,
  STATUS_BLOCKED_MISSING_ADAPTER,
  STATUS_DRAFT_SAVED,
  STATUS_PREVIEW_ONLY,
  build_email_draft_from_weekly_digest,
  save_email_draft,
)
from tech_cartography.delivery.email_sender import can_send_email, send_email_smtp
from tech_cartography.delivery.overview import build_tab_overviews, render_overview_page_md
from tech_cartography.delivery.report_bundle import ReportBundle, build_report_bundle
from tech_cartography.delivery.weekly_digest import WeeklyDigest, build_weekly_digest


@dataclass
class DeliveryPackageResult:
  publication_number: str
  output_dir: str
  paths: dict[str, Path] = field(default_factory=dict)
  snapshot: WeeklyDigestSnapshot | None = None
  diff: DigestDiff | None = None
  is_initial_digest: bool = False
  planned_files: list[str] = field(default_factory=list)
  email_draft: EmailDraft | None = None
  email_send_result: dict[str, Any] | None = None


def save_delivery_outputs(
  *,
  publication_number: str,
  output_dir: Path | str,
  report: ReportBundle,
  digest: WeeklyDigest,
  diff: DigestDiff,
  overview_md: str,
  include_zip: bool = True,
) -> dict[str, Path]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  pub = str(publication_number).strip()

  paths: dict[str, Path] = {}
  paths["overview_page_md"] = out / "overview_page.md"
  paths["intelligence_report_md"] = out / f"intelligence_report_{pub}.md"
  paths["weekly_digest_md"] = out / f"weekly_digest_preview_{pub}.md"
  paths["weekly_digest_html"] = out / f"weekly_digest_preview_{pub}.html"
  paths["digest_diff_md"] = out / f"digest_diff_{pub}.md"

  paths["overview_page_md"].write_text(overview_md, encoding="utf-8")
  paths["intelligence_report_md"].write_text(report.markdown, encoding="utf-8")
  paths["weekly_digest_md"].write_text(digest.markdown_body, encoding="utf-8")
  paths["weekly_digest_html"].write_text(digest.html_body, encoding="utf-8")
  paths["digest_diff_md"].write_text(diff.diff_markdown, encoding="utf-8")

  if include_zip:
    zip_path = out / f"tech_cartography_report_bundle_{pub}.zip"
    _build_zip_bundle(
      zip_path,
      report_path=paths["intelligence_report_md"],
      digest_md_path=paths["weekly_digest_md"],
      diff_path=paths["digest_diff_md"],
      overview_path=paths["overview_page_md"],
      source_artifacts=report.source_artifacts,
      pub=pub,
      project_root=out.parent.parent if out.name == "delivery" else out.parent,
    )
    paths["report_bundle_zip"] = zip_path

  return paths


def _build_zip_bundle(
  zip_path: Path,
  *,
  report_path: Path,
  digest_md_path: Path,
  diff_path: Path,
  overview_path: Path,
  source_artifacts: dict[str, str],
  pub: str,
  project_root: Path,
) -> None:
  watch_brief = project_root / "outputs" / "strategic_watch_briefs" / pub / "strategic_watch_brief.md"
  index_lines = ["# Source Artifact Index", ""]
  for key, path_str in source_artifacts.items():
    index_lines.append(f"- {key}: {path_str}")

  with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
    for src in (report_path, digest_md_path, diff_path, overview_path):
      if src.exists():
        zf.write(src, arcname=src.name)
    if watch_brief.exists():
      zf.write(watch_brief, arcname=watch_brief.name)
    zf.writestr("source_artifact_index.md", "\n".join(index_lines))


def dry_run_delivery_package(
  publication_number: str,
  project_root: Path | str = ".",
  output_dir: Path | str = "outputs/delivery",
) -> dict[str, Any]:
  root = Path(project_root)
  pub = str(publication_number).strip()
  report = build_report_bundle(pub, root)
  paths = report.source_artifacts
  artifact_checks = {key: Path(path).exists() for key, path in paths.items()}
  planned = [
    "overview_page.md",
    f"intelligence_report_{pub}.md",
    f"weekly_digest_preview_{pub}.md",
    f"weekly_digest_preview_{pub}.html",
    f"digest_diff_{pub}.md",
    "latest_snapshot.json",
    f"snapshots/{{timestamp}}_{pub}.json",
    f"tech_cartography_report_bundle_{pub}.zip",
    "email_outbox/email_draft_{pub}.md",
    "email_outbox/email_draft_{pub}.html",
    "email_outbox/email_draft_{pub}.json",
    "email_outbox/outbox_index.json",
  ]
  return {
    "publication_number": pub,
    "artifact_checks": artifact_checks,
    "planned_files": planned,
    "section_count": len(report.sections),
    "missing_sections": sum(1 for s in report.sections if s.missing_artifacts),
  }


def build_delivery_package(
  publication_number: str,
  project_root: Path | str = ".",
  output_dir: Path | str = "outputs/delivery",
  *,
  previous_snapshot_path: Path | str | None = None,
  include_zip: bool = True,
  build_email_draft: bool = False,
  email_to: list[str] | str | None = None,
  email_cc: list[str] | str | None = None,
  subject_prefix: str | None = None,
  send_email: bool = False,
) -> DeliveryPackageResult:
  root = Path(project_root)
  out = Path(output_dir)
  if not out.is_absolute():
    out = root / out
  pub = str(publication_number).strip()

  overview_md = render_overview_page_md()
  report = build_report_bundle(pub, root)
  current_snapshot = build_digest_snapshot(root, pub)

  previous: WeeklyDigestSnapshot | None = None
  if previous_snapshot_path:
    previous = load_snapshot_file(previous_snapshot_path)
  else:
    snapshots_dir = out / "snapshots"
    if snapshots_dir.exists():
      existing = sorted(snapshots_dir.glob(f"*_{pub}.json"))
      if existing:
        previous = load_snapshot_file(existing[-1])

  diff = compare_digest_snapshots(previous, current_snapshot)
  digest = build_weekly_digest(pub, root, diff=diff, snapshot=current_snapshot)

  save_digest_snapshot(current_snapshot, out)
  paths = save_delivery_outputs(
    publication_number=pub,
    output_dir=out,
    report=report,
    digest=digest,
    diff=diff,
    overview_md=overview_md,
    include_zip=include_zip,
  )

  email_draft: EmailDraft | None = None
  email_send_result: dict[str, Any] | None = None

  if build_email_draft:
    draft_status = STATUS_DRAFT_SAVED
    if not email_to and not send_email:
      draft_status = STATUS_PREVIEW_ONLY

    email_draft = build_email_draft_from_weekly_digest(
      digest,
      publication_number=pub,
      to=email_to,
      cc=email_cc,
      subject_prefix=subject_prefix,
      attachments=[
        str(paths.get("intelligence_report_md", "")),
        str(paths.get("digest_diff_md", "")),
      ],
      status=draft_status,
      send_requested=send_email,
    )

    draft_paths = save_email_draft(email_draft, out)
    paths.update(draft_paths)

    if send_email:
      if not email_to:
        pass  # status already blocked_missing_recipient from build_email_draft_from_weekly_digest
      else:
        ready, _ = can_send_email()
        if not ready:
          email_draft.status = STATUS_BLOCKED_MISSING_ADAPTER
        else:
          email_send_result = send_email_smtp(email_draft)
          save_email_draft(email_draft, out)

  return DeliveryPackageResult(
    publication_number=pub,
    output_dir=str(out),
    paths=paths,
    snapshot=current_snapshot,
    diff=diff,
    is_initial_digest=diff.is_initial,
    email_draft=email_draft,
    email_send_result=email_send_result,
  )
