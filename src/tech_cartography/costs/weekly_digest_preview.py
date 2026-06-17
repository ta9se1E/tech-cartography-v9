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
  claims_paper_query_plan = artifacts.get("claims_paper_query_plan") or {}
  openalex_limited = artifacts.get("openalex_limited_execution") or {}
  claim_paper_links = artifacts.get("claim_paper_candidate_links") or []
  paper_candidate_relevance = artifacts.get("paper_candidate_relevance") or {}
  evidence_map_synthesis = artifacts.get("evidence_map_synthesis") or {}

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
    "claims_paper_query_plan": claims_paper_query_plan,
    "openalex_limited_execution": openalex_limited,
    "claim_paper_candidate_links": claim_paper_links,
    "paper_candidate_relevance": paper_candidate_relevance,
    "evidence_map_synthesis": evidence_map_synthesis,
    "china_strategic_watch": cn_watch[:10],
    "next_actions": next_actions[:8],
    "manual_watch_count": acquisition_policy_summary.get("manual_watch_count", len(cn_watch)),
  }


def render_weekly_digest_preview_markdown(preview: dict[str, Any]) -> str:
  policy = preview.get("acquisition_policy") or {}
  ev_map = preview.get("evidence_map_synthesis") or {}
  lines = [
    "# Weekly Digest Preview",
    "",
    preview.get("note_japanese") or "週次メールのプレビューです。実際のメール送信はまだ行いません。",
    "",
    "この内容が週次で届く想定です。",
    "",
    "## 今週の特許インテリジェンス",
    "",
    "### 監視テーマ",
    "",
    f"- {policy.get('name_japanese') or '標準監視モード'}",
    f"- {policy.get('description_japanese') or ''}",
    "",
    "### 今週のDeep Dive対象",
    "",
  ]
  deep_dive_pub = ev_map.get("publication_number") or ""
  deep_dive_title = ev_map.get("title") or ""
  if deep_dive_pub:
    lines.append(f"- {deep_dive_pub} / {deep_dive_title}")
  for row in preview.get("us_deep_dive_candidates", [])[:5]:
    if isinstance(row, dict) and not deep_dive_pub:
      lines.append(f"- {row.get('publication_number', '')} | {row.get('title', '')}")
    elif isinstance(row, dict) and row.get("publication_number") != deep_dive_pub:
      lines.append(f"- {row.get('publication_number', '')} | {row.get('title', '')}")

  if ev_map:
    lines.extend(["", "### Evidence Map Summary", ""])
    lines.append(f"- synthesis status: {ev_map.get('synthesis_status', '')}")
    lines.append(f"- Claim Element数: {ev_map.get('claim_element_count', 0)}")
    lines.append(f"- selected evidence papers: {ev_map.get('selected_evidence_paper_count', 0)}")
    lines.append(f"- claim-paper links: {ev_map.get('claim_paper_link_count', 0)}")
    for finding in (ev_map.get("key_findings_japanese") or [])[:4]:
      lines.append(f"  - {finding}")
    lines.append("- Evidence Gaps:")
    for gap in (ev_map.get("evidence_gaps_japanese") or [])[:4]:
      lines.append(f"  - {gap}")

  lines.extend(["", "### 論文裏取り候補", ""])
  claims_plan = preview.get("claims_paper_query_plan") or {}
  quality = claims_plan.get("quality_summary") or {}
  openalex_limited = preview.get("openalex_limited_execution") or {}
  claim_links = preview.get("claim_paper_candidate_links") or []
  relevance = preview.get("paper_candidate_relevance") or {}

  if claims_plan.get("queries") or claims_plan.get("total_queries", 0) > 0:
    lines.append(f"- manual claimsから生成されたpaper query候補: {claims_plan.get('total_queries', 0)} 件")
    ready = claims_plan.get("plan_ready_for_openalex", quality.get("plan_ready_for_openalex", False))
    lines.append(
      f"- OpenAlex実行準備: {'OK（plan_only）' if ready else '要改善（query候補を追加）'}",
    )
    lines.append(f"- 現在のモード: {claims_plan.get('openalex_mode', 'plan_only')}（本実行はまだ任意）")
    lines.append("- 現在の制約: 明細書・実施例未入力のため数値条件・測定方法の裏取りは限定的")
    lines.append("- 代表query:")
    for example in (claims_plan.get("query_examples") or [])[:3]:
      lines.append(f"  - {example}")
    lines.append("- 次アクション:")
    for action in claims_plan.get("next_actions_japanese") or quality.get("next_actions_japanese") or [
      "descriptionを追加する",
      "OpenAlexを限定実行する",
      "技術者がquery妥当性を確認する",
    ]:
      lines.append(f"  - {action}")
    lines.append(
      "- 請求項ベースのため、論文は証明ではなく supporting evidence candidate として扱います。",
    )
  else:
    lines.append("- manual claimsからのpaper query候補はまだありません。")
    lines.append("- 次アクション: Google Patentsからclaimsを貼り付け、Evidence Validationを実行")

  if openalex_limited or claim_links:
    lines.append(f"- OpenAlex実行モード: {openalex_limited.get('mode', 'plan_only')}")
    papers = openalex_limited.get("paper_records") or []
    if papers:
      lines.append("- 代表論文候補:")
      for paper in papers[:3]:
        lines.append(f"  - {paper.get('title', '(no title)')}")
    if claim_links:
      lines.append("- Claimとの関係:")
      for link in claim_links[:3]:
        if isinstance(link, dict):
          fallback = " [弱い対応]" if link.get("is_fallback_link") else ""
          lines.append(
            f"  - {link.get('element_type')} ↔ {link.get('paper_title')} "
            f"({link.get('link_type')}, {link.get('confidence')}){fallback}",
          )

  if relevance:
    selected = relevance.get("selected_evidence_papers") or relevance.get("selected_paper_records") or []
    if selected:
      lines.append("- Evidence Mapに載せる代表論文:")
      for row in selected[:5]:
        if isinstance(row, dict):
          title = row.get("title", row.get("paper_record", {}).get("title", "(no title)"))
          doi = row.get("doi") or "n/a"
          source = row.get("source") or row.get("source_name") or "n/a"
          cited = row.get("cited_by_count", "n/a")
          lines.append(f"  - {title} (doi={doi}, source={source}, cited_by={cited})")
    broad_count = int(relevance.get("broad_background_count", 0))
    off_topic = int(relevance.get("excluded_off_topic_count", 0))
    lines.append(f"- broad background除外: {broad_count} 件 / off-topic除外: {off_topic} 件")

  lines.extend(["", "### Strategic Watch", ""])
  for row in preview.get("china_strategic_watch", [])[:10]:
    if isinstance(row, dict):
      lines.append(
        f"- {row.get('publication_number', '')} | {row.get('country', '')} | "
        f"{row.get('assignee', '')} | {row.get('watch_reason_japanese', row.get('title', ''))}",
      )
  if not preview.get("china_strategic_watch"):
    lines.append("- （中国 Strategic Watch候補はパイプライン実行後に表示）")

  lines.extend(["", "### 次アクション", ""])
  for action in preview.get("next_actions", []):
    lines.append(f"- {action}")
  if not preview.get("next_actions"):
    lines.extend(
      [
        "- selected evidence papersを技術者が確認する",
        "- descriptionを追加して裏取り精度を上げる",
        "- CN/EP/JP候補をmanual routeで確認する",
        "- OpenAlex queryの妥当性を確認する",
      ],
    )

  lines.append("")
  lines.append("※ 実メール送信・決済機能は未実装です。論文は証明ではなく supporting evidence candidate です。")
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
