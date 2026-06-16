"""Controlled full text retrieval plan: US auto targets vs manual strategic watch."""

from __future__ import annotations

from typing import Any

from tech_cartography.curation.noise_filter import is_likely_noise
from tech_cartography.retrieval.bigquery_fulltext_query_builder import is_us_publication

MANUAL_ROUTE_COUNTRIES = {"CN", "EP", "JP", "WO", "KR"}
FULLTEXT_CAVEAT_JAPANESE = (
  "このTop5は全文取得しやすい米国公報を優先したリストです。"
  "中国・EP・JP等の重要特許は Strategic Watch / Manual Fulltext パッケージで別途確認してください。"
  "中国候補を除外しているわけではありません。"
)


def _country(record: dict[str, Any]) -> str:
  return str(record.get("country", "") or "").upper()


def _source_route(record: dict[str, Any]) -> str:
  return str(record.get("source_route", "") or "").strip()


def _is_us_fulltext_target(record: dict[str, Any]) -> bool:
  pub = str(record.get("publication_number", "") or "")
  country = _country(record)
  route = _source_route(record)
  if not is_us_publication(pub, country):
    return False
  if route and route not in {"us_bigquery_fulltext_candidate", "us_fulltext_candidate", ""}:
    return False
  if is_likely_noise(record) and float(record.get("noise_score", 0) or 0) >= 0.45:
    return False
  return True


def _manual_row(record: dict[str, Any]) -> dict[str, Any]:
  return {
    "publication_number": record.get("publication_number"),
    "title": record.get("title"),
    "assignee": record.get("assignee"),
    "country": record.get("country"),
    "url": record.get("url"),
    "primary_cluster_id": record.get("primary_cluster_id"),
    "source_route": record.get("source_route") or "manual_fulltext_required",
    "manual_route_reason": record.get("manual_route_reason")
    or record.get("watch_reason_japanese")
    or "非米国公報はPDF/Google Patents等での手動全文確認が必要です。",
    "watch_reason_japanese": record.get("watch_reason_japanese")
    or record.get("why_selected_japanese")
    or "",
    "recommended_next_action": record.get("recommended_next_action")
    or record.get("recommended_next_action_japanese")
    or "manual_pdf_check",
  }


def build_controlled_fulltext_plan(
  top5_candidates: list[dict[str, Any]],
  strategic_watch_candidates: list[dict[str, Any]] | None = None,
  *,
  execute: bool = False,
) -> dict[str, Any]:
  strategic_watch_candidates = strategic_watch_candidates or []
  fulltext_targets: list[dict[str, Any]] = []
  manual_required_candidates: list[dict[str, Any]] = []
  strategic_watch_manual_candidates: list[dict[str, Any]] = []
  skipped_candidates: list[dict[str, Any]] = []

  seen_pubs: set[str] = set()

  for record in top5_candidates:
    pub = str(record.get("publication_number", "") or "")
    if _is_us_fulltext_target(record):
      fulltext_targets.append(dict(record))
      seen_pubs.add(pub)
    elif _country(record) in MANUAL_ROUTE_COUNTRIES or not is_us_publication(pub, _country(record)):
      manual_required_candidates.append(_manual_row(record))
      seen_pubs.add(pub)
    else:
      skipped_candidates.append(
        {
          "publication_number": pub,
          "reason": "noise_or_ineligible_for_us_fulltext",
          "noise_score": record.get("noise_score"),
        },
      )

  for record in strategic_watch_candidates:
    pub = str(record.get("publication_number", "") or "")
    if pub in seen_pubs:
      continue
    country = _country(record)
    if country in MANUAL_ROUTE_COUNTRIES or country != "US":
      row = _manual_row(record)
      strategic_watch_manual_candidates.append(row)
      seen_pubs.add(pub)
    elif is_us_publication(pub, country) and pub not in {r.get("publication_number") for r in fulltext_targets}:
      strategic_watch_manual_candidates.append(_manual_row(record))

  cn_watch_count = sum(
    1 for row in strategic_watch_manual_candidates if _country(row) == "CN"
  )

  return {
    "fulltext_targets": fulltext_targets,
    "manual_required_candidates": manual_required_candidates,
    "strategic_watch_manual_candidates": strategic_watch_manual_candidates,
    "skipped_candidates": skipped_candidates,
    "plan_summary": {
      "total_top5_candidates": len(top5_candidates),
      "us_fulltext_targets_count": len(fulltext_targets),
      "manual_required_count": len(manual_required_candidates),
      "strategic_watch_count": len(strategic_watch_candidates),
      "strategic_watch_manual_count": len(strategic_watch_manual_candidates),
      "cn_watch_count": cn_watch_count,
      "skipped_count": len(skipped_candidates),
      "estimated_mode": "execute" if execute else "dry_run",
      "caveat_japanese": FULLTEXT_CAVEAT_JAPANESE,
      "this_list_purpose": "US fulltext retrieval priority",
      "not_global_importance_ranking": True,
    },
  }


def render_manual_fulltext_checklist(
  plan: dict[str, Any],
  *,
  manual_rows: list[dict[str, Any]] | None = None,
  strategic_rows: list[dict[str, Any]] | None = None,
) -> str:
  manual_rows = manual_rows or plan.get("manual_required_candidates", [])
  strategic_rows = strategic_rows or plan.get("strategic_watch_manual_candidates", [])
  summary = plan.get("plan_summary", {})
  lines = [
    "# Manual Full Text Check List",
    "",
    "## 1. Why manual check is needed",
    "",
    "- CN/EP/JP/WO/KRはBigQueryでclaims/descriptionを取れない場合があります",
    "- Google Patents / PDF / patent office sourceで確認します",
    "- 全文が取れない場合でも、戦略監視候補として重要な場合があります",
  ]
  lines.extend(
    [
      "",
      "## 2. China / Non-US Strategic Watch",
      "",
      "- 中国候補を除外していません。Strategic Watchとして別枠で残しています",
      f"- 戦略監視手動候補: {summary.get('strategic_watch_manual_count', len(strategic_rows))} 件",
      f"- 中国候補: {summary.get('cn_watch_count', 0)} 件",
    ],
  )

  zhongfu = [
    row for row in strategic_rows if "zhongfu" in str(row.get("assignee", "")).lower()
  ]
  if zhongfu:
    lines.append("- Zhongfu Shenying系候補を優先して確認してください:")
    for row in zhongfu[:10]:
      lines.append(f"  - {row.get('publication_number')} | {row.get('title')}")

  lines.extend(["", "## 3. What to check manually", ""])
  for item in [
    "請求項",
    "実施例",
    "数値条件",
    "物性値",
    "測定方法",
    "用途",
    "出願人の事業シグナル",
  ]:
    lines.append(f"- {item}")

  lines.extend(["", "## 4. Manual input template", ""])
  for col in [
    "publication_number",
    "claims",
    "independent_claims",
    "description",
    "examples",
    "measured_properties",
    "source_url",
    "source_note",
  ]:
    lines.append(f"- {col}")

  lines.extend(["", "## 5. Manual Required Candidates", ""])
  for row in manual_rows:
    lines.append(
      f"- {row.get('publication_number')} | {row.get('country')} | {row.get('assignee')} | {row.get('title')}",
    )

  lines.extend(["", "## 6. Strategic Watch Manual Candidates", ""])
  for row in strategic_rows[:30]:
    lines.append(
      f"- {row.get('publication_number')} | {row.get('country')} | {row.get('assignee')}",
    )
    if row.get("watch_reason_japanese"):
      lines.append(f"  - {row.get('watch_reason_japanese')}")

  return "\n".join(lines)
