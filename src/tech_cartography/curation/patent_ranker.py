"""Patent ranking for carbon fiber evidence map."""

from __future__ import annotations

import re
from datetime import datetime
from typing import Any

from tech_cartography.curation.dedup import _as_list
from tech_cartography.curation.noise_filter import compute_noise_score, is_likely_noise
from tech_cartography.domain.search_profile import SearchProfile

CLUSTER_PRIORITY = {
  "core_manufacturing": 1.0,
  "surface_interface": 0.95,
  "bundle_prepreg": 0.85,
  "property_defect_control": 0.8,
  "application_pressure_aerospace": 0.7,
  "company_watch": 0.65,
  "other_related": 0.35,
}

IMPORTANT_ASSIGNEES = [
  "toray",
  "teijin",
  "mitsubishi",
  "hyosung",
  "zhongfu",
  "sgl",
  "hexcel",
]

CARBON_FIBER_TERMS = [
  "carbon fiber",
  "carbon fibre",
  "cfrp",
  "polyacrylonitrile",
  "pan",
  "carbonization",
  "prepreg",
]

FULLTEXT_PRIORITY_CLUSTERS = {
  "core_manufacturing",
  "surface_interface",
  "bundle_prepreg",
}


def _parse_year(publication_date: str | None) -> int | None:
  if not publication_date:
    return None
  match = re.search(r"(20\d{2}|19\d{2})", str(publication_date))
  return int(match.group(1)) if match else None


def _theme_relevance_score(record: dict[str, Any], profile: SearchProfile | None) -> float:
  text = " ".join(
    [
      str(record.get("title", "") or ""),
      str(record.get("abstract", "") or ""),
      " ".join(_as_list(record.get("matched_terms"))),
    ],
  ).lower()
  hits = sum(1 for term in CARBON_FIBER_TERMS if term in text)
  profile_hits = 0
  if profile:
    for term in profile.include_terms + profile.materials + profile.processes:
      if term.lower() in text:
        profile_hits += 1
  return min(1.0, 0.15 * hits + 0.05 * profile_hits)


def _cluster_priority_score(record: dict[str, Any]) -> float:
  primary = str(record.get("primary_cluster_id", "other_related"))
  return CLUSTER_PRIORITY.get(primary, 0.3)


def _assignee_importance_score(record: dict[str, Any]) -> float:
  assignee = str(record.get("assignee", "") or "").lower()
  hits = sum(1 for company in IMPORTANT_ASSIGNEES if company in assignee)
  return min(1.0, 0.35 * hits)


def _recency_score(record: dict[str, Any]) -> float:
  year = _parse_year(str(record.get("publication_date", "") or ""))
  if year is None:
    return 0.35
  current_year = datetime.now().year
  age = max(0, current_year - year)
  if age <= 3:
    return 1.0
  if age <= 8:
    return 0.8
  if age <= 15:
    return 0.55
  return 0.35


def _source_route_score(record: dict[str, Any]) -> float:
  country = str(record.get("country", "") or "").upper()
  if country == "US":
    return 1.0
  if country in {"EP", "WO", "JP"}:
    return 0.55
  return 0.4


def _multi_intent_score(record: dict[str, Any]) -> float:
  intents = _as_list(record.get("search_intents"))
  if len(intents) >= 3:
    return 1.0
  if len(intents) == 2:
    return 0.75
  if len(intents) == 1:
    return 0.45
  return 0.0


def _recommended_action(record: dict[str, Any], total_score: float, noise_score: float) -> str:
  if is_likely_noise(record):
    return "likely_noise"
  if (
    total_score >= 0.75
    and str(record.get("country", "")).upper() == "US"
    and str(record.get("claims_source", "")) == "not_fetched"
    and record.get("primary_cluster_id") in FULLTEXT_PRIORITY_CLUSTERS
  ):
    return "full_text_top5_candidate"
  if total_score >= 0.6:
    return "important_metadata_only"
  if str(record.get("country", "")).upper() in {"JP", "EP", "WO"}:
    return "pdf_manual_review"
  if noise_score >= 0.45:
    return "monitor_only"
  return "monitor_only"


def score_patent_record(
  record: dict[str, Any],
  profile: SearchProfile | None = None,
) -> dict[str, Any]:
  noise_score = compute_noise_score(record)
  breakdown = {
    "theme_relevance_score": round(_theme_relevance_score(record, profile), 4),
    "cluster_priority_score": round(_cluster_priority_score(record), 4),
    "assignee_importance_score": round(_assignee_importance_score(record), 4),
    "recency_score": round(_recency_score(record), 4),
    "source_route_score": round(_source_route_score(record), 4),
    "multi_intent_score": round(_multi_intent_score(record), 4),
    "noise_penalty": round(noise_score, 4),
  }
  total_score = round(
    breakdown["theme_relevance_score"] * 0.25
    + breakdown["cluster_priority_score"] * 0.25
    + breakdown["assignee_importance_score"] * 0.15
    + breakdown["recency_score"] * 0.10
    + breakdown["source_route_score"] * 0.10
    + breakdown["multi_intent_score"] * 0.10
    - breakdown["noise_penalty"] * 0.20,
    4,
  )
  total_score = max(0.0, min(1.0, total_score))

  rank_reason_parts = [
    f"cluster={record.get('primary_cluster_id')}",
    f"country={record.get('country', '')}",
    f"noise={noise_score}",
  ]
  if breakdown["assignee_importance_score"] > 0:
    rank_reason_parts.append("major assignee boost")
  if breakdown["multi_intent_score"] >= 0.75:
    rank_reason_parts.append("multi-intent detection")

  enriched = dict(record)
  enriched["noise_score"] = noise_score
  enriched["noise_signals"] = record.get("noise_signals") or []
  enriched["total_score"] = total_score
  enriched["score_breakdown"] = breakdown
  enriched["rank_reason"] = "; ".join(rank_reason_parts)
  enriched["recommended_action"] = _recommended_action(record, total_score, noise_score)
  return enriched


def rank_patent_records(
  records: list[dict[str, Any]],
  profile: SearchProfile | None = None,
) -> list[dict[str, Any]]:
  scored = [score_patent_record(record, profile) for record in records]
  return sorted(scored, key=lambda item: float(item.get("total_score", 0)), reverse=True)


def select_top_patents(records: list[dict[str, Any]], top_n: int = 20) -> list[dict[str, Any]]:
  ranked = rank_patent_records(records) if not records or "total_score" not in records[0] else sorted(
    records,
    key=lambda item: float(item.get("total_score", 0)),
    reverse=True,
  )
  top_records: list[dict[str, Any]] = []
  for index, record in enumerate(ranked[:top_n], start=1):
    row = dict(record)
    row["rank"] = index
    top_records.append(row)
  return top_records


def select_fulltext_candidates(
  records: list[dict[str, Any]],
  top_n: int = 5,
) -> list[dict[str, Any]]:
  ranked = sorted(records, key=lambda item: float(item.get("total_score", 0)), reverse=True)
  selected: list[dict[str, Any]] = []
  assignee_counts: dict[str, int] = {}

  for record in ranked:
    if len(selected) >= top_n:
      break
    if is_likely_noise(record):
      continue
    if str(record.get("claims_source", "")) not in {"", "not_fetched"}:
      continue
    if record.get("primary_cluster_id") not in FULLTEXT_PRIORITY_CLUSTERS and float(
      record.get("total_score", 0),
    ) < 0.55:
      continue

    assignee_key = str(record.get("assignee", "unknown") or "unknown").lower()
    if assignee_counts.get(assignee_key, 0) >= 2:
      continue

    country = str(record.get("country", "") or "").upper()
    us_boost = 0.1 if country == "US" else 0.0
    effective_score = float(record.get("total_score", 0)) + us_boost
    if country != "US" and effective_score < 0.5:
      continue

    row = dict(record)
    row["fulltext_candidate_rank"] = len(selected) + 1
    row["fulltext_candidate_reason"] = (
      f"total_score={record.get('total_score')}; cluster={record.get('primary_cluster_id')}; country={country}"
    )
    row["fulltext_route"] = (
      "us_fulltext_candidate" if country == "US" else "manual_pdf_required"
    )
    row["next_step"] = "全文取得候補。次フェーズでclaims/description取得"
    selected.append(row)
    assignee_counts[assignee_key] = assignee_counts.get(assignee_key, 0) + 1

  return selected
