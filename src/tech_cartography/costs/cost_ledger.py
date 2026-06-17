"""Internal cost ledger — dry-run estimates and BigQuery job actuals (not shown to users)."""

from __future__ import annotations

import csv
import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from tech_cartography.costs.internal_cost_policy import CostVisibilityPolicy

DEFAULT_LEDGER_PATH = "outputs/cost_ledger/cost_ledger.jsonl"
BYTES_PER_TIB = 1024**4


def estimate_usd_from_bytes(bytes_value: int | float, usd_per_tib: float = 6.25) -> float:
  num_bytes = float(bytes_value or 0)
  if num_bytes <= 0:
    return 0.0
  return round((num_bytes / BYTES_PER_TIB) * float(usd_per_tib), 8)


@dataclass
class CostLedgerEntry:
  run_id: str = ""
  stage_id: str = ""
  policy_name: str = ""
  execution_type: str = ""
  publication_number: str = ""
  scope: str = ""
  query_job_id: str = ""
  estimated_bytes: int = 0
  estimated_gb: float = 0.0
  estimated_usd: float = 0.0
  actual_bytes_processed: int = 0
  actual_bytes_billed: int = 0
  actual_usd_estimate: float = 0.0
  cache_hit: bool = False
  retrieval_status: str = ""
  raw_cost_cap_usd: float = 0.0
  buffered_cost_cap_usd: float = 0.0
  remaining_raw_budget_usd: float = 0.0
  created_at: str = ""
  notes: str = ""


def _utc_now_iso() -> str:
  return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _bytes_to_gb(num_bytes: int | float) -> float:
  return round(float(num_bytes or 0) / (1024**3), 6)


def cost_ledger_entry_to_dict(entry: CostLedgerEntry) -> dict[str, Any]:
  return asdict(entry)


def build_cost_ledger_entry_from_estimate(
  *,
  run_id: str,
  stage_id: str,
  policy_name: str,
  execution_type: str,
  publication_number: str = "",
  scope: str = "",
  estimated_bytes: int = 0,
  retrieval_status: str = "dry_run_only",
  raw_cost_cap_usd: float = 0.0,
  buffered_cost_cap_usd: float = 0.0,
  remaining_raw_budget_usd: float = 0.0,
  notes: str = "",
) -> CostLedgerEntry:
  est_usd = estimate_usd_from_bytes(estimated_bytes)
  return CostLedgerEntry(
    run_id=run_id,
    stage_id=stage_id,
    policy_name=policy_name,
    execution_type=execution_type,
    publication_number=publication_number,
    scope=scope,
    estimated_bytes=int(estimated_bytes or 0),
    estimated_gb=_bytes_to_gb(estimated_bytes),
    estimated_usd=est_usd,
    retrieval_status=retrieval_status,
    raw_cost_cap_usd=raw_cost_cap_usd,
    buffered_cost_cap_usd=buffered_cost_cap_usd,
    remaining_raw_budget_usd=remaining_raw_budget_usd,
    created_at=_utc_now_iso(),
    notes=notes,
  )


def extract_bigquery_job_metrics(job: Any) -> dict[str, Any]:
  if job is None:
    return {
      "query_job_id": "",
      "actual_bytes_processed": 0,
      "actual_bytes_billed": 0,
      "cache_hit": False,
    }
  cache_hit = bool(getattr(job, "cache_hit", False))
  processed = int(getattr(job, "total_bytes_processed", 0) or 0)
  billed = getattr(job, "total_bytes_billed", None)
  if billed is None:
    billed = processed
  return {
    "query_job_id": str(getattr(job, "job_id", "") or ""),
    "actual_bytes_processed": processed,
    "actual_bytes_billed": int(billed or 0),
    "cache_hit": cache_hit,
  }


def build_cost_ledger_entry_from_bigquery_job(
  *,
  run_id: str,
  stage_id: str,
  policy_name: str,
  execution_type: str,
  publication_number: str,
  scope: str,
  job: Any,
  estimated_bytes: int = 0,
  retrieval_status: str = "retrieved",
  raw_cost_cap_usd: float = 0.0,
  buffered_cost_cap_usd: float = 0.0,
  remaining_raw_budget_usd: float = 0.0,
  notes: str = "",
) -> CostLedgerEntry:
  metrics = extract_bigquery_job_metrics(job)
  cache_hit = metrics["cache_hit"]
  billed = 0 if cache_hit else int(metrics["actual_bytes_billed"] or 0)
  actual_usd = 0.0 if cache_hit else estimate_usd_from_bytes(billed)
  if billed <= 0 and not cache_hit and estimated_bytes > 0:
    billed = int(estimated_bytes)
    actual_usd = estimate_usd_from_bytes(billed)
    notes = (notes + "; fallback_to_estimate").strip("; ")
  return CostLedgerEntry(
    run_id=run_id,
    stage_id=stage_id,
    policy_name=policy_name,
    execution_type=execution_type,
    publication_number=publication_number,
    scope=scope,
    query_job_id=metrics["query_job_id"],
    estimated_bytes=int(estimated_bytes or 0),
    estimated_gb=_bytes_to_gb(estimated_bytes),
    estimated_usd=estimate_usd_from_bytes(estimated_bytes),
    actual_bytes_processed=int(metrics["actual_bytes_processed"] or 0),
    actual_bytes_billed=billed,
    actual_usd_estimate=actual_usd,
    cache_hit=cache_hit,
    retrieval_status=retrieval_status,
    raw_cost_cap_usd=raw_cost_cap_usd,
    buffered_cost_cap_usd=buffered_cost_cap_usd,
    remaining_raw_budget_usd=remaining_raw_budget_usd,
    created_at=_utc_now_iso(),
    notes=notes,
  )


def append_cost_ledger_entry(entry: CostLedgerEntry | dict[str, Any], path: str | Path) -> None:
  ledger_path = Path(path)
  ledger_path.parent.mkdir(parents=True, exist_ok=True)
  row = entry if isinstance(entry, dict) else cost_ledger_entry_to_dict(entry)
  with ledger_path.open("a", encoding="utf-8") as handle:
    handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def load_cost_ledger(path: str | Path) -> list[dict[str, Any]]:
  ledger_path = Path(path)
  if not ledger_path.exists():
    return []
  rows: list[dict[str, Any]] = []
  for line in ledger_path.read_text(encoding="utf-8").splitlines():
    line = line.strip()
    if not line:
      continue
    try:
      data = json.loads(line)
      if isinstance(data, dict):
        rows.append(data)
    except json.JSONDecodeError:
      continue
  return rows


def summarize_cost_ledger(entries: list[dict[str, Any]]) -> dict[str, Any]:
  estimated_total_usd = 0.0
  actual_total_usd = 0.0
  by_status: dict[str, int] = {}
  for row in entries:
    estimated_total_usd += float(row.get("estimated_usd", 0) or 0)
    actual_total_usd += float(row.get("actual_usd_estimate", 0) or 0)
    status = str(row.get("retrieval_status") or "unknown")
    by_status[status] = by_status.get(status, 0) + 1
  return {
    "entry_count": len(entries),
    "estimated_total_usd": round(estimated_total_usd, 8),
    "actual_total_usd_estimate": round(actual_total_usd, 8),
    "retrieval_status_counts": by_status,
  }


def export_cost_ledger_csv(entries: list[dict[str, Any]], output_path: str | Path) -> str:
  out = Path(output_path)
  out.parent.mkdir(parents=True, exist_ok=True)
  if not entries:
    out.write_text("", encoding="utf-8")
    return str(out)
  fieldnames = list(entries[0].keys())
  for row in entries[1:]:
    for key in row:
      if key not in fieldnames:
        fieldnames.append(key)
  with out.open("w", encoding="utf-8", newline="") as handle:
    writer = csv.DictWriter(handle, fieldnames=fieldnames)
    writer.writeheader()
    writer.writerows(entries)
  return str(out)


_COST_KEYWORDS = ("usd", "price", "cost_cap", "budget", "margin", "ratio", "customer")


def _scrub_public_dict(data: dict[str, Any]) -> dict[str, Any]:
  clean: dict[str, Any] = {}
  for key, value in data.items():
    lower = key.lower()
    if any(token in lower for token in _COST_KEYWORDS):
      continue
    if isinstance(value, dict):
      clean[key] = _scrub_public_dict(value)
    elif isinstance(value, list):
      clean[key] = [
        _scrub_public_dict(item) if isinstance(item, dict) else item for item in value
      ]
    else:
      clean[key] = value
  return clean


def build_public_cost_status(
  summary: dict[str, Any],
  visibility: CostVisibilityPolicy,
  *,
  policy_summary: dict[str, Any] | None = None,
  stop_reason_internal: str | None = None,
) -> dict[str, Any]:
  if visibility.show_cost_to_user or visibility.show_estimated_usd_to_user:
    return _scrub_public_dict({**summary, "policy": policy_summary or {}})

  messages: list[str] = []
  if policy_summary:
    messages.append(f"取得方針: {policy_summary.get('user_facing_name_japanese', '')}")

  if stop_reason_internal:
    from tech_cartography.costs.adaptive_retrieval_controller import build_public_stop_reason

    messages.append(build_public_stop_reason(stop_reason_internal))
  elif summary.get("entry_count", 0) == 0:
    messages.append("今回はメタデータ監視のみを行いました。")
  else:
    messages.append("今回の取得方針内で実行しました。")

  if summary.get("retrieval_status_counts", {}).get("skipped_budget_guard"):
    messages.append("安全上限に近づいたため、追加の全文取得は行いませんでした。")

  public = {
    "execution_status_japanese": messages[0] if messages else "取得方針に沿って処理しました。",
    "status_messages": messages,
    "manual_watch_note": "中国候補は手動確認候補として残しました。",
  }
  if policy_summary:
    public.update(
      {
        "policy_name": policy_summary.get("policy_name"),
        "user_facing_name_japanese": policy_summary.get("user_facing_name_japanese"),
        "included_items": policy_summary.get("user_visible_included_items", []),
        "excluded_items": policy_summary.get("user_visible_excluded_items", []),
      },
    )
  return public
