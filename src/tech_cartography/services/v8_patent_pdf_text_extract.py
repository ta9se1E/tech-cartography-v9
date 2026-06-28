"""Patent PDF text extraction service (Phase 27S.1) — pypdf only, no OCR/LLM."""

from __future__ import annotations

import csv
import hashlib
import io
from pathlib import Path

from tech_cartography.runtime.v8_patent_pdf_text_schema import (
  PDF_TEXT_EXTRACTION_NOTICES,
  PatentPdfTextExtractionResult,
  PatentPdfTextPage,
)
from tech_cartography.runtime.v8_research_theme_schema import normalize_publication_number
from tech_cartography.runtime.v8_sources_schema import utc_now_iso
from tech_cartography.services.v8_google_patents_links import patent_pdfs_dir
from tech_cartography.services.v8_large_candidate_shortlist import load_top5_publications
from tech_cartography.services.v8_sources_table import project_root_from_here

OUTPUT_SUBDIR = "local_v8_pdf_text_extract"
DEFAULT_MIN_TEXT_CHARS_PER_PAGE = 30
DEFAULT_MIN_TOTAL_TEXT = 100
EXTRACTION_METHOD = "pypdf"


def _pypdf_available() -> bool:
  try:
    import pypdf  # noqa: F401
    return True
  except ImportError:
    return False


def find_uploaded_patent_pdfs(case_id: str, project_root: Path | str) -> list[Path]:
  pdf_dir = patent_pdfs_dir(case_id, project_root)
  if not pdf_dir.is_dir():
    return []
  return sorted(pdf_dir.glob("*.pdf"), key=lambda p: p.name)


def infer_publication_number_from_pdf_path(pdf_path: Path) -> str:
  return normalize_publication_number(pdf_path.stem)


def _empty_result(
  *,
  case_id: str,
  publication_number: str,
  source_file: str,
  status: str,
  warning: str,
  needs_ocr: bool = True,
  extraction_method: str = EXTRACTION_METHOD,
) -> PatentPdfTextExtractionResult:
  return PatentPdfTextExtractionResult(
    case_id=case_id,
    publication_number=publication_number,
    source_file=source_file,
    page_count=0,
    total_text_length=0,
    extracted_pages=0,
    needs_ocr=needs_ocr,
    extraction_method=extraction_method,
    pages=[],
    status=status,
    warning=warning,
  )


def extract_text_from_pdf(
  pdf_path: Path,
  case_id: str,
  publication_number: str,
  *,
  max_pages: int | None = None,
  min_text_chars_per_page: int = DEFAULT_MIN_TEXT_CHARS_PER_PAGE,
) -> PatentPdfTextExtractionResult:
  """Extract text with pypdf — never calls Gemini/OpenAI/OCR."""
  norm_pub = normalize_publication_number(publication_number) or infer_publication_number_from_pdf_path(pdf_path)
  source_file = str(pdf_path)

  if not pdf_path.exists():
    return _empty_result(
      case_id=case_id,
      publication_number=norm_pub,
      source_file=source_file,
      status="file_missing",
      warning=f"PDF not found: {pdf_path}",
    )

  if not _pypdf_available():
    return _empty_result(
      case_id=case_id,
      publication_number=norm_pub,
      source_file=source_file,
      status="library_missing",
      warning="pypdf が未インストールです — pip install pypdf",
      extraction_method="none",
    )

  try:
    from pypdf import PdfReader

    reader = PdfReader(str(pdf_path))
    page_count = len(reader.pages)
    limit = page_count if max_pages is None else min(page_count, max_pages)
    pages: list[PatentPdfTextPage] = []
    low_text_pages = 0

    for idx in range(limit):
      page_no = idx + 1
      try:
        raw = reader.pages[idx].extract_text() or ""
      except Exception as exc:
        raw = ""
        page_warning = f"page {page_no} extract error: {exc}"
      else:
        page_warning = None

      text = raw.strip()
      text_len = len(text)
      page_needs_ocr = text_len < min_text_chars_per_page
      if page_needs_ocr:
        low_text_pages += 1

      pages.append(PatentPdfTextPage(
        case_id=case_id,
        publication_number=norm_pub,
        source_file=source_file,
        page_no=page_no,
        text=text,
        text_length=text_len,
        extraction_method=EXTRACTION_METHOD,
        needs_ocr=page_needs_ocr,
        warning=page_warning,
      ))

    total_text = sum(p.text_length for p in pages)
    extracted_pages = sum(1 for p in pages if p.text_length > 0)
    mostly_low = limit > 0 and low_text_pages >= max(1, int(limit * 0.8))
    needs_ocr = (
      total_text < DEFAULT_MIN_TOTAL_TEXT
      or mostly_low
      or extracted_pages == 0
    )

    if total_text == 0:
      status = "needs_ocr" if page_count > 0 else "empty"
    elif needs_ocr:
      status = "needs_ocr"
    else:
      status = "ok"

    warning = None
    if status == "needs_ocr":
      warning = "抽出テキストが少ない — 画像PDFの可能性（OCRは次Phase）"
    elif status == "empty":
      warning = "ページからテキストを抽出できませんでした"

    return PatentPdfTextExtractionResult(
      case_id=case_id,
      publication_number=norm_pub,
      source_file=source_file,
      page_count=page_count,
      total_text_length=total_text,
      extracted_pages=extracted_pages,
      needs_ocr=needs_ocr,
      extraction_method=EXTRACTION_METHOD,
      pages=pages,
      status=status,
      warning=warning,
    )
  except Exception as exc:
    return _empty_result(
      case_id=case_id,
      publication_number=norm_pub,
      source_file=source_file,
      status="error",
      warning=str(exc),
    )


def extract_text_from_uploaded_top5_pdfs(
  case_id: str,
  project_root: Path | str,
  publication_numbers: list[str] | None = None,
  *,
  max_pages: int | None = None,
) -> list[PatentPdfTextExtractionResult]:
  root = Path(project_root)
  pubs = publication_numbers or load_top5_publications(case_id, root)
  if not pubs:
    pdfs = find_uploaded_patent_pdfs(case_id, root)
    pubs = [infer_publication_number_from_pdf_path(p) for p in pdfs]

  by_pub = {infer_publication_number_from_pdf_path(p): p for p in find_uploaded_patent_pdfs(case_id, root)}
  results: list[PatentPdfTextExtractionResult] = []
  for pub in pubs:
    norm = normalize_publication_number(pub)
    pdf_path = by_pub.get(norm)
    if not pdf_path:
      results.append(_empty_result(
        case_id=case_id,
        publication_number=norm,
        source_file=str(patent_pdfs_dir(case_id, root) / f"{norm}.pdf"),
        status="file_missing",
        warning="PDF未アップロード",
        needs_ocr=False,
      ))
      continue
    results.append(extract_text_from_pdf(
      pdf_path, case_id, norm, max_pages=max_pages,
    ))
  return results


def _output_pack_dir(case_id: str, output_root: Path) -> Path:
  stamp = utc_now_iso().replace(":", "").replace("-", "").replace("+00:00", "Z")
  digest = hashlib.sha256(f"{case_id}|pdf_text|{stamp}".encode()).hexdigest()[:8]
  return output_root / OUTPUT_SUBDIR / f"{case_id}_{stamp}_{digest}"


def write_pdf_text_outputs(
  case_id: str,
  results: list[PatentPdfTextExtractionResult],
  output_root: Path | str,
) -> Path:
  root = Path(output_root)
  out_dir = _output_pack_dir(case_id, root)
  out_dir.mkdir(parents=True, exist_ok=True)

  raw_csv = out_dir / "publication_fulltext_raw.csv"
  summary_csv = out_dir / "pdf_text_extraction_summary.csv"
  raw_md = out_dir / "publication_fulltext_raw.md"
  summary_md = out_dir / "pdf_text_extraction_summary.md"

  raw_fields = [
    "case_id", "publication_number", "source_file", "page_no", "text",
    "text_length", "extraction_method", "needs_ocr", "warning",
  ]
  summary_fields = [
    "case_id", "publication_number", "source_file", "page_count", "extracted_pages",
    "total_text_length", "needs_ocr", "extraction_method", "status", "warning",
  ]

  with raw_csv.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=raw_fields)
    writer.writeheader()
    for result in results:
      for page in result.pages:
        writer.writerow({
          "case_id": page.case_id,
          "publication_number": page.publication_number,
          "source_file": page.source_file,
          "page_no": page.page_no,
          "text": page.text,
          "text_length": page.text_length,
          "extraction_method": page.extraction_method,
          "needs_ocr": page.needs_ocr,
          "warning": page.warning or "",
        })

  with summary_csv.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=summary_fields)
    writer.writeheader()
    for result in results:
      writer.writerow({
        "case_id": result.case_id,
        "publication_number": result.publication_number,
        "source_file": result.source_file,
        "page_count": result.page_count,
        "extracted_pages": result.extracted_pages,
        "total_text_length": result.total_text_length,
        "needs_ocr": result.needs_ocr,
        "extraction_method": result.extraction_method,
        "status": result.status,
        "warning": result.warning or "",
      })

  raw_lines = [
    f"# Publication fulltext raw — {case_id}",
    "",
    *[f"- {n}" for n in PDF_TEXT_EXTRACTION_NOTICES],
    "",
  ]
  for result in results:
    raw_lines.append(f"## {result.publication_number}")
    for page in result.pages[:20]:
      preview = (page.text[:500] + "…") if len(page.text) > 500 else page.text
      raw_lines.append(f"### page {page.page_no} (len={page.text_length})")
      raw_lines.append(preview or "（空）")
      raw_lines.append("")
  raw_md.write_text("\n".join(raw_lines), encoding="utf-8")

  sum_lines = [
    f"# PDF text extraction summary — {case_id}",
    "",
    "| publication_number | status | total_text_length | needs_ocr | warning |",
    "| --- | --- | --- | --- | --- |",
  ]
  for result in results:
    sum_lines.append(
      f"| {result.publication_number} | {result.status} | {result.total_text_length} | "
      f"{result.needs_ocr} | {(result.warning or '')[:60]} |"
    )
  summary_md.write_text("\n".join(sum_lines), encoding="utf-8")

  for result in results:
    result.output_dir = str(out_dir)

  return out_dir


def find_latest_pdf_text_extract_dir(
  case_id: str,
  project_root: Path | str | None = None,
) -> Path | None:
  root = Path(project_root or project_root_from_here())
  base = root / "outputs" / OUTPUT_SUBDIR
  if not base.is_dir():
    return None
  dirs = [p for p in base.iterdir() if p.is_dir() and p.name.startswith(f"{case_id}_")]
  if not dirs:
    return None
  return max(dirs, key=lambda p: p.stat().st_mtime)


def load_extraction_summary_from_dir(pack_dir: Path | str) -> dict[str, dict[str, str | int | bool]]:
  """Load pdf_text_extraction_summary.csv as pub -> row dict."""
  path = Path(pack_dir) / "pdf_text_extraction_summary.csv"
  if not path.exists():
    return {}
  by_pub: dict[str, dict] = {}
  with path.open(encoding="utf-8", newline="") as handle:
    for row in csv.DictReader(handle):
      pub = normalize_publication_number(str(row.get("publication_number", "")))
      if pub:
        by_pub[pub] = row
  return by_pub


def get_pdf_pipeline_status(
  case_id: str,
  publication_number: str,
  project_root: Path | str,
) -> dict[str, str | bool | int]:
  """Combined upload + extraction status for UI."""
  from tech_cartography.services.v8_google_patents_links import resolve_pdf_upload_status

  root = Path(project_root)
  norm = normalize_publication_number(publication_number)
  uploaded = resolve_pdf_upload_status(norm, case_id=case_id, project_root=root)
  pdf_uploaded = uploaded == "アップロード済み"

  latest = find_latest_pdf_text_extract_dir(case_id, root)
  summary = load_extraction_summary_from_dir(latest) if latest else {}
  row = summary.get(norm, {})

  text_extracted = bool(row) and str(row.get("status", "")) not in {"", "file_missing"}
  needs_ocr = str(row.get("needs_ocr", "")).lower() in {"true", "1"} or row.get("needs_ocr") is True
  total_len = int(row.get("total_text_length") or 0) if row else 0
  status = str(row.get("status") or "")

  if not pdf_uploaded:
    next_action = "Google PatentsからPDF取得が必要"
  elif not text_extracted:
    next_action = "入力タブで Extract PDF text を実行"
  elif needs_ocr:
    next_action = "画像PDFの可能性 — 将来OCR対象"
  else:
    next_action = "次Phaseで examples / comparative examples を抽出"

  return {
    "pdf_uploaded": pdf_uploaded,
    "text_extracted": text_extracted,
    "needs_ocr": needs_ocr,
    "total_text_length": total_len,
    "extraction_status": status,
    "next_action": next_action,
  }
