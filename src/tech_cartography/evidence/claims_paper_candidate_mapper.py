"""Map claim elements to OpenAlex paper candidate records."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tech_cartography.reports.project_export import save_records_csv

MAPPER_CAVEAT = (
  "Claim × Paper links are supporting evidence candidates only. "
  "They do not prove patent claims. "
  "Without description/examples, technical validation remains limited."
)

TYPE_KEYWORDS: dict[str, tuple[str, ...]] = {
  "material": ("pan", "polyacrylonitrile", "carbon fiber", "precursor", "fiber"),
  "process": ("carbonization", "oxidation", "stabilization", "manufacturing", "heat treatment"),
  "property": ("tensile", "modulus", "strength", "mechanical", "elastic"),
  "structure": ("microstructure", "bundle", "crystallite", "turbostratic", "defect"),
  "surface_interface": ("surface", "sizing", "interface", "adhesion", "modification"),
  "evaluation_method": ("measurement", "evaluation", "characterization", "test method"),
  "application": ("composite", "pressure vessel", "aerospace", "reinforced"),
}


def _tokenize(text: str) -> set[str]:
  return {tok for tok in re.findall(r"[a-z0-9]+", text.lower()) if len(tok) > 2}


PRIORITY_BUCKETS = {
  "strong_material_process_background",
  "property_background",
  "surface_interface_background",
}


def _paper_relevance_bucket(paper_record: dict[str, Any]) -> str:
  return str(paper_record.get("relevance_bucket") or "")


def classify_claim_paper_link(link: dict[str, Any]) -> str:
  relevance_bucket = str(link.get("relevance_bucket") or "")
  if relevance_bucket == "likely_off_topic":
    return "unrelated"
  if relevance_bucket == "broad_composite_background":
    return "weak_background"
  score = float(link.get("link_score", 0))
  element_type = str(link.get("element_type") or "")
  if score < 0.15:
    return "unrelated"
  if score < 0.3:
    return "weak_background"
  if element_type == "material" or link.get("query_type") == "material_process":
    return "material_process_background"
  if element_type == "property" or link.get("query_type") == "property_condition":
    return "property_background"
  if element_type == "structure" or link.get("query_type") == "structure_property":
    return "structure_property_background"
  if element_type in {"surface", "interface"} or link.get("query_type") == "surface_interface":
    return "surface_interface_background"
  if element_type == "evaluation_method" or link.get("query_type") == "measurement_method":
    return "measurement_background"
  return "weak_background"


def _link_confidence(link_score: float, has_description: bool, relevance_bucket: str = "") -> str:
  if relevance_bucket in {"likely_off_topic", "broad_composite_background"}:
    return "weak"
  if link_score >= 0.55 and has_description and relevance_bucket in PRIORITY_BUCKETS:
    return "medium"
  if link_score >= 0.35 or relevance_bucket in PRIORITY_BUCKETS:
    return "low"
  return "weak"


def score_claim_paper_candidate_link(
  claim_element: dict[str, Any],
  paper_record: dict[str, Any],
  *,
  has_description: bool = False,
) -> dict[str, Any]:
  element_type = str(claim_element.get("element_type") or "unknown")
  element_terms = _tokenize(
    " ".join(
      [
        str(claim_element.get("element_text") or ""),
        " ".join(claim_element.get("normalized_terms") or []),
      ],
    ),
  )
  paper_text = _tokenize(
    " ".join(
      [
        str(paper_record.get("title") or ""),
        str(paper_record.get("abstract") or ""),
        str(paper_record.get("query") or ""),
      ],
    ),
  )
  overlap = element_terms & paper_text
  type_keywords = set(TYPE_KEYWORDS.get(element_type, ()))
  type_overlap = type_keywords & paper_text
  relevance_bucket = _paper_relevance_bucket(paper_record)
  relevance_score = float(paper_record.get("relevance_score", 0) or 0)
  link_score = min(
    1.0,
    len(overlap) * 0.12 + len(type_overlap) * 0.15 + (0.1 if overlap else 0.0) + relevance_score * 0.2,
  )

  row = {
    "publication_number": claim_element.get("publication_number") or paper_record.get("publication_number"),
    "element_id": claim_element.get("element_id"),
    "element_type": element_type,
    "paper_id": paper_record.get("paper_id") or paper_record.get("openalex_id"),
    "paper_title": paper_record.get("title"),
    "query_id": paper_record.get("query_id"),
    "query_type": paper_record.get("query_type") or paper_record.get("element_type"),
    "relevance_bucket": relevance_bucket,
    "relevance_score": relevance_score,
    "link_score": round(link_score, 3),
    "overlap_terms": sorted(overlap),
    "has_description": has_description,
    "evidence_role": "supporting_evidence_candidate",
  }
  row["link_type"] = classify_claim_paper_link(row)
  row["confidence"] = _link_confidence(link_score, has_description, relevance_bucket=relevance_bucket)
  if not has_description:
    row["caveat_japanese"] = (
      "明細書・実施例が未入力のため、請求項と論文の対応は限定的な supporting evidence candidate です。"
    )
  else:
    row["caveat_japanese"] = "論文は特許主張の証明ではありません。"
  return row


def map_claim_elements_to_paper_candidates(
  claim_elements: list[dict[str, Any]],
  paper_records: list[dict[str, Any]],
  *,
  has_description: bool = False,
  min_score: float = 0.12,
  use_relevance_filter: bool = True,
) -> list[dict[str, Any]]:
  links: list[dict[str, Any]] = []
  for element in claim_elements:
    for paper in paper_records:
      if use_relevance_filter and _paper_relevance_bucket(paper) == "likely_off_topic":
        continue
      link = score_claim_paper_candidate_link(element, paper, has_description=has_description)
      if link["link_type"] == "unrelated":
        continue
      if float(link["link_score"]) < min_score and link["link_type"] == "weak_background":
        continue
      links.append(link)
  links.sort(
    key=lambda row: (
      0 if str(row.get("relevance_bucket")) in PRIORITY_BUCKETS else 1,
      -float(row.get("relevance_score", 0)),
      -float(row.get("link_score", 0)),
    ),
  )
  return links


def render_claim_paper_candidate_map_markdown(links: list[dict[str, Any]]) -> str:
  lines = [
    "# Claim × Paper Candidate Map",
    "",
    f"- total links: {len(links)}",
    "",
    MAPPER_CAVEAT,
    "",
  ]
  type_counts: dict[str, int] = {}
  conf_counts: dict[str, int] = {}
  for link in links:
    type_counts[str(link.get("link_type"))] = type_counts.get(str(link.get("link_type")), 0) + 1
    conf_counts[str(link.get("confidence"))] = conf_counts.get(str(link.get("confidence")), 0) + 1

  lines.extend(["## link_type distribution", ""])
  for key, count in sorted(type_counts.items()):
    lines.append(f"- {key}: {count}")
  lines.extend(["", "## confidence distribution", ""])
  for key, count in sorted(conf_counts.items()):
    lines.append(f"- {key}: {count}")

  lines.extend(["", "## Representative links", ""])
  for link in links[:10]:
    lines.append(
      f"- {link.get('element_type')} ↔ {link.get('paper_title')} "
      f"({link.get('link_type')}, {link.get('confidence')}, bucket={link.get('relevance_bucket')}, "
      f"score={link.get('link_score')})",
    )
  if not links:
    lines.append("- (no links)")
  lines.append("")
  lines.append("※ 金額情報は含みません。")
  return "\n".join(lines)


def save_claim_paper_candidate_map_artifacts(
  links: list[dict[str, Any]],
  output_dir: str | Path,
) -> dict[str, str]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  json_path = out / "claim_paper_candidate_links.json"
  csv_path = out / "claim_paper_candidate_links.csv"
  md_path = out / "claim_paper_candidate_map.md"
  json_path.write_text(json.dumps(links, indent=2, ensure_ascii=False), encoding="utf-8")
  save_records_csv(links, csv_path)
  md_path.write_text(render_claim_paper_candidate_map_markdown(links), encoding="utf-8")
  return {
    "claim_paper_candidate_links_json": str(json_path),
    "claim_paper_candidate_links_csv": str(csv_path),
    "claim_paper_candidate_map_md": str(md_path),
  }
