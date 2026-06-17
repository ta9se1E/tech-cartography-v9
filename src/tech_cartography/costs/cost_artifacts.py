"""Save internal and public cost artifacts for a pipeline run."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tech_cartography.costs.acquisition_policy_report import (
  build_acquisition_policy_summary,
  save_acquisition_policy_summary,
)
from tech_cartography.costs.cost_ledger import export_cost_ledger_csv, summarize_cost_ledger
from tech_cartography.costs.internal_cost_policy import (
  InternalCostPolicy,
  internal_cost_policy_to_dict,
  public_policy_summary,
)
from tech_cartography.costs.weekly_digest_preview import build_weekly_digest_preview, save_weekly_digest_preview


def save_cost_run_artifacts(
  output_dir: str | Path,
  *,
  policy: InternalCostPolicy,
  adaptive_plan: dict[str, Any],
  ledger_entries: list[dict[str, Any]],
  public_cost_status: dict[str, Any],
  digest_artifacts: dict[str, Any] | None = None,
) -> dict[str, str]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  paths: dict[str, str] = {}

  policy_used = {
    "policy_name": policy.policy_name,
    "internal": internal_cost_policy_to_dict(policy),
    "public": public_policy_summary(policy),
  }
  policy_path = out / "internal_cost_policy_used.json"
  policy_path.write_text(json.dumps(policy_used, indent=2, ensure_ascii=False), encoding="utf-8")
  paths["internal_cost_policy_used_json"] = str(policy_path)

  plan_path = out / "adaptive_retrieval_plan_internal.json"
  plan_path.write_text(json.dumps(adaptive_plan, indent=2, ensure_ascii=False), encoding="utf-8")
  paths["adaptive_retrieval_plan_internal_json"] = str(plan_path)

  ledger_json = out / "cost_ledger.json"
  ledger_json.write_text(json.dumps(ledger_entries, indent=2, ensure_ascii=False), encoding="utf-8")
  paths["cost_ledger_json"] = str(ledger_json)
  paths["cost_ledger_csv"] = export_cost_ledger_csv(ledger_entries, out / "cost_ledger.csv")

  internal_summary = {
    "policy_name": policy.policy_name,
    "ledger_summary": summarize_cost_ledger(ledger_entries),
    "adaptive_plan_counts": {
      "selected": adaptive_plan.get("selected_count", 0),
      "skipped": adaptive_plan.get("skipped_count", 0),
      "manual_watch": adaptive_plan.get("manual_watch_count", 0),
    },
    "remaining_budget_internal": adaptive_plan.get("remaining_budget_internal", {}),
  }
  summary_path = out / "internal_cost_summary.json"
  summary_path.write_text(json.dumps(internal_summary, indent=2, ensure_ascii=False), encoding="utf-8")
  paths["internal_cost_summary_json"] = str(summary_path)

  acquisition = build_acquisition_policy_summary(
    public_policy_summary(policy),
    adaptive_plan,
    public_cost_status,
  )
  paths.update(save_acquisition_policy_summary(acquisition, out))

  if digest_artifacts is not None:
    preview = build_weekly_digest_preview(digest_artifacts, acquisition)
    paths.update(save_weekly_digest_preview(preview, out))

  return paths
