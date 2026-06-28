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
FORBIDDEN_REASON_WORDS = frozenset({
  "裏取り完了", "証明", "権利範囲を支える", "有効", "侵害", "fto", "無効",
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
    example_key = str(fact.get("example_id") or fact.get("example_label") or fact.get("section_id") or "unknown")
    grouped[pub][example_key].append(fact)
  return grouped


def _score_level(score: int) -> str:
  if score >= 7:
    return "high_candidate"
  if score >= 4:
    return "medium_candidate"
  if score >= 2:
    return "low_candidate"
  return "none"


def _determine_support_type(facts: list[dict], score: int) -> str:
  types = {str(f.get("fact_type") or "") for f in facts}
  if "comparison_example" in types:
    return "comparison_support_candidate"
  if "property_value" in types:
    return "property_support_candidate"
  if "process_condition" in types:
    return "process_condition_candidate"
  if "table_value" in types:
    return "table_support_candidate"
  if "structure_characterization" in types:
    return "structure_support_candidate"
  if score >= 2:
    return "partial_example_support_candidate"
  if not facts:
    return "not_enough_information"
  return "no_example_support_candidate"


def _match_field(text: str, value: str | None) -> bool:
  return bool(value and _text_contains(text, value))


def score_claim_example_candidate(
  claim: dict,
  example_facts: list[dict],
  vocabulary: ExtractionVocabulary | None,
) -> tuple[int, ClaimExampleLink]:
  case_id = str(claim.get("case_id", ""))
  pub = normalize_publication_number(str(claim.get("publication_number", "")))
  claim_no = str(claim.get("claim_no", ""))
  claim_text = normalize_claim_text(str(claim.get("claim_text", "")))
  claim_terms = extract_claim_terms(claim_text, vocabulary)

  valid_facts = [f for f in example_facts if str(f.get("evidence_text") or "").strip()]
  warnings: list[str] = []
  if len(valid_facts) < len(example_facts):
    warnings.append("facts without evidence_text were excluded")

  score = 0
  matched: set[str] = set()
  missing: set[str] = set()
  matched_keywords: set[str] = set()
  evidence_texts: list[str] = []
  linked_ids: list[str] = []
  has_property = False
  has_process = False
  has_comparison = False
  has_table = False

  for fact in valid_facts:
    fact_pub = normalize_publication_number(str(fact.get("publication_number", "")))
    if fact_pub != pub:
      continue

    evidence = str(fact.get("evidence_text") or "").strip()
    evidence_texts.append(evidence)
    linked_ids.append(str(fact.get("fact_id") or ""))

    if _match_field(claim_text, fact.get("material")):
      score += 2
      matched.add(str(fact.get("material")))
    if _match_field(claim_text, fact.get("process_step")):
      score += 3
      matched.add(str(fact.get("process_step")))
    if _match_field(claim_text, fact.get("property_name")):
      score += 3
      matched.add(str(fact.get("property_name")))
    if _match_field(claim_text, fact.get("condition_name")):
      score += 2
      matched.add(str(fact.get("condition_name")))
    if _match_field(claim_text, fact.get("structure")):
      score += 2

    fact_type = str(fact.get("fact_type") or "")
    if fact_type == "property_value":
      has_property = True
      score += 3
    elif fact_type == "process_condition":
      has_process = True
      score += 3
    elif fact_type == "comparison_example":
      has_comparison = True
      score += 2
    elif fact_type == "table_value":
      has_table = True
      score += 1

    score += 1  # evidence present

    for kw in str(fact.get("matched_user_keywords") or "").split("|"):
      kw = kw.strip()
      if kw and _text_contains(claim_text, kw):
        matched_keywords.add(kw)
        score += 1

  for category, kws in claim_terms.items():
    for kw in kws:
      found = any(
        _text_contains(str(f.get("evidence_text") or ""), kw)
        or _match_field(str(f.get("material") or ""), kw)
        or _match_field(str(f.get("process_step") or ""), kw)
        or _match_field(str(f.get("property_name") or ""), kw)
        for f in valid_facts
        if normalize_publication_number(str(f.get("publication_number", ""))) == pub
      )
      if found:
        matched.add(kw)
      else:
        missing.add(kw)

  if claim_terms["property"] and not has_property:
    missing.update(claim_terms["property"])
  if claim_terms["process"] and not has_process:
    missing.update(claim_terms["process"])
  if claim_terms["comparison"] and not has_comparison:
    missing.update(claim_terms["comparison"])

  support_level = _score_level(score)
  support_type = _determine_support_type(valid_facts, score)
  if support_level == "none":
    support_type = "no_example_support_candidate"

  example_id = None
  example_label = None
  if valid_facts:
    example_id = valid_facts[0].get("example_id") or None
    example_label = valid_facts[0].get("example_label") or None

  reason = _build_reason(
    claim_no=claim_no,
    example_label=example_label,
    matched=sorted(matched),
    missing=sorted(missing),
    support_level=support_level,
  )

  confidence = min(1.0, round(score / 10.0, 3))
  link = ClaimExampleLink(
    case_id=case_id,
    publication_number=pub,
    claim_no=claim_no,
    claim_text=claim_text,
    example_id=example_id,
    example_label=example_label,
    linked_fact_ids=[fid for fid in linked_ids if fid],
    support_type=support_type,
    support_level=support_level,
    matched_elements=sorted(matched),
    missing_elements=sorted(missing),
    matched_user_keywords=sorted(matched_keywords),
    evidence_texts=evidence_texts[:10],
    reason=reason,
    confidence=confidence,
    needs_human_review=True,
    binding_method=BINDING_METHOD,
    warning="; ".join(warnings) if warnings else None,
  )
  return score, link


def _build_reason(
  *,
  claim_no: str,
  example_label: str | None,
  matched: list[str],
  missing: list[str],
  support_level: str,
) -> str:
  ex = example_label or "抽出ファクト"
  matched_txt = "、".join(matched[:5]) if matched else "（一致語なし）"
  parts = [
    f"claim {claim_no} と {ex} の抽出ファクトで、{matched_txt} が一致候補です（support_level={support_level}）。",
  ]
  if missing:
    parts.append(f"一方で、{ '、'.join(missing[:5]) } は example facts 側で未確認です。")
  parts.append("対応は候補であり、人手確認が必要です。")
  reason = "".join(parts)
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
      best_score = -1
      best_link: ClaimExampleLink | None = None
      if not example_groups:
        _, link = score_claim_example_candidate(claim, [], vocabulary)
        links.append(link)
        continue

      for _example_key, group_facts in example_groups.items():
        score, link = score_claim_example_candidate(claim, group_facts, vocabulary)
        if score > best_score:
          best_score = score
          best_link = link

      links.append(best_link or score_claim_example_candidate(claim, [], vocabulary)[1])

    linked = sum(1 for link in links if link.support_level != "none")
    unlinked = len(links) - linked
    strong = sum(1 for link in links if link.support_level == "high_candidate")
    partial = sum(1 for link in links if link.support_type == "partial_example_support_candidate")
    prop = sum(1 for link in links if link.support_type == "property_support_candidate")
    comp = sum(1 for link in links if link.support_type == "comparison_support_candidate")
    none_count = sum(1 for link in links if link.support_type == "no_example_support_candidate")

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
    "binding_method", "warning",
  ]
  summary_fields = [
    "case_id", "publication_number", "claim_count", "linked_claim_count", "unlinked_claim_count",
    "link_count", "strong_candidate_count", "partial_candidate_count", "property_candidate_count",
    "comparison_candidate_count", "no_candidate_count", "needs_human_review", "status", "warning",
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
        "linked_fact_ids": "|".join(link.linked_fact_ids),
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
