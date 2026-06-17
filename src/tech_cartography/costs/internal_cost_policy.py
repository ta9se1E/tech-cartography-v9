"""Internal cost policy loader — amounts are never exposed to end users."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

import yaml

DEFAULT_POLICY_PATH = "configs/internal_cost_policy.yaml"

SCOPE_LABELS_JA: dict[str, str] = {
  "metadata_only": "書誌・要約メタデータ",
  "claims_only": "請求項",
  "description_only": "明細書",
  "claims_and_description": "請求項と明細書",
}


@dataclass
class InternalCostPolicy:
  policy_name: str
  internal_display_name: str = ""
  user_facing_name_japanese: str = ""
  user_facing_description_japanese: str = ""
  raw_cost_cap_usd: float = 1.5
  safety_margin: float = 1.3
  buffered_cost_cap_usd: float = 1.95
  target_cost_ratio: float = 0.5
  default_scope: str = "metadata_only"
  allowed_scopes: list[str] = field(default_factory=lambda: ["metadata_only"])
  max_fulltext_targets: int = 0
  max_description_targets: int = 0
  fulltext_enabled: bool = False
  non_us_handling: str = "strategic_watch_manual"
  expose_cost_to_user: bool = False
  flags: dict[str, bool] = field(default_factory=dict)


@dataclass
class GlobalHardStop:
  max_raw_cost_usd_per_run: float = 40.0
  max_buffered_cost_usd_per_run: float = 52.0
  behavior: str = "block"


@dataclass
class CostVisibilityPolicy:
  show_cost_to_user: bool = False
  show_price_to_user: bool = False
  show_internal_budget_to_user: bool = False
  show_estimated_usd_to_user: bool = False
  show_actual_usd_to_user: bool = False
  show_acquisition_policy_name: bool = True
  show_acquisition_scope: bool = True
  show_stop_reason_without_cost: bool = True


@dataclass
class InternalCostPolicySet:
  policies: dict[str, InternalCostPolicy]
  default_policy: str
  default_deep_dive_policy: str
  demo_policy: str
  global_hard_stop: GlobalHardStop
  ui_visibility: CostVisibilityPolicy
  source_path: str = DEFAULT_POLICY_PATH


_FLAG_KEYS = (
  "include_metadata_retrieval",
  "include_ranking",
  "include_strategic_watch_alerts",
  "include_weekly_digest_preview",
  "include_claim_element_extraction",
  "include_metadata_based_paper_query_plan",
  "include_examples_extraction",
  "include_measured_properties_extraction",
  "include_evidence_validation_report",
  "include_paper_query_candidates",
  "include_technical_view_report",
  "include_evidence_map",
  "include_synthesis_report",
)


def compute_buffered_cost(raw_cost: float, safety_margin: float = 1.3) -> float:
  return round(float(raw_cost) * float(safety_margin), 4)


def _policy_from_dict(name: str, data: dict[str, Any]) -> InternalCostPolicy:
  raw = float(data.get("raw_cost_cap_usd", 1.5))
  margin = float(data.get("safety_margin", 1.3))
  buffered = data.get("buffered_cost_cap_usd")
  if buffered is None:
    buffered = compute_buffered_cost(raw, margin)
  flags = {key: bool(data.get(key, False)) for key in _FLAG_KEYS}
  return InternalCostPolicy(
    policy_name=name,
    internal_display_name=str(data.get("internal_display_name", name)),
    user_facing_name_japanese=str(data.get("user_facing_name_japanese", name)),
    user_facing_description_japanese=str(data.get("user_facing_description_japanese", "")),
    raw_cost_cap_usd=raw,
    safety_margin=margin,
    buffered_cost_cap_usd=float(buffered),
    target_cost_ratio=float(data.get("target_cost_ratio", 0.5)),
    default_scope=str(data.get("default_scope", "metadata_only")),
    allowed_scopes=list(data.get("allowed_scopes") or ["metadata_only"]),
    max_fulltext_targets=int(data.get("max_fulltext_targets", 0)),
    max_description_targets=int(data.get("max_description_targets", 0)),
    fulltext_enabled=bool(data.get("fulltext_enabled", False)),
    non_us_handling=str(data.get("non_us_handling", "strategic_watch_manual")),
    expose_cost_to_user=bool(data.get("expose_cost_to_user", False)),
    flags=flags,
  )


def load_internal_cost_policy(path: str | Path = DEFAULT_POLICY_PATH) -> InternalCostPolicySet:
  policy_path = Path(path)
  if not policy_path.exists():
    return _fallback_policy_set(str(policy_path))
  data = yaml.safe_load(policy_path.read_text(encoding="utf-8")) or {}
  raw_policies = data.get("cost_policies") or {}
  policies = {name: _policy_from_dict(name, row) for name, row in raw_policies.items() if isinstance(row, dict)}
  hard = data.get("global_hard_stop") or {}
  vis = data.get("ui_visibility") or {}
  return InternalCostPolicySet(
    policies=policies,
    default_policy=str(data.get("default_policy", "watch_run")),
    default_deep_dive_policy=str(data.get("default_deep_dive_policy", "claims_check")),
    demo_policy=str(data.get("demo_policy", "full_deep_dive")),
    global_hard_stop=GlobalHardStop(
      max_raw_cost_usd_per_run=float(hard.get("max_raw_cost_usd_per_run", 40.0)),
      max_buffered_cost_usd_per_run=float(hard.get("max_buffered_cost_usd_per_run", 52.0)),
      behavior=str(hard.get("behavior", "block")),
    ),
    ui_visibility=CostVisibilityPolicy(
      show_cost_to_user=bool(vis.get("show_cost_to_user", False)),
      show_price_to_user=bool(vis.get("show_price_to_user", False)),
      show_internal_budget_to_user=bool(vis.get("show_internal_budget_to_user", False)),
      show_estimated_usd_to_user=bool(vis.get("show_estimated_usd_to_user", False)),
      show_actual_usd_to_user=bool(vis.get("show_actual_usd_to_user", False)),
      show_acquisition_policy_name=bool(vis.get("show_acquisition_policy_name", True)),
      show_acquisition_scope=bool(vis.get("show_acquisition_scope", True)),
      show_stop_reason_without_cost=bool(vis.get("show_stop_reason_without_cost", True)),
    ),
    source_path=str(policy_path),
  )


def _fallback_policy_set(path: str) -> InternalCostPolicySet:
  watch = InternalCostPolicy(
    policy_name="watch_run",
    user_facing_name_japanese="標準監視モード",
    user_facing_description_japanese="技術テーマの新着特許を広く監視します。",
    raw_cost_cap_usd=1.5,
    buffered_cost_cap_usd=1.95,
    default_scope="metadata_only",
    allowed_scopes=["metadata_only"],
    fulltext_enabled=False,
    flags={"include_weekly_digest_preview": True},
  )
  return InternalCostPolicySet(
    policies={"watch_run": watch},
    default_policy="watch_run",
    default_deep_dive_policy="claims_check",
    demo_policy="full_deep_dive",
    global_hard_stop=GlobalHardStop(),
    ui_visibility=CostVisibilityPolicy(),
    source_path=path,
  )


_POLICY_CACHE: InternalCostPolicySet | None = None


def get_internal_cost_policy_set(path: str | Path = DEFAULT_POLICY_PATH) -> InternalCostPolicySet:
  global _POLICY_CACHE
  if _POLICY_CACHE is None or str(_POLICY_CACHE.source_path) != str(path):
    _POLICY_CACHE = load_internal_cost_policy(path)
  return _POLICY_CACHE


def get_internal_cost_policy(
  policy_name: str | None = None,
  *,
  path: str | Path = DEFAULT_POLICY_PATH,
) -> InternalCostPolicy:
  policy_set = get_internal_cost_policy_set(path)
  name = policy_name or policy_set.default_policy
  if name not in policy_set.policies:
    name = policy_set.default_policy
  return policy_set.policies[name]


def get_default_internal_cost_policy(path: str | Path = DEFAULT_POLICY_PATH) -> InternalCostPolicy:
  return get_internal_cost_policy(None, path=path)


def validate_internal_cost_policy(
  policy: InternalCostPolicy,
  hard_stop: GlobalHardStop | None = None,
) -> list[str]:
  errors: list[str] = []
  if policy.raw_cost_cap_usd <= 0:
    errors.append(f"{policy.policy_name}: raw_cost_cap_usd must be positive")
  if hard_stop and policy.raw_cost_cap_usd > hard_stop.max_raw_cost_usd_per_run:
    errors.append(
      f"{policy.policy_name}: raw_cost_cap_usd exceeds global hard stop "
      f"({hard_stop.max_raw_cost_usd_per_run})",
    )
  if hard_stop and policy.buffered_cost_cap_usd > hard_stop.max_buffered_cost_usd_per_run:
    errors.append(
      f"{policy.policy_name}: buffered_cost_cap_usd exceeds global buffered hard stop",
    )
  if policy.default_scope not in policy.allowed_scopes and policy.default_scope != "metadata_only":
    errors.append(f"{policy.policy_name}: default_scope not in allowed_scopes")
  return errors


def internal_cost_policy_to_dict(policy: InternalCostPolicy) -> dict[str, Any]:
  return asdict(policy)


def _included_items(policy: InternalCostPolicy) -> list[str]:
  items = []
  if policy.flags.get("include_metadata_retrieval") or policy.default_scope == "metadata_only":
    items.append("特許候補の更新・ランキング")
  if policy.flags.get("include_ranking"):
    items.append("重要候補ランキング")
  if policy.flags.get("include_strategic_watch_alerts"):
    items.append("中国Strategic Watch")
  if policy.flags.get("include_weekly_digest_preview"):
    items.append("Weekly Digest Preview")
  if policy.fulltext_enabled and "claims_only" in policy.allowed_scopes:
    items.append("US候補の請求項確認")
  if policy.fulltext_enabled and "description_only" in policy.allowed_scopes:
    items.append("US候補の明細書確認")
  if policy.flags.get("include_claim_element_extraction"):
    items.append("Claim Element分解")
  if policy.flags.get("include_evidence_validation_report"):
    items.append("Evidence Validationレポート")
  if policy.flags.get("include_evidence_map"):
    items.append("Evidence Map")
  if policy.flags.get("include_synthesis_report"):
    items.append("統合レポート")
  return items or ["特許候補の定点観測"]


def _excluded_items(policy: InternalCostPolicy) -> list[str]:
  items = []
  if not policy.fulltext_enabled:
    items.append("BigQuery全文取得（今回の取得方針では対象外）")
  if "claims_and_description" not in policy.allowed_scopes:
    items.append("請求項と明細書の同時全文取得")
  if "description_only" not in policy.allowed_scopes and policy.default_scope != "description_only":
    items.append("明細書のみの全文取得")
  items.append("PDF/OCR自動取得")
  items.append("中国・欧州・日本の自動全文取得（手動確認候補として残します）")
  return items


def public_policy_summary(policy: InternalCostPolicy) -> dict[str, Any]:
  scopes_ja = [SCOPE_LABELS_JA.get(s, s) for s in policy.allowed_scopes]
  return {
    "policy_name": policy.policy_name,
    "user_facing_name_japanese": policy.user_facing_name_japanese,
    "user_facing_description_japanese": policy.user_facing_description_japanese,
    "acquisition_scope_japanese": "、".join(scopes_ja),
    "fulltext_enabled": policy.fulltext_enabled,
    "non_us_handling": policy.non_us_handling,
    "user_visible_included_items": _included_items(policy),
    "user_visible_excluded_items": _excluded_items(policy),
  }
