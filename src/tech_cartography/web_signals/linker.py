"""Patent × Paper × Web Signal link candidate builder (Phase 23.4)."""

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

TECHNOLOGY_TERMS_EN: tuple[str, ...] = (
  "polyacrylonitrile",
  "carbon fiber",
  "carbonization",
  "stabilization",
  "surface treatment",
  "tensile strength",
  "pressure vessel",
  "hydrogen tank",
  "aerospace",
  "composite",
  "precursor",
  "cfrp",
  "pan",
  "sizing",
  "modulus",
)

TECHNOLOGY_TERMS_JA: tuple[str, ...] = (
  "pan系",
  "炭素繊維",
  "炭化",
  "耐炎化",
  "表面処理",
  "サイジング",
  "引張強度",
  "弾性率",
  "複合材料",
  "航空機",
  "水素タンク",
  "圧力容器",
  "前駆体",
  "cfrp",
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
  for term in TECHNOLOGY_TERMS_EN:
    if term in normalized and term not in found:
      found.append(term)
  for term in TECHNOLOGY_TERMS_JA:
    if term in normalized and term not in found:
      found.append(term)
  return found


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
) -> int:
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


def infer_link_type(
  *,
  web_signal_type: str,
  matched_terms: list[str],
  has_claim: bool,
  has_paper: bool,
  claim_paper_context: bool,
) -> str:
  signal_type = str(web_signal_type or "").lower()
  if not matched_terms:
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
) -> WebSignalLinkCandidate | None:
  matched = match_terms(left_text, right_text)
  if not matched:
    return None

  web_signal_type = _first_value(web_row, "signal_type", "web_signal_type") or "other"
  source_quality = _first_value(web_row, "source_quality") or "unknown"
  source_url = _first_value(web_row, "source_url", "web_signal_url")
  source_domain = _first_value(web_row, "source_domain", "web_signal_domain")
  evidence_sentence = _combine_evidence_sentences(web_row.get("evidence_sentences")) or None
  if evidence_sentence:
    evidence_sentence = evidence_sentence[:500]

  link_type = infer_link_type(
    web_signal_type=web_signal_type,
    matched_terms=matched,
    has_claim=bool(claim),
    has_paper=bool(paper),
    claim_paper_context=claim_paper_context,
  )
  score = score_link_candidate(
    matched_terms=matched,
    source_quality=source_quality,
    web_signal_type=web_signal_type,
    web_signal_domain=source_domain,
    evidence_sentence=evidence_sentence,
    has_claim_match=bool(claim),
    has_paper_match=bool(paper),
    source_url=source_url,
  )

  return WebSignalLinkCandidate(
    link_id=new_link_id(),
    publication_number=publication_number,
    claim_element_id=(claim or {}).get("claim_element_id") or None,
    claim_element_text=(claim or {}).get("claim_element_text") or None,
    paper_id=(paper or {}).get("paper_id") or None,
    paper_title=(paper or {}).get("paper_title") or None,
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
    confidence=_confidence_from_score(score),
    verification_status="needs_human_review",
    caveat=_caveat_for_link(web_signal_type, link_type),
    next_verification_action=_next_action_for_link(link_type, web_signal_type),
  )


def build_web_signal_link_candidates(
  *,
  publication_number: str,
  evidence_inputs: dict[str, Any],
  web_signal_inputs: dict[str, Any],
  min_link_score: int = 40,
) -> list[WebSignalLinkCandidate]:
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
) -> WebSignalLinkPack:
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


def render_patent_paper_web_signal_summary_md(pack: WebSignalLinkPack) -> str:
  links = pack.link_candidates
  high_priority = [item for item in links if item.link_score >= 60]
  link_type_counts: dict[str, int] = {}
  signal_type_counts: dict[str, int] = {}
  for item in links:
    link_type_counts[item.link_type] = link_type_counts.get(item.link_type, 0) + 1
    signal_type_counts[item.web_signal_type] = signal_type_counts.get(item.web_signal_type, 0) + 1

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
    f"- high priority link candidates (score>=60): {len(high_priority)}",
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

  lines.extend(["", "## Next Verification Actions", ""])
  for action in DEFAULT_NEXT_ACTIONS:
    lines.append(f"- {action}")

  lines.extend(["", "## Important", "", SUMMARY_CAUTION, ""])
  return "\n".join(lines)


def render_next_verification_actions_md() -> str:
  lines = ["# Next Verification Actions", ""]
  for action in DEFAULT_NEXT_ACTIONS:
    lines.append(f"- {action}")
  lines.extend(["", "## Important", "", SUMMARY_CAUTION, ""])
  return "\n".join(lines)


def save_web_signal_link_pack(pack: WebSignalLinkPack, output_dir: Path | str) -> dict[str, Path]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)

  all_records = link_candidates_to_records(pack.link_candidates)
  high_records = link_candidates_to_records([item for item in pack.link_candidates if item.link_score >= 60])

  json_path = out / "web_signal_link_candidates.json"
  csv_path = out / "web_signal_link_candidates.csv"
  high_csv_path = out / "high_priority_web_signal_links.csv"
  summary_path = out / "patent_paper_web_signal_summary.md"
  actions_path = out / "next_verification_actions.md"

  json_path.write_text(json.dumps(pack.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")
  _save_link_csv(all_records, csv_path)
  _save_link_csv(high_records, high_csv_path)
  summary_path.write_text(render_patent_paper_web_signal_summary_md(pack), encoding="utf-8")
  actions_path.write_text(render_next_verification_actions_md(), encoding="utf-8")

  return {
    "web_signal_link_candidates_json": json_path,
    "web_signal_link_candidates_csv": csv_path,
    "high_priority_web_signal_links_csv": high_csv_path,
    "patent_paper_web_signal_summary_md": summary_path,
    "next_verification_actions_md": actions_path,
  }


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
