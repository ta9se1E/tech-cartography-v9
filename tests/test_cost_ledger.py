"""Tests for cost ledger (Phase 16.2)."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.costs.cost_ledger import (
  build_cost_ledger_entry_from_bigquery_job,
  build_cost_ledger_entry_from_estimate,
  build_public_cost_status,
  estimate_usd_from_bytes,
  export_cost_ledger_csv,
  load_cost_ledger,
  summarize_cost_ledger,
)
from tech_cartography.costs.internal_cost_policy import CostVisibilityPolicy


class _MockJob:
  def __init__(
    self,
    *,
    job_id: str = "job-1",
    processed: int = 1024**3,
    billed: int = 1024**3,
    cache_hit: bool = False,
  ) -> None:
    self.job_id = job_id
    self.total_bytes_processed = processed
    self.total_bytes_billed = billed
    self.cache_hit = cache_hit


def test_estimate_usd_from_bytes() -> None:
  usd = estimate_usd_from_bytes(1024**4, usd_per_tib=6.25)
  assert round(usd, 4) == 6.25


def test_build_estimate_entry() -> None:
  entry = build_cost_ledger_entry_from_estimate(
    run_id="r1",
    stage_id="s1",
    policy_name="watch_run",
    execution_type="標準監視",
    estimated_bytes=1024**3,
    retrieval_status="dry_run_only",
    raw_cost_cap_usd=1.5,
  )
  assert entry.estimated_gb > 0
  assert entry.estimated_usd > 0


def test_build_actual_entry_from_mock_job() -> None:
  entry = build_cost_ledger_entry_from_bigquery_job(
    run_id="r1",
    stage_id="s1",
    policy_name="claims_check",
    execution_type="請求項チェック",
    publication_number="US-12565719-B2",
    scope="claims_only",
    job=_MockJob(),
    estimated_bytes=1024**3,
    retrieval_status="actual_cost_recorded",
    raw_cost_cap_usd=2.5,
  )
  assert entry.query_job_id == "job-1"
  assert entry.actual_usd_estimate > 0


def test_cache_hit_actual_cost_zero() -> None:
  entry = build_cost_ledger_entry_from_bigquery_job(
    run_id="r1",
    stage_id="s1",
    policy_name="claims_check",
    execution_type="請求項チェック",
    publication_number="US-1",
    scope="claims_only",
    job=_MockJob(cache_hit=True, billed=1024**4),
    retrieval_status="cache_hit",
    raw_cost_cap_usd=2.5,
  )
  assert entry.cache_hit is True
  assert entry.actual_usd_estimate == 0.0


def test_jsonl_append_and_load(tmp_path: Path) -> None:
  from tech_cartography.costs.cost_ledger import append_cost_ledger_entry, cost_ledger_entry_to_dict

  path = tmp_path / "ledger.jsonl"
  entry = build_cost_ledger_entry_from_estimate(
    run_id="r1",
    stage_id="s1",
    policy_name="watch_run",
    execution_type="標準監視",
    estimated_bytes=1000,
  )
  append_cost_ledger_entry(entry, path)
  rows = load_cost_ledger(path)
  assert len(rows) == 1
  assert rows[0]["policy_name"] == "watch_run"


def test_csv_export(tmp_path: Path) -> None:
  rows = [
    {"run_id": "r1", "estimated_usd": 0.1, "retrieval_status": "dry_run_only"},
    {"run_id": "r1", "actual_usd_estimate": 0.05, "retrieval_status": "actual_cost_recorded"},
  ]
  out = export_cost_ledger_csv(rows, tmp_path / "ledger.csv")
  text = Path(out).read_text(encoding="utf-8")
  assert "estimated_usd" in text
  assert "actual_usd_estimate" in text


def test_summary_actual_total() -> None:
  rows = [
    {"actual_usd_estimate": 0.1},
    {"actual_usd_estimate": 0.2},
  ]
  summary = summarize_cost_ledger(rows)
  assert summary["actual_total_usd_estimate"] == 0.3


def test_public_cost_status_has_no_amounts() -> None:
  summary = summarize_cost_ledger([{"actual_usd_estimate": 1.5, "estimated_usd": 2.0}])
  public = build_public_cost_status(
    summary,
    CostVisibilityPolicy(),
    policy_summary={"user_facing_name_japanese": "標準監視モード"},
  )
  blob = json.dumps(public, ensure_ascii=False).lower()
  assert "usd" not in blob
  assert "1.5" not in blob
  assert public["execution_status_japanese"]
