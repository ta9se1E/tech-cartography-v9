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

  claims_plan = preview.get("claims_paper_query_plan") or {}
  quality = claims_plan.get("quality_summary") or {}
  lines.extend(["", "## 技術の裏取り候補", ""])
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

  openalex_limited = preview.get("openalex_limited_execution") or {}
  claim_links = preview.get("claim_paper_candidate_links") or []
  if openalex_limited or claim_links:
    lines.extend(["", "## 論文裏取り候補", ""])
    lines.append(f"- 実行モード: {openalex_limited.get('mode', 'plan_only')}")
    selected = openalex_limited.get("selected_queries") or []
    lines.append(f"- 実行query: {len(selected)} 件")
    for row in selected[:3]:
      lines.append(f"  - [{row.get('query_type')}] {row.get('query')}")
    papers = openalex_limited.get("paper_records") or []
    lines.append("- 取得された代表論文候補:")
    if papers:
      for paper in papers[:3]:
        lines.append(f"  - {paper.get('title', '(no title)')}")
    else:
      lines.append("  - (まだ取得なし / plan_only)")
    quality = openalex_limited.get("source_quality_summary") or {}
    if quality:
      lines.append("- Source quality:")
      for level, count in sorted(quality.items()):
        lines.append(f"  - {level}: {count}")
    if claim_links:
      lines.append("- Claimとの関係:")
      for link in claim_links[:3]:
        if isinstance(link, dict):
          lines.append(
            f"  - {link.get('element_type')} ↔ {link.get('paper_title')} "
            f"({link.get('link_type')}, {link.get('confidence')})",
          )
    lines.append("- 次アクション:")
    for action in [
      "descriptionを追加する",
      "論文候補を技術者が確認する",
      "OpenAlex queryを調整する",
    ]:
      lines.append(f"  - {action}")
    lines.append(
      "- 論文候補は技術背景の裏取り候補です。特許の有効性、実施可能性、侵害性を判断するものではありません。",
    )

  relevance = preview.get("paper_candidate_relevance") or {}
  if relevance:
    lines.extend(["", "## 論文裏取り候補の絞り込み", ""])
    selected = relevance.get("selected_evidence_papers") or relevance.get("selected_paper_records") or []
    lines.append("- Evidence Mapに載せる代表論文:")
    if selected:
      for row in selected[:5]:
        if isinstance(row, dict):
          lines.append(f"  - {row.get('title', row.get('paper_record', {}).get('title', '(no title)'))}")
    else:
      lines.append("  - (まだ選定なし)")
    broad_count = int(relevance.get("broad_background_count", 0))
    off_topic = int(relevance.get("excluded_off_topic_count", 0))
    lines.append(f"- broad backgroundとして扱う論文: {broad_count} 件")
    lines.append(f"- off-topic除外: {off_topic} 件")
    lines.append("- 次アクション:")
    for action in [
      "selected evidence papersを技術者が確認する",
      "descriptionを追加して裏取り精度を上げる",
      "broad reviewは背景参照のみとする",
    ]:
      lines.append(f"  - {action}")

  ev_map = preview.get("evidence_map_synthesis") or {}
  if ev_map:
    lines.extend(["", "## Evidence Map Summary", ""])
    lines.append(f"- 今週のDeep Dive対象: {ev_map.get('publication_number', '')} / {ev_map.get('title', '')}")
    lines.append(f"- synthesis status: {ev_map.get('synthesis_status', '')}")
    lines.append(f"- Claim Element数: {ev_map.get('claim_element_count', 0)}")
    lines.append(f"- selected evidence papers: {ev_map.get('selected_evidence_paper_count', 0)}")
    lines.append("- claimsから見えた技術要素:")
    for finding in (ev_map.get("key_findings_japanese") or [])[:4]:
      lines.append(f"  - {finding}")
    lines.append("- Evidence Gaps:")
    for gap in (ev_map.get("evidence_gaps_japanese") or [])[:4]:
      lines.append(f"  - {gap}")
    lines.append("- 次に読むべき情報:")
    for action in (ev_map.get("next_actions_japanese") or [])[:4]:
      lines.append(f"  - {action}")

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
