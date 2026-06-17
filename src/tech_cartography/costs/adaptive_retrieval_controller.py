"""Adaptive retrieval controller — internal budget only, no user-facing amounts."""

from __future__ import annotations

from typing import Any

from tech_cartography.costs.internal_cost_policy import InternalCostPolicy, public_policy_summary
from tech_cartography.retrieval.bigquery_fulltext_query_builder import is_us_publication

PUBLIC_STOP_REASONS: dict[str, str] = {
  "budget_exceeded": "安全上限に近づいたため、追加の全文取得は行いませんでした。",
  "policy_no_fulltext": "今回は標準監視モードのため、全文取得は行いませんでした。",
  "policy_scope_blocked": "この実行タイプの取得範囲を超えるため、追加取得は行いませんでした。",
  "next_estimate_exceeds_cap": "この実行タイプの取得範囲を超えるため、追加取得は行いませんでした。",
  "non_us_manual_route": "中国・欧州・日本の候補は手動確認候補として残しました。",
  "max_targets_reached": "今回の取得方針で許可された件数に達したため、追加取得は行いませんでした。",
}


def build_public_stop_reason(internal_stop_reason: str) -> str:
  if not internal_stop_reason:
    return "今回の取得方針に沿って処理しました。"
  return PUBLIC_STOP_REASONS.get(internal_stop_reason, internal_stop_reason)


def _ledger_actual_total(ledger_entries: list[dict[str, Any]]) -> float:
  total = 0.0
  for row in ledger_entries:
    total += float(row.get("actual_usd_estimate", 0) or 0)
  return round(total, 8)


def update_remaining_budget(policy: InternalCostPolicy, ledger_entries: list[dict[str, Any]]) -> dict[str, Any]:
  spent = _ledger_actual_total(ledger_entries)
  remaining = round(max(0.0, float(policy.raw_cost_cap_usd) - spent), 8)
  return {
    "raw_cost_cap_usd": policy.raw_cost_cap_usd,
    "buffered_cost_cap_usd": policy.buffered_cost_cap_usd,
    "actual_spent_usd_estimate": spent,
    "remaining_raw_budget_usd": remaining,
    "budget_exhausted": remaining <= 0,
  }


def stop_reason_if_budget_exceeded(
  policy: InternalCostPolicy,
  ledger_summary: dict[str, Any],
  next_estimate: dict[str, Any] | None = None,
) -> str | None:
  remaining = float(ledger_summary.get("remaining_raw_budget_usd", policy.raw_cost_cap_usd))
  if remaining <= 0:
    return "budget_exceeded"
  if next_estimate and not next_estimate.get("cache_hit"):
    est = float(next_estimate.get("estimated_usd", 0) or 0)
    if est > remaining:
      return "next_estimate_exceeds_cap"
  return None


def should_execute_candidate(
  candidate: dict[str, Any],
  policy: InternalCostPolicy,
  ledger_summary: dict[str, Any],
  estimate: dict[str, Any],
) -> dict[str, Any]:
  pub = str(candidate.get("publication_number") or "")
  country = str(candidate.get("country") or "")
  if not is_us_publication(pub, country):
    return {
      "allowed": False,
      "reason": "non_us_manual_route",
      "public_reason": build_public_stop_reason("non_us_manual_route"),
      "retrieval_status": "skipped_policy_scope",
    }

  if not policy.fulltext_enabled:
    return {
      "allowed": False,
      "reason": "policy_no_fulltext",
      "public_reason": build_public_stop_reason("policy_no_fulltext"),
      "retrieval_status": "skipped_internal_cost_policy",
    }

  scope = str(estimate.get("fulltext_scope") or policy.default_scope)
  if scope not in policy.allowed_scopes and scope != "metadata_only":
    return {
      "allowed": False,
      "reason": "policy_scope_blocked",
      "public_reason": build_public_stop_reason("policy_scope_blocked"),
      "retrieval_status": "skipped_policy_scope",
    }

  if estimate.get("cache_hit"):
    return {"allowed": True, "reason": "cache_hit", "public_reason": "", "retrieval_status": "cache_hit"}

  stop = stop_reason_if_budget_exceeded(policy, ledger_summary, estimate)
  if stop:
    return {
      "allowed": False,
      "reason": stop,
      "public_reason": build_public_stop_reason(stop),
      "retrieval_status": "skipped_budget_guard",
    }

  return {"allowed": True, "reason": "within_budget", "public_reason": "", "retrieval_status": ""}


def select_next_candidate_under_budget(
  candidates: list[dict[str, Any]],
  policy: InternalCostPolicy,
  ledger_entries: list[dict[str, Any]],
  *,
  estimates_by_pub: dict[str, dict[str, Any]] | None = None,
  executed_count: int = 0,
) -> dict[str, Any] | None:
  if not policy.fulltext_enabled:
    return None
  if executed_count >= int(policy.max_fulltext_targets or 0):
    return None

  budget = update_remaining_budget(policy, ledger_entries)
  estimates_by_pub = estimates_by_pub or {}

  for candidate in candidates:
    pub = str(candidate.get("publication_number") or "").strip()
    norm = pub.upper().replace("-", "").replace(" ", "")
    estimate = estimates_by_pub.get(norm) or estimates_by_pub.get(pub) or {"estimated_usd": 0}
    decision = should_execute_candidate(candidate, policy, budget, estimate)
    if decision.get("allowed"):
      return candidate
  return None


def build_adaptive_retrieval_plan(
  candidates: list[dict[str, Any]],
  policy: InternalCostPolicy,
  estimates: dict[str, dict[str, Any]] | None = None,
) -> dict[str, Any]:
  estimates = estimates or {}
  us_candidates = [
    row for row in candidates
    if is_us_publication(str(row.get("publication_number", "")), str(row.get("country", "")))
  ]
  manual_candidates = [
    row for row in candidates
    if not is_us_publication(str(row.get("publication_number", "")), str(row.get("country", "")))
  ]

  selected: list[dict[str, Any]] = []
  skipped: list[dict[str, Any]] = []
  budget = update_remaining_budget(policy, [])

  if policy.fulltext_enabled:
    limit = int(policy.max_fulltext_targets or 0)
    for row in us_candidates[: max(limit, 0)]:
      pub = str(row.get("publication_number", ""))
      norm = pub.upper().replace("-", "").replace(" ", "")
      estimate = estimates.get(norm) or estimates.get(pub) or {}
      decision = should_execute_candidate(row, policy, budget, estimate)
      enriched = {**row, "adaptive_decision": decision}
      if decision.get("allowed") and len(selected) < limit:
        selected.append(enriched)
      else:
        skipped.append(enriched)
    for row in us_candidates[len(selected) + len(skipped):]:
      skipped.append(
        {
          **row,
          "adaptive_decision": {
            "allowed": False,
            "reason": "max_targets_reached",
            "retrieval_status": "skipped_policy_scope",
          },
        },
      )
  else:
    for row in us_candidates:
      skipped.append(
        {
          **row,
          "adaptive_decision": {
            "allowed": False,
            "reason": "policy_no_fulltext",
            "retrieval_status": "skipped_internal_cost_policy",
          },
        },
      )

  public_summary = public_policy_summary(policy)
  stop_reason = None
  if not policy.fulltext_enabled:
    stop_reason = "policy_no_fulltext"
  elif skipped and not selected:
    stop_reason = str(skipped[0].get("adaptive_decision", {}).get("reason", "policy_scope_blocked"))

  return {
    "policy_name": policy.policy_name,
    "public_policy_summary": public_summary,
    "fulltext_enabled": policy.fulltext_enabled,
    "max_fulltext_targets": policy.max_fulltext_targets,
    "default_scope": policy.default_scope,
    "allowed_scopes": policy.allowed_scopes,
    "selected_candidates": selected,
    "skipped_candidates": skipped,
    "manual_route_candidates": manual_candidates,
    "selected_count": len(selected),
    "skipped_count": len(skipped),
    "manual_watch_count": len(manual_candidates),
    "internal_stop_reason": stop_reason,
    "public_stop_reason": build_public_stop_reason(stop_reason or ""),
    "remaining_budget_internal": budget,
  }
