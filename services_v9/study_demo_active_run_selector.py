"""Active search run selector logic for Study Demo (UI-agnostic)."""

from __future__ import annotations

from typing import Any, Mapping

REQUIRED_ACTIVATION_ARTIFACTS = (
  "search_request.json",
  "provider_status.json",
  "patent_results.json",
  "paper_results.json",
  "web_results.json",
  "integrated_signals.json",
  "usage_metrics.json",
  "search_status.json",
  "search_report.md",
)

SELECTOR_WIDGET_KEYS = (
  "study_demo_selected_history_run_id",
  "study_demo_confirm_activate_run",
  "study_demo_activate_run_button",
  "study_demo_reload_active_context_button",
)


def missing_activation_artifacts(artifacts: Mapping[str, Any]) -> list[str]:
  missing: list[str] = []
  for name in REQUIRED_ACTIVATION_ARTIFACTS:
    if name not in artifacts or artifacts.get(name) in (None, "", {}):
      missing.append(name)
  return missing


def summarize_run_for_selector(
  *,
  search_run_id: str,
  artifacts: Mapping[str, Any],
  integrated: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
  request = dict(artifacts.get("search_request.json", {}) or {})
  integrated_payload = dict(integrated or artifacts.get("integrated_signals.json", {}) or {})
  summary = dict(integrated_payload.get("relevance_summary", {}) or {})
  provider_status = dict(artifacts.get("provider_status.json", {}) or {})

  patent_count = int(integrated_payload.get("patent_count", 0) or 0)
  paper_count = int(integrated_payload.get("paper_count", 0) or 0)
  web_count = int(integrated_payload.get("web_count", 0) or 0)
  if not any((patent_count, paper_count, web_count)):
    signals = list(integrated_payload.get("signals", []) or [])
    patent_count = sum(1 for item in signals if str(item.get("source_type", "")) == "patent")
    paper_count = sum(1 for item in signals if str(item.get("source_type", "")) == "paper")
    web_count = sum(1 for item in signals if str(item.get("source_type", "")) in {"web", "web_company"})

  tier_a = int(summary.get("tier_a", 0) or 0)
  tier_b = int(summary.get("tier_b", 0) or 0)
  tier_c = int(summary.get("tier_c", 0) or 0)
  tier_d = int(summary.get("tier_d", 0) or 0)
  if not any((tier_a, tier_b, tier_c, tier_d)):
    for signal in integrated_payload.get("signals", []) or []:
      tier = str(dict(signal).get("relevance_tier", "") or "").upper()
      if tier == "A":
        tier_a += 1
      elif tier == "B":
        tier_b += 1
      elif tier == "C":
        tier_c += 1
      elif tier == "D":
        tier_d += 1

  return {
    "search_run_id": search_run_id,
    "theme": str(request.get("theme", "") or ""),
    "provider_status": {
      name: str(dict(item).get("status", "") or "")
      for name, item in provider_status.items()
      if isinstance(item, dict)
    },
    "provider_counts": {"patent": patent_count, "paper": paper_count, "web": web_count},
    "tier_counts": {"A": tier_a, "B": tier_b, "C": tier_c, "D": tier_d},
    "ranked_count": int(integrated_payload.get("ranked_count", len(integrated_payload.get("signals", []) or [])) or 0),
  }


def should_show_active_run_selector(
  *,
  authenticated: bool,
  history_run_ids: list[str],
  selected_run_id: str,
) -> bool:
  if not authenticated:
    return False
  if not history_run_ids:
    return False
  return bool(str(selected_run_id or "").strip())


def resolve_activation_state(
  *,
  selected_run_id: str,
  active_run_id: str,
  confirm_checked: bool,
  activate_clicked: bool,
  reload_clicked: bool,
  artifacts: Mapping[str, Any],
) -> dict[str, Any]:
  selected = str(selected_run_id or "").strip()
  active = str(active_run_id or "").strip()

  if reload_clicked:
    return {"action": "reload", "selected_run_id": selected}

  if not activate_clicked:
    return {"action": "none", "selected_run_id": selected}

  if active and active == selected:
    return {
      "action": "idempotent",
      "message": f"分析対象は既に設定済みです: {selected}",
      "selected_run_id": selected,
    }

  if active and active != selected and not confirm_checked:
    return {
      "action": "error",
      "error_code": "confirm_required_switch",
      "message": "別runへ切り替えるには確認チェックが必要です。",
      "active_run_id": active,
      "selected_run_id": selected,
    }

  if not active and not confirm_checked:
    return {
      "action": "error",
      "error_code": "confirm_required",
      "message": "確認チェックが必要です。",
      "selected_run_id": selected,
    }

  missing = missing_activation_artifacts(artifacts)
  if missing:
    return {
      "action": "error",
      "error_code": "missing_artifacts",
      "message": f"このrunは分析対象に設定できません。不足artifact: {', '.join(missing)}",
      "missing_artifacts": missing,
    }

  return {"action": "save", "selected_run_id": selected, "previous_active_run_id": active or None}


def format_save_result_message(*, status: str, search_run_id: str) -> str:
  if status == "conflict":
    return "別の参加者が分析対象を更新しました。現在の分析対象を再読み込みしてください。"
  if status in {"saved", "unchanged"}:
    return f"分析対象を設定しました: {search_run_id}"
  return "分析対象の保存に失敗しました。外部検索は実行されていません。"
