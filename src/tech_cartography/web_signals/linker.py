"""Patent × Paper × Web Signal link candidate builder (Phase 23.4 / 23.4.1)."""

from __future__ import annotations

import ast
import csv
import json
import re
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from tech_cartography.reports.project_export import load_records_csv
from tech_cartography.web_signals.schema import utc_now_iso

LINK_TYPES: frozenset[str] = frozenset(
  {
    "technology_theme_match",
    "project_context_match",
    "paper_context_match",
    "company_context_match",
    "weak_keyword_overlap",
    "manual_review_required",
  },
)

MONEY_NATIONAL_TYPES: frozenset[str] = frozenset(
  {"national_project", "money", "grant", "funding", "equipment_investment", "policy"},
)
IR_DISCLOSURE_TYPES: frozenset[str] = frozenset({"ir_disclosure", "disclosure"})
COMPANY_LOCAL_TYPES: frozenset[str] = frozenset({"company", "local_news", "market"})

GOVERNMENT_DOMAIN_HINTS: tuple[str, ...] = (
  "nedo.go.jp",
  "jst.go.jp",
  "meti.go.jp",
  "mext.go.jp",
  "go.jp",
)

STRONG_TERMS: frozenset[str] = frozenset(
  {
    "carbonization",
    "stabilization",
    "surface treatment",
    "sizing",
    "tensile strength",
    "modulus",
    "precursor",
    "polyacrylonitrile",
    "炭化",
    "耐炎化",
    "表面処理",
    "サイジング",
    "引張強度",
    "弾性率",
    "前駆体",
  },
)

MODERATE_TERMS: frozenset[str] = frozenset(
  {
    "carbon fiber",
    "cfrp",
    "composite",
    "aerospace",
    "hydrogen tank",
    "pressure vessel",
    "炭素繊維",
    "複合材料",
    "航空機",
    "水素タンク",
    "圧力容器",
  },
)

BROAD_TERMS: frozenset[str] = frozenset(
  {
    "pan",
    "pan系",
    "material",
    "fiber",
    "project",
    "研究開発",
    "プロジェクト",
    "繊維",
  },
)

ORDERED_MATCH_TERMS: tuple[str, ...] = tuple(
  sorted(STRONG_TERMS | MODERATE_TERMS | BROAD_TERMS, key=len, reverse=True),
)

TECHNOLOGY_TERMS_EN: tuple[str, ...] = tuple(
  term for term in ORDERED_MATCH_TERMS if term.isascii()
)
TECHNOLOGY_TERMS_JA: tuple[str, ...] = tuple(
  term for term in ORDERED_MATCH_TERMS if not term.isascii()
)

CALIBRATION_NOTE = (
  "Phase23.4.1 recalibrates link scores to avoid overclaiming. "
  "High-quality public sources alone do not prove linkage to the target patent."
)

SUMMARY_CAUTION = (
  "These are link candidates, not final conclusions.\n"
  "Web signals are signal candidates, not final conclusions.\n"
  "Papers are supporting evidence candidates, not proof of patent claims.\n"
  "IR / disclosure signals require document-level verification.\n"
  "Money / national_project signals require source verification.\n"
  "This is not FTO, infringement, or validity analysis.\n"
  "Synthetic demo signal must be clearly labeled."
)

LINK_CSV_COLUMNS: tuple[str, ...] = (
  "link_id",
  "publication_number",
  "claim_element_text",
  "paper_title",
  "web_signal_id",
  "web_signal_type",
  "web_signal_title",
  "web_signal_domain",
  "source_quality",
  "link_type",
  "link_score",
  "matched_terms",
  "evidence_sentence",
  "confidence",
  "verification_status",
  "caveat",
  "next_verification_action",
  "web_signal_url",
  "matched_strong_terms",
  "matched_moderate_terms",
  "matched_broad_terms",
  "matched_term_strengths",
  "link_explanation",
  "score_reason",
  "score_cap_reason",
  "needs_manual_review",
  "why_not_conclusive",
)

DEFAULT_NEXT_ACTIONS: tuple[str, ...] = (
  "NEDO / JST / METI など公的プロジェクトページを確認する",
  "Web Signal の source URL を開いて本文確認する",
  "対象特許の description / examples を manual 追加する",
  "Claim Element と Web Signal の技術語一致が同じ意味か技術者が確認する",
  "selected evidence papers との関係を専門家が確認する",
  "IR / disclosure 候補がある場合は原典 PDF / 決算説明資料を確認する",
  "断定的な競合戦略判断には使わない",
)

MEDIUM_CANDIDATE_ACTIONS: tuple[str, ...] = (
  "Open source URL and verify original document context.",
  "Check patent description / examples for thematic alignment.",
  "Compare selected paper technical context with the web signal.",
)

LOW_CANDIDATE_ACTIONS: tuple[str, ...] = (
  "Confirm whether matched terms share the same technical meaning.",
  "Check whether the web signal relates to adjacent technology rather than the target patent.",
)

WEAK_CANDIDATE_ACTIONS: tuple[str, ...] = (
  "Do not add to Evidence Map yet.",
  "Keep as reference candidate pending more information.",
  "Gather stronger claim, paper, or document-level evidence.",
)


@dataclass
class LinkScoringConfig:
  calibrated_scoring: bool = True
  min_high_priority_score: int = 70
  min_top_priority_score: int = 80
  exclude_broad_only_from_high_priority: bool = True
  include_weak_links: bool = True


@dataclass
class CalibratedScoreResult:
  score: int
  confidence: str
  score_reason: str
  score_cap_reason: str


@dataclass
class WebSignalLinkCandidate:
  link_id: str
  publication_number: str
  claim_element_id: str | None
  claim_element_text: str | None
  paper_id: str | None
  paper_title: str | None
  web_signal_id: str
  web_signal_type: str
  web_signal_title: str
  web_signal_url: str
  web_signal_domain: str
  source_quality: str
  link_type: str
  link_score: int
  matched_terms: list[str]
  matched_contexts: list[str]
  evidence_sentence: str | None
  confidence: str
  verification_status: str
  caveat: str
  next_verification_action: str
  matched_strong_terms: list[str] = field(default_factory=list)
  matched_moderate_terms: list[str] = field(default_factory=list)
  matched_broad_terms: list[str] = field(default_factory=list)
  matched_term_strengths: str = ""
  link_explanation: str = ""
  score_reason: str = ""
  score_cap_reason: str = ""
  needs_manual_review: bool = True
  why_not_conclusive: str = ""

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class WebSignalLinkPack:
  publication_number: str
  created_at: str
  patent_title: str | None
  link_candidates: list[WebSignalLinkCandidate]
  input_artifacts: dict[str, str] = field(default_factory=dict)
  caveats: list[str] = field(default_factory=list)
  notes: str = ""

  def to_dict(self) -> dict[str, Any]:
    return {
      "publication_number": self.publication_number,
      "created_at": self.created_at,
      "patent_title": self.patent_title,
      "link_candidates": [item.to_dict() for item in self.link_candidates],
      "input_artifacts": dict(self.input_artifacts),
      "caveats": list(self.caveats),
      "notes": self.notes,
    }


def new_link_id() -> str:
  return f"wlink-{uuid.uuid4().hex[:10]}"


def normalize_text_for_matching(text: str) -> str:
  value = str(text or "").lower()
  value = value.replace("\u3000", " ")
  value = re.sub(r"\s+", " ", value)
  return value.strip()


def extract_technology_terms(text: str) -> list[str]:
  normalized = normalize_text_for_matching(text)
  if not normalized:
    return []
  found: list[str] = []
  for term in ORDERED_MATCH_TERMS:
    if term in normalized and term not in found:
      found.append(term)
  return found


def classify_term_strength(term: str) -> str:
  value = str(term or "").strip().lower()
  if value in STRONG_TERMS:
    return "strong"
  if value in MODERATE_TERMS:
    return "moderate"
  if value in BROAD_TERMS:
    return "broad"
  return "unknown"


def split_terms_by_strength(matched_terms: list[str]) -> tuple[list[str], list[str], list[str]]:
  strong: list[str] = []
  moderate: list[str] = []
  broad: list[str] = []
  for term in matched_terms:
    strength = classify_term_strength(term)
    if strength == "strong":
      strong.append(term)
    elif strength == "moderate":
      moderate.append(term)
    elif strength == "broad":
      broad.append(term)
  return strong, moderate, broad


def is_broad_only_match(matched_terms: list[str]) -> bool:
  if not matched_terms:
    return False
  strong, moderate, _broad = split_terms_by_strength(matched_terms)
  return not strong and not moderate


def has_strong_or_moderate_match(matched_terms: list[str]) -> bool:
  strong, moderate, _broad = split_terms_by_strength(matched_terms)
  return bool(strong or moderate)


def _meaningful_claim_text(text: str | None) -> bool:
  value = str(text or "").strip()
  if not value:
    return False
  if value.endswith("-manual") or re.fullmatch(r"CE-\d+", value, flags=re.IGNORECASE):
    return False
  if len(value) <= 12 and not extract_technology_terms(value):
    return False
  return True


def match_terms(left_text: str, right_text: str) -> list[str]:
  left_terms = set(extract_technology_terms(left_text))
  right_terms = set(extract_technology_terms(right_text))
  return sorted(left_terms & right_terms)


def safe_read_csv(path: Path) -> pd.DataFrame:
  if not path.exists():
    return pd.DataFrame()
  try:
    rows = load_records_csv(str(path))
    return _normalize_dataframe(pd.DataFrame(rows) if rows else pd.DataFrame())
  except Exception:  # noqa: BLE001
    return pd.DataFrame()


def safe_read_json(path: Path) -> dict[str, Any]:
  if not path.exists():
    return {}
  try:
    parsed = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(parsed, dict):
      return parsed
  except (OSError, json.JSONDecodeError):
    return {}
  return {}


def _normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
  if df.empty:
    return df
  out = df.copy()
  for col in out.columns:
    out[col] = out[col].apply(_normalize_cell)
  return out


def _normalize_cell(value: Any) -> Any:
  if value is None:
    return ""
  if isinstance(value, float) and pd.isna(value):
    return ""
  if pd.isna(value):
    return ""
  return value


def _first_value(row: dict[str, Any], *keys: str) -> str:
  for key in keys:
    value = str(row.get(key) or "").strip()
    if value:
      return value
  return ""


def _combine_evidence_sentences(value: Any) -> str:
  if _normalize_cell(value) == "":
    return ""
  text = str(value).strip()
  if text.startswith("[") and text.endswith("]"):
    try:
      parsed = ast.literal_eval(text)
      if isinstance(parsed, list):
        return " ".join(str(item) for item in parsed)
    except (SyntaxError, ValueError):
      pass
  return text.replace(";", " ")


def _web_signal_text(row: dict[str, Any]) -> str:
  parts = [
    _first_value(row, "source_title", "web_signal_title", "title"),
    _combine_evidence_sentences(row.get("evidence_sentences")),
    _first_value(row, "related_project", "related_institution"),
    _first_value(row, "related_technology_terms"),
    _first_value(row, "source_domain", "web_signal_domain"),
  ]
  return " ".join(part for part in parts if part)


def _is_government_domain(domain: str) -> bool:
  lower = str(domain or "").lower()
  return any(hint in lower for hint in GOVERNMENT_DOMAIN_HINTS)


def _confidence_from_score(score: int) -> str:
  if score >= 80:
    return "medium"
  if score >= 50:
    return "low"
  return "weak"


def score_link_candidate(
  *,
  matched_terms: list[str],
  source_quality: str,
  web_signal_type: str,
  web_signal_domain: str,
  evidence_sentence: str | None,
  has_claim_match: bool,
  has_paper_match: bool,
  source_url: str,
  claim_element_text: str | None = None,
  paper_title: str | None = None,
  claim_term_match: bool = False,
  paper_term_match: bool = False,
  calibrated: bool = True,
) -> int:
  if calibrated:
    return score_link_candidate_calibrated(
      matched_terms=matched_terms,
      source_quality=source_quality,
      web_signal_type=web_signal_type,
      web_signal_domain=web_signal_domain,
      evidence_sentence=evidence_sentence,
      source_url=source_url,
      claim_element_text=claim_element_text,
      paper_title=paper_title,
      claim_term_match=claim_term_match,
      paper_term_match=paper_term_match,
    ).score

  score = 20
  quality = str(source_quality or "").lower()
  signal_type = str(web_signal_type or "").lower()

  if quality == "high":
    score += 20
  elif quality in {"low", "unknown"}:
    score -= 20

  if signal_type in MONEY_NATIONAL_TYPES:
    score += 20
  if signal_type in IR_DISCLOSURE_TYPES:
    score += 15
  if has_claim_match:
    score += 20
  if has_paper_match:
    score += 15
  if evidence_sentence:
    score += 10
  if _is_government_domain(web_signal_domain):
    score += 10
  if len(matched_terms) >= 3:
    score += 10

  if not evidence_sentence:
    score -= 10
  if signal_type == "other":
    score -= 10
  if signal_type == "human":
    score -= 20
  if not str(source_url or "").strip():
    score -= 30

  return max(0, min(100, score))


def score_link_candidate_calibrated(
  *,
  matched_terms: list[str],
  source_quality: str,
  web_signal_type: str,
  web_signal_domain: str,
  evidence_sentence: str | None,
  source_url: str,
  claim_element_text: str | None,
  paper_title: str | None,
  claim_term_match: bool,
  paper_term_match: bool,
) -> CalibratedScoreResult:
  score = 20
  reasons: list[str] = []
  caps: list[str] = []

  quality = str(source_quality or "").lower()
  signal_type = str(web_signal_type or "").lower()
  strong, moderate, broad = split_terms_by_strength(matched_terms)
  broad_only = is_broad_only_match(matched_terms)
  has_claim_text = _meaningful_claim_text(claim_element_text)
  has_paper = bool(str(paper_title or "").strip())
  has_url = bool(str(source_url or "").strip())
  has_evidence = bool(str(evidence_sentence or "").strip())

  if quality == "high":
    score += 15
    reasons.append("source_quality=high")
  elif quality == "medium_high":
    score += 10
    reasons.append("source_quality=medium_high")
  elif quality == "medium":
    score += 5
    reasons.append("source_quality=medium")
  elif quality in {"low", "unknown"}:
    score -= 15
    reasons.append("source_quality=low_or_unknown")

  if signal_type in MONEY_NATIONAL_TYPES:
    score += 15
    reasons.append(f"signal_type={signal_type}")
  elif signal_type in IR_DISCLOSURE_TYPES:
    score += 10
    reasons.append(f"signal_type={signal_type}")
  elif signal_type in COMPANY_LOCAL_TYPES:
    score += 8
    reasons.append(f"signal_type={signal_type}")

  if strong:
    score += 20
    reasons.append(f"strong_terms={','.join(strong)}")
  if moderate:
    score += 10
    reasons.append(f"moderate_terms={','.join(moderate)}")
  if broad_only:
    score += 3
    score -= 20
    reasons.append("broad_term_only")
  if len(strong) >= 2:
    score += 10
    reasons.append("strong_terms>=2")
  if len(matched_terms) >= 3 and has_strong_or_moderate_match(matched_terms):
    score += 8
    reasons.append("matched_terms>=3_with_strong_or_moderate")

  if has_claim_text and claim_term_match:
    score += 15
    reasons.append("claim_element_match")
  if has_paper and paper_term_match:
    score += 10
    reasons.append("paper_title_match")
  if has_evidence:
    score += 10
    reasons.append("evidence_sentence_exists=True")
  if has_url:
    score += 5
    reasons.append("source_url_exists=True")
  if _is_government_domain(web_signal_domain):
    score += 5
    reasons.append("government_domain=True")

  if not has_claim_text:
    score -= 10
    reasons.append("claim_element_missing")
  if not has_paper:
    score -= 5
    reasons.append("paper_title_missing")
  if not has_evidence:
    score -= 10
    reasons.append("evidence_sentence_missing")
  if signal_type == "human":
    score -= 20
    reasons.append("human_signal")

  score = max(0, min(100, score))

  if broad_only:
    caps.append("broad_term_only_cap_45")
    score = min(score, 45)
  if not has_claim_text and has_paper and broad_only:
    caps.append("claim_missing_broad_only_cap_40")
    score = min(score, 40)
  elif not has_claim_text and has_paper:
    caps.append("claim_element_missing_cap_75")
    score = min(score, 75)
  elif not has_claim_text and broad_only:
    caps.append("claim_missing_broad_only_cap_40")
    score = min(score, 40)
  if not has_url:
    caps.append("source_url_missing_cap_40")
    score = min(score, 40)
  if signal_type == "human":
    caps.append("human_signal_cap_50")
    score = min(score, 50)
  if signal_type in IR_DISCLOSURE_TYPES:
    caps.append("ir_disclosure_cap_70")
    score = min(score, 70)
  if not has_evidence:
    caps.append("no_evidence_sentence_cap_70")
    score = min(score, 70)

  return CalibratedScoreResult(
    score=score,
    confidence=_confidence_from_score(score),
    score_reason="; ".join(reasons),
    score_cap_reason="; ".join(caps) if caps else "",
  )


def infer_link_type(
  *,
  web_signal_type: str,
  matched_terms: list[str],
  has_claim: bool,
  has_paper: bool,
  claim_paper_context: bool,
  claim_term_match: bool = False,
  paper_term_match: bool = False,
  source_quality: str = "unknown",
  calibrated: bool = True,
) -> str:
  signal_type = str(web_signal_type or "").lower()
  if not matched_terms:
    return "manual_review_required"

  if calibrated:
    broad_only = is_broad_only_match(matched_terms)
    strong_or_moderate = has_strong_or_moderate_match(matched_terms)
    if broad_only or (len(matched_terms) == 1 and matched_terms[0].lower() in {"pan", "pan系"}):
      return "weak_keyword_overlap"
    if signal_type in MONEY_NATIONAL_TYPES and strong_or_moderate:
      return "project_context_match"
    if signal_type in IR_DISCLOSURE_TYPES and strong_or_moderate:
      return "company_context_match"
    if signal_type in COMPANY_LOCAL_TYPES and strong_or_moderate:
      return "company_context_match"
    if has_paper and paper_term_match and strong_or_moderate:
      return "paper_context_match"
    if claim_paper_context and paper_term_match and strong_or_moderate:
      return "paper_context_match"
    if has_claim and claim_term_match and strong_or_moderate:
      return "technology_theme_match"
    if str(source_quality or "").lower() == "high" and not strong_or_moderate:
      return "manual_review_required"
    if broad_only:
      return "weak_keyword_overlap"
    return "manual_review_required"

  if signal_type in MONEY_NATIONAL_TYPES and matched_terms:
    return "project_context_match"
  if signal_type in IR_DISCLOSURE_TYPES and matched_terms:
    return "company_context_match"
  if signal_type in COMPANY_LOCAL_TYPES and matched_terms:
    return "company_context_match"
  if has_paper and matched_terms:
    return "paper_context_match"
  if claim_paper_context and matched_terms:
    return "paper_context_match"
  if has_claim and matched_terms:
    return "technology_theme_match"
  if len(matched_terms) == 1:
    return "weak_keyword_overlap"
  return "technology_theme_match"


def build_link_explanation(
  *,
  web_signal_type: str,
  web_signal_domain: str,
  link_type: str,
  matched_terms: list[str],
  paper_title: str | None,
) -> str:
  terms = ", ".join(matched_terms) if matched_terms else "no terms"
  domain = web_signal_domain or "unknown domain"
  if link_type == "project_context_match":
    return (
      f"{domain} source with {terms} theme overlap"
      f"{' with selected paper' if paper_title else ''}. "
      "This is a project-context candidate, not proof of patent relevance."
    )
  if link_type == "paper_context_match":
    return (
      f"Selected paper and web signal share {terms}. "
      "This is a paper-context candidate, not proof of patent claims."
    )
  if link_type == "technology_theme_match":
    return (
      f"Claim element and web signal share {terms}. "
      "This is a thematic candidate requiring manual technical review."
    )
  if link_type == "weak_keyword_overlap":
    return (
      f"Weak overlap on broad terms ({terms}) only. "
      "Do not treat as a strong linkage."
    )
  return (
    f"{web_signal_type} signal from {domain} shows {terms} overlap. "
    "Manual review required before use."
  )


def build_why_not_conclusive(link_type: str) -> str:
  if link_type == "weak_keyword_overlap":
    return (
      "The link relies on broad keyword overlap only. "
      "Patent description/examples and original source documents require manual review."
    )
  return (
    "The link is based on thematic overlap. "
    "Patent description/examples and original project document require manual review."
  )


def _next_action_for_link(link_type: str, web_signal_type: str) -> str:
  if web_signal_type in IR_DISCLOSURE_TYPES:
    return "Open source document and verify disclosure relevance to claim elements."
  if web_signal_type in MONEY_NATIONAL_TYPES:
    return "Verify public funding / project page and thematic overlap with patent claims."
  if link_type == "paper_context_match":
    return "Confirm whether paper and web signal describe the same technical context."
  if link_type == "technology_theme_match":
    return "Confirm claim element terminology matches web signal context."
  return "Manual review required before using this link candidate."


def _caveat_for_link(web_signal_type: str, link_type: str) -> str:
  parts = ["Link candidate only; not a final conclusion."]
  if web_signal_type in IR_DISCLOSURE_TYPES:
    parts.append("IR / disclosure signals require document-level verification.")
  if web_signal_type in MONEY_NATIONAL_TYPES:
    parts.append("Money / national_project signals require source verification.")
  if link_type == "weak_keyword_overlap":
    parts.append("Keyword overlap alone is insufficient for strategic conclusions.")
  parts.append("This is not FTO, infringement, or validity analysis.")
  return " ".join(parts)


def _dedupe_key(candidate: WebSignalLinkCandidate) -> str:
  return "|".join(
    [
      candidate.web_signal_id,
      str(candidate.claim_element_text or ""),
      str(candidate.paper_title or ""),
      candidate.link_type,
    ],
  )


def deduplicate_link_candidates(
  candidates: list[WebSignalLinkCandidate],
) -> list[WebSignalLinkCandidate]:
  best: dict[str, WebSignalLinkCandidate] = {}
  order: list[str] = []
  for candidate in candidates:
    key = _dedupe_key(candidate)
    existing = best.get(key)
    if existing is None:
      best[key] = candidate
      order.append(key)
      continue
    if candidate.link_score > existing.link_score:
      best[key] = candidate
  return [best[key] for key in order]


def load_evidence_map_inputs(publication_number: str, project_root: Path) -> dict[str, Any]:
  pub = str(publication_number).strip()
  ev_dir = project_root / "outputs" / "evidence_map_synthesis" / pub
  oa_dir = project_root / "outputs" / "openalex_limited_execution"

  synthesis_json_path = ev_dir / "evidence_map_synthesis.json"
  items_path = ev_dir / "evidence_map_items.csv"
  papers_path = oa_dir / "selected_evidence_papers.csv"
  links_path = oa_dir / "claim_paper_candidate_links.csv"

  synthesis_json = safe_read_json(synthesis_json_path)
  items_df = safe_read_csv(items_path)
  papers_df = safe_read_csv(papers_path)
  links_df = safe_read_csv(links_path)

  return {
    "publication_number": pub,
    "evidence_map_dir": str(ev_dir),
    "openalex_dir": str(oa_dir),
    "synthesis_json": synthesis_json,
    "synthesis_json_path": str(synthesis_json_path),
    "evidence_map_items_df": items_df,
    "evidence_map_items_path": str(items_path),
    "selected_papers_df": papers_df,
    "selected_papers_path": str(papers_path),
    "claim_paper_links_df": links_df,
    "claim_paper_links_path": str(links_path),
    "patent_title": str(synthesis_json.get("title") or synthesis_json.get("patent_title") or ""),
  }


def load_web_signal_review_inputs(
  project_root: Path,
  batch_dir: str | None = None,
  *,
  include_ir_disclosure: bool = True,
  include_company_local_news: bool = True,
) -> dict[str, Any]:
  root = Path(project_root)
  if batch_dir:
    review_dir = Path(batch_dir)
    if not review_dir.is_absolute():
      review_dir = root / review_dir
  else:
    review_dir = root / "outputs" / "web_signals" / "tavily_pan_carbon_fiber" / "review_pack"

  paths = {
    "review_items": review_dir / "web_signal_review_items.csv",
    "high_priority": review_dir / "high_priority_web_signals.csv",
    "money_national": review_dir / "money_national_project_candidates.csv",
    "ir_disclosure": review_dir / "ir_disclosure_candidates.csv",
    "company_local": review_dir / "company_local_news_candidates.csv",
    "summary_md": review_dir / "web_signal_review_summary.md",
  }

  frames: list[pd.DataFrame] = [
    safe_read_csv(paths["review_items"]),
    safe_read_csv(paths["high_priority"]),
    safe_read_csv(paths["money_national"]),
  ]
  if include_ir_disclosure:
    frames.append(safe_read_csv(paths["ir_disclosure"]))
  if include_company_local_news:
    frames.append(safe_read_csv(paths["company_local"]))

  combined = _combine_web_signal_frames(frames)
  return {
    "review_pack_dir": str(review_dir),
    "web_signals_df": combined,
    "paths": {key: str(path) for key, path in paths.items()},
  }


def _combine_web_signal_frames(frames: list[pd.DataFrame]) -> pd.DataFrame:
  rows: list[dict[str, Any]] = []
  seen_ids: set[str] = set()
  for frame in frames:
    if frame.empty:
      continue
    for _, row in frame.iterrows():
      row_dict = {str(k): _normalize_cell(v) for k, v in row.to_dict().items()}
      signal_id = _first_value(row_dict, "signal_id", "web_signal_id")
      if signal_id and signal_id in seen_ids:
        continue
      if signal_id:
        seen_ids.add(signal_id)
      rows.append(row_dict)
  return pd.DataFrame(rows) if rows else pd.DataFrame()


def _iter_claim_elements(items_df: pd.DataFrame) -> list[dict[str, str]]:
  if items_df.empty:
    return []
  claims: list[dict[str, str]] = []
  for _, row in items_df.iterrows():
    row_dict = {str(k): _normalize_cell(v) for k, v in row.to_dict().items()}
    claim_id = _first_value(row_dict, "claim_element_id", "claim_element", "element_id")
    claim_text = _first_value(
      row_dict,
      "claim_element_text",
      "element_text",
      "claim_text",
      "text",
      "claim_element",
    )
    if claim_id or claim_text:
      claims.append({"claim_element_id": claim_id, "claim_element_text": claim_text})
  return claims


def _iter_papers(papers_df: pd.DataFrame) -> list[dict[str, str]]:
  if papers_df.empty:
    return []
  papers: list[dict[str, str]] = []
  for _, row in papers_df.iterrows():
    row_dict = {str(k): _normalize_cell(v) for k, v in row.to_dict().items()}
    paper_id = _first_value(row_dict, "paper_id", "openalex_id", "id", "doi")
    title = _first_value(row_dict, "title", "paper_title")
    text = " ".join(
      filter(
        None,
        [
          title,
          _first_value(row_dict, "keywords", "concepts", "abstract", "relevance_bucket"),
        ],
      ),
    )
    if title or text:
      papers.append({"paper_id": paper_id, "paper_title": title, "paper_text": text})
  return papers


def _format_term_strengths(matched_terms: list[str]) -> str:
  parts: list[str] = []
  for term in matched_terms:
    strength = classify_term_strength(term)
    if strength != "unknown":
      parts.append(f"{term}:{strength}")
  return "; ".join(parts)


def is_high_priority_link(
  candidate: WebSignalLinkCandidate,
  config: LinkScoringConfig,
) -> bool:
  if candidate.link_score < config.min_high_priority_score:
    return False
  if not str(candidate.web_signal_url or "").strip():
    return False
  if not str(candidate.evidence_sentence or "").strip():
    return False
  if config.exclude_broad_only_from_high_priority and is_broad_only_match(candidate.matched_terms):
    return False
  if candidate.confidence not in {"medium", "low"}:
    return False
  if candidate.verification_status in {"rejected", "low_quality"}:
    return False
  return True


def is_top_priority_link(
  candidate: WebSignalLinkCandidate,
  config: LinkScoringConfig,
) -> bool:
  if candidate.link_score < config.min_top_priority_score:
    return False
  return has_strong_or_moderate_match(candidate.matched_terms)


def is_weak_link_candidate(candidate: WebSignalLinkCandidate) -> bool:
  if candidate.confidence == "weak":
    return True
  if candidate.link_type == "weak_keyword_overlap":
    return True
  if candidate.link_score < 50:
    return True
  return False


def _build_candidate(
  *,
  publication_number: str,
  patent_title: str | None,
  web_row: dict[str, Any],
  claim: dict[str, str] | None,
  paper: dict[str, str] | None,
  claim_paper_context: bool,
  left_text: str,
  right_text: str,
  contexts: list[str],
  scoring_config: LinkScoringConfig | None = None,
) -> WebSignalLinkCandidate | None:
  matched = match_terms(left_text, right_text)
  if not matched:
    return None

  config = scoring_config or LinkScoringConfig()
  web_signal_type = _first_value(web_row, "signal_type", "web_signal_type") or "other"
  source_quality = _first_value(web_row, "source_quality") or "unknown"
  source_url = _first_value(web_row, "source_url", "web_signal_url")
  source_domain = _first_value(web_row, "source_domain", "web_signal_domain")
  evidence_sentence = _combine_evidence_sentences(web_row.get("evidence_sentences")) or None
  if evidence_sentence:
    evidence_sentence = evidence_sentence[:500]

  claim_element_text = (claim or {}).get("claim_element_text") or None
  paper_title = (paper or {}).get("paper_title") or None
  claim_text = " ".join(filter(None, [claim_element_text, (claim or {}).get("claim_element_id")]))
  paper_text = " ".join(filter(None, [paper_title, (paper or {}).get("paper_text", "")]))

  claim_term_match = bool(claim) and bool(match_terms(claim_text, right_text))
  paper_term_match = bool(paper) and bool(match_terms(paper_text, right_text))

  link_type = infer_link_type(
    web_signal_type=web_signal_type,
    matched_terms=matched,
    has_claim=bool(claim),
    has_paper=bool(paper),
    claim_paper_context=claim_paper_context,
    claim_term_match=claim_term_match,
    paper_term_match=paper_term_match,
    source_quality=source_quality,
    calibrated=config.calibrated_scoring,
  )

  if config.calibrated_scoring:
    calibrated = score_link_candidate_calibrated(
      matched_terms=matched,
      source_quality=source_quality,
      web_signal_type=web_signal_type,
      web_signal_domain=source_domain,
      evidence_sentence=evidence_sentence,
      source_url=source_url,
      claim_element_text=claim_element_text,
      paper_title=paper_title,
      claim_term_match=claim_term_match,
      paper_term_match=paper_term_match,
    )
    score = calibrated.score
    confidence = calibrated.confidence
    score_reason = calibrated.score_reason
    score_cap_reason = calibrated.score_cap_reason
  else:
    score = score_link_candidate(
      matched_terms=matched,
      source_quality=source_quality,
      web_signal_type=web_signal_type,
      web_signal_domain=source_domain,
      evidence_sentence=evidence_sentence,
      has_claim_match=bool(claim),
      has_paper_match=bool(paper),
      source_url=source_url,
      calibrated=False,
    )
    confidence = _confidence_from_score(score)
    score_reason = ""
    score_cap_reason = ""

  strong, moderate, broad = split_terms_by_strength(matched)
  link_explanation = build_link_explanation(
    web_signal_type=web_signal_type,
    web_signal_domain=source_domain,
    link_type=link_type,
    matched_terms=matched,
    paper_title=paper_title,
  )
  why_not_conclusive = build_why_not_conclusive(link_type)

  return WebSignalLinkCandidate(
    link_id=new_link_id(),
    publication_number=publication_number,
    claim_element_id=(claim or {}).get("claim_element_id") or None,
    claim_element_text=claim_element_text,
    paper_id=(paper or {}).get("paper_id") or None,
    paper_title=paper_title,
    web_signal_id=_first_value(web_row, "signal_id", "web_signal_id") or new_link_id(),
    web_signal_type=web_signal_type,
    web_signal_title=_first_value(web_row, "source_title", "web_signal_title", "title"),
    web_signal_url=source_url,
    web_signal_domain=source_domain,
    source_quality=source_quality,
    link_type=link_type,
    link_score=score,
    matched_terms=matched,
    matched_contexts=contexts,
    evidence_sentence=evidence_sentence,
    confidence=confidence,
    verification_status="needs_human_review",
    caveat=_caveat_for_link(web_signal_type, link_type),
    next_verification_action=_next_action_for_link(link_type, web_signal_type),
    matched_strong_terms=strong,
    matched_moderate_terms=moderate,
    matched_broad_terms=broad,
    matched_term_strengths=_format_term_strengths(matched),
    link_explanation=link_explanation,
    score_reason=score_reason,
    score_cap_reason=score_cap_reason,
    needs_manual_review=True,
    why_not_conclusive=why_not_conclusive,
  )


def build_web_signal_link_candidates(
  *,
  publication_number: str,
  evidence_inputs: dict[str, Any],
  web_signal_inputs: dict[str, Any],
  min_link_score: int = 40,
  scoring_config: LinkScoringConfig | None = None,
) -> list[WebSignalLinkCandidate]:
  config = scoring_config or LinkScoringConfig()
  candidates: list[WebSignalLinkCandidate] = []
  web_df = web_signal_inputs.get("web_signals_df")
  if not isinstance(web_df, pd.DataFrame) or web_df.empty:
    return []

  claims = _iter_claim_elements(evidence_inputs.get("evidence_map_items_df", pd.DataFrame()))
  papers = _iter_papers(evidence_inputs.get("selected_papers_df", pd.DataFrame()))
  claim_links_df = evidence_inputs.get("claim_paper_links_df", pd.DataFrame())

  claim_link_rows: list[dict[str, str]] = []
  if isinstance(claim_links_df, pd.DataFrame) and not claim_links_df.empty:
    for _, row in claim_links_df.iterrows():
      row_dict = {str(k): _normalize_cell(v) for k, v in row.to_dict().items()}
      claim_link_rows.append(
        {
          "claim_element_id": _first_value(row_dict, "claim_element_id", "claim_element"),
          "claim_element_text": _first_value(row_dict, "claim_element_text", "claim_element"),
          "paper_title": _first_value(row_dict, "paper_title", "title"),
          "paper_text": " ".join(
            filter(
              None,
              [
                _first_value(row_dict, "paper_title", "title"),
                _first_value(row_dict, "keywords", "concepts"),
              ],
            ),
          ),
        },
      )

  for _, row in web_df.iterrows():
    web_row = {str(k): _normalize_cell(v) for k, v in row.to_dict().items()}
    web_text = _web_signal_text(web_row)

    for claim in claims:
      claim_text = " ".join(filter(None, [claim.get("claim_element_text"), claim.get("claim_element_id")]))
      try:
        candidate = _build_candidate(
          publication_number=publication_number,
          patent_title=str(evidence_inputs.get("patent_title") or ""),
          web_row=web_row,
          claim=claim,
          paper=None,
          claim_paper_context=False,
          left_text=claim_text,
          right_text=web_text,
          contexts=["claim_element", "web_signal"],
          scoring_config=config,
        )
        if candidate:
          candidates.append(candidate)
      except Exception:  # noqa: BLE001
        continue

    for paper in papers:
      try:
        candidate = _build_candidate(
          publication_number=publication_number,
          patent_title=str(evidence_inputs.get("patent_title") or ""),
          web_row=web_row,
          claim=None,
          paper=paper,
          claim_paper_context=False,
          left_text=paper.get("paper_text", ""),
          right_text=web_text,
          contexts=["selected_paper", "web_signal"],
          scoring_config=config,
        )
        if candidate:
          candidates.append(candidate)
      except Exception:  # noqa: BLE001
        continue

    for link_row in claim_link_rows:
      combined = " ".join(
        filter(
          None,
          [link_row.get("claim_element_text"), link_row.get("paper_text")],
        ),
      )
      try:
        candidate = _build_candidate(
          publication_number=publication_number,
          patent_title=str(evidence_inputs.get("patent_title") or ""),
          web_row=web_row,
          claim={
            "claim_element_id": link_row.get("claim_element_id", ""),
            "claim_element_text": link_row.get("claim_element_text", ""),
          },
          paper={
            "paper_id": "",
            "paper_title": link_row.get("paper_title", ""),
            "paper_text": link_row.get("paper_text", ""),
          },
          claim_paper_context=True,
          left_text=combined,
          right_text=web_text,
          contexts=["claim_paper_link", "web_signal"],
          scoring_config=config,
        )
        if candidate:
          candidates.append(candidate)
      except Exception:  # noqa: BLE001
        continue

  deduped = deduplicate_link_candidates(candidates)
  return [item for item in deduped if item.link_score >= min_link_score]


def build_web_signal_link_pack(
  *,
  publication_number: str,
  project_root: Path,
  web_signal_review_dir: str | Path | None = None,
  evidence_map_dir: str | Path | None = None,
  openalex_dir: str | Path | None = None,
  min_link_score: int = 40,
  top_n: int = 20,
  include_ir_disclosure: bool = True,
  include_company_local_news: bool = True,
  scoring_config: LinkScoringConfig | None = None,
) -> WebSignalLinkPack:
  config = scoring_config or LinkScoringConfig()
  root = Path(project_root)
  pub = str(publication_number).strip()
  evidence = load_evidence_map_inputs(pub, root)
  if evidence_map_dir:
    ev_path = Path(evidence_map_dir)
    if not ev_path.is_absolute():
      ev_path = root / ev_path
    evidence["evidence_map_items_df"] = safe_read_csv(ev_path / "evidence_map_items.csv")
    evidence["synthesis_json"] = safe_read_json(ev_path / "evidence_map_synthesis.json")
    evidence["evidence_map_dir"] = str(ev_path)
  if openalex_dir:
    oa_path = Path(openalex_dir)
    if not oa_path.is_absolute():
      oa_path = root / oa_path
    evidence["selected_papers_df"] = safe_read_csv(oa_path / "selected_evidence_papers.csv")
    evidence["claim_paper_links_df"] = safe_read_csv(oa_path / "claim_paper_candidate_links.csv")
    evidence["openalex_dir"] = str(oa_path)

  review_dir = str(web_signal_review_dir) if web_signal_review_dir else None
  web_inputs = load_web_signal_review_inputs(
    root,
    review_dir,
    include_ir_disclosure=include_ir_disclosure,
    include_company_local_news=include_company_local_news,
  )

  links = build_web_signal_link_candidates(
    publication_number=pub,
    evidence_inputs=evidence,
    web_signal_inputs=web_inputs,
    min_link_score=min_link_score,
    scoring_config=config,
  )
  links.sort(key=lambda item: item.link_score, reverse=True)
  if top_n > 0:
    links = links[:top_n]

  return WebSignalLinkPack(
    publication_number=pub,
    created_at=utc_now_iso(),
    patent_title=str(evidence.get("patent_title") or "") or None,
    link_candidates=links,
    input_artifacts={
      "evidence_map_dir": str(evidence.get("evidence_map_dir") or ""),
      "openalex_dir": str(evidence.get("openalex_dir") or ""),
      "web_signal_review_dir": str(web_inputs.get("review_pack_dir") or ""),
      "evidence_map_items_path": str(evidence.get("evidence_map_items_path") or ""),
      "selected_papers_path": str(evidence.get("selected_papers_path") or ""),
      "claim_paper_links_path": str(evidence.get("claim_paper_links_path") or ""),
    },
    caveats=[SUMMARY_CAUTION],
    notes=f"Generated {len(links)} link candidates (min_score={min_link_score}).",
  )


def link_candidates_to_records(candidates: list[WebSignalLinkCandidate]) -> list[dict[str, Any]]:
  records: list[dict[str, Any]] = []
  for item in candidates:
    records.append(
      {
        "link_id": item.link_id,
        "publication_number": item.publication_number,
        "claim_element_text": item.claim_element_text or "",
        "paper_title": item.paper_title or "",
        "web_signal_id": item.web_signal_id,
        "web_signal_type": item.web_signal_type,
        "web_signal_title": item.web_signal_title,
        "web_signal_domain": item.web_signal_domain,
        "source_quality": item.source_quality,
        "link_type": item.link_type,
        "link_score": item.link_score,
        "matched_terms": "; ".join(item.matched_terms),
        "evidence_sentence": item.evidence_sentence or "",
        "confidence": item.confidence,
        "verification_status": item.verification_status,
        "caveat": item.caveat,
        "next_verification_action": item.next_verification_action,
        "web_signal_url": item.web_signal_url,
        "matched_strong_terms": "; ".join(item.matched_strong_terms),
        "matched_moderate_terms": "; ".join(item.matched_moderate_terms),
        "matched_broad_terms": "; ".join(item.matched_broad_terms),
        "matched_term_strengths": item.matched_term_strengths,
        "link_explanation": item.link_explanation,
        "score_reason": item.score_reason,
        "score_cap_reason": item.score_cap_reason,
        "needs_manual_review": item.needs_manual_review,
        "why_not_conclusive": item.why_not_conclusive,
      },
    )
  return records


def _save_link_csv(records: list[dict[str, Any]], path: Path) -> None:
  path.parent.mkdir(parents=True, exist_ok=True)
  with path.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=list(LINK_CSV_COLUMNS), extrasaction="ignore")
    writer.writeheader()
    for record in records:
      writer.writerow({col: record.get(col, "") for col in LINK_CSV_COLUMNS})


def render_patent_paper_web_signal_summary_md(
  pack: WebSignalLinkPack,
  scoring_config: LinkScoringConfig | None = None,
) -> str:
  config = scoring_config or LinkScoringConfig()
  links = pack.link_candidates
  high_priority = [item for item in links if is_high_priority_link(item, config)]
  top_priority = [item for item in links if is_top_priority_link(item, config)]
  weak_links = [item for item in links if is_weak_link_candidate(item)]
  broad_only = [item for item in links if is_broad_only_match(item.matched_terms)]
  claim_missing = [item for item in links if not _meaningful_claim_text(item.claim_element_text)]

  score_ge_80 = sum(1 for item in links if item.link_score >= 80)
  score_60_79 = sum(1 for item in links if 60 <= item.link_score < 80)
  score_40_59 = sum(1 for item in links if 40 <= item.link_score < 60)
  score_lt_40 = sum(1 for item in links if item.link_score < 40)

  conf_medium = sum(1 for item in links if item.confidence == "medium")
  conf_low = sum(1 for item in links if item.confidence == "low")
  conf_weak = sum(1 for item in links if item.confidence == "weak")

  link_type_counts: dict[str, int] = {}
  signal_type_counts: dict[str, int] = {}
  for item in links:
    link_type_counts[item.link_type] = link_type_counts.get(item.link_type, 0) + 1
    signal_type_counts[item.web_signal_type] = signal_type_counts.get(item.web_signal_type, 0) + 1

  medium_candidates = [item for item in links if item.confidence == "medium"]
  low_candidates = [item for item in links if item.confidence == "low"]
  weak_overlap = [item for item in links if item.link_type == "weak_keyword_overlap"]

  lines = [
    "# Patent × Paper × Web Signal Link Candidate Summary",
    "",
    f"- publication_number: {pack.publication_number}",
    f"- patent_title: {pack.patent_title or '(not available)'}",
    f"- created_at: {pack.created_at}",
    f"- evidence_map_dir: {pack.input_artifacts.get('evidence_map_dir', '')}",
    f"- web_signal_review_dir: {pack.input_artifacts.get('web_signal_review_dir', '')}",
    "",
    "## Counts",
    "",
    f"- total link candidates: {len(links)}",
    f"- top priority link candidates (score>={config.min_top_priority_score}, strong/moderate): {len(top_priority)}",
    f"- high priority link candidates (score>={config.min_high_priority_score}): {len(high_priority)}",
    f"- weak link candidates: {len(weak_links)}",
    "",
    "## Score Distribution",
    "",
    f"- score >= 80: {score_ge_80}",
    f"- 60 <= score < 80: {score_60_79}",
    f"- 40 <= score < 60: {score_40_59}",
    f"- score < 40: {score_lt_40}",
    "",
    "## Link Strength Distribution",
    "",
    f"- medium: {conf_medium}",
    f"- low: {conf_low}",
    f"- weak: {conf_weak}",
    "",
    f"- broad term only candidates: {len(broad_only)}",
    f"- claim_element missing candidates: {len(claim_missing)}",
    "",
    "## Link Type Counts",
    "",
  ]
  if link_type_counts:
    for key, count in sorted(link_type_counts.items(), key=lambda kv: (-kv[1], kv[0])):
      lines.append(f"- {key}: {count}")
  else:
    lines.append("- (none)")

  lines.extend(["", "## Web Signal Type Counts", ""])
  if signal_type_counts:
    for key, count in sorted(signal_type_counts.items(), key=lambda kv: (-kv[1], kv[0])):
      lines.append(f"- {key}: {count}")
  else:
    lines.append("- (none)")

  lines.extend(["", "## Top Medium Candidates", ""])
  if medium_candidates:
    for item in medium_candidates[:5]:
      lines.append(
        f"- {item.web_signal_title} (score={item.link_score}, type={item.link_type}, "
        f"terms={', '.join(item.matched_terms)})",
      )
  else:
    lines.append("- (none)")

  lines.extend(["", "## Top Low Candidates", ""])
  if low_candidates:
    for item in low_candidates[:5]:
      lines.append(
        f"- {item.web_signal_title} (score={item.link_score}, type={item.link_type}, "
        f"terms={', '.join(item.matched_terms)})",
      )
  else:
    lines.append("- (none)")

  lines.extend(["", "## weak_keyword_overlap Candidates Summary", ""])
  if weak_overlap:
    for item in weak_overlap[:5]:
      lines.append(
        f"- {item.web_signal_title} (score={item.link_score}, terms={', '.join(item.matched_terms)})",
      )
  else:
    lines.append("- (none)")

  lines.extend(["", "## Top Link Candidates", ""])
  for item in links[:10]:
    lines.extend(
      [
        f"### {item.link_id} (score={item.link_score}, type={item.link_type})",
        "",
        f"- web_signal: {item.web_signal_title}",
        f"- domain: {item.web_signal_domain or '(none)'}",
        f"- source_quality: {item.source_quality}",
        f"- claim_element: {item.claim_element_text or '(none)'}",
        f"- paper: {item.paper_title or '(none)'}",
        f"- matched_terms: {', '.join(item.matched_terms) if item.matched_terms else '(none)'}",
        f"- confidence: {item.confidence}",
        f"- link_explanation: {item.link_explanation}",
        "",
      ],
    )

  gov_links = [
    item
    for item in links
    if _is_government_domain(item.web_signal_domain) or item.source_quality == "high"
  ]
  lines.extend(["## High Quality Public Source Candidates", ""])
  if gov_links:
    for item in gov_links[:5]:
      lines.append(f"- {item.web_signal_title} ({item.web_signal_domain}) score={item.link_score}")
  else:
    lines.append("- (none in current pack)")

  ir_links = [item for item in links if item.web_signal_type in IR_DISCLOSURE_TYPES]
  lines.extend(["", "## IR / Disclosure Note", ""])
  if ir_links:
    lines.append(
      "IR / disclosure link candidates are present. Document-level verification is required "
      "before any strategic use."
    )
  else:
    lines.append("No IR / disclosure link candidates in this pack.")

  lines.extend(["", "## Evidence Gaps", ""])
  lines.append("- claims_only / description / examples may be incomplete for the target patent")
  lines.append("- Web signals are retrieved candidates; thematic overlap is not proof of linkage")
  lines.append("- Expert review is required before Evidence Map integration")

  lines.extend(["", "## Calibration Note", "", CALIBRATION_NOTE, ""])

  lines.extend(["", "## Next Verification Actions", ""])
  for action in DEFAULT_NEXT_ACTIONS:
    lines.append(f"- {action}")

  lines.extend(["", "## Important", "", SUMMARY_CAUTION, ""])
  return "\n".join(lines)


def render_next_verification_actions_md() -> str:
  lines = [
    "# Next Verification Actions",
    "",
    "## Medium Candidates",
    "",
  ]
  for action in MEDIUM_CANDIDATE_ACTIONS:
    lines.append(f"- {action}")
  lines.extend(["", "## Low Candidates", ""])
  for action in LOW_CANDIDATE_ACTIONS:
    lines.append(f"- {action}")
  lines.extend(["", "## Weak Candidates", ""])
  for action in WEAK_CANDIDATE_ACTIONS:
    lines.append(f"- {action}")
  lines.extend(["", "## General Actions", ""])
  for action in DEFAULT_NEXT_ACTIONS:
    lines.append(f"- {action}")
  lines.extend(["", "## Important", "", SUMMARY_CAUTION, ""])
  return "\n".join(lines)


def save_web_signal_link_pack(
  pack: WebSignalLinkPack,
  output_dir: Path | str,
  scoring_config: LinkScoringConfig | None = None,
) -> dict[str, Path]:
  config = scoring_config or LinkScoringConfig()
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)

  all_records = link_candidates_to_records(pack.link_candidates)
  high_items = [item for item in pack.link_candidates if is_high_priority_link(item, config)]
  top_items = [item for item in pack.link_candidates if is_top_priority_link(item, config)]
  weak_items = [item for item in pack.link_candidates if is_weak_link_candidate(item)]

  high_records = link_candidates_to_records(high_items)
  top_records = link_candidates_to_records(top_items)
  weak_records = link_candidates_to_records(weak_items) if config.include_weak_links else []

  json_path = out / "web_signal_link_candidates.json"
  csv_path = out / "web_signal_link_candidates.csv"
  high_csv_path = out / "high_priority_web_signal_links.csv"
  top_csv_path = out / "top_priority_web_signal_links.csv"
  weak_csv_path = out / "weak_web_signal_links.csv"
  summary_path = out / "patent_paper_web_signal_summary.md"
  actions_path = out / "next_verification_actions.md"

  json_path.write_text(json.dumps(pack.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
  _save_link_csv(all_records, csv_path)
  _save_link_csv(high_records, high_csv_path)
  _save_link_csv(top_records, top_csv_path)
  if config.include_weak_links:
    _save_link_csv(weak_records, weak_csv_path)
  summary_path.write_text(
    render_patent_paper_web_signal_summary_md(pack, scoring_config=config),
    encoding="utf-8",
  )
  actions_path.write_text(render_next_verification_actions_md(), encoding="utf-8")

  result = {
    "web_signal_link_candidates_json": json_path,
    "web_signal_link_candidates_csv": csv_path,
    "high_priority_web_signal_links_csv": high_csv_path,
    "top_priority_web_signal_links_csv": top_csv_path,
    "patent_paper_web_signal_summary_md": summary_path,
    "next_verification_actions_md": actions_path,
  }
  if config.include_weak_links:
    result["weak_web_signal_links_csv"] = weak_csv_path
  return result


def dry_run_link_build(
  *,
  publication_number: str,
  project_root: Path,
  web_signal_review_dir: str | Path | None = None,
  evidence_map_dir: str | Path | None = None,
  openalex_dir: str | Path | None = None,
) -> dict[str, Any]:
  root = Path(project_root)
  evidence = load_evidence_map_inputs(publication_number, root)
  if evidence_map_dir:
    ev_path = Path(evidence_map_dir)
    if not ev_path.is_absolute():
      ev_path = root / ev_path
    evidence["evidence_map_items_path"] = str(ev_path / "evidence_map_items.csv")
  if openalex_dir:
    oa_path = Path(openalex_dir)
    if not oa_path.is_absolute():
      oa_path = root / oa_path
    evidence["selected_papers_path"] = str(oa_path / "selected_evidence_papers.csv")
    evidence["claim_paper_links_path"] = str(oa_path / "claim_paper_candidate_links.csv")

  web_inputs = load_web_signal_review_inputs(root, str(web_signal_review_dir) if web_signal_review_dir else None)
  web_df = web_inputs.get("web_signals_df", pd.DataFrame())
  items_df = evidence.get("evidence_map_items_df", pd.DataFrame())
  papers_df = evidence.get("selected_papers_df", pd.DataFrame())
  links_df = evidence.get("claim_paper_links_df", pd.DataFrame())

  return {
    "publication_number": publication_number,
    "artifact_checks": {
      "evidence_map_items": Path(str(evidence.get("evidence_map_items_path", ""))).exists(),
      "selected_papers": Path(str(evidence.get("selected_papers_path", ""))).exists(),
      "claim_paper_links": Path(str(evidence.get("claim_paper_links_path", ""))).exists(),
      "web_signal_review": Path(str(web_inputs.get("review_pack_dir", ""))).exists(),
    },
    "input_counts": {
      "claim_elements": len(_iter_claim_elements(items_df if isinstance(items_df, pd.DataFrame) else pd.DataFrame())),
      "papers": len(_iter_papers(papers_df if isinstance(papers_df, pd.DataFrame) else pd.DataFrame())),
      "claim_paper_links": len(links_df) if isinstance(links_df, pd.DataFrame) else 0,
      "web_signals": len(web_df) if isinstance(web_df, pd.DataFrame) else 0,
    },
    "estimated_pair_checks": (
      len(_iter_claim_elements(items_df if isinstance(items_df, pd.DataFrame) else pd.DataFrame()))
      + len(_iter_papers(papers_df if isinstance(papers_df, pd.DataFrame) else pd.DataFrame()))
      + (len(links_df) if isinstance(links_df, pd.DataFrame) else 0)
    )
    * max(len(web_df) if isinstance(web_df, pd.DataFrame) else 0, 0),
  }
