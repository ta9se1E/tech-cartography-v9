from __future__ import annotations

from tech_cartography.validation.fulltext_readiness import (
  assess_fulltext_readiness,
  classify_fulltext_record_status,
)


def test_dry_run_only_record_is_not_ready() -> None:
  record = {
    "publication_number": "US-1",
    "country": "US",
    "retrieval_status": "dry_run_only",
    "claims": "A method comprising carbon fiber.",
    "description": "Detailed description.",
    "evidence_level": "high_fulltext_evidence",
  }
  assert classify_fulltext_record_status(record) == "dry_run_only"


def test_claims_and_description_is_ready() -> None:
  record = {
    "publication_number": "US-2",
    "country": "US",
    "retrieval_status": "retrieved",
    "claims": "A carbon fiber bundle.",
    "description": "The bundle includes filaments.",
    "evidence_level": "medium_fulltext_evidence",
  }
  assert classify_fulltext_record_status(record) == "ready_for_claim_extraction"


def test_claims_only_is_limited() -> None:
  record = {
    "publication_number": "US-3",
    "country": "US",
    "retrieval_status": "retrieved",
    "claims": "A carbon fiber.",
    "description": None,
    "evidence_level": "low_fulltext_evidence",
  }
  assert classify_fulltext_record_status(record) == "limited_claim_extraction"


def test_cn_manual_candidate_is_manual_required() -> None:
  manual = [
    {
      "publication_number": "CN-121137864-A",
      "country": "CN",
      "assignee": "ZHONGFU SHENYING",
      "source_route": "manual_fulltext_required",
    },
  ]
  readiness = assess_fulltext_readiness([], manual_candidates=manual)
  assert readiness["manual_required_count"] == 1
  assert readiness["manual_required_records"][0]["publication_number"] == "CN-121137864-A"


def test_readiness_counts_and_next_actions() -> None:
  records = [
    {
      "publication_number": "US-1",
      "country": "US",
      "retrieval_status": "dry_run_only",
      "evidence_level": "metadata_only",
    },
    {
      "publication_number": "US-2",
      "country": "US",
      "retrieval_status": "retrieved",
      "claims": "claim text",
      "description": "description text",
      "evidence_level": "high_fulltext_evidence",
    },
  ]
  readiness = assess_fulltext_readiness(records)
  assert readiness["ready_count"] == 1
  assert readiness["dry_run_only_count"] == 1
  action_ids = {row["action_id"] for row in readiness["next_actions"]}
  assert "execute_fulltext_for_us_targets" in action_ids
