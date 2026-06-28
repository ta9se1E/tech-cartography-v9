"""Patent fulltext section extraction (Phase 27S.2) — rule-based, no LLM/OCR."""

from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

from tech_cartography.runtime.v8_patent_section_schema import (
  SECTION_EXTRACTION_NOTICES,
  PatentFulltextSection,
  PatentSectionExtractionResult,
)
from tech_cartography.runtime.v8_research_theme_schema import normalize_publication_number
from tech_cartography.runtime.v8_sources_schema import utc_now_iso
from tech_cartography.services.v8_patent_pdf_text_extract import (
  OUTPUT_SUBDIR as PDF_TEXT_OUTPUT_SUBDIR,
  find_latest_pdf_text_extract_dir,
)
from tech_cartography.services.v8_sources_table import project_root_from_here

OUTPUT_SUBDIR = "local_v8_patent_sections"
VISION_OCR_OUTPUT_SUBDIR = "local_v8_google_vision_ocr"
EXTRACTION_METHOD_VISION = "google_vision_ocr"
MIN_SECTION_TEXT_LENGTH = 40
CONF_STRONG = 0.85
CONF_WEAK = 0.60
CONF_UNKNOWN = 0.30
DETECTION_METHOD = "heading_regex"

# (section_type, pattern, confidence, title_group_index or None)
_HEADING_RULES: list[tuple[str, str, float, int | None]] = [
  # comparative / table / numbered examples first (more specific)
  ("comparative_examples", r"(?m)^\s*(Comparative\s+Example\s*(\d+)|对比例\s*(\d+)|比較例\s*(\d+))\s*$", CONF_STRONG, 1),
  ("comparative_examples", r"(?m)^\s*Comparative\s+Examples?\s*$", CONF_STRONG, None),
  ("comparative_examples", r"(?m)^\s*对比例\s*$", CONF_STRONG, None),
  ("comparative_examples", r"(?m)^\s*比較例\s*$", CONF_STRONG, None),
  ("tables", r"(?m)^\s*(Table\s*(\d+)|表\s*(\d+)|表(\d+))\s*$", CONF_STRONG, 1),
  ("table_candidate", r"(?m)^\s*(性能对比表|对比表|高强高模碳纤维性能对比表)\s*$", CONF_STRONG, None),
  ("table_candidate", r"(?m)^\s*表\s*(\d+)\s*[\.．、:：]?\s*(.*(?:对比|性能|强度|模量).*)$", CONF_STRONG, 1),
  ("examples", r"(?m)^\s*(Example\s*(\d+)|实施例\s*(\d+)|実施例\s*(\d+))\s*$", CONF_STRONG, 1),
  ("examples", r"(?m)^\s*(Examples?|Working\s+Examples?|实施例|実施例)\s*$", CONF_STRONG, None),
  ("claims", r"(?m)^\s*(CLAIMS|Claims|What is claimed is[:：]?|权利要求书|权利要求|請求の範囲|特許請求の範囲)\s*$", CONF_STRONG, 1),
  ("description", r"(?m)^\s*(Description|Detailed\s+Description(?:\s+of\s+the\s+Invention)?|说明书|明細書|発明の詳細な説明)\s*$", CONF_STRONG, 1),
  ("technical_field", r"(?m)^\s*(Technical\s+Field|Field\s+of\s+the\s+Invention|技术领域|技術分野)\s*$", CONF_STRONG, 1),
  ("background", r"(?m)^\s*(Background(?:\s+Art)?|背景技术|背景技術)\s*$", CONF_STRONG, 1),
  ("summary", r"(?m)^\s*(Summary(?:\s+of\s+the\s+Invention)?|发明内容|発明の概要)\s*$", CONF_STRONG, 1),
  ("embodiments", r"(?m)^\s*(Embodiments?|Detailed\s+embodiment|具体实施方式|实施方式|実施形態)\s*$", CONF_STRONG, 1),
  ("drawings", r"(?m)^\s*(Brief\s+Description\s+of\s+(?:the\s+)?Drawings?|附图说明|図面の簡単な説明)\s*$", CONF_WEAK, 1),
  # weak keyword fallbacks
  ("description", r"(?m)^\s*Description\s+of\s+", CONF_WEAK, None),
  ("examples", r"(?m)\bExample\s+\d+\b", CONF_WEAK, None),
]


@dataclass
class _HeadingMatch:
  start: int
  end: int
  section_type: str
  section_title: str | None
  confidence: float
  detection_method: str


@dataclass
class PublicationFulltextRawPackInfo:
  pack_dir: Path
  raw_csv_path: Path
  extraction_method: str
  mtime: float
  publication_numbers: list[str]
  total_rows: int = 0
  total_text_length: int = 0


def _int_field(value: object) -> int:
  if value is None or value == "":
    return 0
  try:
    return int(value)
  except (TypeError, ValueError):
    return 0


def _raw_csv_publication_stats(
  raw_csv: Path,
  publication_number: str | None = None,
) -> tuple[list[str], int, int, bool]:
  """Return pubs, row count, text length sum, and whether google_vision_ocr rows exist."""
  pubs: set[str] = set()
  row_count = 0
  text_length = 0
  has_vision = False
  target = normalize_publication_number(publication_number) if publication_number else None
  with raw_csv.open(encoding="utf-8", newline="") as handle:
    for row in csv.DictReader(handle):
      pub = normalize_publication_number(str(row.get("publication_number", "")))
      if not pub:
        continue
      if target and pub != target:
        continue
      method = str(row.get("extraction_method") or "")
      if method == EXTRACTION_METHOD_VISION:
        has_vision = True
      pubs.add(pub)
      row_count += 1
      length = _int_field(row.get("text_length"))
      if length <= 0:
        length = len(str(row.get("text") or ""))
      text_length += length
  return sorted(pubs), row_count, text_length, has_vision


def _collect_publication_fulltext_raw_packs(
  case_id: str,
  project_root: Path | str,
  *,
  publication_number: str | None = None,
) -> list[PublicationFulltextRawPackInfo]:
  root = Path(project_root)
  packs: list[PublicationFulltextRawPackInfo] = []
  for subdir, method in (
    (PDF_TEXT_OUTPUT_SUBDIR, "pypdf"),
    (VISION_OCR_OUTPUT_SUBDIR, EXTRACTION_METHOD_VISION),
  ):
    base = root / "outputs" / subdir
    if not base.is_dir():
      continue
    for pack in base.iterdir():
      if not pack.is_dir() or not pack.name.startswith(f"{case_id}_"):
        continue
      raw = pack / "publication_fulltext_raw.csv"
      if not raw.exists():
        continue
      pubs, rows, chars, has_vision = _raw_csv_publication_stats(raw, publication_number)
      if publication_number and not pubs:
        continue
      extraction_method = method
      if method == "pypdf" and has_vision:
        extraction_method = EXTRACTION_METHOD_VISION
      packs.append(PublicationFulltextRawPackInfo(
        pack_dir=pack,
        raw_csv_path=raw,
        extraction_method=extraction_method,
        mtime=pack.stat().st_mtime,
        publication_numbers=pubs,
        total_rows=rows,
        total_text_length=chars,
      ))
  return packs


def find_publication_fulltext_raw_pack(
  case_id: str,
  project_root: Path | str,
  publication_number: str | None = None,
  *,
  prefer_ocr: bool = False,
) -> PublicationFulltextRawPackInfo | None:
  """Select publication_fulltext_raw.csv pack for section extraction."""
  packs = _collect_publication_fulltext_raw_packs(
    case_id, project_root, publication_number=publication_number,
  )
  if not packs:
    return None
  if prefer_ocr and publication_number:
    ocr_packs = [
      p for p in packs
      if p.extraction_method == EXTRACTION_METHOD_VISION and p.total_text_length > 0
    ]
    if ocr_packs:
      return max(ocr_packs, key=lambda item: item.mtime)
  return max(packs, key=lambda item: item.mtime)


def find_latest_pdf_text_extract_output(case_id: str, output_root: Path | str) -> Path | None:
  root = Path(output_root)
  base = root / PDF_TEXT_OUTPUT_SUBDIR
  if not base.is_dir():
    return None
  dirs = [p for p in base.iterdir() if p.is_dir() and p.name.startswith(f"{case_id}_")]
  if not dirs:
    return None
  latest = max(dirs, key=lambda p: p.stat().st_mtime)
  raw_csv = latest / "publication_fulltext_raw.csv"
  return latest if raw_csv.exists() else None


def find_latest_publication_fulltext_raw_pack(
  case_id: str,
  project_root: Path | str,
  publication_number: str | None = None,
  *,
  prefer_ocr: bool = False,
) -> tuple[Path | None, str]:
  """Return pack dir with publication_fulltext_raw.csv and extraction method."""
  info = find_publication_fulltext_raw_pack(
    case_id,
    project_root,
    publication_number=publication_number,
    prefer_ocr=prefer_ocr,
  )
  if not info:
    return None, ""
  return info.pack_dir, info.extraction_method


def sections_stale_vs_ocr_output(
  section_summary_row: dict | None,
  section_pack_dir: Path | None,
  ocr_pack_dir: Path | None,
) -> bool:
  """True when OCR fulltext exists but sections are missing, older, or not from OCR."""
  if not ocr_pack_dir or not (ocr_pack_dir / "publication_fulltext_raw.csv").exists():
    return False
  if not section_summary_row:
    return True
  source_raw = str(section_summary_row.get("source_raw_csv") or "")
  if VISION_OCR_OUTPUT_SUBDIR not in source_raw and EXTRACTION_METHOD_VISION not in source_raw:
    return True
  if section_pack_dir and ocr_pack_dir:
    return ocr_pack_dir.stat().st_mtime > section_pack_dir.stat().st_mtime
  return False


def find_latest_section_extract_dir(
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
  pack = max(dirs, key=lambda p: p.stat().st_mtime)
  if (pack / "section_extraction_summary.csv").exists():
    return pack
  return None


def load_publication_fulltext_raw(raw_csv_path: Path) -> list[dict[str, str]]:
  rows: list[dict[str, str]] = []
  with raw_csv_path.open(encoding="utf-8", newline="") as handle:
    for row in csv.DictReader(handle):
      rows.append(dict(row))
  return rows


def normalize_fulltext_pages(rows: list[dict]) -> dict[str, str]:
  by_pub: dict[str, list[tuple[int, str]]] = {}
  for row in rows:
    pub = normalize_publication_number(str(row.get("publication_number", "")))
    if not pub:
      continue
    try:
      page_no = int(row.get("page_no") or 0)
    except ValueError:
      page_no = 0
    text = str(row.get("text") or "")
    by_pub.setdefault(pub, []).append((page_no, text))

  merged: dict[str, str] = {}
  for pub, pages in by_pub.items():
    pages.sort(key=lambda item: item[0])
    merged[pub] = "\n\n".join(text for _, text in pages if text)
  return merged


def _page_rows_for_publication(rows: list[dict], publication_number: str) -> list[dict]:
  norm = normalize_publication_number(publication_number)
  page_rows = [r for r in rows if normalize_publication_number(str(r.get("publication_number", ""))) == norm]
  page_rows.sort(key=lambda r: int(r.get("page_no") or 0))
  return page_rows


def _extract_title_from_match(match: re.Match[str], group_index: int | None) -> str | None:
  if group_index is None:
    return match.group(0).strip()
  title = match.group(group_index)
  if title:
    return title.strip()
  return match.group(0).strip()


def _find_heading_matches(fulltext: str) -> list[_HeadingMatch]:
  matches: list[_HeadingMatch] = []
  for section_type, pattern, confidence, title_group in _HEADING_RULES:
    try:
      for match in re.finditer(pattern, fulltext, flags=re.IGNORECASE):
        title = _extract_title_from_match(match, title_group)
        matches.append(_HeadingMatch(
          start=match.start(),
          end=match.end(),
          section_type=section_type,
          section_title=title,
          confidence=confidence,
          detection_method=DETECTION_METHOD,
        ))
    except re.error:
      continue

  matches.sort(key=lambda item: item.start)
  deduped: list[_HeadingMatch] = []
  for match in matches:
    if deduped and match.start < deduped[-1].end:
      if match.confidence > deduped[-1].confidence:
        deduped[-1] = match
      continue
    deduped.append(match)
  return deduped


def _page_range_for_span(
  page_rows: list[dict],
  char_start: int,
  char_end: int,
  fulltext: str,
) -> tuple[int | None, int | None]:
  if not page_rows:
    return None, None
  offsets: list[tuple[int, int, int]] = []
  cursor = 0
  for row in page_rows:
    text = str(row.get("text") or "")
    page_no = int(row.get("page_no") or 0)
    start = cursor
    end = cursor + len(text)
    offsets.append((start, end, page_no))
    cursor = end + 2  # "\n\n" join separator

  pages: list[int] = []
  for start, end, page_no in offsets:
    if end <= char_start:
      continue
    if start >= char_end:
      break
    pages.append(page_no)
  if not pages:
    return None, None
  return min(pages), max(pages)


def _section_needs_review(
  *,
  section_type: str,
  confidence: float,
  text_length: int,
) -> bool:
  if section_type in {"unknown", "table_candidate"}:
    return True
  if confidence < 0.75:
    return True
  if text_length < MIN_SECTION_TEXT_LENGTH:
    return True
  return False


_TABLE_TITLE_RE = re.compile(
  r"表\s*\d+|性能对比表|对比表|高强高模碳纤维性能|与日本东丽|日本东丽|Toray",
  re.IGNORECASE,
)
_TABLE_PROPERTY_RE = re.compile(
  r"拉伸强度|拉伸模量|强度|模量|GPa|MPa|M55J|M60J|M40J|T300|东丽",
  re.IGNORECASE,
)
_NUMERIC_TOKEN_RE = re.compile(r"\d+\.?\d*")


def _looks_like_table_candidate(text: str) -> bool:
  if not text.strip():
    return False
  if _TABLE_TITLE_RE.search(text):
    return True
  numeric_count = len(_NUMERIC_TOKEN_RE.findall(text))
  return bool(_TABLE_PROPERTY_RE.search(text) and numeric_count >= 3)


def _augment_table_candidate_sections(
  sections: list[PatentFulltextSection],
  *,
  case_id: str,
  publication_number: str,
) -> list[PatentFulltextSection]:
  """Add table_candidate sections for Chinese OCR table-like blocks without removing examples."""
  augmented = list(sections)
  existing_ids = {s.section_id for s in sections}
  for section in sections:
    if section.section_type in {"tables", "table_candidate"}:
      continue
    text = section.section_text
    if not _looks_like_table_candidate(text):
      continue
    section_id = f"{publication_number}_table_candidate_{len(existing_ids) + 1}"
    while section_id in existing_ids:
      section_id = f"{section_id}_dup"
    existing_ids.add(section_id)
    title = None
    title_match = _TABLE_TITLE_RE.search(text)
    if title_match:
      title = title_match.group(0).strip()
    augmented.append(PatentFulltextSection(
      case_id=case_id,
      publication_number=publication_number,
      section_id=section_id,
      section_type="table_candidate",
      section_title=title,
      section_text=text,
      page_start=section.page_start,
      page_end=section.page_end,
      text_length=len(text),
      confidence=min(section.confidence, 0.75),
      needs_human_review=True,
      detection_method="table_keyword_heuristic",
      warning="OCR table candidate — verify values in source PDF",
    ))
  return augmented


def detect_patent_sections_for_publication(
  case_id: str,
  publication_number: str,
  fulltext: str,
  page_texts: list[dict] | None = None,
  *,
  source_raw_csv: str | None = None,
) -> PatentSectionExtractionResult:
  norm_pub = normalize_publication_number(publication_number)
  if not fulltext.strip():
    return PatentSectionExtractionResult(
      case_id=case_id,
      publication_number=norm_pub,
      source_raw_csv=source_raw_csv,
      status="empty_input",
      warning="fulltext is empty",
      needs_human_review=True,
    )

  headings = _find_heading_matches(fulltext)
  sections: list[PatentFulltextSection] = []

  if not headings:
    if page_texts:
      for idx, row in enumerate(page_texts, start=1):
        text = str(row.get("text") or "").strip()
        if not text:
          continue
        page_no = int(row.get("page_no") or idx)
        sections.append(PatentFulltextSection(
          case_id=case_id,
          publication_number=norm_pub,
          section_id=f"{norm_pub}_unknown_p{page_no}",
          section_type="unknown",
          section_title=f"page {page_no}",
          section_text=text,
          page_start=page_no,
          page_end=page_no,
          text_length=len(text),
          confidence=CONF_UNKNOWN,
          needs_human_review=True,
          detection_method="page_fallback",
          warning="no heading detected — page-level unknown section",
        ))
    else:
      text = fulltext.strip()
      sections.append(PatentFulltextSection(
        case_id=case_id,
        publication_number=norm_pub,
        section_id=f"{norm_pub}_unknown_1",
        section_type="unknown",
        section_title=None,
        section_text=text,
        page_start=None,
        page_end=None,
        text_length=len(text),
        confidence=CONF_UNKNOWN,
        needs_human_review=True,
        detection_method="fulltext_fallback",
        warning="no heading detected",
      ))
    status = "no_headings"
  else:
    for idx, heading in enumerate(headings):
      slice_start = heading.start
      slice_end = headings[idx + 1].start if idx + 1 < len(headings) else len(fulltext)
      text = fulltext[slice_start:slice_end].strip()
      page_start, page_end = _page_range_for_span(
        page_texts or [], slice_start, slice_end, fulltext,
      )
      needs_review = _section_needs_review(
        section_type=heading.section_type,
        confidence=heading.confidence,
        text_length=len(text),
      )
      sections.append(PatentFulltextSection(
        case_id=case_id,
        publication_number=norm_pub,
        section_id=f"{norm_pub}_{heading.section_type}_{idx + 1}",
        section_type=heading.section_type,
        section_title=heading.section_title,
        section_text=text,
        page_start=page_start,
        page_end=page_end,
        text_length=len(text),
        confidence=heading.confidence,
        needs_human_review=needs_review,
        detection_method=heading.detection_method,
      ))
    status = "ok"

  sections = _augment_table_candidate_sections(
    sections, case_id=case_id, publication_number=norm_pub,
  )

  examples_count = sum(1 for s in sections if s.section_type == "examples")
  comparative_count = sum(1 for s in sections if s.section_type == "comparative_examples")
  tables_count = sum(1 for s in sections if s.section_type in {"tables", "table_candidate"})
  has_claims = any(s.section_type == "claims" for s in sections)
  has_description = any(s.section_type == "description" for s in sections)
  has_examples = examples_count > 0

  needs_review = (
    any(s.needs_human_review for s in sections)
    or not has_examples
    or any(s.section_type == "unknown" for s in sections)
  )

  warning = None
  if not has_examples:
    warning = "examples section not detected — needs human review"
  elif any(s.section_type == "unknown" for s in sections):
    warning = "unknown sections present — verify headings manually"

  if status == "no_headings" and not warning:
    warning = "no section headings detected"

  return PatentSectionExtractionResult(
    case_id=case_id,
    publication_number=norm_pub,
    source_raw_csv=source_raw_csv,
    section_count=len(sections),
    examples_count=examples_count,
    comparative_examples_count=comparative_count,
    tables_count=tables_count,
    has_claims=has_claims,
    has_description=has_description,
    has_examples=has_examples,
    needs_human_review=needs_review,
    sections=sections,
    status="needs_review" if needs_review else status,
    warning=warning,
  )


def extract_sections_from_pdf_text_output(
  case_id: str,
  raw_csv_path: Path,
  output_root: Path,
) -> list[PatentSectionExtractionResult]:
  rows = load_publication_fulltext_raw(raw_csv_path)
  merged = normalize_fulltext_pages(rows)
  results: list[PatentSectionExtractionResult] = []
  source = str(raw_csv_path)
  for pub, fulltext in sorted(merged.items()):
    page_texts = _page_rows_for_publication(rows, pub)
    results.append(detect_patent_sections_for_publication(
      case_id,
      pub,
      fulltext,
      page_texts,
      source_raw_csv=source,
    ))
  return results


def _output_pack_dir(case_id: str, output_root: Path) -> Path:
  stamp = utc_now_iso().replace(":", "").replace("-", "").replace("+00:00", "Z")
  digest = hashlib.sha256(f"{case_id}|sections|{stamp}".encode()).hexdigest()[:8]
  return output_root / OUTPUT_SUBDIR / f"{case_id}_{stamp}_{digest}"


def write_section_outputs(
  case_id: str,
  results: list[PatentSectionExtractionResult],
  output_root: Path,
) -> Path:
  out_dir = _output_pack_dir(case_id, output_root)
  out_dir.mkdir(parents=True, exist_ok=True)

  sections_csv = out_dir / "publication_fulltext_sections.csv"
  summary_csv = out_dir / "section_extraction_summary.csv"
  sections_md = out_dir / "publication_fulltext_sections.md"
  summary_md = out_dir / "section_extraction_summary.md"

  section_fields = [
    "case_id", "publication_number", "section_id", "section_type", "section_title",
    "section_text", "page_start", "page_end", "text_length", "confidence",
    "needs_human_review", "detection_method", "warning",
  ]
  summary_fields = [
    "case_id", "publication_number", "source_raw_csv", "section_count",
    "examples_count", "comparative_examples_count", "tables_count",
    "has_claims", "has_description", "has_examples", "needs_human_review",
    "status", "warning",
  ]

  with sections_csv.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=section_fields)
    writer.writeheader()
    for result in results:
      for section in result.sections:
        writer.writerow({
          "case_id": section.case_id,
          "publication_number": section.publication_number,
          "section_id": section.section_id,
          "section_type": section.section_type,
          "section_title": section.section_title or "",
          "section_text": section.section_text,
          "page_start": section.page_start if section.page_start is not None else "",
          "page_end": section.page_end if section.page_end is not None else "",
          "text_length": section.text_length,
          "confidence": section.confidence,
          "needs_human_review": section.needs_human_review,
          "detection_method": section.detection_method,
          "warning": section.warning or "",
        })

  with summary_csv.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=summary_fields)
    writer.writeheader()
    for result in results:
      writer.writerow({
        "case_id": result.case_id,
        "publication_number": result.publication_number,
        "source_raw_csv": result.source_raw_csv or "",
        "section_count": result.section_count,
        "examples_count": result.examples_count,
        "comparative_examples_count": result.comparative_examples_count,
        "tables_count": result.tables_count,
        "has_claims": result.has_claims,
        "has_description": result.has_description,
        "has_examples": result.has_examples,
        "needs_human_review": result.needs_human_review,
        "status": result.status,
        "warning": result.warning or "",
      })

  md_lines = [
    f"# Publication fulltext sections — {case_id}",
    "",
    *[f"- {n}" for n in SECTION_EXTRACTION_NOTICES],
    "",
  ]
  for result in results:
    md_lines.append(f"## {result.publication_number}")
    for section in result.sections[:30]:
      preview = (section.section_text[:400] + "…") if len(section.section_text) > 400 else section.section_text
      md_lines.append(
        f"### {section.section_type} — {section.section_title or section.section_id} "
        f"(conf={section.confidence}, review={section.needs_human_review})"
      )
      md_lines.append(preview or "（空）")
      md_lines.append("")
  sections_md.write_text("\n".join(md_lines), encoding="utf-8")

  sum_lines = [
    f"# Section extraction summary — {case_id}",
    "",
    "| publication_number | sections | examples | comparative | tables | has_examples | review |",
    "| --- | --- | --- | --- | --- | --- | --- |",
  ]
  for result in results:
    sum_lines.append(
      f"| {result.publication_number} | {result.section_count} | {result.examples_count} | "
      f"{result.comparative_examples_count} | {result.tables_count} | {result.has_examples} | "
      f"{result.needs_human_review} |"
    )
  summary_md.write_text("\n".join(sum_lines), encoding="utf-8")

  for result in results:
    result.output_dir = str(out_dir)
  return out_dir


def load_section_summary_from_dir(pack_dir: Path | str) -> dict[str, dict]:
  path = Path(pack_dir) / "section_extraction_summary.csv"
  if not path.exists():
    return {}
  by_pub: dict[str, dict] = {}
  with path.open(encoding="utf-8", newline="") as handle:
    for row in csv.DictReader(handle):
      pub = normalize_publication_number(str(row.get("publication_number", "")))
      if pub:
        by_pub[pub] = row
  return by_pub


def get_section_pipeline_status(
  case_id: str,
  publication_number: str,
  project_root: Path | str,
) -> dict[str, str | bool | int]:
  root = Path(project_root)
  norm = normalize_publication_number(publication_number)
  latest = find_latest_section_extract_dir(case_id, root)
  summary = load_section_summary_from_dir(latest) if latest else {}
  row = summary.get(norm, {})

  sections_extracted = bool(row) and str(row.get("status", "")) not in {"", "empty_input"}
  has_examples = str(row.get("has_examples", "")).lower() in {"true", "1"} or row.get("has_examples") is True
  needs_review = str(row.get("needs_human_review", "")).lower() in {"true", "1"} or row.get("needs_human_review") is True
  examples_count = int(row.get("examples_count") or 0) if row else 0
  comparative_count = int(row.get("comparative_examples_count") or 0) if row else 0
  tables_count = int(row.get("tables_count") or 0) if row else 0

  return {
    "sections_extracted": sections_extracted,
    "has_examples": has_examples,
    "examples_count": examples_count,
    "comparative_examples_count": comparative_count,
    "tables_count": tables_count,
    "section_needs_human_review": needs_review,
    "section_status": str(row.get("status") or ""),
  }


def get_combined_patent_pdf_pipeline_status(
  case_id: str,
  publication_number: str,
  project_root: Path | str,
) -> dict[str, str | bool | int]:
  from tech_cartography.services.v8_patent_pdf_text_extract import get_pdf_pipeline_status

  pdf = get_pdf_pipeline_status(case_id, publication_number, project_root)
  section = get_section_pipeline_status(case_id, publication_number, project_root)
  merged: dict[str, str | bool | int] = {**pdf, **section}

  if not pdf["pdf_uploaded"]:
    next_action = "PDFを取得してアップロード"
  elif not pdf["text_extracted"]:
    next_action = "Extract PDF text"
  elif pdf.get("needs_ocr"):
    next_action = "画像PDFの可能性 — 将来OCR対象"
  elif not section["sections_extracted"]:
    next_action = "Extract sections"
  elif section["section_needs_human_review"]:
    next_action = "セクション判定の人手確認が必要"
  elif section["has_examples"]:
    next_action = "Extract example facts"
  else:
    next_action = "examples未検出 — セクション人手確認"

  merged["next_action"] = next_action
  return merged
