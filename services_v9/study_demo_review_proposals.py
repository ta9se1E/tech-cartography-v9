"""Deterministic review → search improvement proposal engine for Study Demo."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from services_v9.study_demo_review_schema import (
  ACCEPT_REASON_CODES,
  DECISION_ACCEPT,
  DECISION_REJECT,
  EXCLUDE_PROPOSAL_BLOCKED_REASONS,
  REJECT_REASON_CODES,
  normalize_decision,
  normalize_reason_codes,
)
from services_v9.watch_profile_schema import normalize_terms, parse_terms

PROPOSAL_TYPES = frozenset(
  {
    "add_include_keyword",
    "add_exclude_keyword",
    "boost_company",
    "boost_cpc_ipc",
    "boost_country",
    "boost_source_type",
    "lower_source_type",
    "add_exact_phrase_candidate",
    "content_type_reclassification",
    "duplicate_rule_candidate",
    "no_change_observation",
  }
)

PROPOSAL_STATUS_PROPOSED = "proposed"
PROPOSAL_STATUS_APPROVED = "approved"
PROPOSAL_STATUS_REJECTED = "rejected"
PROPOSAL_STATUS_APPLIED = "applied_to_draft"

STOP_WORDS = frozenset(
  {
    "the",
    "and",
    "for",
    "with",
    "carbon",
    "fiber",
    "pan",
    "の",
    "に",
    "を",
    "が",
    "は",
    "と",
    "で",
  }
)

ACADEMIC_DOMAIN_HINTS = ("doi.org", "arxiv.org", "springer", "elsevier", "nature.com", "ieee.org", "sciencedirect")


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).isoformat()


def _tokenize(text: str) -> list[str]:
  parts = re.split(r"[\s,;/、]+", str(text or "").lower())
  return [part.strip() for part in parts if part.strip()]


def _is_identifier_like(token: str) -> bool:
  if re.fullmatch(r"[a-z]{2}\d{5,}[a-z]?\d?", token, flags=re.IGNORECASE):
    return True
  if re.fullmatch(r"10\.\d{4,9}/[-._;()/:\dA-Za-z]+", token):
    return True
  return False


def _proposal_id(proposal_type: str, normalized_value: str, source_run_id: str) -> str:
  blob = f"{proposal_type}|{normalized_value}|{source_run_id}"
  return f"prop_{hashlib.sha256(blob.encode('utf-8')).hexdigest()[:16]}"


def _proposal_set_id(reviews: Sequence[Mapping[str, Any]], source_run_id: str) -> str:
  canonical = []
  for item in sorted(reviews, key=lambda row: str(row.get("signal_id", ""))):
    canonical.append(
      {
        "signal_id": item.get("signal_id"),
        "decision": normalize_decision(item.get("decision", "")),
        "reason_codes": normalize_reason_codes(item.get("reason_codes", [])),
      }
    )
  blob = json.dumps({"source_run_id": source_run_id, "reviews": canonical}, sort_keys=True, ensure_ascii=False)
  return f"ps_{hashlib.sha256(blob.encode('utf-8')).hexdigest()[:16]}"


def _confidence(support_count: int, opposing: int = 0) -> str:
  if support_count >= 5 and opposing == 0:
    return "high"
  if support_count >= 3:
    return "medium"
  if support_count >= 2:
    return "low"
  return "low"


def _collect_core_keywords(profile_keywords: Mapping[str, Any] | None) -> set[str]:
  keywords = dict(profile_keywords or {})
  terms: set[str] = set()
  for values in keywords.values():
    for item in list(values or []):
      token = str(item or "").strip().lower()
      if token:
        terms.add(token)
  return terms


def _signal_tokens(signal: Mapping[str, Any]) -> list[str]:
  blob = " ".join(
    [
      str(signal.get("title", "")),
      str(signal.get("summary", "")),
      str(signal.get("organization", "")),
    ]
  )
  return _tokenize(blob)


def _looks_academic(signal: Mapping[str, Any]) -> bool:
  metadata = dict(signal.get("metadata", {}) or {})
  if metadata.get("doi"):
    return True
  url = str(signal.get("url", "") or signal.get("source_url", "") or "")
  host = urlparse(url).netloc.lower()
  return any(hint in host for hint in ACADEMIC_DOMAIN_HINTS)


def generate_review_proposals(
  *,
  reviews: Sequence[Mapping[str, Any]],
  signals: Sequence[Mapping[str, Any]],
  source_run_id: str,
  profile_keywords: Mapping[str, Any] | None = None,
  theme_name: str = "",
) -> dict[str, Any]:
  signal_by_id = {str(item.get("signal_id", "")): dict(item) for item in signals}
  eligible_reviews = [
    dict(item)
    for item in reviews
    if item.get("reviewed") or item.get("reviewed_at")
  ]
  proposal_set_id = _proposal_set_id(eligible_reviews, source_run_id)
  core_keywords = _collect_core_keywords(profile_keywords)
  theme_tokens = set(_tokenize(theme_name))

  accept_reviews = [item for item in eligible_reviews if normalize_decision(item.get("decision")) == DECISION_ACCEPT]
  reject_reviews = [item for item in eligible_reviews if normalize_decision(item.get("decision")) == DECISION_REJECT]

  include_token_support: Counter[str] = Counter()
  include_token_reviews: dict[str, list[str]] = defaultdict(list)
  include_token_signals: dict[str, list[str]] = defaultdict(list)

  exclude_token_support: Counter[str] = Counter()
  exclude_token_reviews: dict[str, list[str]] = defaultdict(list)
  exclude_token_signals: dict[str, list[str]] = defaultdict(list)
  exclude_token_reasons: dict[str, set[str]] = defaultdict(set)

  company_support: Counter[str] = Counter()
  company_reviews: dict[str, list[str]] = defaultdict(list)
  company_signals: dict[str, list[str]] = defaultdict(list)

  cpc_support: Counter[str] = Counter()
  cpc_reviews: dict[str, list[str]] = defaultdict(list)
  cpc_signals: dict[str, list[str]] = defaultdict(list)

  proposals: list[dict[str, Any]] = []

  for review in accept_reviews:
    signal = signal_by_id.get(str(review.get("signal_id", "")), {})
    reasons = set(normalize_reason_codes(review.get("reason_codes", [])))
    if not reasons.intersection(ACCEPT_REASON_CODES):
      continue
    for token in _signal_tokens(signal):
      if len(token) < 3 or token in STOP_WORDS or token in core_keywords or token in theme_tokens:
        continue
      if _is_identifier_like(token):
        continue
      include_token_support[token] += 1
      include_token_reviews[token].append(str(review.get("signal_id", "")))
      include_token_signals[token].append(str(signal.get("signal_id", "")))
    org = str(signal.get("organization", "") or "").strip()
    if org and org.lower() not in {"unknown", "n/a", "none"}:
      company_support[org] += 1
      company_reviews[org].append(str(review.get("signal_id", "")))
      company_signals[org].append(str(signal.get("signal_id", "")))
    metadata = dict(signal.get("metadata", {}) or {})
    for code in list(metadata.get("cpc_codes", []) or []) + list(metadata.get("ipc_codes", []) or []):
      text = str(code or "").strip().upper()
      if text:
        cpc_support[text] += 1
        cpc_reviews[text].append(str(review.get("signal_id", "")))
        cpc_signals[text].append(str(signal.get("signal_id", "")))

  for review in reject_reviews:
    signal = signal_by_id.get(str(review.get("signal_id", "")), {})
    reasons = set(normalize_reason_codes(review.get("reason_codes", [])))
    blocked = reasons.intersection(EXCLUDE_PROPOSAL_BLOCKED_REASONS)
    if blocked:
      continue
    if not reasons.intersection(
      {
        "theme_mismatch",
        "material_mismatch",
        "process_mismatch",
        "property_mismatch",
        "commercial_noise",
      }
    ):
      continue
    for token in _signal_tokens(signal):
      if len(token) < 4 or token in STOP_WORDS or token in core_keywords or token in theme_tokens:
        continue
      if _is_identifier_like(token):
        continue
      exclude_token_support[token] += 1
      exclude_token_reviews[token].append(str(review.get("signal_id", "")))
      exclude_token_signals[token].append(str(signal.get("signal_id", "")))
      exclude_token_reasons[token].update(reasons)

  accept_tokens = {token for token, count in include_token_support.items() if count >= 2}

  for token, count in include_token_support.items():
    if count < 2:
      continue
    if token in accept_tokens and token in {t for t, c in exclude_token_support.items() if c >= 1}:
      continue
    normalized = token.lower()
    proposals.append(
      _build_proposal(
        proposal_type="add_include_keyword",
        proposed_value=token,
        normalized_value=normalized,
        source_run_id=source_run_id,
        supporting_review_ids=include_token_reviews[token],
        supporting_signal_ids=include_token_signals[token],
        supporting_reason_codes=["direct_evidence", "useful_supporting_evidence"],
        support_count=count,
        confidence=_confidence(count),
        expected_effect="recall向上",
        recall_risk="low",
        precision_risk="medium",
        explanation=f"採用レビュー{count}件で共通する語句",
      )
    )

  for token, count in exclude_token_support.items():
    if count < 3:
      continue
    if token in accept_tokens:
      continue
    normalized = token.lower()
    proposals.append(
      _build_proposal(
        proposal_type="add_exclude_keyword",
        proposed_value=token,
        normalized_value=normalized,
        source_run_id=source_run_id,
        supporting_review_ids=exclude_token_reviews[token],
        supporting_signal_ids=exclude_token_signals[token],
        supporting_reason_codes=sorted(exclude_token_reasons[token]),
        support_count=count,
        confidence=_confidence(count),
        expected_effect="precision向上",
        recall_risk="high",
        precision_risk="medium",
        explanation=f"除外レビュー{count}件で共通する語句（検索漏れリスクあり）",
      )
    )

  for org, count in company_support.items():
    if count < 2:
      continue
    proposals.append(
      _build_proposal(
        proposal_type="boost_company",
        proposed_value=org,
        normalized_value=org.strip(),
        source_run_id=source_run_id,
        supporting_review_ids=company_reviews[org],
        supporting_signal_ids=company_signals[org],
        supporting_reason_codes=["important_company_signal"],
        support_count=count,
        confidence=_confidence(count),
        expected_effect="注目企業の優先度向上",
        recall_risk="low",
        precision_risk="low",
        explanation=f"採用レビュー{count}件で同一organization",
      )
    )

  for code, count in cpc_support.items():
    if count < 2:
      continue
    proposals.append(
      _build_proposal(
        proposal_type="boost_cpc_ipc",
        proposed_value=code,
        normalized_value=code.upper(),
        source_run_id=source_run_id,
        supporting_review_ids=cpc_reviews[code],
        supporting_signal_ids=cpc_signals[code],
        supporting_reason_codes=["important_patent_family"],
        support_count=count,
        confidence=_confidence(count),
        expected_effect="分類コード重点化",
        recall_risk="low",
        precision_risk="medium",
        explanation=f"採用レビュー{count}件で同一CPC/IPC",
      )
    )

  for review in reject_reviews:
    signal = signal_by_id.get(str(review.get("signal_id", "")), {})
    reasons = set(normalize_reason_codes(review.get("reason_codes", [])))
    if "wrong_content_type" not in reasons and "academic_result_in_web_channel" not in reasons:
      continue
    if str(signal.get("source_type", "")) != "web_company" and str(signal.get("source_type", "")) != "web":
      continue
    if not _looks_academic(signal):
      continue
    proposals.append(
      _build_proposal(
        proposal_type="content_type_reclassification",
        proposed_value=str(signal.get("title", "")),
        normalized_value=str(signal.get("signal_id", "")),
        source_run_id=source_run_id,
        supporting_review_ids=[str(review.get("signal_id", ""))],
        supporting_signal_ids=[str(signal.get("signal_id", ""))],
        supporting_reason_codes=sorted(reasons),
        support_count=1,
        confidence="low",
        expected_effect="Paperチャネル再分類候補（提案のみ）",
        recall_risk="medium",
        precision_risk="medium",
        explanation="Web取得だが学術ドメイン/DOI候補あり",
      )
    )

  if not proposals:
    proposals.append(
      _build_proposal(
        proposal_type="no_change_observation",
        proposed_value="insufficient_review_support",
        normalized_value="insufficient_review_support",
        source_run_id=source_run_id,
        supporting_review_ids=[str(item.get("signal_id", "")) for item in eligible_reviews[:5]],
        supporting_signal_ids=[],
        supporting_reason_codes=[],
        support_count=len(eligible_reviews),
        confidence="low",
        expected_effect="観察のみ",
        recall_risk="low",
        precision_risk="low",
        explanation="検索条件へ反映できる十分なレビューがまだありません",
        status=PROPOSAL_STATUS_PROPOSED,
      )
    )

  return {
    "proposal_set_id": proposal_set_id,
    "source_run_id": source_run_id,
    "generation_precondition": {"review_count": len(eligible_reviews)},
    "created_at": _utc_now_iso(),
    "proposals": proposals,
    "summary": {
      "review_count": len(eligible_reviews),
      "accept_count": len(accept_reviews),
      "reject_count": len(reject_reviews),
      "proposal_count": len([item for item in proposals if item.get("proposal_type") != "no_change_observation"]),
      "observation_only": any(item.get("proposal_type") == "no_change_observation" for item in proposals),
    },
  }


def _build_proposal(
  *,
  proposal_type: str,
  proposed_value: str,
  normalized_value: str,
  source_run_id: str,
  supporting_review_ids: Sequence[str],
  supporting_signal_ids: Sequence[str],
  supporting_reason_codes: Sequence[str],
  support_count: int,
  confidence: str,
  expected_effect: str,
  recall_risk: str,
  precision_risk: str,
  explanation: str,
  status: str = PROPOSAL_STATUS_PROPOSED,
) -> dict[str, Any]:
  return {
    "proposal_id": _proposal_id(proposal_type, normalized_value, source_run_id),
    "proposal_type": proposal_type,
    "proposed_value": proposed_value,
    "normalized_value": normalized_value,
    "source_run_id": source_run_id,
    "supporting_review_ids": list(supporting_review_ids),
    "supporting_signal_ids": list(supporting_signal_ids),
    "supporting_reason_codes": list(supporting_reason_codes),
    "support_count": int(support_count),
    "confidence": confidence,
    "expected_effect": expected_effect,
    "recall_risk": recall_risk,
    "precision_risk": precision_risk,
    "explanation": explanation,
    "status": status,
    "created_at": _utc_now_iso(),
  }


def apply_approved_proposals_to_profile_draft(
  *,
  base_profile: Mapping[str, Any],
  approved_proposals: Sequence[Mapping[str, Any]],
  source_review_run_ids: Sequence[str],
  theme_id: str,
) -> dict[str, Any]:
  draft_id = f"draft_{uuid.uuid4().hex[:8]}"
  next_version = int(base_profile.get("watch_profile_version", 1) or 1) + 1
  keywords = dict(base_profile.get("keywords", {}) or {})
  before = {
    "include_keywords": _flatten_keywords(keywords),
    "exclude_keywords": normalize_terms(list(keywords.get("exclude_en", []) or []) + list(keywords.get("exclude_ja", []) or [])),
    "target_companies": list(base_profile.get("target_companies", []) or []),
    "priority_rules": list(base_profile.get("priority_rules", []) or []),
  }
  include_added: list[str] = []
  exclude_added: list[str] = []
  companies_added: list[str] = []
  cpc_added: list[str] = []
  reclass_candidates: list[str] = []

  target_companies = normalize_terms(list(base_profile.get("target_companies", []) or []))
  priority_rules = normalize_terms(list(base_profile.get("priority_rules", []) or []))
  exclude_en = normalize_terms(list(keywords.get("exclude_en", []) or []))
  exclude_ja = normalize_terms(list(keywords.get("exclude_ja", []) or []))
  core_en = normalize_terms(list(keywords.get("core_en", []) or []))

  for proposal in approved_proposals:
    ptype = str(proposal.get("proposal_type", "") or "")
    value = str(proposal.get("proposed_value", "") or "").strip()
    if not value:
      continue
    if ptype == "add_include_keyword" and value not in core_en:
      core_en.append(value)
      include_added.append(value)
    elif ptype == "add_exclude_keyword":
      if value not in exclude_en:
        exclude_en.append(value)
      exclude_added.append(value)
    elif ptype == "boost_company" and value not in target_companies:
      target_companies.append(value)
      companies_added.append(value)
    elif ptype == "boost_cpc_ipc":
      rule = f"boost_cpc:{value}"
      if rule not in priority_rules:
        priority_rules.append(rule)
      cpc_added.append(value)
    elif ptype == "content_type_reclassification":
      reclass_candidates.append(value)

  keywords["core_en"] = core_en
  keywords["exclude_en"] = exclude_en
  keywords["exclude_ja"] = exclude_ja
  after = {
    "include_keywords": _flatten_keywords(keywords),
    "exclude_keywords": normalize_terms(exclude_en + exclude_ja),
    "target_companies": target_companies,
    "priority_rules": priority_rules,
  }
  return {
    "draft_id": draft_id,
    "base_profile_id": base_profile.get("watch_profile_id"),
    "base_profile_version": base_profile.get("watch_profile_version"),
    "base_profile_signature": base_profile.get("watch_profile_signature"),
    "proposed_profile_version": next_version,
    "source_review_run_ids": list(source_review_run_ids),
    "approved_proposal_ids": [str(item.get("proposal_id", "")) for item in approved_proposals],
    "before": before,
    "after": after,
    "diff": {
      "include_keywords_added": include_added,
      "exclude_keywords_added": exclude_added,
      "companies_added": companies_added,
      "cpc_ipc_boost_added": cpc_added,
      "reclassification_candidates": reclass_candidates,
      "unchanged": [],
    },
    "keywords": keywords,
    "target_companies": target_companies,
    "priority_rules": priority_rules,
    "created_at": _utc_now_iso(),
    "status": "draft_not_applied",
    "application_scope": "study_demo_only",
    "theme_id": theme_id,
    "path_hint": f"analysis_context/profile_drafts/{theme_id}/v{next_version}_{draft_id}.json",
  }


def _flatten_keywords(keywords: Mapping[str, Any]) -> list[str]:
  terms: list[str] = []
  for key in ("core_en", "core_ja", "application_en", "application_ja", "material_process_en", "material_process_ja"):
    terms.extend(normalize_terms(list(keywords.get(key, []) or [])))
  return normalize_terms(terms)


def profile_draft_path(theme_id: str, version: int, draft_id: str) -> str:
  safe_theme = re.sub(r"[^A-Za-z0-9._-]+", "_", str(theme_id or ""))
  return f"analysis_context/profile_drafts/{safe_theme}/v{int(version)}_{draft_id}.json"


def proposal_storage_path(search_run_id: str, proposal_set_id: str) -> str:
  safe_run = re.sub(r"[^A-Za-z0-9._-]+", "_", str(search_run_id or ""))
  return f"analysis_context/review_proposals/{safe_run}/{proposal_set_id}.json"
