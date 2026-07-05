"""Human review schema and reason taxonomy for Study Demo."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence

REVIEW_SCHEMA_VERSION = 2
REVIEWER_SCOPE = "shared_study_demo"

DECISION_ACCEPT = "accept"
DECISION_HOLD = "hold"
DECISION_REJECT = "reject"

LEGACY_DECISION_MAP = {
  "accepted": DECISION_ACCEPT,
  "accept": DECISION_ACCEPT,
  "採用": DECISION_ACCEPT,
  "pending": DECISION_HOLD,
  "hold": DECISION_HOLD,
  "保留": DECISION_HOLD,
  "rejected": DECISION_REJECT,
  "reject": DECISION_REJECT,
  "見送り": DECISION_REJECT,
}

ACCEPT_REASON_CODES = frozenset(
  {
    "direct_evidence",
    "useful_supporting_evidence",
    "important_company_signal",
    "important_process_condition",
    "important_property_evidence",
    "important_patent_family",
    "important_review_paper",
  }
)

HOLD_REASON_CODES = frozenset(
  {
    "needs_fulltext",
    "needs_claim_review",
    "needs_method_review",
    "needs_duplicate_check",
    "unclear_relevance",
    "useful_background",
  }
)

REJECT_REASON_CODES = frozenset(
  {
    "theme_mismatch",
    "material_mismatch",
    "process_mismatch",
    "property_mismatch",
    "application_only_match",
    "duplicate",
    "known_information",
    "weak_evidence",
    "wrong_content_type",
    "non_target_language_or_region",
    "commercial_noise",
    "academic_result_in_web_channel",
  }
)

ALL_REASON_CODES = ACCEPT_REASON_CODES | HOLD_REASON_CODES | REJECT_REASON_CODES

REASON_LABELS_JA: dict[str, str] = {
  "direct_evidence": "直接証拠",
  "useful_supporting_evidence": "有用な補助証拠",
  "important_company_signal": "重要な企業シグナル",
  "important_process_condition": "重要なプロセス条件",
  "important_property_evidence": "重要な物性証拠",
  "important_patent_family": "重要な特許ファミリー",
  "important_review_paper": "重要なレビュー論文",
  "needs_fulltext": "全文確認が必要",
  "needs_claim_review": "請求項確認が必要",
  "needs_method_review": "評価法確認が必要",
  "needs_duplicate_check": "重複確認が必要",
  "unclear_relevance": "関連性が不明",
  "useful_background": "背景理解として有用",
  "theme_mismatch": "テーマ不一致",
  "material_mismatch": "材料不一致",
  "process_mismatch": "プロセス不一致",
  "property_mismatch": "物性不一致",
  "application_only_match": "用途のみ一致",
  "duplicate": "重複",
  "known_information": "既知情報",
  "weak_evidence": "証拠が弱い",
  "wrong_content_type": "コンテンツ種別不一致",
  "non_target_language_or_region": "対象外言語/地域",
  "commercial_noise": "商用ノイズ",
  "academic_result_in_web_channel": "Web取得の学術結果",
}

EXCLUDE_PROPOSAL_BLOCKED_REASONS = frozenset({"duplicate", "known_information", "weak_evidence"})


def normalize_decision(value: Any) -> str:
  text = str(value or "").strip().lower()
  mapped = LEGACY_DECISION_MAP.get(text) or LEGACY_DECISION_MAP.get(str(value or "").strip())
  if mapped:
    return mapped
  if text in {DECISION_ACCEPT, DECISION_HOLD, DECISION_REJECT}:
    return text
  return DECISION_HOLD


def normalize_reason_codes(codes: Sequence[Any] | None) -> list[str]:
  normalized: list[str] = []
  seen: set[str] = set()
  for item in list(codes or []):
    code = str(item or "").strip()
    if not code or code not in ALL_REASON_CODES or code in seen:
      continue
    seen.add(code)
    normalized.append(code)
  return normalized


def reasons_for_decision(decision: str) -> list[str]:
  normalized = normalize_decision(decision)
  if normalized == DECISION_ACCEPT:
    return sorted(ACCEPT_REASON_CODES)
  if normalized == DECISION_REJECT:
    return sorted(REJECT_REASON_CODES)
  return sorted(HOLD_REASON_CODES)


def reason_label_ja(code: str) -> str:
  return REASON_LABELS_JA.get(str(code or ""), str(code or ""))


def normalize_review_record(
  raw: Mapping[str, Any],
  *,
  signal_id: str,
  search_run_id: str,
  context_generation: int | None = None,
) -> dict[str, Any]:
  decision = normalize_decision(raw.get("decision", raw.get("review_decision", "hold")))
  reason_codes = normalize_reason_codes(raw.get("reason_codes", []) or [])
  comment = str(raw.get("comment", raw.get("review_note", raw.get("note", ""))) or "").strip()
  reviewed = bool(raw.get("reviewed", False) or raw.get("reviewed_at") or decision)
  return {
    "signal_id": signal_id,
    "decision": decision,
    "reason_codes": reason_codes,
    "comment": comment,
    "reviewed_at": str(raw.get("reviewed_at", "") or "") or (datetime.now(timezone.utc).isoformat() if reviewed else ""),
    "reviewed_signal_version": raw.get("reviewed_signal_version"),
    "source_run_id": str(raw.get("source_run_id", search_run_id) or search_run_id),
    "context_generation": context_generation if context_generation is not None else raw.get("context_generation"),
    "reviewer_scope": REVIEWER_SCOPE,
    "proposal_eligible": decision in {DECISION_ACCEPT, DECISION_REJECT},
    "review_schema_version": REVIEW_SCHEMA_VERSION,
    "reviewed": reviewed,
    "review_decision": _decision_label_ja(decision),
    "review_priority": raw.get("review_priority", 2),
  }


def _decision_label_ja(decision: str) -> str:
  if decision == DECISION_ACCEPT:
    return "採用"
  if decision == DECISION_REJECT:
    return "見送り"
  return "保留"


def validate_review_record(review: Mapping[str, Any]) -> list[str]:
  warnings: list[str] = []
  if not review.get("reason_codes"):
    warnings.append("reason_codes_missing")
  decision = normalize_decision(review.get("decision", ""))
  for code in normalize_reason_codes(review.get("reason_codes", [])):
    allowed = reasons_for_decision(decision)
    if code not in allowed:
      warnings.append(f"reason_not_allowed_for_decision:{code}")
  return warnings


def summarize_review_decisions(reviews: Sequence[Mapping[str, Any]]) -> dict[str, int]:
  summary = {"accept": 0, "hold": 0, "reject": 0, "unreviewed": 0}
  for item in reviews:
    if not item.get("reviewed") and not item.get("reviewed_at"):
      summary["unreviewed"] += 1
      continue
    decision = normalize_decision(item.get("decision", ""))
    summary[decision] = summary.get(decision, 0) + 1
  return summary


def summarize_reason_codes(reviews: Sequence[Mapping[str, Any]]) -> dict[str, int]:
  counts: dict[str, int] = {}
  for item in reviews:
    for code in normalize_reason_codes(item.get("reason_codes", [])):
      counts[code] = counts.get(code, 0) + 1
  return dict(sorted(counts.items(), key=lambda row: (-row[1], row[0])))


def merge_reviews_for_run(
  existing: Sequence[Mapping[str, Any]],
  updated: Mapping[str, Any],
  *,
  signal_id: str,
) -> list[dict[str, Any]]:
  merged = [dict(item) for item in existing if str(item.get("signal_id", "")) != signal_id]
  merged.append(dict(updated))
  return merged


def reviews_match_generation(reviews: Sequence[Mapping[str, Any]], generation: int | None) -> bool:
  if generation is None:
    return True
  for item in reviews:
    item_generation = item.get("context_generation")
    if item_generation is not None and int(item_generation) != int(generation):
      return False
  return True
