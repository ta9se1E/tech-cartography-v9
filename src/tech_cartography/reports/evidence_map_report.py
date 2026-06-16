"""Carbon Fiber Evidence Map report generation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from tech_cartography.curation.noise_filter import is_likely_noise
from tech_cartography.reports.project_export import build_output_directory


def build_evidence_map_summary(
  classified_records: list[dict[str, Any]],
  ranked_records: list[dict[str, Any]],
  *,
  top_records: list[dict[str, Any]] | None = None,
  fulltext_candidates: list[dict[str, Any]] | None = None,
  strategic_watch_candidates: list[dict[str, Any]] | None = None,
  country_watch_summary: list[dict[str, Any]] | None = None,
  company_watch_summary: list[dict[str, Any]] | None = None,
  cluster_summary: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
  top_records = top_records or []
  fulltext_candidates = fulltext_candidates or []
  strategic_watch_candidates = strategic_watch_candidates or []
  country_watch_summary = country_watch_summary or []
  company_watch_summary = company_watch_summary or []
  cluster_summary = cluster_summary or []
  noise_candidates = [
    {
      "publication_number": record.get("publication_number"),
      "title": record.get("title"),
      "noise_score": record.get("noise_score"),
      "noise_signals": record.get("noise_signals", []),
      "reason": record.get("rank_reason"),
    }
    for record in ranked_records
    if is_likely_noise(record) or float(record.get("noise_score", 0) or 0) >= 0.45
  ]

  return {
    "total_records": len(classified_records),
    "deduped_records": len(classified_records),
    "cluster_count": len(cluster_summary),
    "top20_count": len(top_records),
    "top5_fulltext_count": len(fulltext_candidates),
    "strategic_watch_count": len(strategic_watch_candidates),
    "cluster_summary": cluster_summary,
    "top20_patents": top_records,
    "top5_fulltext_candidates": fulltext_candidates,
    "strategic_watch_candidates": strategic_watch_candidates,
    "country_watch_summary": country_watch_summary,
    "company_watch_summary": company_watch_summary,
    "noise_candidates": noise_candidates,
    "next_phases": [
      "Top5 full text取得",
      "Strategic Watch候補のPDF/manual確認",
      "Claim Element Extraction",
      "OpenAlex paper evidence",
      "SourceQuality評価",
    ],
  }


def render_evidence_map_markdown(summary: dict[str, Any]) -> str:
  lines = [
    "# Carbon Fiber Evidence Map v1",
    "",
    "## 1. 検索結果サマリー",
    "",
    f"- 総件数: {summary.get('total_records', 0)}",
    f"- 重複除去後件数: {summary.get('deduped_records', 0)}",
    f"- クラスタ数: {summary.get('cluster_count', 0)}",
    f"- Top20重要特許: {summary.get('top20_count', 0)}",
    f"- Top5全文取得候補: {summary.get('top5_fulltext_count', 0)}",
    f"- Strategic Watch候補: {summary.get('strategic_watch_count', 0)}",
    "",
    "> US Top5は全文取得優先リストであり、世界の重要度ランキングではありません。",
    "> CN/EP/JP等は全文取得ルートが異なるため、Strategic Watchとして別管理します。",
    "",
    "## 2. 技術クラスタ",
    "",
  ]

  for cluster in summary.get("cluster_summary", []):
    lines.extend(
      [
        f"### {cluster.get('name')} (`{cluster.get('cluster_id')}`)",
        f"- 特許件数: {cluster.get('patent_count', 0)}",
        f"- 代表語: {', '.join(cluster.get('representative_terms', []))}",
        f"- 代表企業: {', '.join(cluster.get('top_assignees', [])) or '（なし）'}",
        f"- 代表特許: {', '.join(cluster.get('representative_patents', [])) or '（なし）'}",
        f"- コメント: {cluster.get('description', '')}",
        "",
      ],
    )

  lines.extend(["## 3. 重要特許Top20", ""])
  lines.append(
    "| rank | publication_number | title | assignee | country | primary_cluster | total_score | recommended_action | rank_reason |",
  )
  lines.append("|---:|---|---|---|---|---:|---:|---|---|")
  for record in summary.get("top20_patents", []):
    lines.append(
      f"| {record.get('rank', '')} | {record.get('publication_number', '')} | "
      f"{record.get('title', '')} | {record.get('assignee', '')} | {record.get('country', '')} | "
      f"{record.get('primary_cluster_id', '')} | {record.get('total_score', '')} | "
      f"{record.get('recommended_action', '')} | {record.get('rank_reason', '')} |",
    )

  lines.extend(
    [
      "",
      "## 4. Top5全文取得候補",
      "",
      "- 目的: BigQueryでclaims/descriptionを取得しやすいUS公報を優先",
      "- 注意: このリストは全文取得容易性の優先であり、世界の戦略的重要度ランキングではない",
      "",
    ],
  )
  for record in summary.get("top5_fulltext_candidates", []):
    lines.extend(
      [
        f"- {record.get('publication_number')} | {record.get('title')} | {record.get('assignee')}",
        f"  - reason: {record.get('fulltext_candidate_reason', '')}",
        f"  - caveat: {record.get('caveat_japanese', '')}",
        f"  - next_step: {record.get('next_step', '')}",
      ],
    )

  lines.extend(
    [
      "",
      "## Strategic Watch Candidates",
      "",
      "中国・EP・JP等を含む戦略監視候補。Full text取得しやすさとは別に、技術・競合として重要な候補。",
      "metadata_onlyであり、PDF/manual確認が必要な場合があります。",
      "",
    ],
  )
  for record in summary.get("strategic_watch_candidates", [])[:20]:
    lines.extend(
      [
        f"- {record.get('publication_number')} | {record.get('country')} | {record.get('assignee')}",
        f"  - title: {record.get('title')}",
        f"  - watch_reason: {record.get('watch_reason_japanese', '')}",
        f"  - manual_route: {record.get('manual_route_reason', '')}",
        f"  - next_action: {record.get('recommended_next_action', '')}",
      ],
    )

  lines.extend(["", "## China / Non-US Watch", ""])
  cn_rows = [
    row for row in summary.get("country_watch_summary", []) if str(row.get("country")) == "CN"
  ]
  if cn_rows:
    for row in cn_rows:
      lines.append(
        f"- CN候補{row.get('candidate_count')}件 / priority={row.get('watch_priority')} / "
        f"{row.get('note_japanese', '')}",
      )
    zhongfu_rows = [
      row
      for row in summary.get("company_watch_summary", [])
      if "Zhongfu" in str(row.get("normalized_company", ""))
    ]
    if zhongfu_rows:
      lines.append("- Zhongfu Shenying系の監視候補が複数検出されています。PDF/Google Patentsで追加確認してください。")
  else:
    lines.append("- 今回のStrategic Watch候補にCNは未検出、または件数が少ないです。")

  lines.extend(["", "## 5. ノイズ・注意候補", ""])
  for item in summary.get("noise_candidates", [])[:20]:
    lines.append(
      f"- {item.get('publication_number')}: noise_score={item.get('noise_score')} "
      f"signals={item.get('noise_signals')}",
    )

  lines.extend(["", "## 6. 次フェーズ", ""])
  for step in summary.get("next_phases", []):
    lines.append(f"- {step}")

  return "\n".join(lines)


def save_evidence_map_report(markdown: str, output_dir: str | Path) -> str:
  path = Path(output_dir) / "carbon_fiber_evidence_map_report.md"
  path.parent.mkdir(parents=True, exist_ok=True)
  path.write_text(markdown, encoding="utf-8")
  return str(path)
