"""Relevance filter for OpenAlex paper candidates (Phase 19.1)."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from tech_cartography.reports.project_export import load_records_csv, save_records_csv

_SYNTHETIC_PAPER_ID = re.compile(r"^W\d+$", re.I)

SELECTED_EVIDENCE_PAPER_COLUMNS = (
  "publication_number",
  "paper_id",
  "openalex_id",
  "title",
  "doi",
  "publication_year",
  "source",
  "cited_by_count",
  "is_oa",
  "query",
  "query_type",
  "relevance_bucket",
  "relevance_score",
  "relevance_confidence",
  "recommended_evidence_role",
  "concepts",
  "keywords",
)


def is_synthetic_paper_id(paper_id: str) -> bool:
  pid = str(paper_id or "").strip()
  if not pid:
    return True
  if _SYNTHETIC_PAPER_ID.match(pid):
    return True
  if pid.lower().startswith("w-") or pid.lower() in {"w-off", "w-broad"}:
    return True
  return False


def resolve_paper_id(paper: dict[str, Any]) -> str:
  for key in ("openalex_id", "paper_id", "work_id"):
    value = str(paper.get(key) or "").strip()
    if value and not is_synthetic_paper_id(value):
      return value
  openalex_id = str(paper.get("openalex_id") or "").strip()
  if openalex_id:
    return openalex_id
  doi = str(paper.get("doi") or "").strip()
  if doi:
    return doi
  return str(paper.get("paper_id") or paper.get("work_id") or "")


def records_have_synthetic_ids(records: list[dict[str, Any]]) -> bool:
  if not records:
    return False
  synthetic = sum(
    1 for row in records
    if is_synthetic_paper_id(str(row.get("paper_id") or row.get("openalex_id") or ""))
  )
  return synthetic >= max(1, len(records) // 2)


def load_openalex_paper_records(paper_records_path: str | Path) -> list[dict[str, Any]]:
  path = Path(paper_records_path)
  if not path.exists():
    raise FileNotFoundError(f"paper records not found: {path}")

  records = load_records_csv(str(path))
  json_path = path.with_suffix(".json")
  if json_path.exists() and (not records or records_have_synthetic_ids(records)):
    try:
      payload = json.loads(json_path.read_text(encoding="utf-8"))
      if isinstance(payload, list) and payload:
        records = payload
    except json.JSONDecodeError:
      pass
  return [dict(row) for row in records]


def build_selected_evidence_paper_row(
  paper: dict[str, Any],
  relevance: dict[str, Any],
  *,
  publication_number: str = "",
) -> dict[str, Any]:
  paper_id = resolve_paper_id(paper)
  openalex_id = str(paper.get("openalex_id") or "").strip()
  if not openalex_id and "openalex.org" in paper_id:
    openalex_id = paper_id
  source = str(paper.get("source") or paper.get("source_name") or paper.get("journal") or "")
  is_oa = paper.get("is_oa")
  if is_oa in (None, ""):
    is_oa = paper.get("is_open_access")
  return {
    "publication_number": str(publication_number or paper.get("publication_number") or ""),
    "paper_id": paper_id,
    "openalex_id": openalex_id,
    "title": str(paper.get("title") or ""),
    "doi": str(paper.get("doi") or ""),
    "publication_year": paper.get("publication_year") or "",
    "source": source,
    "cited_by_count": paper.get("cited_by_count") if paper.get("cited_by_count") not in (None, "") else 0,
    "is_oa": is_oa if is_oa not in (None, "") else "",
    "query": str(paper.get("query") or ""),
    "query_type": str(paper.get("query_type") or ""),
    "relevance_bucket": str(relevance.get("relevance_bucket") or paper.get("relevance_bucket") or ""),
    "relevance_score": relevance.get("relevance_score", paper.get("relevance_score", 0)),
    "relevance_confidence": str(relevance.get("confidence") or paper.get("relevance_confidence") or ""),
    "recommended_evidence_role": str(
      relevance.get("recommended_evidence_role") or paper.get("recommended_evidence_role") or "",
    ),
    "concepts": paper.get("concepts") or [],
    "keywords": paper.get("keywords") or [],
  }

FILTER_CAVEAT_JAPANESE = (
  "論文候補は特許請求項の証明ではなく supporting evidence candidate です。"
  "広い複合材料レビューは背景候補として扱い、"
  "PAN系炭素繊維・炭化・物性に近い論文を Evidence Map 候補として優先します。"
  "明細書・実施例が未入力の場合、技術妥当性評価には限界があります。"
)

REPORT_INTRO_JAPANESE = (
  "広い複合材料レビューは背景候補として扱い、"
  "PAN系炭素繊維・炭化・物性に近い論文をEvidence Map候補として優先します。"
)

BUCKET_PRIORITY = {
  "strong_material_process_background": 0,
  "property_background": 1,
  "surface_interface_background": 2,
  "weak_background": 3,
  "broad_composite_background": 4,
  "likely_off_topic": 5,
}

MATERIAL_PROCESS_TERMS = (
  "pan",
  "polyacrylonitrile",
  "carbon fiber",
  "precursor",
  "stabilization",
  "oxidation",
  "carbonization",
  "heat treatment",
)

PROPERTY_TERMS = (
  "tensile strength",
  "elastic modulus",
  "modulus",
  "mechanical properties",
  "tensile",
)

SURFACE_TERMS = (
  "surface treatment",
  "sizing",
  "interfacial adhesion",
  "interphase",
  "interface engineering",
)

STRUCTURE_TERMS = (
  "microstructure",
  "defects",
  "crystallite",
)

POSITIVE_PHRASES = MATERIAL_PROCESS_TERMS + PROPERTY_TERMS + SURFACE_TERMS + STRUCTURE_TERMS

NEGATIVE_BROAD_PHRASES = (
  "natural fiber",
  "glass fiber",
  "hemp fiber",
  "jute fiber",
  "flax fiber",
  "general composite",
  "fiber-reinforced polymer composites review",
  "fiber reinforced polymer composites review",
  "biomedical",
  "marine application",
  "corrosion only",
  "tribology only",
  "alternative medicine",
)

OFF_TOPIC_PHRASES = (
  "quantum computing",
  "machine learning drug",
  "covid vaccine",
  "climate policy",
)


@dataclass
class PaperCandidateRelevance:
  publication_number: str = ""
  work_id: str = ""
  title: str = ""
  relevance_bucket: str = "weak_background"
  relevance_score: float = 0.0
  matched_positive_terms: list[str] = field(default_factory=list)
  matched_negative_terms: list[str] = field(default_factory=list)
  recommended_evidence_role: str = "supporting_evidence_candidate"
  confidence: str = "weak"
  caveat_japanese: str = FILTER_CAVEAT_JAPANESE
  next_action_japanese: str = "技術者が論文タイトル・抄録を確認してください"

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


def _normalize_text(paper: dict[str, Any]) -> str:
  return " ".join(
    [
      str(paper.get("title") or ""),
      str(paper.get("abstract") or ""),
      str(paper.get("query") or ""),
    ],
  ).lower()


def _find_phrases(text: str, phrases: tuple[str, ...]) -> list[str]:
  found: list[str] = []
  for phrase in phrases:
    if phrase in text:
      found.append(phrase)
  return found


def _has_carbon_fiber_focus(text: str) -> bool:
  carbon_markers = ("carbon fiber", "polyacrylonitrile", " pan ", "pan precursor", "pan-based")
  padded = f" {text} "
  return any(marker in padded or marker.strip() in text for marker in carbon_markers)


def _classify_bucket(
  text: str,
  positive: list[str],
  negative: list[str],
  relevance_score: float,
) -> str:
  if any(phrase in text for phrase in OFF_TOPIC_PHRASES) and not positive:
    return "likely_off_topic"

  glass_or_natural_only = (
    any(term in text for term in ("natural fiber", "glass fiber", "hemp fiber", "jute fiber", "flax fiber"))
    and not _has_carbon_fiber_focus(text)
  )
  general_composite_review = (
    "composite" in text
    and "review" in text
    and not _has_carbon_fiber_focus(text)
    and not any(term in text for term in MATERIAL_PROCESS_TERMS[:4])
  )
  if glass_or_natural_only or general_composite_review:
    return "broad_composite_background"

  material_hits = _find_phrases(text, MATERIAL_PROCESS_TERMS)
  property_hits = _find_phrases(text, PROPERTY_TERMS)
  surface_hits = _find_phrases(text, SURFACE_TERMS)

  property_focus = bool(property_hits) and (
    len(property_hits) >= len(material_hits)
    or any(term in text for term in ("tensile strength", "elastic modulus", "mechanical properties"))
  )
  surface_focus = bool(surface_hits) and any(
    term in text for term in ("surface treatment", "sizing", "interphase", "interfacial adhesion", "interface engineering")
  )

  if property_focus and relevance_score >= 0.3:
    return "property_background"
  if surface_focus and relevance_score >= 0.28:
    return "surface_interface_background"
  if material_hits and relevance_score >= 0.35:
    return "strong_material_process_background"

  if negative and not positive:
    return "likely_off_topic"
  if negative and relevance_score < 0.25:
    return "broad_composite_background"
  if relevance_score < 0.15:
    return "likely_off_topic"
  if relevance_score < 0.3:
    return "weak_background"
  return "weak_background"


def _score_relevance(text: str, positive: list[str], negative: list[str], claim_elements: list[dict[str, Any]] | None) -> float:
  score = min(0.9, len(positive) * 0.12 + (0.15 if _has_carbon_fiber_focus(text) else 0.0))
  if any(term in text for term in PROPERTY_TERMS):
    score += 0.08
  if any(term in text for term in SURFACE_TERMS):
    score += 0.06
  score -= len(negative) * 0.1
  if claim_elements:
    claim_terms: set[str] = set()
    for element in claim_elements:
      claim_terms.update(re.findall(r"[a-z0-9]+", str(element.get("element_text") or "").lower()))
      for term in element.get("normalized_terms") or []:
        claim_terms.add(str(term).lower())
    paper_tokens = set(re.findall(r"[a-z0-9]+", text))
    overlap = claim_terms & paper_tokens
    score += min(0.2, len(overlap) * 0.04)
  return round(max(0.0, min(1.0, score)), 3)


def _confidence_for_bucket(bucket: str, relevance_score: float, has_description: bool = False) -> str:
  if bucket in {"likely_off_topic", "broad_composite_background"}:
    return "weak"
  if bucket in {"strong_material_process_background", "property_background", "surface_interface_background"}:
    if relevance_score >= 0.55 and has_description:
      return "medium"
    return "low"
  if relevance_score >= 0.4:
    return "low"
  return "weak"


def classify_evidence_role(paper: dict[str, Any], score: dict[str, Any]) -> str:
  bucket = str(score.get("relevance_bucket") or paper.get("relevance_bucket") or "weak_background")
  mapping = {
    "strong_material_process_background": "material_process_supporting_evidence",
    "property_background": "property_supporting_evidence",
    "surface_interface_background": "surface_interface_supporting_evidence",
    "broad_composite_background": "broad_background_literature",
    "weak_background": "weak_background_literature",
    "likely_off_topic": "excluded_off_topic",
  }
  return mapping.get(bucket, "supporting_evidence_candidate")


def evaluate_paper_candidate_relevance(
  paper: dict[str, Any],
  claim_elements: list[dict[str, Any]] | None = None,
  *,
  has_description: bool = False,
) -> dict[str, Any]:
  text = _normalize_text(paper)
  positive = _find_phrases(text, POSITIVE_PHRASES)
  negative = _find_phrases(text, NEGATIVE_BROAD_PHRASES + OFF_TOPIC_PHRASES)
  relevance_score = _score_relevance(text, positive, negative, claim_elements)
  bucket = _classify_bucket(text, positive, negative, relevance_score)
  confidence = _confidence_for_bucket(bucket, relevance_score, has_description=has_description)

  result = PaperCandidateRelevance(
    publication_number=str(paper.get("publication_number") or ""),
    work_id=str(paper.get("paper_id") or paper.get("openalex_id") or paper.get("work_id") or ""),
    title=str(paper.get("title") or ""),
    relevance_bucket=bucket,
    relevance_score=relevance_score,
    matched_positive_terms=positive,
    matched_negative_terms=negative,
    recommended_evidence_role=classify_evidence_role(paper, {"relevance_bucket": bucket}),
    confidence=confidence,
    caveat_japanese=FILTER_CAVEAT_JAPANESE,
    next_action_japanese=(
      "Evidence Map候補として確認"
      if bucket in {"strong_material_process_background", "property_background", "surface_interface_background"}
      else "背景文献として参照のみ"
      if bucket == "broad_composite_background"
      else "除外または弱い背景候補として扱う"
    ),
  )
  row = result.to_dict()
  row["paper_record"] = paper
  return row


def filter_and_rank_paper_candidates(
  papers: list[dict[str, Any]],
  claim_elements: list[dict[str, Any]] | None = None,
  *,
  top_n: int = 5,
  has_description: bool = False,
) -> list[dict[str, Any]]:
  evaluated = [
    evaluate_paper_candidate_relevance(paper, claim_elements, has_description=has_description)
    for paper in papers
  ]
  eligible = [
    row for row in evaluated
    if row.get("relevance_bucket") not in {"likely_off_topic", "broad_composite_background"}
  ]
  eligible.sort(
    key=lambda row: (
      BUCKET_PRIORITY.get(str(row.get("relevance_bucket")), 99),
      -float(row.get("relevance_score", 0)),
    ),
  )
  return eligible[:top_n]


def render_paper_candidate_relevance_report(filtered: list[dict[str, Any]], all_papers: list[dict[str, Any]]) -> str:
  all_evaluated = [
    evaluate_paper_candidate_relevance(paper)
    for paper in all_papers
  ]
  bucket_counts: dict[str, int] = {}
  for row in all_evaluated:
    bucket = str(row.get("relevance_bucket"))
    bucket_counts[bucket] = bucket_counts.get(bucket, 0) + 1

  excluded = [row for row in all_evaluated if row.get("relevance_bucket") in {"likely_off_topic", "broad_composite_background"}]

  lines = [
    "# Paper Candidate Relevance Filter Report",
    "",
    REPORT_INTRO_JAPANESE,
    "",
    f"- total paper candidates: {len(all_papers)}",
    f"- selected evidence papers: {len(filtered)}",
    "",
    "## relevance bucket distribution",
    "",
  ]
  for bucket, count in sorted(bucket_counts.items(), key=lambda item: BUCKET_PRIORITY.get(item[0], 99)):
    lines.append(f"- {bucket}: {count}")

  lines.extend(["", "## representative selected papers", ""])
  for row in filtered[:5]:
    lines.append(
      f"- {row.get('title')} "
      f"({row.get('relevance_bucket')}, score={row.get('relevance_score')}, confidence={row.get('confidence')})",
    )
  if not filtered:
    lines.append("- (none selected)")

  lines.extend(["", "## excluded broad / off-topic papers", ""])
  for row in excluded[:10]:
    lines.append(
      f"- {row.get('title')} ({row.get('relevance_bucket')}, negatives={row.get('matched_negative_terms')})",
    )
  if not excluded:
    lines.append("- (none)")

  lines.extend(["", "## caveat", "", FILTER_CAVEAT_JAPANESE, "", "※ 金額情報は含みません。"])
  return "\n".join(lines)


def apply_relevance_to_paper_records(
  papers: list[dict[str, Any]],
  claim_elements: list[dict[str, Any]] | None = None,
  *,
  top_n: int = 5,
  has_description: bool = False,
) -> dict[str, Any]:
  all_evaluated = [
    evaluate_paper_candidate_relevance(paper, claim_elements, has_description=has_description)
    for paper in papers
  ]
  selected = filter_and_rank_paper_candidates(
    papers,
    claim_elements,
    top_n=top_n,
    has_description=has_description,
  )
  publication_number = ""
  if claim_elements:
    publication_number = str(claim_elements[0].get("publication_number") or "")
  if not publication_number and papers:
    publication_number = str(papers[0].get("publication_number") or "")

  selected_papers = []
  for row in selected:
    paper = dict(row.get("paper_record") or {})
    selected_papers.append(
      build_selected_evidence_paper_row(
        paper,
        row,
        publication_number=publication_number,
      ),
    )
  return {
    "all_evaluated": all_evaluated,
    "selected": selected,
    "selected_papers": selected_papers,
    "excluded_off_topic_count": sum(
      1 for row in all_evaluated if row.get("relevance_bucket") == "likely_off_topic"
    ),
    "broad_background_count": sum(
      1 for row in all_evaluated if row.get("relevance_bucket") == "broad_composite_background"
    ),
  }


def save_paper_candidate_relevance_artifacts(
  result: dict[str, Any],
  output_dir: str | Path,
) -> dict[str, str]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  all_rows = result.get("all_evaluated") or []
  selected = result.get("selected") or []
  selected_papers = result.get("selected_papers") or []

  json_path = out / "paper_candidate_relevance.json"
  json_path.write_text(json.dumps(all_rows, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
  report_path = out / "paper_candidate_relevance_report.md"
  all_papers = [row.get("paper_record") or {} for row in all_rows]
  report_path.write_text(render_paper_candidate_relevance_report(selected, all_papers), encoding="utf-8")

  return {
    "paper_candidate_relevance_json": str(json_path),
    "paper_candidate_relevance_csv": save_records_csv(all_rows, out / "paper_candidate_relevance.csv"),
    "paper_candidate_relevance_report_md": str(report_path),
    "selected_evidence_papers_csv": save_records_csv(
      [{col: row.get(col, "") for col in SELECTED_EVIDENCE_PAPER_COLUMNS} for row in selected_papers],
      out / "selected_evidence_papers.csv",
    ),
  }
