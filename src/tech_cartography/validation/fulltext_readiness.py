"""Assess full-text record readiness for claim element extraction."""

from __future__ import annotations

from typing import Any

FULLTEXT_EVIDENCE_LEVELS = frozenset(
  {
    "high_fulltext_evidence",
    "medium_fulltext_evidence",
    "low_fulltext_evidence",
  },
)

MANUAL_SOURCE_ROUTES = frozenset(
  {
    "manual_fulltext_required",
    "unsupported_country",
    "strategic_watch_manual",
  },
)


def _has_claims(record: dict[str, Any]) -> bool:
  claims = str(record.get("claims") or record.get("claims_text") or "").strip()
  independent = record.get("independent_claims") or []
  return bool(claims) or bool(independent)


def _has_description(record: dict[str, Any]) -> bool:
  description = str(record.get("description") or record.get("description_text") or "").strip()
  return bool(description)


def _has_examples(record: dict[str, Any]) -> bool:
  examples = record.get("examples")
  if isinstance(examples, str):
    return bool(examples.strip())
  return bool(examples)


def _has_measured_properties(record: dict[str, Any]) -> bool:
  measured = record.get("measured_properties")
  if isinstance(measured, list):
    return len(measured) > 0
  if isinstance(measured, str):
    return bool(measured.strip())
  return bool(measured)


def _manual_pub_set(manual_candidates: list[dict[str, Any]] | None) -> set[str]:
  return {
    str(row.get("publication_number") or "").strip()
    for row in (manual_candidates or [])
    if str(row.get("publication_number") or "").strip()
  }


def _is_manual_record(record: dict[str, Any], manual_pubs: set[str]) -> bool:
  pub = str(record.get("publication_number") or "").strip()
  if pub and pub in manual_pubs:
    return True
  source_route = str(record.get("source_route") or "").strip().lower()
  if source_route in MANUAL_SOURCE_ROUTES:
    return True
  retrieval_status = str(record.get("retrieval_status") or "").strip().lower()
  if retrieval_status == "manual_required":
    return True
  country = str(record.get("country") or "").strip().upper()
  if country and country != "US" and source_route:
    if "manual" in source_route or "watch" in source_route:
      return True
  return False


def classify_fulltext_record_status(
  record: dict[str, Any],
  manual_candidates: list[dict[str, Any]] | None = None,
) -> str:
  manual_pubs = _manual_pub_set(manual_candidates)
  if _is_manual_record(record, manual_pubs):
    return "manual_required"

  retrieval_status = str(record.get("retrieval_status") or "").strip().lower()
  if retrieval_status in {"manual_claims_loaded", "manual_fulltext_loaded"}:
    if _has_claims(record):
      return "ready_for_claim_extraction"
    return "metadata_only"

  if retrieval_status == "dry_run_only":
    return "dry_run_only"
  if retrieval_status == "skipped_not_selected":
    return "skipped_not_selected"
  if retrieval_status == "execute_blocked_confirmation_required":
    return "execute_blocked_confirmation_required"
  if retrieval_status == "cost_guard_failed":
    return "cost_guard_failed"
  if retrieval_status == "cost_guard_requires_expensive_confirmation":
    return "cost_guard_requires_expensive_confirmation"
  if retrieval_status == "blocked_by_usd_guard":
    return "blocked_by_usd_guard"
  if retrieval_status in {"cache_hit", "retrieved", "allowed_expensive_execute"}:
    pass
  if retrieval_status == "query_error":
    return "query_error"
  if retrieval_status in {"not_found", "missing"}:
    return "not_found"

  has_claims = _has_claims(record)
  has_description = _has_description(record)
  has_examples = _has_examples(record)
  has_measured = _has_measured_properties(record)
  has_supporting_body = has_description or has_examples or has_measured
  evidence_level = str(record.get("evidence_level") or "").strip()

  if has_claims and has_supporting_body and evidence_level in FULLTEXT_EVIDENCE_LEVELS:
    return "ready_for_claim_extraction"

  if has_claims and not has_supporting_body:
    return "limited_claim_extraction"

  if has_description and not has_claims:
    return "limited_claim_extraction"

  return "metadata_only"


def select_records_ready_for_claim_extraction(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
  return [
    record
    for record in records
    if classify_fulltext_record_status(record) == "ready_for_claim_extraction"
  ]


def select_records_needing_manual_fulltext(
  records: list[dict[str, Any]],
  manual_candidates: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
  manual_pubs = _manual_pub_set(manual_candidates)
  manual_rows: list[dict[str, Any]] = []
  seen: set[str] = set()

  for candidate in manual_candidates or []:
    pub = str(candidate.get("publication_number") or "").strip()
    if not pub or pub in seen:
      continue
    seen.add(pub)
    manual_rows.append({**candidate, "readiness_status": "manual_required"})

  for record in records:
    status = classify_fulltext_record_status(record, manual_candidates)
    if status != "manual_required":
      continue
    pub = str(record.get("publication_number") or "").strip()
    if pub and pub not in seen:
      seen.add(pub)
      manual_rows.append({**record, "readiness_status": status})

  return manual_rows


def build_fulltext_next_actions(readiness: dict[str, Any]) -> list[dict[str, Any]]:
  actions: list[dict[str, Any]] = []

  if readiness.get("dry_run_only_count", 0) > 0 or readiness.get("cost_guard_failed_count", 0) > 0:
    actions.append(
      {
        "action_id": "execute_fulltext_for_us_targets",
        "priority": "high",
        "reason": "US fulltext targets are still dry-run or blocked; execute controlled fulltext (claims_only first).",
      },
    )
  if readiness.get("cost_guard_requires_expensive_count", 0) > 0:
    actions.append(
      {
        "action_id": "allow_expensive_fulltext_for_us_target",
        "priority": "high",
        "reason": "GB limit exceeded but USD within budget; add --allow-expensive-fulltext after review.",
      },
    )

  if readiness.get("manual_required_count", 0) > 0:
    actions.append(
      {
        "action_id": "add_manual_fulltext_for_cn_watch",
        "priority": "high",
        "reason": "CN/EP/JP strategic watch candidates require manual PDF or Google Patents review.",
      },
    )
  manual_loaded = sum(
    1
    for row in readiness.get("classified_records", [])
    if str(row.get("retrieval_status") or "") in {"manual_claims_loaded", "manual_fulltext_loaded"}
  )
  if manual_loaded > 0:
    actions.append(
      {
        "action_id": "continue_manual_claim_extraction",
        "priority": "high",
        "reason": "Manual fulltext input loaded; continue claim element extraction on claims-only route.",
      },
    )

  if readiness.get("manual_required_count", 0) > 0:
    actions.append(
      {
        "action_id": "review_manual_fulltext_checklist",
        "priority": "medium",
        "reason": "Manual fulltext checklist should be reviewed before claim extraction for non-US patents.",
      },
    )

  if readiness.get("ready_count", 0) > 0 or readiness.get("limited_count", 0) > 0:
    actions.append(
      {
        "action_id": "run_claim_element_after_fulltext",
        "priority": "medium",
        "reason": "Some records are ready or limited for claim element extraction.",
      },
    )
  elif readiness.get("total_records", 0) > 0:
    actions.append(
      {
        "action_id": "continue_with_limited_metadata_report",
        "priority": "medium",
        "reason": "No claim-ready fulltext yet; continue with metadata-only evidence validation report.",
      },
    )

  return actions


def assess_fulltext_readiness(
  records: list[dict[str, Any]],
  manual_candidates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
  classified: list[dict[str, Any]] = []
  buckets: dict[str, list[dict[str, Any]]] = {
    "ready_for_claim_extraction": [],
    "limited_claim_extraction": [],
    "dry_run_only": [],
    "skipped_not_selected": [],
    "execute_blocked_confirmation_required": [],
    "manual_required": [],
    "metadata_only": [],
    "not_found": [],
    "query_error": [],
    "cost_guard_failed": [],
    "cost_guard_requires_expensive_confirmation": [],
    "blocked_by_usd_guard": [],
  }

  for record in records:
    status = classify_fulltext_record_status(record, manual_candidates)
    enriched = {**record, "readiness_status": status}
    classified.append(enriched)
    buckets[status].append(enriched)

  manual_required_records = select_records_needing_manual_fulltext(records, manual_candidates)
  manual_required_count = len(manual_required_records)

  ready_count = len(buckets["ready_for_claim_extraction"])
  limited_count = len(buckets["limited_claim_extraction"])
  dry_run_only_count = len(buckets["dry_run_only"])
  skipped_not_selected_count = len(buckets["skipped_not_selected"])
  not_ready_count = (
    len(buckets["metadata_only"])
    + len(buckets["not_found"])
    + len(buckets["query_error"])
    + len(buckets["cost_guard_failed"])
    + len(buckets["cost_guard_requires_expensive_confirmation"])
    + len(buckets["blocked_by_usd_guard"])
    + dry_run_only_count
    + skipped_not_selected_count
    + len(buckets["execute_blocked_confirmation_required"])
  )

  readiness = {
    "total_records": len(records),
    "ready_count": ready_count,
    "limited_count": limited_count,
    "dry_run_only_count": dry_run_only_count,
    "skipped_not_selected_count": skipped_not_selected_count,
    "execute_blocked_count": len(buckets["execute_blocked_confirmation_required"]),
    "manual_required_count": manual_required_count,
    "cost_guard_failed_count": len(buckets["cost_guard_failed"]),
    "cost_guard_requires_expensive_count": len(buckets["cost_guard_requires_expensive_confirmation"]),
    "blocked_by_usd_count": len(buckets["blocked_by_usd_guard"]),
    "not_ready_count": not_ready_count,
    "ready_records": buckets["ready_for_claim_extraction"],
    "limited_records": buckets["limited_claim_extraction"],
    "dry_run_only_records": buckets["dry_run_only"],
    "manual_required_records": manual_required_records,
    "classified_records": classified,
    "caveats": [
      "Paper evidence candidates do not prove patent claims.",
      "Missing fulltext does not mean a patent is unimportant.",
      "CN/EP/JP candidates remain on the manual watch route.",
    ],
  }
  readiness["next_actions"] = build_fulltext_next_actions(readiness)
  return readiness
