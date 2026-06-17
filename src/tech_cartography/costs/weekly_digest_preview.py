"""Weekly digest preview — no email sending, no monetary amounts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def build_weekly_digest_preview(
  artifacts: dict[str, Any],
  acquisition_policy_summary: dict[str, Any],
) -> dict[str, Any]:
  top20 = artifacts.get("top20_patents") or []
  us_deep_dive = artifacts.get("us_deep_dive_candidates") or []
  cn_watch = artifacts.get("strategic_watch") or []
  next_actions = artifacts.get("next_actions") or []

  return {
    "title": "Weekly Digest Preview",
    "note_japanese": (
      "これは週次メールのプレビューです。実際のメール送信はまだ行いません。"
      "金額・課金情報は含みません。"
    ),
    "acquisition_policy": {
      "name_japanese": acquisition_policy_summary.get("user_facing_name_japanese"),
      "description_japanese": acquisition_policy_summary.get("user_facing_description_japanese"),
      "included_items": acquisition_policy_summary.get("included_items", []),
      "excluded_items": acquisition_policy_summary.get("excluded_items", []),
    },
    "important_patents": top20[:10],
    "us_deep_dive_candidates": us_deep_dive[:5],
    "china_strategic_watch": cn_watch[:10],
    "next_actions": next_actions[:8],
    "manual_watch_count": acquisition_policy_summary.get("manual_watch_count", len(cn_watch)),
  }


def render_weekly_digest_preview_markdown(preview: dict[str, Any]) -> str:
  policy = preview.get("acquisition_policy") or {}
  lines = [
    "# Weekly Digest Preview",
    "",
    preview.get("note_japanese") or "週次メールのプレビューです。実際のメール送信はまだ行いません。",
    "",
    "## 今週の取得方針",
    "",
    f"**{policy.get('name_japanese') or ''}**",
    "",
    policy.get("description_japanese") or "",
    "",
    "### 取得範囲",
    "",
  ]
  for item in policy.get("included_items", []):
    lines.append(f"- {item}")
  lines.extend(["", "### 深掘り対象外", ""])
  for item in policy.get("excluded_items", []):
    lines.append(f"- {item}")

  lines.extend(["", "## 今週の重要特許", ""])
  for row in preview.get("important_patents", [])[:10]:
    if isinstance(row, dict):
      lines.append(
        f"- {row.get('publication_number', '')} | {row.get('title', '')} | {row.get('assignee', '')}",
      )
    else:
      lines.append(f"- {row}")

  lines.extend(["", "## 中国 Strategic Watch", ""])
  for row in preview.get("china_strategic_watch", [])[:10]:
    if isinstance(row, dict):
      lines.append(
        f"- {row.get('publication_number', '')} | {row.get('country', '')} | "
        f"{row.get('assignee', '')} | {row.get('watch_reason_japanese', row.get('title', ''))}",
      )

  lines.extend(["", "## US Deep Dive候補", ""])
  for row in preview.get("us_deep_dive_candidates", [])[:5]:
    if isinstance(row, dict):
      lines.append(f"- {row.get('publication_number', '')} | {row.get('title', '')}")

  lines.extend(["", "## 今週の次アクション", ""])
  for action in preview.get("next_actions", []):
    lines.append(f"- {action}")
  if not preview.get("next_actions"):
    lines.extend(
      [
        "- claims取得の要否を確認",
        "- description取得の要否を確認",
        "- CN PDF手動確認",
        "- OpenAlex plan確認",
      ],
    )

  lines.append("")
  lines.append("※ 実メール送信・決済機能は未実装です。")
  return "\n".join(lines)


def save_weekly_digest_preview(preview: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  json_path = out / "weekly_digest_preview.json"
  md_path = out / "weekly_digest_preview.md"
  json_path.write_text(json.dumps(preview, indent=2, ensure_ascii=False), encoding="utf-8")
  md_path.write_text(render_weekly_digest_preview_markdown(preview), encoding="utf-8")
  return {
    "weekly_digest_preview_json": str(json_path),
    "weekly_digest_preview_md": str(md_path),
  }
