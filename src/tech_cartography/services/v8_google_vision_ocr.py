"""Google Cloud Vision OCR fallback for patent PDFs (Phase 27S.5)."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import re
from pathlib import Path

from tech_cartography.runtime.v8_google_vision_ocr_schema import (
  EXTRACTION_METHOD_VISION,
  GOOGLE_VISION_OCR_NOTICES,
  OCR_HUMAN_REVIEW_WARNING,
  GoogleVisionOcrPage,
  GoogleVisionOcrResult,
)
from tech_cartography.runtime.v8_research_theme_schema import normalize_publication_number
from tech_cartography.runtime.v8_sources_schema import utc_now_iso
from tech_cartography.services.v8_patent_pdf_storage import get_patent_pdf_path
from tech_cartography.services.v8_sources_table import project_root_from_here

ENABLE_GOOGLE_VISION_OCR_ENV = "ENABLE_GOOGLE_VISION_OCR"
GOOGLE_CLOUD_PROJECT_ENV = "GOOGLE_CLOUD_PROJECT"
GOOGLE_VISION_OCR_GCS_BUCKET_ENV = "GOOGLE_VISION_OCR_GCS_BUCKET"
GOOGLE_VISION_OCR_GCS_PREFIX_ENV = "GOOGLE_VISION_OCR_GCS_PREFIX"
GOOGLE_VISION_OCR_MAX_PAGES_ENV = "GOOGLE_VISION_OCR_MAX_PAGES"
GOOGLE_VISION_OCR_TIMEOUT_SEC_ENV = "GOOGLE_VISION_OCR_TIMEOUT_SEC"

OUTPUT_SUBDIR = "local_v8_google_vision_ocr"
DEFAULT_GCS_PREFIX = "tech-cartography-v8/ocr"
DEFAULT_MAX_PAGES = 20
DEFAULT_TIMEOUT_SEC = 300


def _env_bool(name: str, default: bool = False) -> bool:
  raw = os.getenv(name)
  if raw is None:
    return default
  return raw.strip().lower() in {"1", "true", "yes", "on"}


def is_google_vision_ocr_enabled() -> bool:
  return _env_bool(ENABLE_GOOGLE_VISION_OCR_ENV, False)


def get_google_cloud_project() -> str | None:
  value = os.getenv(GOOGLE_CLOUD_PROJECT_ENV, "").strip()
  return value or None


def get_ocr_bucket_name() -> str | None:
  value = os.getenv(GOOGLE_VISION_OCR_GCS_BUCKET_ENV, "").strip()
  return value or None


def get_ocr_prefix() -> str:
  return os.getenv(GOOGLE_VISION_OCR_GCS_PREFIX_ENV, DEFAULT_GCS_PREFIX).strip().strip("/")


def get_ocr_max_pages() -> int | None:
  raw = os.getenv(GOOGLE_VISION_OCR_MAX_PAGES_ENV, "").strip()
  if not raw:
    return DEFAULT_MAX_PAGES
  try:
    return int(raw)
  except ValueError:
    return DEFAULT_MAX_PAGES


def get_ocr_timeout_sec() -> int:
  raw = os.getenv(GOOGLE_VISION_OCR_TIMEOUT_SEC_ENV, "").strip()
  if not raw:
    return DEFAULT_TIMEOUT_SEC
  try:
    return int(raw)
  except ValueError:
    return DEFAULT_TIMEOUT_SEC


def vision_ocr_availability_message() -> str:
  if not is_google_vision_ocr_enabled():
    return f"{ENABLE_GOOGLE_VISION_OCR_ENV}=false — Google Vision OCR disabled"
  if not get_ocr_bucket_name():
    return f"{GOOGLE_VISION_OCR_GCS_BUCKET_ENV} not set — OCR bucket missing"
  missing = _missing_dependencies()
  if missing:
    return f"Missing packages: {', '.join(missing)}"
  return "Google Vision OCR ready — explicit button trigger only"


def _missing_dependencies() -> list[str]:
  missing: list[str] = []
  try:
    import google.cloud.vision  # noqa: F401
  except ImportError:
    missing.append("google-cloud-vision")
  try:
    import google.cloud.storage  # noqa: F401
  except ImportError:
    missing.append("google-cloud-storage")
  return missing


def build_ocr_gcs_prefix(case_id: str, publication_number: str) -> str:
  norm = normalize_publication_number(publication_number)
  base = get_ocr_prefix()
  return f"{base}/{case_id}/{norm}"


def upload_pdf_to_gcs(local_pdf_path: Path, bucket_name: str, gcs_prefix: str) -> str:
  from google.cloud import storage

  client = storage.Client(project=get_google_cloud_project())
  bucket = client.bucket(bucket_name)
  blob_name = f"{gcs_prefix.rstrip('/')}/input/{local_pdf_path.name}"
  blob = bucket.blob(blob_name)
  blob.upload_from_filename(str(local_pdf_path), content_type="application/pdf")
  return f"gs://{bucket_name}/{blob_name}"


def start_vision_pdf_ocr(
  gcs_input_uri: str,
  gcs_output_uri: str,
  max_pages: int | None,
  *,
  timeout_sec: int | None = None,
):
  from google.cloud import vision

  client = vision.ImageAnnotatorClient()
  gcs_source = vision.GcsSource(uri=gcs_input_uri)
  input_config = vision.InputConfig(gcs_source=gcs_source, mime_type="application/pdf")
  gcs_destination = vision.GcsDestination(uri=gcs_output_uri)
  output_config = vision.OutputConfig(gcs_destination=gcs_destination, batch_size=1)
  feature = vision.Feature(type_=vision.Feature.Type.DOCUMENT_TEXT_DETECTION)
  request = vision.AsyncAnnotateFileRequest(
    features=[feature],
    input_config=input_config,
    output_config=output_config,
  )
  operation = client.async_batch_annotate_files(requests=[request])
  if timeout_sec is not None:
    operation.result(timeout=timeout_sec)
  return operation


def download_vision_ocr_json_outputs(
  bucket_name: str,
  output_prefix: str,
  local_output_dir: Path,
) -> list[Path]:
  from google.cloud import storage

  client = storage.Client(project=get_google_cloud_project())
  bucket = client.bucket(bucket_name)
  prefix = output_prefix.rstrip("/") + "/"
  local_output_dir.mkdir(parents=True, exist_ok=True)
  paths: list[Path] = []
  for blob in bucket.list_blobs(prefix=prefix):
    if not blob.name.endswith(".json"):
      continue
    local_path = local_output_dir / Path(blob.name).name
    blob.download_to_filename(str(local_path))
    paths.append(local_path)
  return sorted(paths, key=_natural_sort_key)


def _natural_sort_key(path: Path) -> tuple:
  parts: list[object] = []
  for chunk in re.split(r"(\d+)", path.name):
    if chunk.isdigit():
      parts.append(int(chunk))
    else:
      parts.append(chunk.lower())
  return tuple(parts)


def sort_vision_ocr_json_paths(json_paths: list[Path]) -> list[Path]:
  return sorted(json_paths, key=_natural_sort_key)


def _page_no_from_json_filename(json_path: Path, fallback: int) -> int:
  match = re.search(r"output-(\d+)-to-\d+\.json", json_path.name, re.IGNORECASE)
  if match:
    return int(match.group(1))
  match = re.search(r"(\d+)", json_path.stem)
  if match:
    return int(match.group(1))
  return fallback


def _text_from_full_text_annotation(annotation: dict) -> str:
  full_text = str(annotation.get("text") or "").strip()
  if full_text:
    return full_text
  pages = annotation.get("pages") or []
  if pages:
    parts: list[str] = []
    for page in pages:
      page_text = _text_from_page_dict(page)
      if page_text:
        parts.append(page_text)
    if parts:
      return "\n".join(parts).strip()
  return ""


def _text_from_page_dict(page: dict) -> str:
  parts: list[str] = []
  for block in page.get("blocks") or []:
    for para in block.get("paragraphs") or []:
      for word in para.get("words") or []:
        for symbol in word.get("symbols") or []:
          parts.append(str(symbol.get("text") or ""))
  return "".join(parts).strip()


def parse_vision_ocr_json_outputs(
  json_paths: list[Path],
  case_id: str,
  publication_number: str,
  source_pdf_path: Path,
) -> GoogleVisionOcrResult:
  """Aggregate all Vision OCR JSON files — one response per page."""
  norm = normalize_publication_number(publication_number)
  pages: list[GoogleVisionOcrPage] = []
  response_count = 0
  sequential_page = 0

  for json_path in sort_vision_ocr_json_paths(json_paths):
    try:
      payload = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
      continue

    responses = payload.get("responses") or []
    if not responses and "fullTextAnnotation" in payload:
      responses = [{"fullTextAnnotation": payload["fullTextAnnotation"]}]

    for response in responses:
      response_count += 1
      sequential_page += 1
      annotation = response.get("fullTextAnnotation") or {}
      text = _text_from_full_text_annotation(annotation)
      page_no = _page_no_from_json_filename(json_path, sequential_page)
      warning = None if text else "empty OCR text — skipped in section extraction"
      pages.append(GoogleVisionOcrPage(
        case_id=case_id,
        publication_number=norm,
        page_no=page_no,
        text=text,
        text_length=len(text),
        confidence=None,
        warning=warning,
      ))

  pages.sort(key=lambda p: p.page_no)
  extracted_pages = sum(1 for p in pages if p.text_length > 0)
  total_len = sum(p.text_length for p in pages)

  if not pages or extracted_pages == 0:
    return GoogleVisionOcrResult(
      case_id=case_id,
      publication_number=norm,
      source_pdf_path=str(source_pdf_path),
      page_count=response_count or None,
      extracted_pages=0,
      total_text_length=0,
      status="parse_failed",
      warning="OCR JSON parsed but no text extracted",
      needs_human_review=True,
    )

  return GoogleVisionOcrResult(
    case_id=case_id,
    publication_number=norm,
    source_pdf_path=str(source_pdf_path),
    page_count=response_count or len(pages),
    extracted_pages=extracted_pages,
    total_text_length=total_len,
    needs_human_review=True,
    status="ocr_completed",
    warning=OCR_HUMAN_REVIEW_WARNING,
    pages=pages,
  )


def _empty_result(
  case_id: str,
  publication_number: str,
  source_pdf_path: Path,
  status: str,
  warning: str,
) -> GoogleVisionOcrResult:
  return GoogleVisionOcrResult(
    case_id=case_id,
    publication_number=normalize_publication_number(publication_number),
    source_pdf_path=str(source_pdf_path),
    status=status,
    warning=warning,
    needs_human_review=True,
  )


def run_google_vision_ocr_for_pdf(
  case_id: str,
  publication_number: str,
  pdf_path: Path,
  output_root: Path,
) -> GoogleVisionOcrResult:
  norm = normalize_publication_number(publication_number)
  if not is_google_vision_ocr_enabled():
    return _empty_result(case_id, norm, pdf_path, "disabled", f"{ENABLE_GOOGLE_VISION_OCR_ENV}=false")

  bucket = get_ocr_bucket_name()
  if not bucket:
    return _empty_result(case_id, norm, pdf_path, "bucket_missing", "OCR GCS bucket not configured")

  missing = _missing_dependencies()
  if missing:
    return _empty_result(
      case_id, norm, pdf_path, "dependency_missing",
      f"Install: {', '.join(missing)}",
    )

  if not pdf_path.exists():
    return _empty_result(case_id, norm, pdf_path, "upload_failed", f"PDF not found: {pdf_path}")

  gcs_prefix = build_ocr_gcs_prefix(case_id, norm)
  gcs_output_prefix = f"{gcs_prefix}/output"
  gcs_output_uri = f"gs://{bucket}/{gcs_output_prefix}/"

  try:
    gcs_input_uri = upload_pdf_to_gcs(pdf_path, bucket, gcs_prefix)
  except Exception as exc:
    return _empty_result(case_id, norm, pdf_path, "upload_failed", str(exc))

  try:
    start_vision_pdf_ocr(
      gcs_input_uri, gcs_output_uri, get_ocr_max_pages(), timeout_sec=get_ocr_timeout_sec(),
    )
  except Exception as exc:
    err = str(exc)
    status = "ocr_failed" if "timeout" in err.lower() or "deadline" in err.lower() else "auth_error"
    return GoogleVisionOcrResult(
      case_id=case_id,
      publication_number=norm,
      source_pdf_path=str(pdf_path),
      gcs_input_uri=gcs_input_uri,
      gcs_output_uri=gcs_output_uri,
      status=status,
      warning=err,
      needs_human_review=True,
    )

  out_dir = _output_pack_dir(case_id, output_root)
  json_dir = out_dir / "raw_vision_json"
  try:
    json_paths = download_vision_ocr_json_outputs(bucket, gcs_output_prefix, json_dir)
  except Exception as exc:
    return GoogleVisionOcrResult(
      case_id=case_id,
      publication_number=norm,
      source_pdf_path=str(pdf_path),
      gcs_input_uri=gcs_input_uri,
      gcs_output_uri=gcs_output_uri,
      status="parse_failed",
      warning=str(exc),
      needs_human_review=True,
    )

  result = parse_vision_ocr_json_outputs(json_paths, case_id, norm, pdf_path)
  result.gcs_input_uri = gcs_input_uri
  result.gcs_output_uri = gcs_output_uri
  write_vision_ocr_outputs(case_id, [result], output_root, pack_dir=out_dir)
  return result


def _output_pack_dir(case_id: str, output_root: Path) -> Path:
  stamp = utc_now_iso().replace(":", "").replace("-", "").replace("+00:00", "Z")
  digest = hashlib.sha256(f"{case_id}|vision_ocr|{stamp}".encode()).hexdigest()[:8]
  return Path(output_root) / OUTPUT_SUBDIR / f"{case_id}_{stamp}_{digest}"


def write_vision_ocr_outputs(
  case_id: str,
  results: list[GoogleVisionOcrResult],
  output_root: Path | str,
  *,
  pack_dir: Path | None = None,
) -> Path:
  root = Path(output_root)
  out_dir = pack_dir or _output_pack_dir(case_id, root)
  out_dir.mkdir(parents=True, exist_ok=True)

  pages_csv = out_dir / "google_vision_ocr_pages.csv"
  summary_csv = out_dir / "google_vision_ocr_summary.csv"
  raw_csv = out_dir / "publication_fulltext_raw.csv"
  pages_md = out_dir / "google_vision_ocr_pages.md"
  summary_md = out_dir / "google_vision_ocr_summary.md"

  page_fields = [
    "case_id", "publication_number", "page_no", "text", "text_length",
    "confidence", "extraction_method", "needs_human_review", "warning",
  ]
  summary_fields = [
    "case_id", "publication_number", "source_pdf_path", "gcs_input_uri", "gcs_output_uri",
    "page_count", "extracted_pages", "total_text_length", "needs_human_review",
    "status", "warning", "output_dir",
  ]
  raw_fields = [
    "case_id", "publication_number", "source_file", "page_no", "text",
    "text_length", "extraction_method", "needs_ocr", "warning",
  ]

  with pages_csv.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=page_fields)
    writer.writeheader()
    for result in results:
      for page in result.pages:
        writer.writerow({
          "case_id": page.case_id,
          "publication_number": page.publication_number,
          "page_no": page.page_no,
          "text": page.text,
          "text_length": page.text_length,
          "confidence": page.confidence if page.confidence is not None else "",
          "extraction_method": page.extraction_method,
          "needs_human_review": page.needs_human_review,
          "warning": page.warning or "",
        })

  with summary_csv.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=summary_fields)
    writer.writeheader()
    for result in results:
      writer.writerow({
        "case_id": result.case_id,
        "publication_number": result.publication_number,
        "source_pdf_path": result.source_pdf_path,
        "gcs_input_uri": result.gcs_input_uri or "",
        "gcs_output_uri": result.gcs_output_uri or "",
        "page_count": result.page_count or 0,
        "extracted_pages": result.extracted_pages,
        "total_text_length": result.total_text_length,
        "needs_human_review": result.needs_human_review,
        "status": result.status,
        "warning": result.warning or "",
        "output_dir": str(out_dir),
      })

  with raw_csv.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=raw_fields)
    writer.writeheader()
    for result in results:
      for page in result.pages:
        writer.writerow({
          "case_id": page.case_id,
          "publication_number": page.publication_number,
          "source_file": result.source_pdf_path,
          "page_no": page.page_no,
          "text": page.text,
          "text_length": page.text_length,
          "extraction_method": EXTRACTION_METHOD_VISION,
          "needs_ocr": False,
          "warning": OCR_HUMAN_REVIEW_WARNING,
        })

  md_lines = [f"# Google Vision OCR pages — {case_id}", ""]
  for notice in GOOGLE_VISION_OCR_NOTICES:
    md_lines.append(f"- {notice}")
  md_lines.append("")
  for result in results:
    md_lines.append(f"## {result.publication_number} ({result.status})")
    for page in result.pages[:10]:
      preview = (page.text[:300] + "…") if len(page.text) > 300 else page.text
      md_lines.append(f"### page {page.page_no}")
      md_lines.append(preview or "（空）")
      md_lines.append("")
  pages_md.write_text("\n".join(md_lines), encoding="utf-8")

  sum_lines = [
    f"# Google Vision OCR summary — {case_id}",
    "",
    "| publication_number | status | extracted_pages | total_text_length | warning |",
    "| --- | --- | --- | --- | --- |",
  ]
  for result in results:
    sum_lines.append(
      f"| {result.publication_number} | {result.status} | {result.extracted_pages} | "
      f"{result.total_text_length} | {(result.warning or '')[:60]} |"
    )
  summary_md.write_text("\n".join(sum_lines), encoding="utf-8")

  for result in results:
    result.output_dir = str(out_dir)
  return out_dir


def write_vision_ocr_as_publication_fulltext_raw(
  case_id: str,
  result: GoogleVisionOcrResult,
  output_root: Path,
) -> Path:
  return write_vision_ocr_outputs(case_id, [result], output_root)


def find_latest_google_vision_ocr_dir(
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
  latest = max(dirs, key=lambda p: p.stat().st_mtime)
  if (latest / "publication_fulltext_raw.csv").exists():
    return latest
  return None


def load_ocr_summary_from_dir(pack_dir: Path | str) -> dict[str, dict]:
  path = Path(pack_dir) / "google_vision_ocr_summary.csv"
  if not path.exists():
    return {}
  by_pub: dict[str, dict] = {}
  with path.open(encoding="utf-8", newline="") as handle:
    for row in csv.DictReader(handle):
      pub = normalize_publication_number(str(row.get("publication_number", "")))
      if pub:
        by_pub[pub] = row
  return by_pub


def load_vision_ocr_raw_csv_stats(
  raw_csv_path: Path | str,
  publication_number: str,
) -> dict[str, int | bool | str]:
  """Read OCR stats from publication_fulltext_raw.csv without calling Vision API."""
  path = Path(raw_csv_path)
  norm = normalize_publication_number(publication_number)
  rows = 0
  text_length = 0
  has_vision = False
  if not path.exists():
    return {
      "extracted": False,
      "rows": 0,
      "total_text_length": 0,
      "raw_csv_path": str(path),
    }
  with path.open(encoding="utf-8", newline="") as handle:
    for row in csv.DictReader(handle):
      pub = normalize_publication_number(str(row.get("publication_number", "")))
      if pub != norm:
        continue
      method = str(row.get("extraction_method") or "")
      if method != EXTRACTION_METHOD_VISION:
        continue
      has_vision = True
      rows += 1
      try:
        length = int(row.get("text_length") or 0)
      except (TypeError, ValueError):
        length = 0
      if length <= 0:
        length = len(str(row.get("text") or ""))
      text_length += length
  return {
    "extracted": has_vision and rows > 0 and text_length > 0,
    "rows": rows,
    "total_text_length": text_length,
    "raw_csv_path": str(path),
  }


def resolve_pdf_path_for_ocr(
  case_id: str,
  publication_number: str,
  project_root: Path | str,
) -> Path:
  return get_patent_pdf_path(case_id, project_root, publication_number)


def _read_summary_source_pdf_path(output_dir: Path, publication_number: str) -> Path | None:
  summary_csv = output_dir / "google_vision_ocr_summary.csv"
  if not summary_csv.exists():
    return None
  norm = normalize_publication_number(publication_number)
  with summary_csv.open(encoding="utf-8", newline="") as handle:
    for row in csv.DictReader(handle):
      if normalize_publication_number(str(row.get("publication_number", ""))) == norm:
        path = str(row.get("source_pdf_path") or "").strip()
        return Path(path) if path else None
  return None


def find_vision_ocr_raw_json_dir(output_dir: Path) -> Path | None:
  json_dir = output_dir / "raw_vision_json"
  if json_dir.is_dir() and any(json_dir.glob("*.json")):
    return json_dir
  return None


def find_latest_vision_ocr_raw_json_dir(
  case_id: str,
  publication_number: str,
  output_root: Path | str,
) -> Path | None:
  root = Path(output_root)
  base = root / OUTPUT_SUBDIR
  if not base.is_dir():
    return None
  norm = normalize_publication_number(publication_number)
  candidates: list[tuple[Path, float]] = []
  for pack in base.iterdir():
    if not pack.is_dir() or not pack.name.startswith(f"{case_id}_"):
      continue
    json_dir = find_vision_ocr_raw_json_dir(pack)
    if not json_dir:
      continue
    summary = load_ocr_summary_from_dir(pack)
    if norm in summary or not summary:
      candidates.append((json_dir, pack.stat().st_mtime))
  if not candidates:
    return None
  return max(candidates, key=lambda item: item[1])[0]


def reparse_existing_vision_ocr_output(
  output_dir: Path,
  case_id: str,
  publication_number: str,
  *,
  source_pdf_path: Path | None = None,
  project_root: Path | str | None = None,
) -> GoogleVisionOcrResult:
  """Re-parse raw_vision_json without calling Vision API."""
  json_dir = find_vision_ocr_raw_json_dir(output_dir)
  norm = normalize_publication_number(publication_number)
  if not json_dir:
    return _empty_result(
      case_id, norm, source_pdf_path or Path("missing.pdf"),
      "parse_failed", "raw_vision_json not found",
    )

  root = Path(project_root or project_root_from_here())
  pdf_path = source_pdf_path or _read_summary_source_pdf_path(output_dir, publication_number)
  if pdf_path is None or not pdf_path.exists():
    pdf_path = resolve_pdf_path_for_ocr(case_id, publication_number, root)

  json_paths = list(json_dir.glob("*.json"))
  result = parse_vision_ocr_json_outputs(json_paths, case_id, publication_number, pdf_path)

  summary = load_ocr_summary_from_dir(output_dir).get(norm, {})
  if summary.get("gcs_input_uri"):
    result.gcs_input_uri = str(summary["gcs_input_uri"])
  if summary.get("gcs_output_uri"):
    result.gcs_output_uri = str(summary["gcs_output_uri"])

  output_root = root / "outputs"
  write_vision_ocr_outputs(case_id, [result], output_root, pack_dir=output_dir)
  return result
