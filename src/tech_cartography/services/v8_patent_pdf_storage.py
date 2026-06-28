"""Patent PDF storage helpers (Phase 27S.4.2)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.runtime.v8_research_theme_schema import normalize_publication_number
from tech_cartography.services.v8_google_patents_links import (
  patent_pdfs_dir,
  resolve_pdf_upload_status,
  save_patent_pdf_upload,
)
from tech_cartography.services.v8_large_candidate_shortlist import load_top5_publications


def get_patent_pdf_dir(case_id: str, project_root: Path | str) -> Path:
  return patent_pdfs_dir(case_id, project_root)


def get_patent_pdf_path(case_id: str, project_root: Path | str, publication_number: str) -> Path:
  norm = normalize_publication_number(publication_number)
  return get_patent_pdf_dir(case_id, project_root) / f"{norm}.pdf"


def list_uploaded_patent_pdfs(case_id: str, project_root: Path | str) -> list[Path]:
  pdf_dir = get_patent_pdf_dir(case_id, project_root)
  if not pdf_dir.is_dir():
    return []
  return sorted(pdf_dir.glob("*.pdf"))


def save_uploaded_patent_pdf(
  case_id: str,
  project_root: Path | str,
  publication_number: str,
  pdf_bytes: bytes,
  *,
  original_filename: str = "",
  allowed_publications: list[str] | None = None,
) -> Path:
  """Save PDF to cases/{case_id}/patent_pdfs/{publication_number}.pdf."""
  norm = normalize_publication_number(publication_number)
  if not norm:
    raise ValueError("publication_number is required")

  allowed = allowed_publications
  if allowed is None:
    allowed = load_top5_publications(case_id, project_root)
  if allowed:
    allowed_norm = {normalize_publication_number(p) for p in allowed if p}
    if norm not in allowed_norm:
      raise ValueError(f"{norm} は Top5 に含まれていません — 保存をスキップしました")

  return save_patent_pdf_upload(
    case_id=case_id,
    publication_number=norm,
    pdf_bytes=pdf_bytes,
    original_filename=original_filename,
    project_root=project_root,
  )


def get_patent_pdf_upload_info(
  case_id: str,
  project_root: Path | str,
  publication_number: str,
  *,
  session_uploads: dict[str, str] | None = None,
) -> dict[str, str | int | bool]:
  norm = normalize_publication_number(publication_number)
  path = get_patent_pdf_path(case_id, project_root, norm)
  uploaded = resolve_pdf_upload_status(
    norm, case_id=case_id, project_root=project_root, session_uploads=session_uploads,
  ) == "アップロード済み"
  size = path.stat().st_size if path.exists() else 0
  return {
    "publication_number": norm,
    "pdf_path": str(path),
    "file_size": size,
    "uploaded": uploaded,
    "upload_status": "アップロード済み" if uploaded else "未アップロード",
  }
