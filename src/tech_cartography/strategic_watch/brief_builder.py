"""Build Strategic Watch Brief from existing Evidence Map / Paper / Web Signal outputs (Phase 23.5)."""

from __future__ import annotations

import json
import re
import uuid
from pathlib import Path
from typing import Any

import pandas as pd

from tech_cartography.reports.project_export import load_records_csv
from tech_cartography.strategic_watch.schema import (
  BRIEF_CAUTION,
  ITEM_CAVEAT,
  WATCH_PRIORITY_NOTE,
  StrategicWatchBrief,
  StrategicWatchItem,
)
from tech_cartography.web_signals.linker import is_broad_only_match
from tech_cartography.web_signals.schema import utc_now_iso

NOT_AVAILABLE = "not available"

MONEY_TYPES: frozenset[str] = frozenset({"money", "grant", "funding", "equipment_investment", "policy"})
IR_TYPES: frozenset[str] = frozenset({"ir_disclosure", "disclosure"})

WATCH_ITEM_CSV_COLUMNS: tuple[str, ...] = (
  "watch_id",
  "publication_number",
  "watch_theme",
  "watch_type",
  "watch_priority",
  "target_patent",
  "related_claim_element",
  "related_paper_title",
  "related_web_signal_title",
  "related_web_signal_domain",
  "source_quality",
  "link_type",
  "link_score",
  "link_confidence",
  "why_it_matters",
  "evidence_basis",
  "evidence_gap",
  "next_verification_action",
  "caveat",
  "related_web_signal_url",
)

DEFAULT_EVIDENCE_GAPS: tuple[str, ...] = (
  "Target patent description/examples are not yet verified.",
  "Direct linkage between web signals and the target patent is not confirmed.",
  "Selected papers are supporting evidence candidates, not proof of patent claims.",
  "Relationship between public projects and commercial implementation is not confirmed.",
  "IR/disclosure candidates require original PDF verification.",
  "Claims-only route limits confidence to medium at most.",
)

NATIONAL_PROJECT_ACTION = (
  "Open NEDO / JST / METI source pages and verify project name, implementer, period, "
  "and target technology. Confirm whether claim elements cover the same technical scope."
)

PATENT_PAPER_WEB_ACTION = (
  "Have an expert confirm whether claim element, selected paper, and web signal use "
  "matched terms in the same technical sense. Add patent description/examples manually "
  "and re-evaluate."
)

IR_DISCLOSURE_ACTION = (
  "Verify original documents (earnings presentation, integrated report, EDINET, JPX/TDnet). "
  "Confirm whether business investment / R&D / capex descriptions relate to the target technology."
)

COMPANY_LOCAL_ACTION = (
  "Verify official company announcements or local news originals. "
  "Confirm facts about R&D, equipment investment, joint research, or commercialization."
)

WEAK_ACTION = (
  "Do not add to Evidence Map yet. Keep as reference candidate pending more information."
)


def new_watch_id() -> str:
  return f"watch-{uuid.uuid4().hex[:10]}"


def safe_read_csv(path: Path) -> pd.DataFrame:
  if not path.exists():
    return pd.DataFrame()
  try:
    rows = load_records_csv(str(path))
    return _normalize_dataframe(pd.DataFrame(rows) if rows else pd.DataFrame())
  except Exception:  # noqa: BLE001
    return pd.DataFrame()


def safe_read_text(path: Path) -> str | None:
  if not path.exists():
    return None
  try:
    return path.read_text(encoding="utf-8")
  except OSError:
    return None


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


def _cell_str(row: pd.Series, *keys: str) -> str:
  for key in keys:
    value = str(row.get(key) or "").strip()
    if value and value.lower() not in {"nan", "none"}:
      return value
  return ""


def _parse_terms(value: str) -> list[str]:
  text = str(value or "").strip()
  if not text:
    return []
  parts = re.split(r"[;,]", text)
  return [part.strip() for part in parts if part.strip()]


def _is_broad_only_row(row: pd.Series) -> bool:
  matched = _parse_terms(_cell_str(row, "matched_terms"))
  if matched:
    return is_broad_only_match(matched)
  broad = _parse_terms(_cell_str(row, "matched_broad_terms"))
  moderate = _parse_terms(_cell_str(row, "matched_moderate_terms"))
  strong = _parse_terms(_cell_str(row, "matched_strong_terms"))
  return bool(broad) and not moderate and not strong


def infer_watch_type(row: pd.Series) -> str:
  signal_type = _cell_str(row, "web_signal_type", "signal_type").lower()
  link_type = _cell_str(row, "link_type")
  paper_title = _cell_str(row, "paper_title", "related_paper_title")

  if link_type == "project_context_match" and paper_title:
    return "patent_paper_web_signal"
  if signal_type == "national_project":
    return "national_project_signal"
  if signal_type in MONEY_TYPES:
    return "money_signal"
  if signal_type in IR_TYPES:
    return "ir_disclosure_signal"
  if signal_type == "company":
    return "company_signal"
  if signal_type == "local_news":
    return "local_news_signal"
  if paper_title:
    return "patent_paper_web_signal"
  if signal_type in MONEY_TYPES or signal_type == "national_project":
    return "national_project_signal"
  return "patent_paper_web_signal"


def infer_watch_theme(row: pd.Series) -> str:
  terms = _parse_terms(_cell_str(row, "matched_terms"))
  signal_type = _cell_str(row, "web_signal_type", "signal_type").lower()
  domain = _cell_str(row, "web_signal_domain", "related_web_signal_domain", "source_domain")
  link_type = _cell_str(row, "link_type")

  term_set = {t.lower() for t in terms}
  if signal_type in IR_TYPES or "ir" in domain:
    return "IR / disclosure verification candidate"
  if any(t in term_set for t in {"cfrp", "carbon fiber", "炭素繊維", "composite", "複合材料"}):
    if any(t in term_set for t in {"hydrogen tank", "水素タンク", "pressure vessel", "圧力容器"}):
      return "Carbon fiber cost reduction and hydrogen tank application signal"
    return "CFRP / carbon fiber national project signal"
  if any(t in term_set for t in {"pan", "pan系", "polyacrylonitrile", "前駆体", "precursor"}):
    if any(t in term_set for t in {"stabilization", "耐炎化", "carbonization", "炭化"}):
      return "PAN precursor and stabilization research signal"
    return "PAN precursor research signal"
  if any(t in term_set for t in {"surface treatment", "表面処理", "sizing", "サイジング"}):
    return "Surface treatment / sizing supporting evidence signal"
  if domain.endswith("go.jp") or "nedo" in domain or "jst" in domain or "meti" in domain:
    return "NEDO / JST / METI public project context signal"
  if link_type == "project_context_match":
    return "Public project context signal"
  if link_type == "paper_context_match":
    return "Paper-aligned web signal context"
  return "Technology theme watch candidate"


def infer_watch_priority(row: pd.Series) -> str:
  score_raw = row.get("link_score", 0)
  try:
    score = int(float(score_raw))
  except (TypeError, ValueError):
    score = 0

  confidence = _cell_str(row, "confidence", "link_confidence").lower() or "unknown"
  source_quality = _cell_str(row, "source_quality").lower()
  has_url = bool(_cell_str(row, "web_signal_url", "related_web_signal_url", "source_url"))
  has_evidence = bool(_cell_str(row, "evidence_sentence"))
  broad_only = _is_broad_only_row(row)

  if (
    score >= 80
    and confidence == "medium"
    and source_quality == "high"
    and not broad_only
    and has_evidence
    and has_url
  ):
    return "high"

  if score < 60 or confidence == "weak" or broad_only or not has_evidence:
    return "low"

  if 60 <= score < 80 and confidence in {"low", "medium"} and has_url:
    return "medium"

  if score >= 80 and has_url and has_evidence and not broad_only:
    return "medium"

  return "low"


def _build_evidence_gap_text() -> str:
  return " ".join(DEFAULT_EVIDENCE_GAPS)


def _next_action_for_watch_type(watch_type: str, watch_priority: str) -> str:
  if watch_priority == "low" or watch_type == "evidence_gap":
    return WEAK_ACTION
  if watch_type in {"national_project_signal", "money_signal"}:
    return NATIONAL_PROJECT_ACTION
  if watch_type == "patent_paper_web_signal":
    return PATENT_PAPER_WEB_ACTION
  if watch_type == "ir_disclosure_signal":
    return IR_DISCLOSURE_ACTION
  if watch_type in {"company_signal", "local_news_signal"}:
    return COMPANY_LOCAL_ACTION
  return NATIONAL_PROJECT_ACTION


def _build_why_it_matters(row: pd.Series, watch_type: str) -> str:
  signal_type = _cell_str(row, "web_signal_type", "signal_type")
  source_quality = _cell_str(row, "source_quality") or "unknown"
  link_type = _cell_str(row, "link_type") or "unknown"
  terms = _cell_str(row, "matched_terms")
  paper = _cell_str(row, "paper_title", "related_paper_title")
  title = _cell_str(row, "web_signal_title", "related_web_signal_title", "source_title")
  domain = _cell_str(row, "web_signal_domain", "source_domain")

  if watch_type == "ir_disclosure_signal":
    return (
      f"IR/disclosure signal ({title}) may relate to {terms or 'target technology themes'}. "
      "Document-level verification is required before strategic use."
    )
  if domain.endswith("go.jp") or "nedo" in domain.lower():
    return (
      "NEDO / JST / METIなどの公的ソースで炭素繊維・CFRP・PAN系技術に関する研究開発シグナルが"
      f"確認されたため、対象特許の技術領域と同じ周辺テーマとして監視価値があります。"
      f"（signal_type={signal_type}, quality={source_quality}, link_type={link_type}"
      f"{', paper=' + paper[:60] if paper else ''}）。"
      "ただし、対象特許との直接関係は未確認です。"
    )
  return (
    f"Web signal ({title or signal_type}) overlaps on {terms or 'technology keywords'} "
    f"with selected evidence context (link_type={link_type}, quality={source_quality}). "
    "This is a monitoring candidate; direct patent relevance is not confirmed."
  )


def _build_evidence_basis(row: pd.Series) -> str:
  parts = [
    f"title={_cell_str(row, 'web_signal_title', 'source_title')}",
    f"domain={_cell_str(row, 'web_signal_domain', 'source_domain')}",
    f"quality={_cell_str(row, 'source_quality') or 'unknown'}",
    f"terms={_cell_str(row, 'matched_terms')}",
    f"link_type={_cell_str(row, 'link_type')}",
    f"paper={_cell_str(row, 'paper_title', 'related_paper_title')}",
  ]
  evidence = _cell_str(row, "evidence_sentence")
  if evidence:
    parts.append(f"evidence={evidence[:200]}")
  return "; ".join(part for part in parts if not part.endswith("="))


def build_watch_items_from_web_signal_links(
  df: pd.DataFrame,
  publication_number: str,
) -> list[StrategicWatchItem]:
  if df.empty:
    return []

  items: list[StrategicWatchItem] = []
  seen: set[str] = set()

  for _, row in df.iterrows():
    link_id = _cell_str(row, "link_id") or new_watch_id()
    dedupe_key = "|".join(
      [
        _cell_str(row, "web_signal_id"),
        _cell_str(row, "paper_title"),
        _cell_str(row, "claim_element_text"),
        _cell_str(row, "web_signal_title"),
      ],
    )
    if dedupe_key in seen:
      continue
    seen.add(dedupe_key)

    watch_type = infer_watch_type(row)
    watch_priority = infer_watch_priority(row)
    why = _build_why_it_matters(row, watch_type)
    basis = _build_evidence_basis(row)
    gap = _build_evidence_gap_text()
    action = _cell_str(row, "next_verification_action") or _next_action_for_watch_type(
      watch_type,
      watch_priority,
    )

    try:
      link_score = int(float(row.get("link_score", 0)))
    except (TypeError, ValueError):
      link_score = 0

    confidence = _cell_str(row, "confidence", "link_confidence").lower() or "unknown"
    if confidence not in {"medium", "low", "weak"}:
      confidence = "unknown"

    items.append(
      StrategicWatchItem(
        watch_id=link_id.replace("wlink-", "watch-") if link_id.startswith("wlink-") else link_id,
        publication_number=publication_number,
        watch_theme=infer_watch_theme(row),
        watch_type=watch_type,
        target_patent=publication_number,
        related_claim_element=_cell_str(row, "claim_element_text") or None,
        related_paper_title=_cell_str(row, "paper_title", "related_paper_title") or None,
        related_web_signal_title=_cell_str(row, "web_signal_title", "source_title") or None,
        related_web_signal_url=_cell_str(row, "web_signal_url", "source_url") or None,
        related_web_signal_domain=_cell_str(row, "web_signal_domain", "source_domain") or None,
        source_quality=_cell_str(row, "source_quality") or "unknown",
        link_type=_cell_str(row, "link_type") or None,
        link_score=link_score,
        link_confidence=confidence,
        watch_priority=watch_priority,
        why_it_matters=why,
        evidence_basis=basis,
        evidence_gap=gap,
        next_verification_action=action,
        caveat=ITEM_CAVEAT,
        is_synthetic_demo=False,
      ),
    )

  items.sort(key=lambda item: (item.watch_priority != "high", item.watch_priority != "medium", -item.link_score))
  return items


def _build_evidence_gap_items(publication_number: str, synthesis: dict[str, Any]) -> list[StrategicWatchItem]:
  gaps = synthesis.get("evidence_gaps") or synthesis.get("gaps") or []
  if isinstance(gaps, str):
    gaps = [gaps]
  if not isinstance(gaps, list):
    gaps = list(DEFAULT_EVIDENCE_GAPS)
  if not gaps:
    gaps = list(DEFAULT_EVIDENCE_GAPS)

  items: list[StrategicWatchItem] = []
  for idx, gap in enumerate(gaps[:5], start=1):
    text = str(gap).strip()
    if not text:
      continue
    items.append(
      StrategicWatchItem(
        watch_id=f"watch-gap-{idx}",
        publication_number=publication_number,
        watch_theme="Evidence gap requiring manual follow-up",
        watch_type="evidence_gap",
        target_patent=publication_number,
        related_claim_element=None,
        related_paper_title=None,
        related_web_signal_title=None,
        related_web_signal_url=None,
        related_web_signal_domain=None,
        source_quality="unknown",
        link_type=None,
        link_score=0,
        link_confidence="unknown",
        watch_priority="low",
        why_it_matters=f"Evidence Map synthesis flagged: {text}",
        evidence_basis="evidence_map_synthesis.json",
        evidence_gap=text,
        next_verification_action=WEAK_ACTION,
        caveat=ITEM_CAVEAT,
      ),
    )
  return items


def build_evidence_gaps(brief: StrategicWatchBrief) -> list[str]:
  gaps = list(DEFAULT_EVIDENCE_GAPS)
  for item in brief.watch_items:
    if item.watch_type == "evidence_gap" and item.evidence_gap not in gaps:
      gaps.append(item.evidence_gap)
  return gaps


def build_next_actions(brief: StrategicWatchBrief) -> list[str]:
  actions: list[str] = []
  seen: set[str] = set()
  for item in brief.watch_items:
    if item.next_verification_action and item.next_verification_action not in seen:
      actions.append(item.next_verification_action)
      seen.add(item.next_verification_action)
  if not actions:
    actions = [NATIONAL_PROJECT_ACTION, PATENT_PAPER_WEB_ACTION, WEAK_ACTION]
  return actions


def build_executive_summary(brief: StrategicWatchBrief) -> str:
  total = len(brief.watch_items)
  high = sum(1 for item in brief.watch_items if item.watch_priority == "high")
  medium = sum(1 for item in brief.watch_items if item.watch_priority == "medium")
  low = sum(1 for item in brief.watch_items if item.watch_priority == "low")
  national = sum(
    1 for item in brief.watch_items if item.watch_type in {"national_project_signal", "money_signal"}
  )
  ir_count = sum(1 for item in brief.watch_items if item.watch_type == "ir_disclosure_signal")
  cross = sum(1 for item in brief.watch_items if item.watch_type == "patent_paper_web_signal")

  return (
    f"Strategic Watch Brief for {brief.publication_number} consolidates {total} watch candidates "
    f"from Evidence Map, paper evidence, and calibrated web signal links. "
    f"Priority mix: high={high}, medium={medium}, low={low}. "
    f"National project/money signals={national}, IR/disclosure={ir_count}, "
    f"patent×paper×web candidates={cross}. "
    f"{WATCH_PRIORITY_NOTE} "
    "This brief organizes what to monitor next; it is not a final conclusion."
  )


def strategic_watch_items_to_dataframe(items: list[StrategicWatchItem]) -> pd.DataFrame:
  rows: list[dict[str, Any]] = []
  for item in items:
    rows.append(
      {
        "watch_id": item.watch_id,
        "publication_number": item.publication_number,
        "watch_theme": item.watch_theme,
        "watch_type": item.watch_type,
        "watch_priority": item.watch_priority,
        "target_patent": item.target_patent,
        "related_claim_element": item.related_claim_element or "",
        "related_paper_title": item.related_paper_title or "",
        "related_web_signal_title": item.related_web_signal_title or "",
        "related_web_signal_domain": item.related_web_signal_domain or "",
        "source_quality": item.source_quality,
        "link_type": item.link_type or "",
        "link_score": item.link_score,
        "link_confidence": item.link_confidence,
        "why_it_matters": item.why_it_matters,
        "evidence_basis": item.evidence_basis,
        "evidence_gap": item.evidence_gap,
        "next_verification_action": item.next_verification_action,
        "caveat": item.caveat,
        "related_web_signal_url": item.related_web_signal_url or "",
      },
    )
  return pd.DataFrame(rows, columns=list(WATCH_ITEM_CSV_COLUMNS))


def render_strategic_watch_brief_md(brief: StrategicWatchBrief) -> str:
  pub = brief.publication_number
  lines = [
    f"# Strategic Watch Brief: {pub}",
    "",
    f"- created_at: {brief.created_at}",
    f"- brief_title: {brief.brief_title}",
    "",
    "## Executive Summary",
    "",
    brief.executive_summary,
    "",
    "## What we can say",
    "",
    "- Evidence Map, selected papers, and web signal links show thematic overlap worth monitoring.",
    "- Public sources (NEDO/JST/METI) and paper contexts help prioritize next verification steps.",
    "- Watch priorities reflect monitoring attention, not confirmed facts.",
    "",
    "## What we cannot say",
    "",
    "- We cannot confirm direct relevance to specific patent claims without manual review.",
    "- We cannot infer FTO, infringement, or validity from this brief.",
    "- Papers do not prove patent claims; web signals are candidates only.",
    "",
    "## Top Strategic Watch Items",
    "",
  ]

  if brief.top_watch_items:
    for item in brief.top_watch_items[:10]:
      lines.extend(
        [
          f"### {item.watch_theme} ({item.watch_priority})",
          "",
          f"- watch_type: {item.watch_type}",
          f"- web_signal: {item.related_web_signal_title or '(none)'}",
          f"- paper: {item.related_paper_title or '(none)'}",
          f"- link_score: {item.link_score} / confidence: {item.link_confidence}",
          f"- why_it_matters: {item.why_it_matters}",
          f"- next_action: {item.next_verification_action}",
          "",
        ],
      )
  else:
    lines.append("- (none)")

  def _section(title: str, watch_types: set[str]) -> list[str]:
    section_lines = [f"## {title}", ""]
    filtered = [item for item in brief.watch_items if item.watch_type in watch_types]
    if filtered:
      for item in filtered[:10]:
        section_lines.append(
          f"- {item.watch_theme} [{item.watch_priority}] "
          f"score={item.link_score} — {item.related_web_signal_title or item.why_it_matters[:80]}",
        )
    else:
      section_lines.append("- (none in current brief)")
    section_lines.append("")
    return section_lines

  lines.extend(_section("National Project / Money Signals", {"national_project_signal", "money_signal"}))
  lines.extend(_section("IR / Disclosure Signals", {"ir_disclosure_signal"}))
  lines.extend(_section("Patent × Paper × Web Signal Candidates", {"patent_paper_web_signal"}))

  lines.extend(["## Evidence Gaps", ""])
  for gap in brief.evidence_gaps:
    lines.append(f"- {gap}")

  lines.extend(["", "## Next Verification Actions", ""])
  for action in brief.next_actions:
    lines.append(f"- {action}")

  lines.extend(["", "## Important Caveats", "", BRIEF_CAUTION, "", WATCH_PRIORITY_NOTE, ""])
  return "\n".join(lines)


def render_strategic_watch_next_actions_md(brief: StrategicWatchBrief) -> str:
  lines = ["# Strategic Watch — Next Verification Actions", ""]
  for priority in ("high", "medium", "low"):
    items = [item for item in brief.watch_items if item.watch_priority == priority]
    if not items:
      continue
    lines.append(f"## {priority.title()} Priority")
    lines.append("")
    seen: set[str] = set()
    for item in items:
      if item.next_verification_action in seen:
        continue
      lines.append(f"- {item.next_verification_action}")
      seen.add(item.next_verification_action)
    lines.append("")
  lines.extend(["## Important", "", BRIEF_CAUTION, ""])
  return "\n".join(lines)


def build_strategic_watch_brief(
  publication_number: str,
  project_root: Path | str = ".",
  web_signal_link_dir: Path | None = None,
  *,
  min_watch_score: int = 40,
  top_n: int = 10,
) -> StrategicWatchBrief:
  root = Path(project_root)
  pub = str(publication_number).strip()

  if web_signal_link_dir:
    link_dir = Path(web_signal_link_dir)
    if not link_dir.is_absolute():
      link_dir = root / link_dir
  else:
    link_dir = root / "outputs" / "web_signal_links" / pub

  ev_dir = root / "outputs" / "evidence_map_synthesis" / pub
  oa_dir = root / "outputs" / "openalex_limited_execution"
  review_dir = root / "outputs" / "web_signals" / "tavily_pan_carbon_fiber" / "review_pack"

  link_candidates_path = link_dir / "web_signal_link_candidates.csv"
  top_links_path = link_dir / "top_priority_web_signal_links.csv"
  high_links_path = link_dir / "high_priority_web_signal_links.csv"
  link_summary_path = link_dir / "patent_paper_web_signal_summary.md"
  link_actions_path = link_dir / "next_verification_actions.md"

  synthesis_path = ev_dir / "evidence_map_synthesis.json"
  synthesis_md_path = ev_dir / "evidence_map_synthesis.md"
  items_path = ev_dir / "evidence_map_items.csv"
  papers_path = oa_dir / "selected_evidence_papers.csv"
  claim_paper_path = oa_dir / "claim_paper_candidate_links.csv"

  links_df = safe_read_csv(link_candidates_path)
  if links_df.empty:
    links_df = safe_read_csv(high_links_path)

  if not links_df.empty and "link_score" in links_df.columns:
    links_df = links_df.copy()
    links_df["_score_num"] = pd.to_numeric(links_df["link_score"], errors="coerce").fillna(0)
    links_df = links_df[links_df["_score_num"] >= min_watch_score].drop(columns=["_score_num"])

  watch_items = build_watch_items_from_web_signal_links(links_df, pub)
  synthesis = safe_read_json(synthesis_path)
  watch_items.extend(_build_evidence_gap_items(pub, synthesis))

  top_source_df = safe_read_csv(top_links_path)
  if not top_source_df.empty:
    top_ids = {
      _cell_str(row, "link_id")
      for _, row in top_source_df.iterrows()
    }
    top_items = [item for item in watch_items if item.watch_id.replace("watch-", "wlink-") in top_ids or item.watch_id in top_ids]
  else:
    top_items = [item for item in watch_items if item.watch_priority in {"high", "medium"}]
  top_items = sorted(top_items, key=lambda item: (-item.link_score, item.watch_priority != "high"))[:top_n]

  patent_title = str(synthesis.get("title") or synthesis.get("patent_title") or pub)
  brief = StrategicWatchBrief(
    publication_number=pub,
    created_at=utc_now_iso(),
    brief_title=f"Strategic Watch Brief: {pub}",
    executive_summary="",
    watch_items=watch_items,
    top_watch_items=top_items,
    evidence_gaps=[],
    next_actions=[],
    input_artifacts={
      "web_signal_link_candidates_csv": str(link_candidates_path),
      "top_priority_web_signal_links_csv": str(top_links_path),
      "high_priority_web_signal_links_csv": str(high_links_path),
      "patent_paper_web_signal_summary_md": str(link_summary_path),
      "next_verification_actions_md": str(link_actions_path),
      "evidence_map_synthesis_json": str(synthesis_path),
      "evidence_map_synthesis_md": str(synthesis_md_path),
      "evidence_map_items_csv": str(items_path),
      "selected_evidence_papers_csv": str(papers_path),
      "claim_paper_candidate_links_csv": str(claim_paper_path),
      "web_signal_review_summary_md": str(review_dir / "web_signal_review_summary.md"),
    },
    caveats=[BRIEF_CAUTION],
    notes=f"Generated from {len(links_df)} link rows (min_score={min_watch_score}).",
  )
  brief.evidence_gaps = build_evidence_gaps(brief)
  brief.next_actions = build_next_actions(brief)
  brief.executive_summary = build_executive_summary(brief)
  return brief


def dry_run_strategic_watch_brief(
  publication_number: str,
  project_root: Path | str = ".",
  web_signal_link_dir: Path | None = None,
) -> dict[str, Any]:
  root = Path(project_root)
  pub = str(publication_number).strip()
  if web_signal_link_dir:
    link_dir = Path(web_signal_link_dir)
    if not link_dir.is_absolute():
      link_dir = root / link_dir
  else:
    link_dir = root / "outputs" / "web_signal_links" / pub

  paths = {
    "web_signal_link_candidates": link_dir / "web_signal_link_candidates.csv",
    "top_priority_links": link_dir / "top_priority_web_signal_links.csv",
    "evidence_map_synthesis": root / "outputs" / "evidence_map_synthesis" / pub / "evidence_map_synthesis.json",
  }
  links_df = safe_read_csv(paths["web_signal_link_candidates"])
  return {
    "publication_number": pub,
    "artifact_checks": {key: path.exists() for key, path in paths.items()},
    "input_counts": {
      "link_candidates": len(links_df),
      "estimated_watch_items": len(links_df),
    },
  }
