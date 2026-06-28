"""Claim-example binding service (Phase 27S.4) — rule-based, no LLM."""

from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

from tech_cartography.runtime.v8_claim_example_binding_schema import (
  CLAIM_EXAMPLE_BINDING_NOTICES,
  VALID_SUPPORT_LEVELS,
  VALID_SUPPORT_TYPES,
  ClaimExampleBindingResult,
  ClaimExampleLink,
)
from tech_cartography.runtime.v8_extraction_vocabulary_schema import ExtractionVocabulary
from tech_cartography.runtime.v8_research_theme_schema import normalize_publication_number
from tech_cartography.runtime.v8_sources_schema import utc_now_iso
from tech_cartography.services.v8_claim_input_loader import load_claims_input_csv
from tech_cartography.services.v8_extraction_vocabulary import load_extraction_vocabulary
from tech_cartography.services.v8_gemini_example_facts import find_latest_example_facts_dir
from tech_cartography.services.v8_sources_table import project_root_from_here

OUTPUT_SUBDIR = "local_v8_claim_example_links"
BINDING_METHOD = "rule_keyword_match"
BINDING_VERSION = "phase27s54"
PUBLICATION_LEVEL_KEY = "__publication_level__"
MAX_LINKED_FACT_IDS = 10
MAX_EVIDENCE_SNIPPETS = 5
MAX_TYPE_EVIDENCE = 3

_SECTION_EXAMPLE_ID_RE = re.compile(r"_examples?_(\d+)\b", re.IGNORECASE)
_EVIDENCE_EXAMPLE_RE = re.compile(r"(?:实施例|実施例|Example)\s*(\d+)", re.IGNORECASE)

FACT_TYPE_PROCESS = frozenset({"process_condition"})
FACT_TYPE_PROPERTY = frozenset({"property_value", "property_candidate"})
FACT_TYPE_STRUCTURE = frozenset({"structure_property", "structure_characterization"})
FACT_TYPE_TABLE = frozenset({"table_candidate", "table_value"})
FACT_TYPE_COMPARISON = frozenset({"comparison_candidate", "comparison_example"})

FORBIDDEN_REASON_WORDS = frozenset({
  "裏取り完了", "証明", "権利範囲を支える", "支えています", "証明しています",
  "有効", "侵害", "fto", "無効", "権利範囲を確認",
})


def find_latest_example_facts_output(case_id: str, output_root: Path | str) -> Path | None:
  root = Path(output_root)
  project_root = root.parent if root.name == "outputs" else root
  latest = find_latest_example_facts_dir(case_id, project_root)
  if latest and (latest / "example_facts.csv").exists():
    return latest
  base = project_root / "outputs" / "local_v8_example_facts"
  if base.is_dir():
    dirs = [p for p in base.iterdir() if p.is_dir() and p.name.startswith(f"{case_id}_")]
    if dirs:
      candidate = max(dirs, key=lambda p: p.stat().st_mtime)
      if (candidate / "example_facts.csv").exists():
        return candidate
  return None


def find_latest_claim_example_links_dir(
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
  return pack if (pack / "claim_example_binding_summary.csv").exists() else None


def load_claims_input(case_id: str, project_root: Path | str) -> list[dict[str, str]]:
  rows, _warnings = load_claims_input_csv(case_id, project_root=project_root)
  result: list[dict[str, str]] = []
  for row in rows:
    if not row.has_loaded_text():
      continue
    result.append({
      "case_id": row.case_id,
      "publication_number": normalize_publication_number(row.publication_number),
      "claim_no": str(row.claim_no),
      "claim_text": row.claim_text,
      "source": row.claim_source_type,
      "status": "loaded",
    })
  return result


def load_example_facts(example_facts_csv: Path) -> list[dict[str, str]]:
  facts: list[dict[str, str]] = []
  with example_facts_csv.open(encoding="utf-8", newline="") as handle:
    for row in csv.DictReader(handle):
      facts.append(dict(row))
  return facts


def normalize_claim_text(text: str) -> str:
  return " ".join(text.split()).strip()


def _text_contains(haystack: str, needle: str) -> bool:
  if not needle or not haystack:
    return False
  return needle.lower() in haystack.lower()


def extract_claim_terms(
  claim_text: str,
  vocabulary: ExtractionVocabulary | None,
) -> dict[str, list[str]]:
  text = claim_text.lower()
  terms: dict[str, list[str]] = {
    "material": [],
    "process": [],
    "property": [],
    "structure": [],
    "comparison": [],
  }
  if not vocabulary:
    return terms
  mapping = {
    "material": vocabulary.material_keywords,
    "process": vocabulary.process_keywords,
    "property": vocabulary.property_keywords,
    "structure": vocabulary.structure_keywords,
    "comparison": vocabulary.comparison_keywords,
  }
  seen: set[str] = set()
  for category, keywords in mapping.items():
    for kw in keywords:
      key = kw.lower()
      if key in seen:
        continue
      if key in text:
        seen.add(key)
        terms[category].append(kw)
  return terms


def _clean_field(value: object) -> str | None:
  if value is None:
    return None
  text = str(value).strip()
  if not text or text.lower() in {"nan", "none", "null", ""}:
    return None
  return text


def _infer_example_from_section_id(section_id: str) -> str | None:
  match = _SECTION_EXAMPLE_ID_RE.search(section_id)
  if match:
    return f"Example {match.group(1)}"
  return None


def _infer_example_from_evidence(evidence: str) -> str | None:
  match = _EVIDENCE_EXAMPLE_RE.search(evidence)
  if match:
    return f"Example {match.group(1)}"
  return None


def _normalize_example_identifier(value: object) -> str | None:
  raw = _clean_field(value)
  if not raw:
    return None
  if re.match(r"^fact_\d+$", raw, re.IGNORECASE):
    return None
  cn = re.match(r"^实施例\s*(\d+)$", raw)
  if cn:
    return f"Example {cn.group(1)}"
  en = re.match(r"^Example\s*(\d+)$", raw, re.IGNORECASE)
  if en:
    return f"Example {en.group(1)}"
  if raw.startswith("CN") and "_examples_" in raw:
    return _infer_example_from_section_id(raw)
  if "_Example_" in raw:
    tail = raw.rsplit("_Example_", 1)[-1]
    en2 = re.match(r"^(\d+)$", tail.strip())
    if en2:
      return f"Example {en2.group(1)}"
  return raw


def _example_group_key(fact: dict) -> tuple[str, str | None, str | None, bool]:
  example_id = _normalize_example_identifier(fact.get("example_id"))
  example_label = _normalize_example_identifier(fact.get("example_label"))
  section_id = _clean_field(fact.get("section_id")) or ""
  section_type = str(fact.get("section_type") or "")
  evidence = str(fact.get("evidence_text") or "")

  inferred_from_section = _infer_example_from_section_id(section_id)
  inferred_from_evidence = _infer_example_from_evidence(evidence)

  if example_id:
    return example_id, example_id, example_label or inferred_from_section, False
  if example_label:
    return example_label, inferred_from_evidence or inferred_from_section or example_label, example_label, False
  if inferred_from_section:
    return inferred_from_section, inferred_from_section, example_label, False
  if inferred_from_evidence:
    return inferred_from_evidence, inferred_from_evidence, example_label, False
  if section_id and ("example" in section_id.lower() or "实施例" in section_id):
    return section_id, inferred_from_section, section_id, False
  if section_type == "table_candidate" and section_id:
    return section_id, inferred_from_evidence, example_label, inferred_from_evidence is None
  if section_id:
    return section_id, inferred_from_evidence, example_label, inferred_from_evidence is None
  return PUBLICATION_LEVEL_KEY, None, None, True


def group_example_facts_by_publication_and_example(
  facts: list[dict],
) -> dict[str, dict[str, list[dict]]]:
  grouped: dict[str, dict[str, list[dict]]] = defaultdict(lambda: defaultdict(list))
  for fact in facts:
    evidence = str(fact.get("evidence_text") or "").strip()
    if not evidence:
      continue
    pub = normalize_publication_number(str(fact.get("publication_number", "")))
    if not pub:
      continue
    group_key, _, _, _ = _example_group_key(fact)
    grouped[pub][group_key].append(fact)
  return grouped


def _score_level(score: int, matched_count: int, category_count: int) -> str:
  if matched_count >= 5 and category_count >= 2:
    return "high_candidate"
  if score >= 7 or (matched_count >= 5 and category_count >= 1):
    return "high_candidate"
  if score >= 4 or matched_count >= 3:
    return "medium_candidate"
  if score >= 2 or matched_count >= 1:
    return "low_candidate"
  return "none"


def _fact_type_category(fact_type: str) -> str | None:
  if fact_type in FACT_TYPE_PROCESS:
    return "process"
  if fact_type in FACT_TYPE_PROPERTY:
    return "property"
  if fact_type in FACT_TYPE_STRUCTURE:
    return "structure"
  if fact_type in FACT_TYPE_TABLE:
    return "table"
  if fact_type in FACT_TYPE_COMPARISON:
    return "comparison"
  return None


def _determine_support_type(
  *,
  process_count: int,
  property_count: int,
  structure_count: int,
  table_count: int,
  comparison_count: int,
  is_publication_level: bool,
  matched_count: int,
) -> str:
  if matched_count == 0:
    return "no_example_support_candidate"
  if is_publication_level:
    return "publication_level_support_candidate"
  categories = sum(
    1 for count in (process_count, property_count, structure_count, table_count, comparison_count)
    if count > 0
  )
  if categories >= 2:
    return "mixed_support_candidate"
  if table_count > 0 and table_count >= max(process_count, property_count, structure_count, comparison_count):
    return "table_support_candidate"
  if comparison_count > 0 and comparison_count >= max(process_count, property_count, structure_count, table_count):
    return "comparison_support_candidate"
  if structure_count > 0 and structure_count >= max(process_count, property_count, table_count, comparison_count):
    return "structure_support_candidate"
  if property_count > 0 and property_count >= max(process_count, structure_count, table_count, comparison_count):
    return "property_support_candidate"
  if process_count > 0:
    return "process_support_candidate"
  return "partial_example_support_candidate"


def _fact_matches_claim(
  claim_text: str,
  fact: dict,
  claim_terms: dict[str, list[str]],
) -> bool:
  evidence = str(fact.get("evidence_text") or "").strip()
  if not evidence:
    return False
  claim_lower = claim_text.lower()
  evidence_lower = evidence.lower()
  for field in (
    "material", "process_step", "property_name", "condition_name",
    "property_value", "condition_value", "comparison_target",
  ):
    val = _clean_field(fact.get(field))
    if val and val.lower() in claim_lower:
      return True
    if val and _text_contains(evidence, val):
      for terms in claim_terms.values():
        if any(_text_contains(t, val) or _text_contains(val, t) for t in terms):
          return True
  for terms in claim_terms.values():
    for kw in terms:
      if kw.lower() in evidence_lower or kw.lower() in claim_lower:
        if kw.lower() in evidence_lower:
          return True
  prop_name = _clean_field(fact.get("property_name"))
  if prop_name and (prop_name.replace("_", " ") in claim_lower or prop_name in claim_lower):
    return True

  fact_type = str(fact.get("fact_type") or "")
  if fact_type in FACT_TYPE_PROPERTY | FACT_TYPE_STRUCTURE:
    normalized = (prop_name or "").replace("_", " ")
    for kw in claim_terms.get("property", []) + claim_terms.get("structure", []):
      if kw.lower() in claim_lower and (
        kw.lower() in evidence_lower
        or normalized.lower() in kw.lower()
        or kw.lower() in normalized.lower()
      ):
        return True

  if fact_type in FACT_TYPE_PROCESS:
    for kw in claim_terms.get("process", []):
      if kw.lower() not in claim_lower:
        continue
      if kw.lower() in evidence_lower:
        return True
      step = (_clean_field(fact.get("process_step")) or "").lower()
      if step and (step in kw.lower() or kw.lower() in step):
        return True
    if "graphitization" in claim_lower and "石墨化" in evidence:
      return True
    if "carbonization" in claim_lower and "碳化" in evidence:
      return True
    if ("stretch" in claim_lower or "ratio" in claim_lower) and ("拉伸" in evidence or "倍率" in evidence):
      return True
    if ("time" in claim_lower or "dwell" in claim_lower or "min" in claim_lower) and (
      "时间" in evidence or "min" in evidence_lower
    ):
      return True

  if fact_type in FACT_TYPE_TABLE | FACT_TYPE_COMPARISON:
    if any(token in claim_lower for token in ("comparison", "table", "strength", "modulus", "performance")):
      if any(token in evidence for token in ("表", "对比", "M55", "M60", "Toray", "东丽")):
        return True

  return False


def _matched_element_from_fact(fact: dict) -> str | None:
  for field in (
    "property_name", "process_step", "condition_name", "material",
    "property_value", "condition_value", "comparison_target",
  ):
    val = _clean_field(fact.get(field))
    if val:
      return val
  fact_type = str(fact.get("fact_type") or "")
  if fact_type:
    return fact_type
  return None


def _resolve_example_identity(
  group_key: str,
  facts: list[dict],
) -> tuple[str | None, str | None, bool]:
  is_publication_level = group_key == PUBLICATION_LEVEL_KEY
  example_id = None
  example_label = None
  for fact in facts:
    example_id = example_id or _normalize_example_identifier(fact.get("example_id"))
    example_label = example_label or _normalize_example_identifier(fact.get("example_label"))
    section_id = _clean_field(fact.get("section_id")) or ""
    evidence = str(fact.get("evidence_text") or "")
    example_id = example_id or _infer_example_from_section_id(section_id)
    example_id = example_id or _infer_example_from_evidence(evidence)
  if is_publication_level and not example_id:
    return None, None, True
  if not example_id and group_key != PUBLICATION_LEVEL_KEY:
    if group_key.startswith("Example") or "实施例" in group_key:
      example_id = group_key
    elif not example_label:
      example_label = group_key
  if example_id:
    is_publication_level = False
  return example_id, example_label, is_publication_level


def _match_field(text: str, value: str | None) -> bool:
  return bool(value and _text_contains(text, value))


def score_claim_example_candidate(
  claim: dict,
  example_facts: list[dict],
  vocabulary: ExtractionVocabulary | None,
  *,
  group_key: str = "",
  source_example_facts_csv: str | None = None,
) -> tuple[int, ClaimExampleLink]:
  case_id = str(claim.get("case_id", ""))
  pub = normalize_publication_number(str(claim.get("publication_number", "")))
  claim_no = str(claim.get("claim_no", ""))
  claim_text = normalize_claim_text(str(claim.get("claim_text", "")))
  claim_terms = extract_claim_terms(claim_text, vocabulary)

  valid_facts = [
    f for f in example_facts
    if str(f.get("evidence_text") or "").strip()
    and normalize_publication_number(str(f.get("publication_number", ""))) == pub
  ]
  warnings: list[str] = []
  if len(valid_facts) < len(example_facts):
    warnings.append("facts without evidence_text were excluded")

  example_id, example_label, is_publication_level = _resolve_example_identity(group_key, valid_facts)

  score = 0
  matched: set[str] = set()
  missing: set[str] = set()
  matched_keywords: set[str] = set()
  linked_ids: list[str] = []
  matched_fact_types: set[str] = set()
  evidence_texts: list[str] = []
  process_evidence: list[str] = []
  property_evidence: list[str] = []
  structure_evidence: list[str] = []
  table_evidence: list[str] = []
  comparison_evidence: list[str] = []
  process_count = 0
  property_count = 0
  structure_count = 0
  table_count = 0
  comparison_count = 0

  for fact in valid_facts:
    if not _fact_matches_claim(claim_text, fact, claim_terms):
      continue

    fact_id = str(fact.get("fact_id") or "")
    if fact_id:
      linked_ids.append(fact_id)
    evidence = str(fact.get("evidence_text") or "").strip()
    evidence_texts.append(evidence)
    fact_type = str(fact.get("fact_type") or "unknown")
    matched_fact_types.add(fact_type)
    element = _matched_element_from_fact(fact)
    if element:
      matched.add(element)

    category = _fact_type_category(fact_type)
    if category == "process":
      process_count += 1
      process_evidence.append(evidence)
      score += 3
    elif category == "property":
      property_count += 1
      property_evidence.append(evidence)
      score += 3
    elif category == "structure":
      structure_count += 1
      structure_evidence.append(evidence)
      score += 2
    elif category == "table":
      table_count += 1
      table_evidence.append(evidence)
      score += 2
    elif category == "comparison":
      comparison_count += 1
      comparison_evidence.append(evidence)
      score += 2
    else:
      score += 1

    for kw in str(fact.get("matched_user_keywords") or "").split("|"):
      kw = kw.strip()
      if kw and (_text_contains(claim_text, kw) or _text_contains(evidence, kw)):
        matched_keywords.add(kw)
        score += 1

  matched_count = len(linked_ids)
  category_count = sum(
    1 for c in (process_count, property_count, structure_count, table_count, comparison_count) if c > 0
  )

  for category, kws in claim_terms.items():
    for kw in kws:
      found = kw in matched or any(_text_contains(ev, kw) for ev in evidence_texts)
      if found:
        matched.add(kw)
      else:
        missing.add(kw)

  if claim_terms["property"] and property_count == 0:
    missing.update(claim_terms["property"])
  if claim_terms["process"] and process_count == 0:
    missing.update(claim_terms["process"])
  if claim_terms["comparison"] and comparison_count == 0:
    missing.update(claim_terms["comparison"])

  support_level = _score_level(score, matched_count, category_count)
  support_type = _determine_support_type(
    process_count=process_count,
    property_count=property_count,
    structure_count=structure_count,
    table_count=table_count,
    comparison_count=comparison_count,
    is_publication_level=is_publication_level,
    matched_count=matched_count,
  )
  if support_level == "none":
    support_type = "no_example_support_candidate"

  top_snippets = evidence_texts[:MAX_EVIDENCE_SNIPPETS]
  reason = _build_reason(
    claim_no=claim_no,
    example_id=example_id,
    example_label=example_label,
    matched=sorted(matched),
    missing=sorted(missing),
    support_level=support_level,
    support_type=support_type,
    matched_fact_types=sorted(matched_fact_types),
    top_evidence=top_snippets,
    is_publication_level=is_publication_level,
  )

  confidence = min(1.0, round(score / 12.0, 3))
  link = ClaimExampleLink(
    case_id=case_id,
    publication_number=pub,
    claim_no=claim_no,
    claim_text=claim_text,
    example_id=example_id,
    example_label=example_label,
    linked_fact_ids=linked_ids[:MAX_LINKED_FACT_IDS],
    support_type=support_type,
    support_level=support_level,
    matched_elements=sorted(matched),
    missing_elements=sorted(missing),
    matched_user_keywords=sorted(matched_keywords),
    evidence_texts=evidence_texts[:MAX_EVIDENCE_SNIPPETS],
    reason=reason,
    confidence=confidence,
    needs_human_review=True,
    binding_method=BINDING_METHOD,
    warning="; ".join(warnings) if warnings else None,
    matched_fact_types=sorted(matched_fact_types),
    matched_fact_count=matched_count,
    process_match_count=process_count,
    property_match_count=property_count,
    structure_match_count=structure_count,
    table_match_count=table_count,
    comparison_match_count=comparison_count,
    selected_example_score=score,
    top_evidence_snippets=top_snippets,
    process_evidence_texts=process_evidence[:MAX_TYPE_EVIDENCE],
    property_evidence_texts=property_evidence[:MAX_TYPE_EVIDENCE],
    structure_evidence_texts=structure_evidence[:MAX_TYPE_EVIDENCE],
    table_evidence_texts=table_evidence[:MAX_TYPE_EVIDENCE],
    comparison_evidence_texts=comparison_evidence[:MAX_TYPE_EVIDENCE],
    source_example_facts_csv=source_example_facts_csv,
    binding_version=BINDING_VERSION,
  )
  return score, link


def _build_reason(
  *,
  claim_no: str,
  example_id: str | None,
  example_label: str | None,
  matched: list[str],
  missing: list[str],
  support_level: str,
  support_type: str,
  matched_fact_types: list[str],
  top_evidence: list[str],
  is_publication_level: bool,
) -> str:
  if example_id:
    ex_ref = example_id
  elif example_label:
    ex_ref = example_label
  elif is_publication_level:
    ex_ref = "publication-level facts"
  else:
    ex_ref = "抽出ファクト"

  type_txt = "、".join(matched_fact_types[:6]) if matched_fact_types else "（fact_type未特定）"
  matched_txt = "、".join(matched[:8]) if matched else "（一致語なし）"
  evidence_txt = " / ".join(e[:80] for e in top_evidence[:3]) if top_evidence else "（根拠候補なし）"

  parts = [
    f"claim {claim_no} は {ex_ref} の",
  ]
  if support_type == "mixed_support_candidate":
    parts.append("工程条件・物性候補・表候補")
  elif support_type == "process_support_candidate":
    parts.append("工程条件候補")
  elif support_type == "property_support_candidate":
    parts.append("物性候補")
  elif support_type == "structure_support_candidate":
    parts.append("構造指標候補")
  elif support_type == "table_support_candidate":
    parts.append("表候補")
  elif support_type == "comparison_support_candidate":
    parts.append("比較表候補")
  else:
    parts.append("抽出ファクト")
  parts.append("と対応する可能性があります。")
  parts.append(f"主な一致候補: {matched_txt}。")
  parts.append(f"fact_type: {type_txt}。")
  parts.append(f"根拠候補: {evidence_txt}。")
  if missing:
    parts.append(f"未確認: {'、'.join(missing[:5])}。")
  parts.append("OCR由来の可能性があり、人手確認が必要です（候補）。")
  parts.append(f"support_level={support_level}, support_type={support_type}。")
  reason = "".join(parts)
  if len(reason) > 1000:
    reason = reason[:997] + "..."
  for forbidden in FORBIDDEN_REASON_WORDS:
    if forbidden.lower() in reason.lower():
      reason = reason.replace(forbidden, "未確認")
  return reason


def bind_claims_to_example_facts(
  case_id: str,
  project_root: Path,
  output_root: Path,
  *,
  max_examples_per_claim: int = 3,
) -> list[ClaimExampleBindingResult]:
  del max_examples_per_claim  # best example group per claim for now
  vocabulary = load_extraction_vocabulary(case_id, project_root)
  claims = load_claims_input(case_id, project_root)
  facts_dir = find_latest_example_facts_output(case_id, output_root)
  if not facts_dir:
    return [ClaimExampleBindingResult(
      case_id=case_id,
      publication_number="",
      status="no_example_facts",
      warning="example_facts.csv not found",
      needs_human_review=True,
    )]

  facts = load_example_facts(facts_dir / "example_facts.csv")
  grouped = group_example_facts_by_publication_and_example(facts)

  by_pub_claims: dict[str, list[dict]] = defaultdict(list)
  for claim in claims:
    by_pub_claims[normalize_publication_number(str(claim.get("publication_number", "")))].append(claim)

  results: list[ClaimExampleBindingResult] = []
  for pub, pub_claims in sorted(by_pub_claims.items()):
    if not pub:
      continue
    links: list[ClaimExampleLink] = []
    example_groups = grouped.get(pub, {})

    for claim in pub_claims:
      if not example_groups:
        _, link = score_claim_example_candidate(
          claim, [], vocabulary,
          source_example_facts_csv=str(facts_dir / "example_facts.csv"),
        )
        links.append(link)
        continue

      candidates: list[tuple[int, ClaimExampleLink]] = []
      for group_key, group_facts in example_groups.items():
        score, link = score_claim_example_candidate(
          claim, group_facts, vocabulary,
          group_key=group_key,
          source_example_facts_csv=str(facts_dir / "example_facts.csv"),
        )
        has_example = bool(link.example_id or link.example_label)
        adjusted = score + (5 if has_example else 0)
        candidates.append((adjusted, link))

      candidates.sort(key=lambda item: item[0], reverse=True)
      best_score, best_link = candidates[0] if candidates else (-1, None)
      if best_link and not (best_link.example_id or best_link.example_label):
        for alt_score, alt_link in candidates[1:]:
          if (alt_link.example_id or alt_link.example_label) and alt_score >= max(1, int(best_score * 0.5)):
            best_link = alt_link
            break

      links.append(best_link or score_claim_example_candidate(
        claim, [], vocabulary, source_example_facts_csv=str(facts_dir / "example_facts.csv"),
      )[1])

    linked = sum(1 for link in links if link.support_level != "none")
    unlinked = len(links) - linked
    strong = sum(1 for link in links if link.support_level == "high_candidate")
    partial = sum(1 for link in links if link.support_type == "partial_example_support_candidate")
    prop = sum(1 for link in links if link.support_type == "property_support_candidate")
    comp = sum(1 for link in links if link.support_type in {"comparison_support_candidate", "comparison_candidate"})
    none_count = sum(1 for link in links if link.support_type == "no_example_support_candidate")
    process_support = sum(1 for link in links if link.support_type == "process_support_candidate")
    structure_support = sum(1 for link in links if link.support_type == "structure_support_candidate")
    table_support = sum(1 for link in links if link.support_type == "table_support_candidate")
    mixed_support = sum(1 for link in links if link.support_type == "mixed_support_candidate")
    pub_level_support = sum(1 for link in links if link.support_type == "publication_level_support_candidate")
    linked_fact_count = sum(link.matched_fact_count for link in links)
    linked_examples = {
      link.example_id or link.example_label
      for link in links
      if link.support_level != "none" and (link.example_id or link.example_label)
    }

    results.append(ClaimExampleBindingResult(
      case_id=case_id,
      publication_number=pub,
      claim_count=len(pub_claims),
      linked_claim_count=linked,
      unlinked_claim_count=unlinked,
      link_count=len(links),
      strong_candidate_count=strong,
      partial_candidate_count=partial,
      property_candidate_count=prop,
      comparison_candidate_count=comp,
      no_candidate_count=none_count,
      process_support_count=process_support,
      property_support_count=prop,
      structure_support_count=structure_support,
      table_support_count=table_support,
      comparison_support_count=comp,
      mixed_support_count=mixed_support,
      publication_level_support_count=pub_level_support,
      linked_fact_count=linked_fact_count,
      linked_example_count=len(linked_examples),
      source_example_facts_csv=str(facts_dir / "example_facts.csv"),
      needs_human_review=True,
      links=links,
      status="ok" if facts else "no_facts_for_pub",
      warning=None if example_groups else f"no example facts for {pub}",
    ))

  if not results and claims:
    results.append(ClaimExampleBindingResult(
      case_id=case_id,
      publication_number="",
      claim_count=len(claims),
      unlinked_claim_count=len(claims),
      no_candidate_count=len(claims),
      status="no_match",
      warning="claims loaded but no binding results",
      needs_human_review=True,
    ))
  return results


def _build_review_prompt(link: ClaimExampleLink) -> str:
  return "\n".join([
    f"Review claim-example binding candidate for {link.publication_number} claim {link.claim_no}.",
    "Do not invent facts. Assess whether evidence_text supports the claim elements as candidates only.",
    f"Claim text: {link.claim_text[:2000]}",
    f"Support type: {link.support_type} / level: {link.support_level}",
    f"Matched elements: {', '.join(link.matched_elements)}",
    f"Missing elements: {', '.join(link.missing_elements)}",
    "Evidence texts:",
    *[f"- {t[:500]}" for t in link.evidence_texts[:5]],
    "Return JSON review notes only — human review required.",
  ])


def write_claim_example_binding_outputs(
  case_id: str,
  results: list[ClaimExampleBindingResult],
  output_root: Path,
) -> Path:
  stamp = utc_now_iso().replace(":", "").replace("-", "").replace("+00:00", "Z")
  digest = hashlib.sha256(f"{case_id}|claim_example|{stamp}".encode()).hexdigest()[:8]
  out_dir = Path(output_root) / OUTPUT_SUBDIR / f"{case_id}_{stamp}_{digest}"
  out_dir.mkdir(parents=True, exist_ok=True)

  links_csv = out_dir / "claim_example_links.csv"
  links_json = out_dir / "claim_example_links.json"
  links_md = out_dir / "claim_example_links.md"
  summary_csv = out_dir / "claim_example_binding_summary.csv"
  summary_md = out_dir / "claim_example_binding_summary.md"
  review_md = out_dir / "claim_example_review_prompts.md"

  link_fields = [
    "case_id", "publication_number", "claim_no", "claim_text", "example_id", "example_label",
    "linked_fact_ids", "support_type", "support_level", "matched_elements", "missing_elements",
    "matched_user_keywords", "evidence_texts", "reason", "confidence", "needs_human_review",
    "binding_method", "warning", "matched_fact_types", "matched_fact_count",
    "process_match_count", "property_match_count", "structure_match_count", "table_match_count",
    "comparison_match_count", "selected_example_score", "top_evidence_snippets",
    "process_evidence_texts", "property_evidence_texts", "structure_evidence_texts",
    "table_evidence_texts", "comparison_evidence_texts", "source_example_facts_csv",
    "binding_version",
  ]
  summary_fields = [
    "case_id", "publication_number", "claim_count", "linked_claim_count", "unlinked_claim_count",
    "link_count", "strong_candidate_count", "partial_candidate_count", "property_candidate_count",
    "comparison_candidate_count", "no_candidate_count", "process_support_count",
    "property_support_count", "structure_support_count", "table_support_count",
    "comparison_support_count", "mixed_support_count", "publication_level_support_count",
    "linked_fact_count", "linked_example_count", "source_example_facts_csv",
    "needs_human_review", "status", "warning",
  ]

  all_links = [link for result in results for link in result.links]
  with links_csv.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=link_fields)
    writer.writeheader()
    for link in all_links:
      writer.writerow({
        "case_id": link.case_id,
        "publication_number": link.publication_number,
        "claim_no": link.claim_no,
        "claim_text": link.claim_text,
        "example_id": link.example_id or "",
        "example_label": link.example_label or "",
        "linked_fact_ids": ";".join(link.linked_fact_ids),
        "support_type": link.support_type,
        "support_level": link.support_level,
        "matched_elements": "|".join(link.matched_elements),
        "missing_elements": "|".join(link.missing_elements),
        "matched_user_keywords": "|".join(link.matched_user_keywords),
        "evidence_texts": " || ".join(link.evidence_texts),
        "reason": link.reason,
        "confidence": link.confidence,
        "needs_human_review": link.needs_human_review,
        "binding_method": link.binding_method,
        "warning": link.warning or "",
        "matched_fact_types": "|".join(link.matched_fact_types),
        "matched_fact_count": link.matched_fact_count,
        "process_match_count": link.process_match_count,
        "property_match_count": link.property_match_count,
        "structure_match_count": link.structure_match_count,
        "table_match_count": link.table_match_count,
        "comparison_match_count": link.comparison_match_count,
        "selected_example_score": link.selected_example_score,
        "top_evidence_snippets": " || ".join(link.top_evidence_snippets),
        "process_evidence_texts": " || ".join(link.process_evidence_texts),
        "property_evidence_texts": " || ".join(link.property_evidence_texts),
        "structure_evidence_texts": " || ".join(link.structure_evidence_texts),
        "table_evidence_texts": " || ".join(link.table_evidence_texts),
        "comparison_evidence_texts": " || ".join(link.comparison_evidence_texts),
        "source_example_facts_csv": link.source_example_facts_csv or "",
        "binding_version": link.binding_version,
      })

  links_json.write_text(
    json.dumps([link.to_dict() for link in all_links], ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
  )

  md_lines = [f"# Claim-example links — {case_id}", "", *[f"- {n}" for n in CLAIM_EXAMPLE_BINDING_NOTICES], ""]
  for link in all_links[:50]:
    md_lines.append(f"## {link.publication_number} claim {link.claim_no}")
    md_lines.append(f"- support: {link.support_type} / {link.support_level}")
    md_lines.append(f"- reason: {link.reason}")
    md_lines.append(f"- evidence: {' | '.join(link.evidence_texts[:2])}")
    md_lines.append("")
  links_md.write_text("\n".join(md_lines), encoding="utf-8")

  with summary_csv.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=summary_fields)
    writer.writeheader()
    for result in results:
      writer.writerow({
        "case_id": result.case_id,
        "publication_number": result.publication_number,
        "claim_count": result.claim_count,
        "linked_claim_count": result.linked_claim_count,
        "unlinked_claim_count": result.unlinked_claim_count,
        "link_count": result.link_count,
        "strong_candidate_count": result.strong_candidate_count,
        "partial_candidate_count": result.partial_candidate_count,
        "property_candidate_count": result.property_candidate_count,
        "comparison_candidate_count": result.comparison_candidate_count,
        "no_candidate_count": result.no_candidate_count,
        "process_support_count": result.process_support_count,
        "property_support_count": result.property_support_count,
        "structure_support_count": result.structure_support_count,
        "table_support_count": result.table_support_count,
        "comparison_support_count": result.comparison_support_count,
        "mixed_support_count": result.mixed_support_count,
        "publication_level_support_count": result.publication_level_support_count,
        "linked_fact_count": result.linked_fact_count,
        "linked_example_count": result.linked_example_count,
        "source_example_facts_csv": result.source_example_facts_csv or "",
        "needs_human_review": result.needs_human_review,
        "status": result.status,
        "warning": result.warning or "",
      })

  sum_md = [
    f"# Claim-example binding summary — {case_id}",
    "",
    "| publication | claims | linked | unlinked | strong | property | comparison | no_candidate |",
    "| --- | --- | --- | --- | --- | --- | --- | --- |",
  ]
  for result in results:
    sum_md.append(
      f"| {result.publication_number} | {result.claim_count} | {result.linked_claim_count} | "
      f"{result.unlinked_claim_count} | {result.strong_candidate_count} | "
      f"{result.property_candidate_count} | {result.comparison_candidate_count} | "
      f"{result.no_candidate_count} |"
    )
  summary_md.write_text("\n".join(sum_md), encoding="utf-8")

  prompts = [f"## {link.publication_number} claim {link.claim_no}\n```\n{_build_review_prompt(link)}\n```\n" for link in all_links[:100]]
  review_md.write_text(
    f"# Claim-example review prompts — {case_id}\n\n" + "\n".join(prompts),
    encoding="utf-8",
  )

  for result in results:
    result.output_dir = str(out_dir)
  return out_dir


def should_rerun_claim_example_binding(
  case_id: str,
  project_root: Path | str,
) -> tuple[bool, str | None, str | None]:
  """True when latest example_facts is newer than latest binding output."""
  root = Path(project_root)
  output_root = root / "outputs"
  facts_dir = find_latest_example_facts_output(case_id, output_root)
  bind_dir = find_latest_claim_example_links_dir(case_id, root)
  if not facts_dir:
    return False, None, None
  facts_csv = facts_dir / "example_facts.csv"
  if not bind_dir:
    return True, str(facts_csv), None
  bind_csv = bind_dir / "claim_example_links.csv"
  summary = load_binding_summary_from_dir(bind_dir)
  source_from_summary = next(
    (str(row.get("source_example_facts_csv") or "") for row in summary.values() if row.get("source_example_facts_csv")),
    "",
  )
  facts_mtime = facts_csv.stat().st_mtime if facts_csv.exists() else 0
  bind_mtime = bind_csv.stat().st_mtime if bind_csv.exists() else 0
  if facts_mtime > bind_mtime:
    return True, str(facts_csv), str(bind_dir)
  if source_from_summary and Path(source_from_summary).resolve() != facts_csv.resolve():
    return True, str(facts_csv), str(bind_dir)
  return False, str(facts_csv), str(bind_dir)


def load_binding_summary_from_dir(pack_dir: Path | str) -> dict[str, dict]:
  path = Path(pack_dir) / "claim_example_binding_summary.csv"
  if not path.exists():
    return {}
  by_pub: dict[str, dict] = {}
  with path.open(encoding="utf-8", newline="") as handle:
    for row in csv.DictReader(handle):
      pub = normalize_publication_number(str(row.get("publication_number", "")))
      if pub:
        by_pub[pub] = row
  return by_pub


def get_claim_example_binding_pipeline_status(
  case_id: str,
  publication_number: str,
  project_root: Path | str,
) -> dict[str, str | bool | int]:
  root = Path(project_root)
  norm = normalize_publication_number(publication_number)
  latest = find_latest_claim_example_links_dir(case_id, root)
  summary = load_binding_summary_from_dir(latest) if latest else {}
  row = summary.get(norm, {})

  generated = bool(row) and str(row.get("status", "")) not in {"", "no_example_facts"}
  linked = int(row.get("linked_claim_count") or 0) if row else 0
  unlinked = int(row.get("unlinked_claim_count") or 0) if row else 0

  return {
    "claim_example_links_generated": generated and int(row.get("link_count") or 0) > 0,
    "linked_claim_count": linked,
    "unlinked_claim_count": unlinked,
    "binding_status": str(row.get("status") or ""),
  }


def get_full_patent_document_pipeline_status(
  case_id: str,
  publication_number: str,
  project_root: Path | str,
) -> dict[str, str | bool | int]:
  from tech_cartography.services.v8_gemini_example_facts import (
    get_example_facts_pipeline_status,
  )
  from tech_cartography.services.v8_patent_section_extract import (
    get_combined_patent_pdf_pipeline_status,
  )

  merged: dict[str, str | bool | int] = {
    **get_combined_patent_pdf_pipeline_status(case_id, publication_number, project_root),
    **get_example_facts_pipeline_status(case_id, publication_number, project_root),
    **get_claim_example_binding_pipeline_status(case_id, publication_number, project_root),
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
  elif merged.get("example_facts_extracted") and not merged.get("claim_example_links_generated"):
    next_action = "Claim-Example対応候補の生成"
  elif merged.get("claim_example_links_generated"):
    next_action = "Gapロジック更新へ（次Phase）"
  elif merged.get("facts_needs_human_review") or merged.get("section_needs_human_review"):
    next_action = "抽出結果の人手確認が必要"
  elif merged.get("has_examples"):
    next_action = "Extract example facts"
  else:
    next_action = "examples未検出 — セクション人手確認"

  merged["next_action"] = next_action
  return merged
