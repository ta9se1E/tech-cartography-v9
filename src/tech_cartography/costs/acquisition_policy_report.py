"""User-facing acquisition policy summary (no monetary amounts)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_acquisition_policy_summary(
  policy_summary: dict[str, Any],
  adaptive_plan: dict[str, Any] | None = None,
  public_cost_status: dict[str, Any] | None = None,
) -> dict[str, Any]:
  plan = adaptive_plan or {}
  status = public_cost_status or {}
  stop_reason = plan.get("public_stop_reason") or status.get("execution_status_japanese", "")
  return {
    "policy_name": policy_summary.get("policy_name"),
    "user_facing_name_japanese": policy_summary.get("user_facing_name_japanese"),
    "user_facing_description_japanese": policy_summary.get("user_facing_description_japanese"),
    "included_items": policy_summary.get("user_visible_included_items", []),
    "excluded_items": policy_summary.get("user_visible_excluded_items", []),
    "fulltext_enabled": policy_summary.get("fulltext_enabled", False),
    "acquisition_scope_japanese": policy_summary.get("acquisition_scope_japanese", ""),
    "selected_targets_count": plan.get("selected_count", 0),
    "skipped_reason_japanese": stop_reason,
    "manual_watch_count": plan.get("manual_watch_count", 0),
    "execution_status_japanese": status.get("execution_status_japanese", stop_reason or "取得方針に沿って処理しました。"),
    "status_messages": status.get("status_messages", []),
  }


def render_acquisition_policy_markdown(summary: dict[str, Any]) -> str:
  lines = [
    "# 今回の取得方針",
    "",
    "## 実行タイプ",
    "",
    summary.get("user_facing_name_japanese", ""),
    "",
    summary.get("user_facing_description_japanese", ""),
    "",
    "## 取得する情報",
    "",
  ]
  for item in summary.get("included_items", []):
    lines.append(f"- {item}")
  if not summary.get("included_items"):
    lines.append("- 特許候補の定点観測")

  lines.extend(["", "## 今回取得しない情報", ""])
  for item in summary.get("excluded_items", []):
    lines.append(f"- {item}")

  lines.extend(
    [
      "",
      "## 停止理由",
      "",
      summary.get("skipped_reason_japanese") or "今回の取得方針に沿って処理しました。",
      "",
      f"- 手動確認候補（中国等）: {summary.get('manual_watch_count', 0)} 件",
      f"- 全文取得対象: {summary.get('selected_targets_count', 0)} 件",
      "",
      "※ 金額・原価・課金情報は表示していません。取得範囲のみをお知らせします。",
    ],
  )
  return "\n".join(lines)


def save_acquisition_policy_summary(summary: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  json_path = out / "acquisition_policy_summary.json"
  md_path = out / "acquisition_policy_summary.md"
  json_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
  md_path.write_text(render_acquisition_policy_markdown(summary), encoding="utf-8")
  return {
    "acquisition_policy_summary_json": str(json_path),
    "acquisition_policy_summary_md": str(md_path),
  }
