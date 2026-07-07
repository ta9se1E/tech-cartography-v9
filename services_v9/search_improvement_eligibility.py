"""Proposal eligibility and internal token guards for Study Demo."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from services_v9.simple_review_state import is_saved_review, normalize_simple_decision
from services_v9.study_demo_review_schema import normalize_decision

INTERNAL_TOKEN_PATTERN = re.compile(
  r"^(?:[a-z_]+:(?:title|abstract|summary|metadata))|(?:exact_phrase:)|(?:_score$)|(?:^[a-z_]+:[a-z_]+$)",
  re.IGNORECASE,
)
PROVIDER_PRIORITY_TYPES = frozenset({"boost_source_type", "lower_source_type"})
MIN_VALID_REVIEWS = 3
MIN_PATTERN_SUPPORT = 2


def reject_internal_token(token: str) -> bool:
  text = str(token or "").strip()
  if not text:
    return True
  if INTERNAL_TOKEN_PATTERN.search(text):
    return True
  if ":" in text and not text.startswith("http"):
    left, right = text.split(":", 1)
    if left.isalpha() or "_" in left:
      return True
  if text.endswith("_score"):
    return True
  return False


def normalize_human_keyword(token: str) -> str | None:
  text = str(token or "").strip()
  if not text or reject_internal_token(text):
    return None
  normalized = re.sub(r"[_]+", " ", text.lower()).strip()
  normalized = re.sub(r"\s+", " ", normalized)
  if len(normalized) < 3:
    return None
  return normalized


def build_insufficient_review_message() -> str:
  return (
    "現在はレビュー件数が不足しているため、検索条件の変更案はまだ生成しません。\n"
    "3件以上の人間レビュー後に、追加キーワード・除外語・検索範囲の候補を提示します。"
  )


def evaluate_proposal_eligibility(
  reviews: Sequence[Mapping[str, Any]],
  *,
  min_valid_reviews: int = MIN_VALID_REVIEWS,
) -> dict[str, Any]:
  valid = [
    item
    for item in reviews
    if is_saved_review(item) and normalize_simple_decision(item.get("decision", "")) != "unreviewed"
  ]
  decision_classes = {
    normalize_simple_decision(item.get("decision", ""))
    for item in valid
    if normalize_simple_decision(item.get("decision", "")) in {"accept", "hold", "reject"}
  }
  eligible = len(valid) >= min_valid_reviews and len(decision_classes) >= 2
  return {
    "eligible": eligible,
    "valid_review_count": len(valid),
    "decision_class_count": len(decision_classes),
    "reason": "" if eligible else "insufficient_reviews_or_decision_diversity",
    "message": "" if eligible else build_insufficient_review_message(),
  }


def validate_proposal_evidence(proposal: Mapping[str, Any]) -> list[str]:
  errors: list[str] = []
  proposal_type = str(proposal.get("proposal_type", "") or "")
  value = str(proposal.get("proposed_value", "") or "")
  normalized = str(proposal.get("normalized_value", "") or "")
  if proposal_type in PROVIDER_PRIORITY_TYPES:
    errors.append("provider_priority_hidden")
  if reject_internal_token(value) or reject_internal_token(normalized):
    errors.append("internal_token")
  if int(proposal.get("support_count", 0) or 0) < MIN_PATTERN_SUPPORT and proposal_type not in {
    "no_change_observation",
  }:
    errors.append("insufficient_pattern_support")
  if not normalize_human_keyword(value) and proposal_type in {"add_include_keyword", "add_exclude_keyword"}:
    errors.append("not_human_readable")
  return errors


def filter_human_proposals(
  proposals: Sequence[Mapping[str, Any]],
  *,
  simple_mode: bool = True,
) -> list[dict[str, Any]]:
  filtered: list[dict[str, Any]] = []
  for item in proposals:
    proposal = dict(item)
    proposal_type = str(proposal.get("proposal_type", "") or "")
    if proposal_type == "no_change_observation":
      filtered.append(proposal)
      continue
    if simple_mode and proposal_type in PROVIDER_PRIORITY_TYPES:
      continue
    if validate_proposal_evidence(proposal):
      continue
    human = normalize_human_keyword(str(proposal.get("proposed_value", "") or ""))
    if human:
      proposal["human_label"] = human
    filtered.append(proposal)
  return filtered


__all__ = [
  "MIN_PATTERN_SUPPORT",
  "MIN_VALID_REVIEWS",
  "build_insufficient_review_message",
  "evaluate_proposal_eligibility",
  "filter_human_proposals",
  "normalize_human_keyword",
  "reject_internal_token",
  "validate_proposal_evidence",
]
