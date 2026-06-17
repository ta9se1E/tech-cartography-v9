"""Weekly digest preview — no email sending, no monetary amounts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tech_cartography.manual.manual_fulltext_loader import get_manual_fulltext_status


def _bigquery_body_status(row: dict[str, Any]) -> str:
  probe = row.get("availability_probe") or {}
  status = str(row.get("retrieval_status") or probe.get("probe_status") or "")
  if status == "manual_fulltext_loaded":
    return "BigQuery本文: 未取得（Manual descriptionあり）"
  if status in {"retrieved", "cache_hit", "fulltext_probe_found_claims", "allowed_expensive_execute"}:
    return "BigQuery本文: 取得済み"
  if status in {"manual_claims_loaded"}:
    return "BigQuery本文: 未取得"
  if status in {"skipped_known_not_found", "manual_google_patents_recommended", "bigquery_fulltext_not_available", "fulltext_probe_not_found", "not_found", "manual_route_recommended"}:
    return "BigQuery本文: 未取得"
  return "BigQuery本文: 未確認"


def _manual_route_status(publication_number: str, input_dir: str) -> dict[str, str]:
  status = get_manual_fulltext_status(publication_number, input_dir)
  if not status.get("manual_input_exists"):
    return {
      "manual_route_label": "claims入力待ち",
      "next_action": "Google Patentsからclaimsを貼り付け",
      "analysis_note": "",
    }
  if status.get("claims_present"):
    note = "請求項ベースの限定解析に進めます"
    if not status.get("description_present"):
      note += "（明細書なし・限定解析）"
    return {
      "manual_route_label": "claims入力済み",
      "next_action": "Claim Element抽出を確認",
      "analysis_note": note,
    }
  return {
    "manual_route_label": "claims入力待ち",
    "next_action": "Google Patentsからclaimsを貼り付け",
    "analysis_note": "",
  }


def build_weekly_digest_preview(
  artifacts: dict[str, Any],
  acquisition_policy_summary: dict[str, Any],
) -> dict[str, Any]:
  top20 = artifacts.get("top20_patents") or []
  us_deep_dive = artifacts.get("us_deep_dive_candidates") or []
  cn_watch = artifacts.get("strategic_watch") or []
  next_actions = artifacts.get("next_actions") or []
  manual_input_dir = str(artifacts.get("manual_fulltext_input_dir") or "outputs/manual_fulltext_inputs")

  def _bq_status(row: dict[str, Any]) -> str:
    if not isinstance(row, dict):
      return "BigQuery未確認"
    probe = row.get("availability_probe") or {}
    status = str(row.get("retrieval_status") or probe.get("probe_status") or "")
    if status in {"retrieved", "cache_hit", "fulltext_probe_found_claims", "allowed_expensive_execute", "manual_fulltext_loaded"}:
      return "BigQuery取得可"
    if status in {"manual_claims_loaded"}:
      return "BigQueryでは未確認のためManual Route利用中"
    if status in {"skipped_known_not_found", "manual_google_patents_recommended", "bigquery_fulltext_not_available", "fulltext_probe_not_found", "not_found", "manual_route_recommended"}:
      return "BigQueryでは未確認のためManual Route推奨"
    return "BigQuery未確認"

  us_deep_dive_enriched = []
  us_deep_dive_status_lines: list[dict[str, Any]] = []
  for row in us_deep_dive[:5]:
    if isinstance(row, dict):
      pub = str(row.get("publication_number") or "")
      enriched = dict(row)
      enriched["bigquery_availability_status_japanese"] = _bq_status(row)
      manual_info = _manual_route_status(pub, manual_input_dir)
      enriched["manual_route_status_japanese"] = manual_info["manual_route_label"]
      enriched["manual_next_action_japanese"] = manual_info["next_action"]
      enriched["manual_analysis_note_japanese"] = manual_info["analysis_note"]
      us_deep_dive_enriched.append(enriched)
      us_deep_dive_status_lines.append(
        {
          "publication_number": pub,
          "title": row.get("title"),
          "bigquery_body_status": _bigquery_body_status(row),
          "manual_route_status": manual_info["manual_route_label"],
          "next_action": manual_info["next_action"],
          "analysis_note": manual_info["analysis_note"],
        },
      )
    else:
      us_deep_dive_enriched.append(row)

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
    "us_deep_dive_candidates": us_deep_dive_enriched,
    "us_deep_dive_status": us_deep_dive_status_lines,
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
      bq = row.get("bigquery_availability_status_japanese", "")
      manual = row.get("manual_route_status_japanese", "")
      suffix = f" | {bq}" if bq else ""
      if manual:
        suffix += f" | Manual Route: {manual}"
      lines.append(f"- {row.get('publication_number', '')} | {row.get('title', '')}{suffix}")

  lines.extend(["", "## US Deep Dive状況", ""])
  status_rows = preview.get("us_deep_dive_status") or preview.get("us_deep_dive_candidates") or []
  for row in status_rows[:5]:
    if not isinstance(row, dict):
      continue
    pub = row.get("publication_number", "")
    bq_body = row.get("bigquery_body_status") or row.get("bigquery_availability_status_japanese", "")
    manual_route = row.get("manual_route_status") or row.get("manual_route_status_japanese", "")
    next_action = row.get("next_action") or row.get("manual_next_action_japanese", "")
    analysis = row.get("analysis_note") or row.get("manual_analysis_note_japanese", "")
    lines.append(f"### {pub}")
    lines.append(f"- {bq_body or 'BigQuery本文: 未確認'}")
    lines.append(f"- Manual Route: {manual_route or 'claims入力待ち'}")
    if next_action:
      lines.append(f"- 次アクション: {next_action}")
    if analysis:
      lines.append(f"- {analysis}")
    lines.append("")

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
