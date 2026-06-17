"""Load manual fulltext input as FullTextRecord-compatible dicts."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tech_cartography.evidence.evidence_coverage import (
  detect_independent_claims,
  evaluate_evidence_coverage,
  extract_examples,
  extract_measured_properties,
)
from tech_cartography.manual.manual_fulltext_input_schema import (
  ManualFulltextInput,
  load_manual_fulltext_input,
  normalize_manual_claims_text,
  normalize_manual_description_text,
  validate_manual_fulltext_input,
)

BQ_FALLBACK_RETRIEVAL_STATUSES = frozenset(
  {
    "not_found",
    "manual_google_patents_recommended",
    "bigquery_fulltext_not_available",
    "skipped_known_not_found",
    "fulltext_probe_not_found",
    "manual_route_recommended",
    "publication_number_variant_mismatch",
    "dry_run_only",
  },
)


def build_manual_evidence_coverage(record: dict[str, Any]) -> dict[str, Any]:
  claims = str(record.get("claims") or "")
  description = str(record.get("description") or "")
  coverage = evaluate_evidence_coverage(record)
  if claims and not description:
    coverage = {
      **coverage,
      "description_support": "limited_no_description",
      "examples_support": "not_available",
      "has_description": False,
      "has_examples": False,
    }
  elif claims and description:
    coverage = {
      **coverage,
      "description_support": "manual_description",
      "examples_support": "available" if coverage.get("has_examples") else "limited",
    }
  return coverage


def convert_manual_input_to_fulltext_record(
  manual_input: ManualFulltextInput,
  base_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
  base = dict(base_metadata or {})
  claims = normalize_manual_claims_text(str(manual_input.claims_text or ""))
  description = normalize_manual_description_text(str(manual_input.description_text or ""))
  route = str(manual_input.input_route or "manual_user_paste")
  claims_source = route if claims else "not_fetched"
  description_source = route if description else "not_fetched"

  payload = {
    "publication_number": manual_input.publication_number,
    "title": base.get("title"),
    "assignee": base.get("assignee"),
    "country": base.get("country") or "US",
    "url": manual_input.source_url or base.get("url"),
    "abstract": base.get("abstract"),
    "claims": claims or None,
    "independent_claims": detect_independent_claims(claims) if claims else [],
    "description": description or None,
    "examples": extract_examples(description) if description else None,
    "measured_properties": extract_measured_properties("\n".join(filter(None, [claims, description]))),
    "claims_source": claims_source,
    "description_source": description_source,
    "fulltext_source": "manual_input",
    "source_route": "manual_fulltext_input",
    "input_route": route,
    "entered_by": manual_input.entered_by,
    "manual_input_scope": manual_input.input_scope,
    "manual_validation_status": manual_input.validation_status,
  }

  if claims and description:
    payload["retrieval_status"] = "manual_fulltext_loaded"
    payload["evidence_level"] = "medium_fulltext_evidence"
  elif claims:
    payload["retrieval_status"] = "manual_claims_loaded"
    payload["evidence_level"] = "low_fulltext_evidence"
  else:
    payload["retrieval_status"] = "manual_metadata_only"
    payload["evidence_level"] = "metadata_only"

  payload["claims_length"] = len(claims) if claims else 0
  payload["description_length"] = len(description) if description else 0
  payload["evidence_coverage"] = build_manual_evidence_coverage(payload)
  payload["manual_route"] = True
  return payload


def merge_manual_fulltext_with_metadata(manual_record: dict[str, Any], metadata_record: dict[str, Any]) -> dict[str, Any]:
  merged = {**metadata_record, **manual_record}
  for key in ("title", "assignee", "country", "url", "abstract"):
    if not merged.get(key) and metadata_record.get(key):
      merged[key] = metadata_record[key]
  if manual_record.get("claims"):
    merged["claims"] = manual_record["claims"]
    merged["claims_length"] = manual_record.get("claims_length", len(manual_record["claims"]))
  if manual_record.get("description"):
    merged["description"] = manual_record["description"]
    merged["description_length"] = manual_record.get("description_length", len(manual_record["description"]))
  merged["evidence_coverage"] = build_manual_evidence_coverage(merged)
  merged["manual_route"] = True
  return merged


def load_manual_fulltext_as_record(
  publication_number: str,
  input_dir: str | Path,
  *,
  base_metadata: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
  manual = load_manual_fulltext_input(publication_number, input_dir)
  if manual is None:
    return None
  validation = validate_manual_fulltext_input(manual)
  if validation["validation_status"] in {"empty_input", "invalid_publication_number", "missing_claims"}:
    return None
  manual.validation_status = validation["validation_status"]
  manual.input_scope = validation.get("input_scope", manual.input_scope)
  record = convert_manual_input_to_fulltext_record(manual, base_metadata)
  if base_metadata:
    record = merge_manual_fulltext_with_metadata(record, base_metadata)
  return record


def manual_input_exists(publication_number: str, input_dir: str | Path) -> bool:
  return load_manual_fulltext_input(publication_number, input_dir) is not None


def get_manual_fulltext_status(publication_number: str, input_dir: str | Path) -> dict[str, Any]:
  manual = load_manual_fulltext_input(publication_number, input_dir)
  if manual is None:
    return {
      "publication_number": publication_number,
      "manual_input_exists": False,
      "claims_present": False,
      "description_present": False,
      "validation_status": "not_found",
      "ready_for_claim_extraction": False,
      "route_label_japanese": "claims入力待ち",
    }
  validation = validate_manual_fulltext_input(manual)
  claims_ok = bool(validation.get("claims_present"))
  return {
    "publication_number": publication_number,
    "manual_input_exists": True,
    "claims_present": claims_ok,
    "description_present": bool(validation.get("description_present")),
    "validation_status": validation["validation_status"],
    "input_route": manual.input_route,
    "ready_for_claim_extraction": claims_ok,
    "route_label_japanese": "claims入力済み" if claims_ok else "claims入力待ち",
  }


def should_apply_manual_fallback(record: dict[str, Any]) -> bool:
  status = str(record.get("retrieval_status") or "").lower()
  if status in BQ_FALLBACK_RETRIEVAL_STATUSES:
    return True
  if status in {"retrieved", "cache_hit", "allowed_expensive_execute"}:
    claims = str(record.get("claims") or "").strip()
    return not claims
  return False


def apply_manual_fulltext_to_record(
  record: dict[str, Any],
  *,
  input_dir: str | Path,
  enable: bool = True,
) -> dict[str, Any]:
  if not enable:
    return record
  pub = str(record.get("publication_number") or "").strip()
  if not pub:
    return record
  manual_record = load_manual_fulltext_as_record(pub, input_dir, base_metadata=record)
  if manual_record is None:
    return record
  if not should_apply_manual_fallback(record) and str(record.get("retrieval_status")) not in {
    "manual_claims_loaded",
    "manual_fulltext_loaded",
  }:
    existing_claims = str(record.get("claims") or "").strip()
    if existing_claims:
      return record
  return merge_manual_fulltext_with_metadata(manual_record, record)


def apply_manual_fulltext_fallback(
  records: list[dict[str, Any]],
  *,
  input_dir: str | Path,
  enable: bool = True,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
  if not enable:
    return records, []
  updated: list[dict[str, Any]] = []
  applied: list[dict[str, Any]] = []
  for record in records:
    before_status = record.get("retrieval_status")
    merged = apply_manual_fulltext_to_record(record, input_dir=input_dir, enable=enable)
    updated.append(merged)
    if merged.get("retrieval_status") in {"manual_claims_loaded", "manual_fulltext_loaded"} and (
      before_status != merged.get("retrieval_status")
    ):
      applied.append(
        {
          "publication_number": merged.get("publication_number"),
          "previous_retrieval_status": before_status,
          "retrieval_status": merged.get("retrieval_status"),
          "claims_length": merged.get("claims_length", 0),
        },
      )
  return updated, applied
