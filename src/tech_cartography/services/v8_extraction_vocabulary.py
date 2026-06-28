"""Extraction focus vocabulary service (Phase 27S.3)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from tech_cartography.runtime.v8_extraction_vocabulary_schema import ExtractionVocabulary
from tech_cartography.runtime.v8_sources_schema import utc_now_iso
from tech_cartography.services.v8_research_theme_defaults import load_research_theme_profile

CASE_01_ID = "case_01_pan_graphitization"

CASE_01_DEFAULT_VOCAB: dict[str, list[str]] = {
  "material_keywords": [
    "PAN", "polyacrylonitrile", "聚丙烯腈", "ポリアクリロニトリル", "precursor",
    "acrylic fiber", "原丝", "前駆体", "原糸", "carbon fiber", "炭素繊維",
  ],
  "process_keywords": [
    "stabilization", "oxidation", "pre-oxidation", "carbonization", "graphitization",
    "drawing", "stretching", "heat treatment", "预氧化", "碳化", "石墨化", "牵伸",
    "耐炎化", "酸化", "炭化", "黒鉛化", "延伸", "熱処理",
  ],
  "property_keywords": [
    "tensile strength", "tensile modulus", "elongation", "fineness", "density", "modulus",
    "拉伸强度", "拉伸模量", "伸长率", "线密度", "引張強度", "引張弾性率", "伸度", "繊度",
  ],
  "structure_keywords": [
    "orientation", "defect", "void", "fuzz", "fusion", "crystallinity", "graphite crystallite",
    "配向", "欠陥", "ボイド", "融着", "结晶", "取向",
  ],
  "comparison_keywords": [
    "example", "comparative example", "control", "实施例", "对比例", "実施例", "比較例",
  ],
  "table_keywords": ["table", "表", "表1", "Table 1"],
  "exclusion_keywords": [
    "CNT", "carbon nanotube", "graphene", "nanofiber", "activated carbon",
  ],
}


def vocabulary_path(case_id: str, project_root: Path | str) -> Path:
  return Path(project_root) / "cases" / case_id / "extraction_vocabulary.json"


def parse_keyword_text(text: str) -> list[str]:
  if not text:
    return []
  parts = re.split(r"[,，\n\r]+", text)
  seen_lower: set[str] = set()
  result: list[str] = []
  for part in parts:
    keyword = part.strip()
    if not keyword:
      continue
    key = keyword.lower()
    if key in seen_lower:
      continue
    seen_lower.add(key)
    result.append(keyword)
  return result


def keywords_to_text(keywords: list[str]) -> str:
  return "\n".join(keywords)


def get_default_extraction_vocabulary(case_id: str) -> ExtractionVocabulary:
  if case_id == CASE_01_ID:
    vocab = ExtractionVocabulary(
      case_id=case_id,
      material_keywords=list(CASE_01_DEFAULT_VOCAB["material_keywords"]),
      process_keywords=list(CASE_01_DEFAULT_VOCAB["process_keywords"]),
      property_keywords=list(CASE_01_DEFAULT_VOCAB["property_keywords"]),
      structure_keywords=list(CASE_01_DEFAULT_VOCAB["structure_keywords"]),
      comparison_keywords=list(CASE_01_DEFAULT_VOCAB["comparison_keywords"]),
      table_keywords=list(CASE_01_DEFAULT_VOCAB["table_keywords"]),
      exclusion_keywords=list(CASE_01_DEFAULT_VOCAB["exclusion_keywords"]),
      source="case_default",
    )
    return merge_theme_profile_into_vocabulary(case_id, vocab)

  theme = load_research_theme_profile(case_id)
  return ExtractionVocabulary(
    case_id=case_id,
    theme_name=theme.theme_name if theme else None,
    theme_description=theme.theme_description if theme else None,
    material_keywords=list(theme.material_process_keywords[:15]) if theme else [],
    process_keywords=[],
    property_keywords=[],
    structure_keywords=[],
    comparison_keywords=["example", "comparative example", "实施例", "对比例", "実施例", "比較例"],
    table_keywords=["table", "表", "Table 1", "表1"],
    exclusion_keywords=[],
    source="default",
  )


def merge_theme_profile_into_vocabulary(
  case_id: str,
  vocabulary: ExtractionVocabulary,
  theme_profile: dict | None = None,
) -> ExtractionVocabulary:
  theme = load_research_theme_profile(case_id) if theme_profile is None else None
  if theme:
    vocabulary.theme_name = theme.theme_name
    vocabulary.theme_description = theme.theme_description
  elif theme_profile:
    vocabulary.theme_name = theme_profile.get("theme_name")
    vocabulary.theme_description = theme_profile.get("theme_description")
  return vocabulary


def load_extraction_vocabulary(case_id: str, project_root: Path | str) -> ExtractionVocabulary:
  path = vocabulary_path(case_id, project_root)
  if path.exists():
    data = json.loads(path.read_text(encoding="utf-8"))
    return ExtractionVocabulary.from_dict(data)
  return get_default_extraction_vocabulary(case_id)


def save_extraction_vocabulary(
  case_id: str,
  project_root: Path | str,
  vocabulary: ExtractionVocabulary,
) -> Path:
  path = vocabulary_path(case_id, project_root)
  path.parent.mkdir(parents=True, exist_ok=True)
  vocabulary.case_id = case_id
  vocabulary.updated_at = utc_now_iso()
  if vocabulary.source == "default":
    vocabulary.source = "user"
  path.write_text(
    json.dumps(vocabulary.to_dict(), ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
  )
  return path


def build_vocabulary_context_for_prompt(vocabulary: ExtractionVocabulary) -> str:
  lines = ["## User extraction focus vocabulary (hints only — not a source of facts)"]
  if vocabulary.theme_name:
    lines.append(f"Research theme: {vocabulary.theme_name}")
  if vocabulary.theme_description:
    lines.append(f"Theme description: {vocabulary.theme_description}")
  for label, attr in (
    ("Material keywords", "material_keywords"),
    ("Process keywords", "process_keywords"),
    ("Property keywords", "property_keywords"),
    ("Structure keywords", "structure_keywords"),
    ("Comparison keywords", "comparison_keywords"),
    ("Table keywords", "table_keywords"),
    ("Exclusion hints (do not invent facts about these)", "exclusion_keywords"),
  ):
    values = getattr(vocabulary, attr)
    if values:
      lines.append(f"{label}: {', '.join(values)}")
  if vocabulary.user_notes:
    lines.append(f"User notes: {vocabulary.user_notes}")
  return "\n".join(lines)
