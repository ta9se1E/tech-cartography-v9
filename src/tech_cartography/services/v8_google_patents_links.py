"""Google Patents URL builder for Top5 PDF collection (Phase 27S.0)."""

from __future__ import annotations

import csv
import hashlib
from pathlib import Path

from tech_cartography.runtime.v8_google_patents_links_schema import (
  GOOGLE_PATENTS_SAFETY_NOTICES,
  PDF_DOWNLOAD_INSTRUCTION,
  PDF_UPLOAD_NEXT_ACTION,
  GooglePatentsLink,
  GooglePatentsLinksExport,
)
from tech_cartography.runtime.v8_research_theme_schema import normalize_publication_number
from tech_cartography.runtime.v8_sources_schema import utc_now_iso
from tech_cartography.services.v8_deep_dive_shortlist import load_top5_candidate_records
from tech_cartography.services.v8_large_candidate_shortlist import load_top5_publications
from tech_cartography.services.v8_sources_table import project_root_from_here

GOOGLE_PATENTS_BASE = "https://patents.google.com/patent"
GOOGLE_PATENTS_SEARCH_BASE = "https://patents.google.com/"
LOCAL_LINKS_SUBDIR = "local_v8_google_patents_links"


def build_google_patents_url(publication_number: str, *, language: str = "en") -> str:
  """Build Google Patents page URL — not a direct PDF URL."""
  norm = normalize_publication_number(publication_number)
  if not norm:
    return ""
  lang = (language or "en").strip().lower()
  return f"{GOOGLE_PATENTS_BASE}/{norm}/{lang}"


def build_google_patents_search_url(publication_number: str) -> str:
  norm = normalize_publication_number(publication_number)
  if not norm:
    return GOOGLE_PATENTS_SEARCH_BASE
  return f"{GOOGLE_PATENTS_SEARCH_BASE}?q={norm}"


def patent_pdfs_dir(case_id: str, project_root: Path | str | None = None) -> Path:
  root = Path(project_root or project_root_from_here())
  return root / "cases" / case_id / "patent_pdfs"


def resolve_pdf_upload_status(
  publication_number: str,
  *,
  case_id: str,
  project_root: Path | str | None = None,
  session_uploads: dict[str, str] | None = None,
) -> str:
  """Return アップロード済み if a matching PDF exists locally or in session."""
  norm = normalize_publication_number(publication_number)
  if session_uploads:
    for key, _name in session_uploads.items():
      if normalize_publication_number(key) == norm:
        return "アップロード済み"
  pdf_dir = patent_pdfs_dir(case_id, project_root)
  if not pdf_dir.is_dir():
    return "未アップロード"
  for path in pdf_dir.glob("*.pdf"):
    stem_norm = normalize_publication_number(path.stem)
    if stem_norm == norm or norm in normalize_publication_number(path.name):
      return "アップロード済み"
  return "未アップロード"


def save_patent_pdf_upload(
  *,
  case_id: str,
  publication_number: str,
  pdf_bytes: bytes,
  original_filename: str,
  project_root: Path | str | None = None,
) -> Path:
  """Persist uploaded PDF for upload-status tracking (no parsing)."""
  norm = normalize_publication_number(publication_number)
  if not norm:
    raise ValueError("publication_number is required")
  out_dir = patent_pdfs_dir(case_id, project_root)
  out_dir.mkdir(parents=True, exist_ok=True)
  out_path = out_dir / f"{norm}.pdf"
  out_path.write_bytes(pdf_bytes)
  return out_path


def build_top5_google_patents_links(
  case_id: str,
  project_root: Path | str | None = None,
  *,
  session_uploads: dict[str, str] | None = None,
) -> list[GooglePatentsLink]:
  root = Path(project_root or project_root_from_here())
  pubs = load_top5_publications(case_id, root)
  meta = load_top5_candidate_records(case_id, root)
  links: list[GooglePatentsLink] = []
  for i, pub in enumerate(pubs, start=1):
    if not pub:
      continue
    info = meta.get(pub, {})
    links.append(GooglePatentsLink(
      case_id=case_id,
      publication_number=normalize_publication_number(pub),
      title=info.get("title", ""),
      assignee=info.get("organization", ""),
      year=info.get("year", ""),
      google_patents_url=build_google_patents_url(pub),
      google_patents_search_url=build_google_patents_search_url(pub),
      pdf_download_instruction=PDF_DOWNLOAD_INSTRUCTION,
      pdf_upload_status=resolve_pdf_upload_status(
        pub, case_id=case_id, project_root=root, session_uploads=session_uploads,
      ),
      next_action=PDF_UPLOAD_NEXT_ACTION,
      rank=i,
    ))
  return links


def _links_export_dir(case_id: str, project_root: Path) -> Path:
  stamp = utc_now_iso().replace(":", "").replace("-", "").replace("+00:00", "Z")
  digest = hashlib.sha256(f"{case_id}|{stamp}".encode()).hexdigest()[:8]
  return project_root / "outputs" / LOCAL_LINKS_SUBDIR / f"{case_id}_{stamp}_{digest}"


def links_to_csv_text(links: list[GooglePatentsLink]) -> str:
  import io

  buf = io.StringIO()
  fieldnames = [
    "case_id", "publication_number", "title", "assignee", "year",
    "google_patents_url", "pdf_download_instruction", "pdf_upload_status", "next_action",
  ]
  writer = csv.DictWriter(buf, fieldnames=fieldnames)
  writer.writeheader()
  for link in links:
    writer.writerow({
      "case_id": link.case_id,
      "publication_number": link.publication_number,
      "title": link.title,
      "assignee": link.assignee,
      "year": link.year,
      "google_patents_url": link.google_patents_url,
      "pdf_download_instruction": link.pdf_download_instruction,
      "pdf_upload_status": link.pdf_upload_status,
      "next_action": link.next_action,
    })
  return buf.getvalue()


def links_to_markdown(links: list[GooglePatentsLink]) -> str:
  lines = [
    f"# Top5 Google Patents Links — {links[0].case_id if links else ''}",
    "",
    "## Safety",
    *[f"- {n}" for n in GOOGLE_PATENTS_SAFETY_NOTICES],
    "",
    "| publication_number | title | Google Patents | pdf_upload_status | next_action |",
    "| --- | --- | --- | --- | --- |",
  ]
  for link in links:
    title = (link.title or "—")[:60].replace("|", "/")
    lines.append(
      f"| {link.publication_number} | {title} | {link.google_patents_url} | "
      f"{link.pdf_upload_status} | {link.next_action} |"
    )
  return "\n".join(lines)


def export_google_patents_links(
  links: list[GooglePatentsLink],
  *,
  project_root: Path | str | None = None,
) -> GooglePatentsLinksExport:
  root = Path(project_root or project_root_from_here())
  case_id = links[0].case_id if links else "unknown"
  out_dir = _links_export_dir(case_id, root)
  out_dir.mkdir(parents=True, exist_ok=True)
  csv_path = out_dir / "google_patents_links.csv"
  md_path = out_dir / "google_patents_links.md"
  csv_path.write_text(links_to_csv_text(links), encoding="utf-8")
  md_path.write_text(links_to_markdown(links), encoding="utf-8")
  return GooglePatentsLinksExport(
    case_id=case_id,
    output_dir=str(out_dir),
    csv_path=str(csv_path),
    md_path=str(md_path),
    link_count=len(links),
  )
