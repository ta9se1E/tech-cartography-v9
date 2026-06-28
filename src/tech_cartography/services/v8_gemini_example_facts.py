"""Gemini example facts extraction service (Phase 27S.3)."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from pathlib import Path

from tech_cartography.runtime.v8_example_facts_schema import (
  EXAMPLE_FACTS_NOTICES,
  VALID_FACT_TYPES,
  ExampleFact,
  ExampleFactsExtractionResult,
)
from tech_cartography.runtime.v8_extraction_vocabulary_schema import ExtractionVocabulary
from tech_cartography.runtime.v8_research_theme_schema import normalize_publication_number
from tech_cartography.runtime.v8_sources_schema import utc_now_iso
from tech_cartography.services.v8_extraction_vocabulary import (
  build_vocabulary_context_for_prompt,
  load_extraction_vocabulary,
  save_extraction_vocabulary,
)
from tech_cartography.services.v8_llm_provider_gemini import (
  GeminiProviderError,
  generate_json_with_gemini,
  is_gemini_example_facts_enabled,
)
from tech_cartography.services.v8_patent_section_extract import (
  OUTPUT_SUBDIR as SECTIONS_OUTPUT_SUBDIR,
  find_latest_section_extract_dir,
)
from tech_cartography.services.v8_research_theme_defaults import load_research_theme_profile
from tech_cartography.services.v8_sources_table import project_root_from_here

OUTPUT_SUBDIR = "local_v8_example_facts"
PRIMARY_SECTION_TYPES = frozenset({"examples", "comparative_examples", "tables"})
FALLBACK_SECTION_TYPE = "embodiments"
EXCLUDED_SECTION_TYPES = frozenset({"claims", "background", "summary", "unknown"})
MAX_FACTS_PER_SECTION = 50
MAX_CHARS_PER_SECTION_DEFAULT = 12000

PROMPT_RULES = """
You extract structured facts from patent examples.
- Use only facts explicitly written in the provided text.
- User-provided vocabulary is extraction focus, not a source of facts.
- Do not infer missing values from vocabulary.
- Do not invent examples, numbers, units, materials, or properties.
- Extract important explicitly written facts even if they are not in the vocabulary.
- Return valid JSON only.
- Every extracted fact must include evidence_text copied from the source text.
- If no facts are found, return an empty facts array.
- This is not a legal analysis.
- Do not assess infringement, validity, FTO, or claim scope.
- Label all outputs as candidates requiring human review.
- Set needs_human_review to true for every fact.
"""


def find_latest_patent_sections_output(case_id: str, output_root: Path | str) -> Path | None:
  root = Path(output_root)
  latest = find_latest_section_extract_dir(case_id, root)
  if latest and (latest / "publication_fulltext_sections.csv").exists():
    return latest
  base = root / SECTIONS_OUTPUT_SUBDIR
  if not base.is_dir():
    return None
  dirs = [p for p in base.iterdir() if p.is_dir() and p.name.startswith(f"{case_id}_")]
  if not dirs:
    return None
  pack = max(dirs, key=lambda p: p.stat().st_mtime)
  return pack if (pack / "publication_fulltext_sections.csv").exists() else None


def find_latest_example_facts_dir(
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
  return pack if (pack / "example_facts_summary.csv").exists() else None


def load_sections_csv(sections_csv_path: Path) -> list[dict[str, str]]:
  rows: list[dict[str, str]] = []
  with sections_csv_path.open(encoding="utf-8", newline="") as handle:
    for row in csv.DictReader(handle):
      rows.append(dict(row))
  return rows


def load_target_sections(sections_csv_path: Path) -> list[dict[str, str]]:
  rows = load_sections_csv(sections_csv_path)
  by_pub: dict[str, list[dict[str, str]]] = {}
  for row in rows:
    section_type = str(row.get("section_type") or "")
    if section_type in EXCLUDED_SECTION_TYPES:
      continue
    pub = normalize_publication_number(str(row.get("publication_number", "")))
    if not pub:
      continue
    by_pub.setdefault(pub, []).append(row)

  selected: list[dict[str, str]] = []
  for pub_rows in by_pub.values():
    primary = [r for r in pub_rows if str(r.get("section_type")) in PRIMARY_SECTION_TYPES]
    if primary:
      selected.extend(primary)
    else:
      selected.extend(r for r in pub_rows if str(r.get("section_type")) == FALLBACK_SECTION_TYPE)
  return selected


def _normalize_ws(text: str) -> str:
  return " ".join(text.split())


def _evidence_in_source(evidence: str, source: str) -> bool:
  if not evidence or not evidence.strip():
    return False
  ev = evidence.strip()
  if ev in source:
    return True
  return _normalize_ws(ev) in _normalize_ws(source)


def _all_vocabulary_keywords(vocabulary: ExtractionVocabulary) -> list[str]:
  return vocabulary.all_keywords()


def recompute_matched_keywords(text: str, vocabulary: ExtractionVocabulary) -> list[str]:
  haystack = text.lower()
  matched: list[str] = []
  seen: set[str] = set()
  for keyword in _all_vocabulary_keywords(vocabulary):
    if keyword.lower() in haystack:
      key = keyword.lower()
      if key not in seen:
        seen.add(key)
        matched.append(keyword)
  return matched


def build_example_facts_prompt(
  section: dict[str, str],
  vocabulary: ExtractionVocabulary,
  theme_context: dict | None = None,
) -> str:
  section_text = str(section.get("section_text") or "")
  if len(section_text) > MAX_CHARS_PER_SECTION_DEFAULT:
    section_text = section_text[:MAX_CHARS_PER_SECTION_DEFAULT] + "\n...[truncated]"

  theme_lines: list[str] = []
  if theme_context:
    if theme_context.get("theme_name"):
      theme_lines.append(f"Theme: {theme_context['theme_name']}")
    if theme_context.get("theme_description"):
      theme_lines.append(f"Description: {theme_context['theme_description']}")

  metadata = "\n".join([
    f"publication_number: {section.get('publication_number', '')}",
    f"section_id: {section.get('section_id', '')}",
    f"section_type: {section.get('section_type', '')}",
    f"section_title: {section.get('section_title', '')}",
    f"page_start: {section.get('page_start', '')}",
    f"page_end: {section.get('page_end', '')}",
  ])

  json_schema = """
{
  "facts": [
    {
      "example_id": "Example 1",
      "example_label": "Example 1",
      "fact_type": "process_condition",
      "material": "PAN precursor fiber",
      "process_step": "carbonization",
      "condition_name": "temperature",
      "condition_value": "1200",
      "condition_unit": "°C",
      "property_name": null,
      "property_value": null,
      "property_unit": null,
      "comparison_type": null,
      "comparison_target": null,
      "table_id": null,
      "evidence_text": "verbatim quote from section text",
      "matched_user_keywords": ["PAN", "carbonization"],
      "confidence": 0.75,
      "needs_human_review": true
    }
  ]
}
"""

  return "\n\n".join([
    PROMPT_RULES.strip(),
    "\n".join(theme_lines) if theme_lines else "",
    build_vocabulary_context_for_prompt(vocabulary),
    "## Target section metadata",
    metadata,
    "## Section text",
    section_text,
    "## Required JSON output format",
    json_schema.strip(),
    "Return JSON only.",
  ]).strip()


def _parse_int(value: str | None) -> int | None:
  if value is None or value == "":
    return None
  try:
    return int(value)
  except (TypeError, ValueError):
    return None


def _clamp_confidence(value: object) -> float:
  try:
    num = float(value)
  except (TypeError, ValueError):
    return 0.5
  return max(0.0, min(1.0, round(num, 3)))


def _normalize_fact_type(raw: str | None) -> str:
  if not raw:
    return "unknown"
  normalized = raw.strip().lower().replace(" ", "_").replace("-", "_")
  if normalized in VALID_FACT_TYPES:
    return normalized
  return "unknown"


def parse_example_facts_json(
  raw_response: str,
  *,
  case_id: str,
  publication_number: str,
  section: dict[str, str],
  vocabulary: ExtractionVocabulary,
) -> list[ExampleFact]:
  try:
    payload = json.loads(raw_response)
  except json.JSONDecodeError:
    return []

  items = payload.get("facts") if isinstance(payload, dict) else []
  if not isinstance(items, list):
    return []

  source_text = str(section.get("section_text") or "")
  pub = normalize_publication_number(publication_number)
  section_id = str(section.get("section_id") or f"{pub}_section")
  section_type = str(section.get("section_type") or "")
  page_start = _parse_int(section.get("page_start"))
  page_end = _parse_int(section.get("page_end"))

  facts: list[ExampleFact] = []
  for idx, item in enumerate(items[:MAX_FACTS_PER_SECTION]):
    if not isinstance(item, dict):
      continue
    evidence = str(item.get("evidence_text") or "").strip()
    if not evidence:
      continue

    fact = ExampleFact(
      case_id=case_id,
      publication_number=pub,
      section_id=section_id,
      section_type=section_type,
      fact_id=f"{section_id}_fact_{idx + 1}",
      evidence_text=evidence,
      fact_type=_normalize_fact_type(str(item.get("fact_type") or "")),
      example_id=item.get("example_id"),
      example_label=item.get("example_label"),
      material=item.get("material"),
      process_step=item.get("process_step"),
      condition_name=item.get("condition_name"),
      condition_value=str(item["condition_value"]) if item.get("condition_value") is not None else None,
      condition_unit=item.get("condition_unit"),
      property_name=item.get("property_name"),
      property_value=str(item["property_value"]) if item.get("property_value") is not None else None,
      property_unit=item.get("property_unit"),
      comparison_type=item.get("comparison_type"),
      comparison_target=item.get("comparison_target"),
      table_id=item.get("table_id"),
      matched_user_keywords=[],
      page_start=page_start,
      page_end=page_end,
      confidence=_clamp_confidence(item.get("confidence", 0.75)),
      needs_human_review=True,
      extraction_method="gemini",
    )
    facts.append(validate_example_fact(fact, source_text, vocabulary))
  return facts


def validate_example_fact(
  fact: ExampleFact,
  source_text: str,
  vocabulary: ExtractionVocabulary,
) -> ExampleFact:
  fact.needs_human_review = True
  combined = " ".join(filter(None, [
    fact.evidence_text, source_text, fact.material or "", fact.process_step or "",
    fact.condition_value or "", fact.property_value or "",
  ]))
  fact.matched_user_keywords = recompute_matched_keywords(combined, vocabulary)

  if not _evidence_in_source(fact.evidence_text, source_text):
    fact.warning = "evidence_text not found verbatim in source section"
    fact.confidence = _clamp_confidence(fact.confidence * 0.5)
  return fact


def _aggregate_result(
  case_id: str,
  publication_number: str,
  sections: list[dict[str, str]],
  facts: list[ExampleFact],
  *,
  source_sections_csv: str | None,
  status: str,
  warning: str | None = None,
) -> ExampleFactsExtractionResult:
  pub = normalize_publication_number(publication_number)
  pub_facts = [f for f in facts if f.publication_number == pub]
  example_ids = {f.example_id or f.example_label for f in pub_facts if f.example_id or f.example_label}
  comp_count = sum(1 for f in pub_facts if f.fact_type == "comparison_example" or f.section_type == "comparative_examples")
  prop_count = sum(1 for f in pub_facts if f.fact_type == "property_value")
  proc_count = sum(1 for f in pub_facts if f.fact_type == "process_condition")
  keyword_set: set[str] = set()
  for fact in pub_facts:
    keyword_set.update(fact.matched_user_keywords)

  return ExampleFactsExtractionResult(
    case_id=case_id,
    publication_number=pub,
    source_sections_csv=source_sections_csv,
    target_section_count=len(sections),
    fact_count=len(pub_facts),
    example_count=len(example_ids),
    comparative_example_count=comp_count,
    property_fact_count=prop_count,
    process_condition_fact_count=proc_count,
    matched_user_keyword_count=len(keyword_set),
    needs_human_review=True,
    facts=pub_facts,
    status=status,
    warning=warning,
  )


def extract_example_facts_from_sections(
  case_id: str,
  sections_csv_path: Path,
  output_root: Path,
  project_root: Path,
  *,
  use_gemini: bool,
  max_sections: int | None = None,
  max_chars_per_section: int = MAX_CHARS_PER_SECTION_DEFAULT,
) -> tuple[list[ExampleFactsExtractionResult], list[tuple[str, str]], ExtractionVocabulary]:
  """Returns results, prompt pairs (section_id, prompt), vocabulary."""
  del max_chars_per_section  # applied in build_example_facts_prompt via module constant
  vocabulary = load_extraction_vocabulary(case_id, project_root)
  theme = load_research_theme_profile(case_id, project_root)
  theme_context = None
  if theme:
    theme_context = {"theme_name": theme.theme_name, "theme_description": theme.theme_description}

  target_sections = load_target_sections(sections_csv_path)
  if max_sections is not None:
    target_sections = target_sections[:max_sections]

  if not target_sections:
    return [], [], vocabulary

  by_pub: dict[str, list[dict[str, str]]] = {}
  for section in target_sections:
    pub = normalize_publication_number(str(section.get("publication_number", "")))
    by_pub.setdefault(pub, []).append(section)

  all_facts: list[ExampleFact] = []
  prompts: list[tuple[str, str]] = []
  gemini_warning: str | None = None
  status = "prompts_only"

  if use_gemini and is_gemini_example_facts_enabled():
    status = "ok"
    for section in target_sections:
      prompt = build_example_facts_prompt(section, vocabulary, theme_context)
      section_id = str(section.get("section_id") or "section")
      prompts.append((section_id, prompt))
      try:
        raw = generate_json_with_gemini(prompt)
        pub = normalize_publication_number(str(section.get("publication_number", "")))
        parsed = parse_example_facts_json(
          raw, case_id=case_id, publication_number=pub, section=section, vocabulary=vocabulary,
        )
        all_facts.extend(parsed)
      except GeminiProviderError as exc:
        gemini_warning = str(exc)
        status = "gemini_error"
        break
  else:
    for section in target_sections:
      prompt = build_example_facts_prompt(section, vocabulary, theme_context)
      section_id = str(section.get("section_id") or "section")
      prompts.append((section_id, prompt))
    status = "gemini_disabled" if use_gemini else "prompts_only"

  results: list[ExampleFactsExtractionResult] = []
  for pub, pub_sections in sorted(by_pub.items()):
    warning = gemini_warning
    if not use_gemini or not is_gemini_example_facts_enabled():
      warning = warning or "Gemini not invoked — prompts exported only"
    results.append(_aggregate_result(
      case_id, pub, pub_sections, all_facts,
      source_sections_csv=str(sections_csv_path),
      status=status,
      warning=warning,
    ))
  return results, prompts, vocabulary


def write_example_facts_outputs(
  case_id: str,
  results: list[ExampleFactsExtractionResult],
  output_root: Path,
  vocabulary: ExtractionVocabulary,
  prompts: list[tuple[str, str]] | None = None,
) -> Path:
  stamp = utc_now_iso().replace(":", "").replace("-", "").replace("+00:00", "Z")
  digest = hashlib.sha256(f"{case_id}|example_facts|{stamp}".encode()).hexdigest()[:8]
  out_dir = Path(output_root) / OUTPUT_SUBDIR / f"{case_id}_{stamp}_{digest}"
  out_dir.mkdir(parents=True, exist_ok=True)

  facts_csv = out_dir / "example_facts.csv"
  facts_json = out_dir / "example_facts.json"
  facts_md = out_dir / "example_facts.md"
  summary_csv = out_dir / "example_facts_summary.csv"
  summary_md = out_dir / "example_facts_summary.md"
  prompts_md = out_dir / "gemini_prompts.md"
  vocab_copy = out_dir / "extraction_vocabulary.json"

  fact_fields = [
    "case_id", "publication_number", "section_id", "section_type", "example_id", "example_label",
    "fact_id", "fact_type", "material", "process_step", "condition_name", "condition_value",
    "condition_unit", "property_name", "property_value", "property_unit", "comparison_type",
    "comparison_target", "table_id", "evidence_text", "matched_user_keywords", "page_start",
    "page_end", "confidence", "needs_human_review", "extraction_method", "warning",
  ]
  summary_fields = [
    "case_id", "publication_number", "source_sections_csv", "target_section_count", "fact_count",
    "example_count", "comparative_example_count", "property_fact_count",
    "process_condition_fact_count", "matched_user_keyword_count", "needs_human_review",
    "status", "warning",
  ]

  all_facts = [fact for result in results for fact in result.facts]
  with facts_csv.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fact_fields)
    writer.writeheader()
    for fact in all_facts:
      writer.writerow({
        "case_id": fact.case_id,
        "publication_number": fact.publication_number,
        "section_id": fact.section_id,
        "section_type": fact.section_type,
        "example_id": fact.example_id or "",
        "example_label": fact.example_label or "",
        "fact_id": fact.fact_id,
        "fact_type": fact.fact_type,
        "material": fact.material or "",
        "process_step": fact.process_step or "",
        "condition_name": fact.condition_name or "",
        "condition_value": fact.condition_value or "",
        "condition_unit": fact.condition_unit or "",
        "property_name": fact.property_name or "",
        "property_value": fact.property_value or "",
        "property_unit": fact.property_unit or "",
        "comparison_type": fact.comparison_type or "",
        "comparison_target": fact.comparison_target or "",
        "table_id": fact.table_id or "",
        "evidence_text": fact.evidence_text,
        "matched_user_keywords": "|".join(fact.matched_user_keywords),
        "page_start": fact.page_start if fact.page_start is not None else "",
        "page_end": fact.page_end if fact.page_end is not None else "",
        "confidence": fact.confidence,
        "needs_human_review": fact.needs_human_review,
        "extraction_method": fact.extraction_method,
        "warning": fact.warning or "",
      })

  facts_json.write_text(
    json.dumps([f.to_dict() for f in all_facts], ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
  )

  md_lines = [f"# Example facts — {case_id}", "", *[f"- {n}" for n in EXAMPLE_FACTS_NOTICES], ""]
  for fact in all_facts[:100]:
    md_lines.append(f"## {fact.fact_id} ({fact.fact_type})")
    md_lines.append(f"- evidence: {fact.evidence_text[:300]}")
    md_lines.append(f"- matched_keywords: {', '.join(fact.matched_user_keywords)}")
    md_lines.append(f"- needs_human_review: {fact.needs_human_review}")
    md_lines.append("")
  facts_md.write_text("\n".join(md_lines), encoding="utf-8")

  with summary_csv.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=summary_fields)
    writer.writeheader()
    for result in results:
      writer.writerow({
        "case_id": result.case_id,
        "publication_number": result.publication_number,
        "source_sections_csv": result.source_sections_csv or "",
        "target_section_count": result.target_section_count,
        "fact_count": result.fact_count,
        "example_count": result.example_count,
        "comparative_example_count": result.comparative_example_count,
        "property_fact_count": result.property_fact_count,
        "process_condition_fact_count": result.process_condition_fact_count,
        "matched_user_keyword_count": result.matched_user_keyword_count,
        "needs_human_review": result.needs_human_review,
        "status": result.status,
        "warning": result.warning or "",
      })

  sum_md = [
    f"# Example facts summary — {case_id}",
    "",
    "| publication_number | facts | examples | property | process | keywords | review |",
    "| --- | --- | --- | --- | --- | --- | --- |",
  ]
  for result in results:
    sum_md.append(
      f"| {result.publication_number} | {result.fact_count} | {result.example_count} | "
      f"{result.property_fact_count} | {result.process_condition_fact_count} | "
      f"{result.matched_user_keyword_count} | {result.needs_human_review} |"
    )
  summary_md.write_text("\n".join(sum_md), encoding="utf-8")

  prompt_lines = [f"# Gemini prompts — {case_id}", ""]
  for section_id, prompt in prompts or []:
    prompt_lines.append(f"## Section {section_id}")
    prompt_lines.append("```")
    prompt_lines.append(prompt)
    prompt_lines.append("```")
    prompt_lines.append("")
  prompts_md.write_text("\n".join(prompt_lines), encoding="utf-8")

  vocab_copy.write_text(
    json.dumps(vocabulary.to_dict(), ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
  )

  for result in results:
    result.output_dir = str(out_dir)
  return out_dir


def load_example_facts_summary_from_dir(pack_dir: Path | str) -> dict[str, dict]:
  path = Path(pack_dir) / "example_facts_summary.csv"
  if not path.exists():
    return {}
  by_pub: dict[str, dict] = {}
  with path.open(encoding="utf-8", newline="") as handle:
    for row in csv.DictReader(handle):
      pub = normalize_publication_number(str(row.get("publication_number", "")))
      if pub:
        by_pub[pub] = row
  return by_pub


def get_example_facts_pipeline_status(
  case_id: str,
  publication_number: str,
  project_root: Path | str,
) -> dict[str, str | bool | int]:
  root = Path(project_root)
  norm = normalize_publication_number(publication_number)
  latest = find_latest_example_facts_dir(case_id, root)
  summary = load_example_facts_summary_from_dir(latest) if latest else {}
  row = summary.get(norm, {})

  facts_extracted = bool(row) and str(row.get("status", "")) not in {"", "no_target_sections"}
  fact_count = int(row.get("fact_count") or 0) if row else 0
  keyword_count = int(row.get("matched_user_keyword_count") or 0) if row else 0
  needs_review = str(row.get("needs_human_review", "")).lower() in {"true", "1"} or row.get("needs_human_review") is True

  return {
    "example_facts_extracted": facts_extracted and fact_count > 0,
    "facts_prompts_exported": facts_extracted,
    "fact_count": fact_count,
    "property_fact_count": int(row.get("property_fact_count") or 0) if row else 0,
    "process_condition_fact_count": int(row.get("process_condition_fact_count") or 0) if row else 0,
    "matched_user_keyword_count": keyword_count,
    "facts_needs_human_review": needs_review,
    "facts_status": str(row.get("status") or ""),
  }


def get_full_patent_document_pipeline_status(
  case_id: str,
  publication_number: str,
  project_root: Path | str,
) -> dict[str, str | bool | int]:
  from tech_cartography.services.v8_patent_section_extract import get_combined_patent_pdf_pipeline_status

  merged: dict[str, str | bool | int] = {
    **get_combined_patent_pdf_pipeline_status(case_id, publication_number, project_root),
    **get_example_facts_pipeline_status(case_id, publication_number, project_root),
  }

  if not merged["pdf_uploaded"]:
    next_action = "PDFを取得してアップロード"
  elif not merged["text_extracted"]:
    next_action = "Extract PDF text"
  elif merged.get("needs_ocr"):
    next_action = "画像PDFの可能性 — 将来OCR対象"
  elif not merged.get("sections_extracted"):
    next_action = "Extract sections"
  elif merged.get("has_examples") and not merged.get("example_facts_extracted"):
    next_action = "Extract example facts"
  elif merged.get("facts_needs_human_review") or merged.get("section_needs_human_review"):
    next_action = "抽出結果の人手確認が必要"
  elif merged.get("example_facts_extracted"):
    next_action = "Claim-example bindingへ（次Phase）"
  elif merged.get("has_examples"):
    next_action = "Extract example facts"
  else:
    next_action = "examples未検出 — セクション人手確認"

  merged["next_action"] = next_action
  return merged


def export_gemini_prompts_only(
  case_id: str,
  sections_csv_path: Path,
  output_root: Path,
  project_root: Path,
) -> Path:
  results, prompts, vocabulary = extract_example_facts_from_sections(
    case_id, sections_csv_path, output_root, project_root, use_gemini=False,
  )
  return write_example_facts_outputs(case_id, results, output_root, vocabulary, prompts)
