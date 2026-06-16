"""Rule-based technology classifier for carbon fiber evidence map."""

from __future__ import annotations

import json
import re
from collections import Counter, defaultdict
from typing import Any

from tech_cartography.curation.dedup import _as_list
from tech_cartography.domain.technology_cluster import (
  TechnologyCluster,
  default_carbon_fiber_clusters,
)

TEXT_FIELDS = ("title", "abstract", "assignee", "cpc_codes", "ipc_codes")
COMPANY_CLUSTER_ID = "company_watch"
FALLBACK_CLUSTER_ID = "other_related"


def _combined_text(record: dict[str, Any]) -> str:
  parts = [str(record.get(field, "") or "") for field in TEXT_FIELDS]
  parts.extend(_as_list(record.get("matched_terms")))
  return " ".join(parts).lower()


def _term_in_text(text: str, term: str) -> bool:
  normalized = term.strip().lower()
  if not normalized:
    return False
  if normalized == "pan":
    return bool(re.search(r"\bpan\b", text, re.IGNORECASE))
  if " " in normalized:
    return normalized in text
  return bool(re.search(rf"\b{re.escape(normalized)}\b", text, re.IGNORECASE))


def _assignee_matches(text: str, term: str) -> bool:
  return term.strip().lower() in text


def infer_cluster_scores(
  record: dict[str, Any],
  cluster_definitions: list[TechnologyCluster],
) -> dict[str, float]:
  text = _combined_text(record)
  assignee_text = str(record.get("assignee", "") or "").lower()
  search_intents = {item.lower() for item in _as_list(record.get("search_intents"))}
  scores: dict[str, float] = {}

  for cluster in cluster_definitions:
    score = 0.0
    for term in cluster.representative_terms:
      weight = 1.0
      if cluster.cluster_id == COMPANY_CLUSTER_ID:
        if _assignee_matches(assignee_text, term):
          score += 2.0
        elif _term_in_text(text, term):
          score += 0.5
        continue

      if _term_in_text(str(record.get("title", "") or "").lower(), term):
        score += 2.0
      elif _term_in_text(str(record.get("abstract", "") or "").lower(), term):
        score += 1.5
      elif any(_term_in_text(item.lower(), term) for item in _as_list(record.get("matched_terms"))):
        score += 1.2
      elif _term_in_text(text, term):
        score += 1.0

    for intent in cluster.search_intents:
      if intent.lower() in search_intents:
        score += 0.4

    if score > 0:
      scores[cluster.cluster_id] = round(score, 4)

  if not scores:
    scores[FALLBACK_CLUSTER_ID] = 0.1
  return scores


def assign_primary_cluster(cluster_scores: dict[str, float]) -> str:
  if not cluster_scores:
    return FALLBACK_CLUSTER_ID
  return max(cluster_scores.items(), key=lambda item: item[1])[0]


def assign_secondary_clusters(
  cluster_scores: dict[str, float],
  threshold: float = 0.25,
) -> list[str]:
  if not cluster_scores:
    return []
  primary = assign_primary_cluster(cluster_scores)
  primary_score = cluster_scores.get(primary, 0.0)
  cutoff = max(threshold, primary_score * threshold)
  return [
    cluster_id
    for cluster_id, score in sorted(cluster_scores.items(), key=lambda item: item[1], reverse=True)
    if cluster_id != primary and score >= cutoff
  ]


def _cluster_name(cluster_id: str, clusters: list[TechnologyCluster]) -> str:
  for cluster in clusters:
    if cluster.cluster_id == cluster_id:
      return cluster.name
  return cluster_id


def _build_classification_reason(
  record: dict[str, Any],
  primary_cluster_id: str,
  cluster_scores: dict[str, float],
  clusters: list[TechnologyCluster],
) -> str:
  reasons: list[str] = []
  matched_terms = [term.lower() for term in _as_list(record.get("matched_terms"))]
  title = str(record.get("title", "") or "").lower()
  assignee = str(record.get("assignee", "") or "").lower()

  if primary_cluster_id == "core_manufacturing":
    hits = [term for term in ("carbonization", "pan", "polyacrylonitrile", "stabilization") if term in matched_terms or term in title]
    if hits:
      reasons.append(
        f"matched_termsまたはtitleに {' / '.join(hits)} が含まれるため core_manufacturing に分類",
      )
  elif primary_cluster_id == "bundle_prepreg" and ("prepreg" in title or "bundle" in title or "tow" in title):
    reasons.append("titleに prepreg / bundle / tow が含まれるため bundle_prepreg に分類")
  elif primary_cluster_id == "surface_interface":
    if any(token in title or token in str(record.get("abstract", "")).lower() for token in ("surface treatment", "interface adhesion", "sizing")):
      reasons.append("surface treatment / interface adhesion / sizing が検出されたため surface_interface に分類")
  elif primary_cluster_id == "application_pressure_aerospace":
    if any(token in title for token in ("pressure vessel", "aerospace", "composite")):
      reasons.append("pressure vessel / aerospace / composite が検出されたため application_pressure_aerospace に分類")
  elif primary_cluster_id == COMPANY_CLUSTER_ID:
    if any(company.lower() in assignee for company in ("toray", "teijin", "mitsubishi", "hyosung", "zhongfu")):
      reasons.append("assigneeに主要企業が含まれ、company_watch意図で検出されたため company_watch も付与")

  if not reasons:
    reasons.append(
      f"cluster_scores={json.dumps(cluster_scores, ensure_ascii=False)} により {primary_cluster_id} を primary に設定",
    )
  return "; ".join(reasons)


def classify_patent_record(
  record: dict[str, Any],
  cluster_definitions: list[TechnologyCluster] | None = None,
) -> dict[str, Any]:
  clusters = cluster_definitions or default_carbon_fiber_clusters()
  cluster_scores = infer_cluster_scores(record, clusters)
  primary_cluster_id = assign_primary_cluster(cluster_scores)
  secondary_cluster_ids = assign_secondary_clusters(cluster_scores)

  enriched = dict(record)
  enriched["primary_cluster_id"] = primary_cluster_id
  enriched["primary_cluster_name"] = _cluster_name(primary_cluster_id, clusters)
  enriched["secondary_cluster_ids"] = secondary_cluster_ids
  enriched["cluster_scores"] = cluster_scores
  enriched["classification_reason"] = _build_classification_reason(
    record,
    primary_cluster_id,
    cluster_scores,
    clusters,
  )
  return enriched


def classify_patent_records(records: list[dict[str, Any]]) -> dict[str, Any]:
  clusters = default_carbon_fiber_clusters()
  classified = [classify_patent_record(record, clusters) for record in records]
  return {
    "classified_records": classified,
    "cluster_summary": build_cluster_summary(classified, clusters),
  }


def build_cluster_summary(
  classified_records: list[dict[str, Any]],
  cluster_definitions: list[TechnologyCluster] | None = None,
) -> list[dict[str, Any]]:
  clusters = cluster_definitions or default_carbon_fiber_clusters()
  cluster_map = {cluster.cluster_id: cluster for cluster in clusters}
  grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)

  for record in classified_records:
    grouped[record.get("primary_cluster_id", FALLBACK_CLUSTER_ID)].append(record)

  summaries: list[dict[str, Any]] = []
  for cluster_id, cluster in cluster_map.items():
    records = grouped.get(cluster_id, [])
    assignee_counter = Counter(
      str(record.get("assignee", "") or "Unknown") for record in records
    )
    summaries.append(
      {
        "cluster_id": cluster_id,
        "name": cluster.name,
        "description": cluster.description,
        "patent_count": len({record.get("publication_number") for record in records}),
        "representative_terms": cluster.representative_terms,
        "top_assignees": [name for name, _ in assignee_counter.most_common(5)],
        "representative_patents": [
          str(record.get("publication_number", ""))
          for record in sorted(
            records,
            key=lambda item: float(item.get("total_score", 0) or 0),
            reverse=True,
          )[:5]
        ],
        "evidence_status": cluster.evidence_status,
        "notes": cluster.notes,
      },
    )
  return summaries
