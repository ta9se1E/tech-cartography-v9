"""Web Signal Review Pack — human review workflow (Phase 23.2)."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import pandas as pd

from tech_cartography.reports.project_export import save_records_csv
from tech_cartography.web_signals.schema import WebSignal, WebSignalBatch, apply_validation_rules, utc_now_iso
from tech_cartography.web_signals.store import SUMMARY_CAUTION

DEFAULT_REVIEW_KEYWORDS: tuple[str, ...] = (
  "PAN",
  "polyacrylonitrile",
  "carbon fiber",
  "carbonization",
  "stabilization",
  "surface treatment",
  "sizing",
  "tensile strength",
  "modulus",
  "composite",
  "hydrogen tank",
  "pressure vessel",
  "炭素繊維",
  "PAN系",
  "炭化",
  "耐炎化",
  "表面処理",
  "サイジング",
  "引張強度",
  "弾性率",
  "複合材料",
  "水素タンク",
  "圧力容器",
  "設備投資",
  "研究開発",
  "決算説明",
  "統合報告書",
  "適時開示",
  "NEDO",
  "JST",
  "METI",
  "経済産業省",
)

IR_DISCLOSURE_TYPES: frozenset[str] = frozenset({"ir_disclosure", "disclosure"})
MONEY_NATIONAL_TYPES: frozenset[str] = frozenset(
  {"money", "national_project", "grant", "funding", "equipment_investment"},
)
COMPANY_LOCAL_TYPES: frozenset[str] = frozenset({"company", "local_news", "market"})

LOW_TRUST_CATEGORIES: frozenset[str] = frozenset({"job_board", "social", "blog"})
HIGH_TRUST_CATEGORIES: frozenset[str] = frozenset(
  {"public_funding", "national_project", "disclosure_platform", "ir_official"},
)

SENTENCE_SPLIT_PATTERN = re.compile(r"(?<=[。.!?])\s+|\n+")

REVIEW_PACK_VERSION = "phase23.2"


@dataclass
class WebSignalReviewItem:
  signal_id: str
  signal_type: str
  review_priority: int
  source_quality: str
  source_category: str
  source_title: str
  source_url: str
  source_domain: str
  disclosure_type: str
  related_company: str
  related_project: str
  related_institution: str
  related_technology_terms: list[str]
  evidence_sentences: list[str]
  confidence: str
  verification_status: str
  caveat: str
  next_verification_action: str
  keep_for_evidence_map: bool
  rejection_reason: str | None = None

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class WebSignalReviewPack:
  batch_id: str
  topic: str
  created_at: str
  review_pack_version: str
  total_signals: int
  deduplicated_count: int
  duplicates_removed: int
  review_min_priority: int
  keywords: list[str]
  items: list[WebSignalReviewItem] = field(default_factory=list)
  high_priority_items: list[WebSignalReviewItem] = field(default_factory=list)
  ir_disclosure_candidates: list[WebSignalReviewItem] = field(default_factory=list)
  money_national_project_candidates: list[WebSignalReviewItem] = field(default_factory=list)
  company_local_news_candidates: list[WebSignalReviewItem] = field(default_factory=list)
  rejected_items: list[WebSignalReviewItem] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return {
      "batch_id": self.batch_id,
      "topic": self.topic,
      "created_at": self.created_at,
      "review_pack_version": self.review_pack_version,
      "total_signals": self.total_signals,
      "deduplicated_count": self.deduplicated_count,
      "duplicates_removed": self.duplicates_removed,
      "review_min_priority": self.review_min_priority,
      "keywords": list(self.keywords),
      "item_count": len(self.items),
      "high_priority_count": len(self.high_priority_items),
      "ir_disclosure_count": len(self.ir_disclosure_candidates),
      "money_national_project_count": len(self.money_national_project_candidates),
      "company_local_news_count": len(self.company_local_news_candidates),
      "rejected_count": len(self.rejected_items),
      "items": [item.to_dict() for item in self.items],
      "high_priority_items": [item.to_dict() for item in self.high_priority_items],
      "ir_disclosure_candidates": [item.to_dict() for item in self.ir_disclosure_candidates],
      "money_national_project_candidates": [item.to_dict() for item in self.money_national_project_candidates],
      "company_local_news_candidates": [item.to_dict() for item in self.company_local_news_candidates],
      "rejected_items": [item.to_dict() for item in self.rejected_items],
    }


def extract_evidence_sentences(text: str, keywords: list[str], max_sentences: int = 3) -> list[str]:
  if not str(text or "").strip() or max_sentences <= 0:
    return []
  lowered_keywords = [keyword.lower() for keyword in keywords if str(keyword).strip()]
  if not lowered_keywords:
    return []

  sentences: list[str] = []
  for chunk in SENTENCE_SPLIT_PATTERN.split(str(text).strip()):
    sentence = chunk.strip()
    if len(sentence) < 8:
      continue
    lower_sentence = sentence.lower()
    if any(keyword in lower_sentence for keyword in lowered_keywords):
      sentences.append(sentence)
    if len(sentences) >= max_sentences:
      break
  return sentences


def infer_next_verification_action(signal: WebSignal) -> str:
  if str(signal.next_verification_action or "").strip():
    return str(signal.next_verification_action).strip()

  signal_type = str(signal.signal_type or "")
  source_category = str(signal.source_category or "")

  if signal.is_synthetic_demo:
    return "Replace synthetic demo placeholder with verified real source before use."
  if signal_type == "human":
    return "Verify identity and role linkage before use."
  if signal_type in IR_DISCLOSURE_TYPES:
    return "Open source document and verify disclosure type and fiscal period."
  if signal_type in MONEY_NATIONAL_TYPES:
    return "Verify funding source page and project linkage."
  if source_category == "disclosure_platform":
    return "Confirm filing document; do not treat search snippet as verified disclosure."
  if signal_type in COMPANY_LOCAL_TYPES:
    return "Verify company/region linkage and publication date."
  return "Review source page relevance and entity linkage."


def _combined_text(signal: WebSignal) -> str:
  parts = [
    signal.source_title or "",
    signal.raw_snippet or "",
    signal.extracted_text or "",
    " ".join(signal.extracted_evidence_sentences or []),
    " ".join(signal.related_technology_terms or []),
  ]
  return " ".join(part for part in parts if part).strip()


def _has_technology_keywords(text: str, keywords: list[str]) -> bool:
  lower = text.lower()
  return any(keyword.lower() in lower for keyword in keywords if keyword.strip())


def _is_thin_content(signal: WebSignal) -> bool:
  snippet = str(signal.raw_snippet or "").strip()
  extracted = str(signal.extracted_text or "").strip()
  if signal.is_synthetic_demo:
    return False
  if snippet in {"", "(no snippet)"} and not extracted:
    return True
  return len(snippet) < 20 and len(extracted) < 20


def score_review_priority(signal: WebSignal, keywords: list[str] | None = None) -> int:
  keywords = list(keywords or DEFAULT_REVIEW_KEYWORDS)
  signal = apply_validation_rules(signal)
  score = 30
  text = _combined_text(signal)

  quality = str(signal.source_quality or "unknown").lower()
  category = str(signal.source_category or "").lower()
  signal_type = str(signal.signal_type or "other")

  if quality == "high":
    score += 20
  elif quality == "medium_high":
    score += 12
  elif quality == "medium":
    score += 5
  elif quality in {"low", "unknown"}:
    score -= 20

  if signal_type in MONEY_NATIONAL_TYPES:
    score += 15
  if signal_type in IR_DISCLOSURE_TYPES:
    score += 15
  if category in HIGH_TRUST_CATEGORIES:
    score += 10
  if _has_technology_keywords(text, keywords):
    score += 10
  if str(signal.source_url or "").strip():
    score += 10
  if signal.extracted_evidence_sentences:
    score += 10

  if not str(signal.source_url or "").strip():
    score -= 30
  if _is_thin_content(signal):
    score -= 15
  if category in LOW_TRUST_CATEGORIES:
    score -= 15
  if signal_type == "human":
    score -= 20
  if signal_type == "other":
    score -= 10
  if not signal.extracted_evidence_sentences and not extract_evidence_sentences(
    f"{signal.raw_snippet or ''} {signal.extracted_text or ''}",
    keywords,
    max_sentences=1,
  ):
    score -= 10

  return max(0, min(100, score))


def _dedupe_key(signal: WebSignal) -> str:
  url = str(signal.source_url or "").strip().lower()
  if url:
    return f"url::{url}"
  title = re.sub(r"\s+", " ", str(signal.source_title or "").strip().lower())
  domain = str(signal.source_domain or "").strip().lower()
  return f"title_domain::{title}::{domain}"


def deduplicate_signals(signals: list[WebSignal], keywords: list[str] | None = None) -> tuple[list[WebSignal], int]:
  keywords = list(keywords or DEFAULT_REVIEW_KEYWORDS)
  best_by_key: dict[str, WebSignal] = {}
  order: list[str] = []

  for signal in signals:
    key = _dedupe_key(signal)
    existing = best_by_key.get(key)
    if existing is None:
      best_by_key[key] = signal
      order.append(key)
      continue
    if score_review_priority(signal, keywords) > score_review_priority(existing, keywords):
      best_by_key[key] = signal

  deduped = [best_by_key[key] for key in order]
  removed = max(0, len(signals) - len(deduped))
  return deduped, removed


def filter_low_value_signals(
  signals: list[WebSignal],
  keywords: list[str] | None = None,
) -> tuple[list[WebSignal], list[tuple[WebSignal, str]]]:
  keywords = list(keywords or DEFAULT_REVIEW_KEYWORDS)
  kept: list[WebSignal] = []
  rejected: list[tuple[WebSignal, str]] = []

  for signal in signals:
    normalized = apply_validation_rules(signal)
    evidence = list(normalized.extracted_evidence_sentences or [])
    if not evidence:
      evidence = extract_evidence_sentences(
        f"{normalized.raw_snippet or ''} {normalized.extracted_text or ''}",
        keywords,
      )

    reason: str | None = None
    if not str(normalized.source_url or "").strip() and not normalized.is_synthetic_demo:
      reason = "missing_source_url"
    elif not str(normalized.source_title or "").strip():
      reason = "missing_source_title"
    elif (
      str(normalized.source_quality or "").lower() == "low"
      and not evidence
      and not normalized.is_synthetic_demo
    ):
      reason = "low_quality_without_evidence"
    elif normalized.signal_type == "other" and not evidence and not normalized.is_synthetic_demo:
      reason = "other_type_without_evidence"
    elif (
      not normalized.is_synthetic_demo
      and "example.invalid" in str(normalized.source_url or "").lower()
    ):
      reason = "placeholder_invalid_domain"
    elif _is_thin_content(normalized) and not evidence and not normalized.is_synthetic_demo:
      reason = "thin_content"

    if reason:
      rejected.append((normalized, reason))
    else:
      kept.append(normalized)

  return kept, rejected


def _signal_to_review_item(
  signal: WebSignal,
  *,
  keywords: list[str],
  review_min_priority: int,
  rejection_reason: str | None = None,
) -> WebSignalReviewItem:
  normalized = apply_validation_rules(signal)
  evidence = list(normalized.extracted_evidence_sentences or [])
  if not evidence:
    evidence = extract_evidence_sentences(
      f"{normalized.raw_snippet or ''} {normalized.extracted_text or ''}",
      keywords,
    )

  priority = score_review_priority(normalized, keywords)
  next_action = infer_next_verification_action(normalized)
  keep = (
    rejection_reason is None
    and priority >= review_min_priority
    and normalized.verification_status != "rejected"
    and (not normalized.is_synthetic_demo or normalized.verification_status == "synthetic_demo")
  )

  return WebSignalReviewItem(
    signal_id=normalized.signal_id,
    signal_type=normalized.signal_type,
    review_priority=priority,
    source_quality=str(normalized.source_quality or "unknown"),
    source_category=str(normalized.source_category or "unknown"),
    source_title=str(normalized.source_title or ""),
    source_url=str(normalized.source_url or ""),
    source_domain=str(normalized.source_domain or ""),
    disclosure_type=str(normalized.disclosure_type or ""),
    related_company=str(normalized.related_company or ""),
    related_project=str(normalized.related_project or ""),
    related_institution=str(normalized.related_institution or ""),
    related_technology_terms=list(normalized.related_technology_terms or []),
    evidence_sentences=evidence,
    confidence=normalized.confidence,
    verification_status=normalized.verification_status,
    caveat=normalized.caveat,
    next_verification_action=next_action,
    keep_for_evidence_map=keep and priority >= 40,
    rejection_reason=rejection_reason,
  )


def build_web_signal_review_pack(
  batch: WebSignalBatch,
  *,
  keywords: list[str] | None = None,
  review_min_priority: int = 0,
  save_rejected: bool = True,
) -> WebSignalReviewPack:
  keyword_list = list(keywords or DEFAULT_REVIEW_KEYWORDS)
  total = len(batch.signals)

  deduped, duplicates_removed = deduplicate_signals(batch.signals, keyword_list)
  kept_signals, rejected_pairs = filter_low_value_signals(deduped, keyword_list)

  items: list[WebSignalReviewItem] = []
  rejected_items: list[WebSignalReviewItem] = []

  for signal in kept_signals:
    try:
      items.append(
        _signal_to_review_item(
          signal,
          keywords=keyword_list,
          review_min_priority=review_min_priority,
        ),
      )
    except Exception:  # noqa: BLE001 — one bad signal must not stop the pack
      continue

  if save_rejected:
    for signal, reason in rejected_pairs:
      try:
        rejected_items.append(
          _signal_to_review_item(
            signal,
            keywords=keyword_list,
            review_min_priority=review_min_priority,
            rejection_reason=reason,
          ),
        )
      except Exception:  # noqa: BLE001
        continue

  items.sort(key=lambda item: item.review_priority, reverse=True)

  high_priority_items = [
    item for item in items if item.review_priority >= max(review_min_priority, 60)
  ]
  ir_disclosure_candidates = [item for item in items if item.signal_type in IR_DISCLOSURE_TYPES]
  money_national_project_candidates = [
    item for item in items if item.signal_type in MONEY_NATIONAL_TYPES
  ]
  company_local_news_candidates = [
    item for item in items if item.signal_type in COMPANY_LOCAL_TYPES
  ]

  return WebSignalReviewPack(
    batch_id=batch.batch_id,
    topic=batch.topic,
    created_at=utc_now_iso(),
    review_pack_version=REVIEW_PACK_VERSION,
    total_signals=total,
    deduplicated_count=len(deduped),
    duplicates_removed=duplicates_removed,
    review_min_priority=review_min_priority,
    keywords=keyword_list,
    items=items,
    high_priority_items=high_priority_items,
    ir_disclosure_candidates=ir_disclosure_candidates,
    money_national_project_candidates=money_national_project_candidates,
    company_local_news_candidates=company_local_news_candidates,
    rejected_items=rejected_items,
  )


def review_pack_to_dataframe(pack: WebSignalReviewPack) -> pd.DataFrame:
  rows = [item.to_dict() for item in pack.items]
  if not rows:
    return pd.DataFrame(
      columns=[
        "signal_id",
        "signal_type",
        "review_priority",
        "source_quality",
        "source_category",
        "source_title",
        "source_url",
        "source_domain",
        "disclosure_type",
        "evidence_sentences",
        "confidence",
        "verification_status",
        "keep_for_evidence_map",
        "rejection_reason",
      ],
    )
  frame = pd.DataFrame(rows)
  if "evidence_sentences" in frame.columns:
    frame["evidence_sentences"] = frame["evidence_sentences"].apply(
      lambda value: "; ".join(value) if isinstance(value, list) else str(value or ""),
    )
  if "related_technology_terms" in frame.columns:
    frame["related_technology_terms"] = frame["related_technology_terms"].apply(
      lambda value: "; ".join(value) if isinstance(value, list) else str(value or ""),
    )
  return frame


def render_review_pack_summary_md(pack: WebSignalReviewPack) -> str:
  top_targets = sorted(pack.items, key=lambda item: item.review_priority, reverse=True)[:10]
  action_lines: list[str] = []
  seen_actions: set[str] = set()
  for item in top_targets:
    action = item.next_verification_action.strip()
    if action and action not in seen_actions:
      seen_actions.add(action)
      action_lines.append(f"- {action}")

  lines = [
    "# Web Signal Review Pack Summary",
    "",
    "## Purpose",
    "",
    "Organize Tavily-retrieved web signal candidates for human review before any Evidence Map linkage.",
    "This pack does not perform Patent × Paper × Web Signal automatic linking.",
    "",
    f"- batch_id: {pack.batch_id}",
    f"- topic: {pack.topic}",
    f"- created_at: {pack.created_at}",
    f"- review_pack_version: {pack.review_pack_version}",
    f"- review_min_priority: {pack.review_min_priority}",
    "",
    "## Counts",
    "",
    f"- total signals: {pack.total_signals}",
    f"- deduplicated signals: {pack.deduplicated_count}",
    f"- duplicates removed: {pack.duplicates_removed}",
    f"- review items kept: {len(pack.items)}",
    f"- high priority signals: {len(pack.high_priority_items)}",
    f"- IR / disclosure candidates: {len(pack.ir_disclosure_candidates)}",
    f"- money / national project candidates: {len(pack.money_national_project_candidates)}",
    f"- company / local news candidates: {len(pack.company_local_news_candidates)}",
    f"- rejected / low quality sources: {len(pack.rejected_items)}",
    "",
    "## Top 10 Review Targets",
    "",
  ]

  if top_targets:
    for item in top_targets:
      lines.extend(
        [
          f"### {item.signal_id} (priority={item.review_priority}, type={item.signal_type})",
          "",
          f"- title: {item.source_title}",
          f"- source: {item.source_url or '(none)'}",
          f"- domain: {item.source_domain or '(none)'}",
          f"- source_quality: {item.source_quality}",
          f"- disclosure_type: {item.disclosure_type or '(none)'}",
          f"- evidence: {' | '.join(item.evidence_sentences) if item.evidence_sentences else '(none)'}",
          f"- next_verification_action: {item.next_verification_action}",
          "",
        ],
      )
  else:
    lines.extend(["_No review targets in this pack._", ""])

  lines.extend(["## Next Verification Actions", ""])
  if action_lines:
    lines.extend(action_lines)
  else:
    lines.append("- No actions generated.")
  lines.extend(["", "## Important", "", SUMMARY_CAUTION, ""])
  return "\n".join(lines)


def _items_to_records(items: list[WebSignalReviewItem]) -> list[dict[str, Any]]:
  records: list[dict[str, Any]] = []
  for item in items:
    row = item.to_dict()
    row["evidence_sentences"] = "; ".join(item.evidence_sentences)
    row["related_technology_terms"] = "; ".join(item.related_technology_terms)
    records.append(row)
  return records


def save_web_signal_review_pack(pack: WebSignalReviewPack, output_dir: Path | str) -> dict[str, Path]:
  out = Path(output_dir) / "review_pack"
  out.mkdir(parents=True, exist_ok=True)

  json_path = out / "web_signal_review_pack.json"
  json_path.write_text(json.dumps(pack.to_dict(), indent=2, ensure_ascii=False), encoding="utf-8")

  items_csv = out / "web_signal_review_items.csv"
  high_csv = out / "high_priority_web_signals.csv"
  ir_csv = out / "ir_disclosure_candidates.csv"
  money_csv = out / "money_national_project_candidates.csv"
  company_csv = out / "company_local_news_candidates.csv"
  rejected_csv = out / "rejected_or_low_quality_sources.csv"
  summary_md = out / "web_signal_review_summary.md"

  save_records_csv(review_pack_to_dataframe(pack).to_dict(orient="records"), items_csv)
  save_records_csv(_items_to_records(pack.high_priority_items), high_csv)
  save_records_csv(_items_to_records(pack.ir_disclosure_candidates), ir_csv)
  save_records_csv(_items_to_records(pack.money_national_project_candidates), money_csv)
  save_records_csv(_items_to_records(pack.company_local_news_candidates), company_csv)
  save_records_csv(_items_to_records(pack.rejected_items), rejected_csv)
  summary_md.write_text(render_review_pack_summary_md(pack), encoding="utf-8")

  return {
    "web_signal_review_pack_json": json_path,
    "web_signal_review_items_csv": items_csv,
    "high_priority_web_signals_csv": high_csv,
    "ir_disclosure_candidates_csv": ir_csv,
    "money_national_project_candidates_csv": money_csv,
    "company_local_news_candidates_csv": company_csv,
    "rejected_or_low_quality_sources_csv": rejected_csv,
    "web_signal_review_summary_md": summary_md,
  }
