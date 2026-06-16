"""Strategic watch candidate selection for non-US and global competition monitoring."""

from __future__ import annotations

from collections import Counter, defaultdict
from typing import Any

from tech_cartography.curation.dedup import _as_list
from tech_cartography.curation.noise_filter import (
  detect_noise_categories,
  detect_noise_signals,
  is_likely_noise,
)
from tech_cartography.curation.patent_ranker import (
  BUNDLE_PREPREG_TERMS,
  CORE_MANUFACTURING_TERMS,
  FULLTEXT_PRIORITY_CLUSTERS,
  GLOBAL_STRATEGIC_ASSIGNEES,
  PROPERTY_TERMS,
  SURFACE_INTERFACE_TERMS,
  ZHONGFU_ASSIGNEE_PATTERNS,
  _count_term_hits,
  _record_text,
)
from tech_cartography.ui.japanese_labels import translate_cluster_id, translate_recommended_next_action

STRATEGIC_KEY_TERMS = [
  "pan",
  "polyacrylonitrile",
  "precursor",
  "carbonization",
  "carbonisation",
  "dry-jet wet-spinning",
  "dry jet wet spinning",
  "pre-oxidation",
  "pre oxidation",
  "large-tow",
  "large tow",
  "surface treatment",
  "sizing",
  "tensile strength",
  "modulus",
  "tow",
  "prepreg",
]

MANUAL_ROUTE_COUNTRIES = {"CN", "EP", "JP", "WO", "KR"}


def _country(record: dict[str, Any]) -> str:
  return str(record.get("country", "") or "").upper()


def _is_zhongfu_assignee(record: dict[str, Any]) -> bool:
  assignee = str(record.get("assignee", "") or "").lower()
  return any(pattern in assignee for pattern in ZHONGFU_ASSIGNEE_PATTERNS)


def _is_global_strategic_assignee(record: dict[str, Any]) -> bool:
  assignee = str(record.get("assignee", "") or "").lower()
  return any(pattern in assignee for pattern in GLOBAL_STRATEGIC_ASSIGNEES)


def classify_watch_reason(record: dict[str, Any]) -> list[str]:
  reasons: list[str] = []
  country = _country(record)
  cluster = str(record.get("primary_cluster_id", ""))

  if country in MANUAL_ROUTE_COUNTRIES:
    reasons.append(f"non_us_manual_route:{country}")
  if _is_zhongfu_assignee(record):
    reasons.append("zhongfu_shenying_assignee")
  elif _is_global_strategic_assignee(record):
    reasons.append("major_carbon_fiber_assignee")
  if cluster in FULLTEXT_PRIORITY_CLUSTERS:
    reasons.append(f"priority_cluster:{cluster}")
  if cluster == "company_watch":
    reasons.append("company_watch_cluster")
  if _count_term_hits(_record_text(record), STRATEGIC_KEY_TERMS) >= 2:
    reasons.append("core_carbon_fiber_terms")
  if float(record.get("strategic_score", record.get("total_score", 0)) or 0) >= 0.65:
    reasons.append("high_strategic_score")
  return reasons


def assign_manual_route_reason(record: dict[str, Any]) -> str:
  country = _country(record)
  if country == "US":
    return ""
  if country in MANUAL_ROUTE_COUNTRIES:
    return (
      f"{country}公報のため、PDFまたはGoogle Patents等での手動全文確認が必要です。"
      "metadata_onlyのため、請求項・実施例はまだ確認していません。"
    )
  if country:
    return f"{country}公報は手動全文確認ルートです。"
  return "国コード不明のため、手動確認が必要です。"


def _recommended_next_action(record: dict[str, Any]) -> str:
  country = _country(record)
  if is_likely_noise(record):
    return "expert_review_required"
  if _is_zhongfu_assignee(record) or _is_global_strategic_assignee(record):
    if country != "US":
      return "monitor_company_activity"
  if country in MANUAL_ROUTE_COUNTRIES:
    return "manual_pdf_check"
  if country == "US":
    return "compare_with_us_fulltext_candidate"
  return "add_to_monthly_watch"


def score_strategic_watch_candidate(record: dict[str, Any]) -> dict[str, Any]:
  text = _record_text(record)
  cluster = str(record.get("primary_cluster_id", ""))
  country = _country(record)

  base = float(record.get("strategic_score", record.get("total_score", 0)) or 0)
  strategic_terms = _count_term_hits(text, STRATEGIC_KEY_TERMS)
  core_hits = _count_term_hits(
    text,
    CORE_MANUFACTURING_TERMS + SURFACE_INTERFACE_TERMS + BUNDLE_PREPREG_TERMS + PROPERTY_TERMS,
  )

  watch_score = base
  watch_score += min(0.25, 0.05 * strategic_terms)
  watch_score += min(0.20, 0.04 * core_hits)
  if cluster in FULLTEXT_PRIORITY_CLUSTERS:
    watch_score += 0.12
  if cluster == "company_watch":
    watch_score += 0.08
  if _is_zhongfu_assignee(record):
    watch_score += 0.20
  elif _is_global_strategic_assignee(record):
    watch_score += 0.10
  if country in MANUAL_ROUTE_COUNTRIES and core_hits >= 1:
    watch_score += 0.08

  noise = float(record.get("noise_score", 0) or 0)
  watch_score -= noise * 0.30
  if is_likely_noise(record):
    watch_score -= 0.35

  watch_score = round(max(0.0, min(1.0, watch_score)), 4)
  score_detail = {
    "base_strategic_score": round(base, 4),
    "strategic_term_hits": strategic_terms,
    "core_content_hits": core_hits,
    "zhongfu_boost": _is_zhongfu_assignee(record),
    "major_assignee_boost": _is_global_strategic_assignee(record),
    "non_us_manual_route": country in MANUAL_ROUTE_COUNTRIES,
    "noise_penalty": round(noise, 4),
  }
  return {"strategic_watch_score": watch_score, "score_detail": score_detail}


def build_watch_reason_japanese(record: dict[str, Any], score_detail: dict[str, Any]) -> str:
  reasons: list[str] = []
  country = _country(record)
  cluster = str(record.get("primary_cluster_id", ""))

  if _is_zhongfu_assignee(record):
    reasons.append("中複神鷹系など中国炭素繊維有力企業の出願")
  elif _is_global_strategic_assignee(record):
    reasons.append("Toray・Teijin・Hyosungなど主要炭素繊維関連企業の出願")
  if cluster in FULLTEXT_PRIORITY_CLUSTERS:
    reasons.append(f"技術分類が{translate_cluster_id(cluster)}に該当")
  if score_detail.get("strategic_term_hits", 0) >= 2:
    reasons.append("PAN・炭化・dry-jet wet-spinningなど戦略的重要語を含む")
  if country in MANUAL_ROUTE_COUNTRIES:
    reasons.append(f"{country}公報のためPDF/Google Patentsでの手動確認が必要")
  elif country == "US":
    reasons.append("米国公報。全文取得候補とも比較して監視")
  if float(record.get("noise_score", 0) or 0) < 0.35:
    reasons.append("ノイズ度は比較的低い")
  if not reasons:
    reasons.append("技術・競合として読む価値がある候補")
  reasons.append("中国候補を除外しているわけではなく、全文取得ルートが異なるため別枠で監視します")
  return "。".join(reasons) + "。"


def _determine_source_route(record: dict[str, Any]) -> str:
  country = _country(record)
  if country == "US":
    return "us_bigquery_fulltext_candidate"
  if country in MANUAL_ROUTE_COUNTRIES or country:
    return "manual_fulltext_required"
  return "metadata_only"


def select_strategic_watch_candidates(
  records: list[dict[str, Any]],
  top_n: int = 20,
) -> list[dict[str, Any]]:
  scored_pool: list[tuple[float, dict[str, Any], dict[str, Any]]] = []

  for record in records:
    if is_likely_noise(record):
      continue
    scored = score_strategic_watch_candidate(record)
    watch_score = float(scored["strategic_watch_score"])
    if watch_score < 0.25:
      continue
    scored_pool.append((watch_score, record, scored["score_detail"]))

  scored_pool.sort(key=lambda item: item[0], reverse=True)

  selected: list[dict[str, Any]] = []
  assignee_counts: dict[str, int] = {}
  country_counts: dict[str, int] = {}

  for watch_score, record, score_detail in scored_pool:
    if len(selected) >= top_n:
      break

    assignee_key = str(record.get("assignee", "unknown") or "unknown").lower()
    country = _country(record)
    if assignee_counts.get(assignee_key, 0) >= 3 and not _is_zhongfu_assignee(record):
      continue
    if country_counts.get(country, 0) >= 8 and country != "CN":
      continue

    watch_reasons = classify_watch_reason(record)
    route = _determine_source_route(record)
    row = dict(record)
    row["strategic_watch_rank"] = len(selected) + 1
    row["strategic_watch_score"] = watch_score
    row["final_score"] = float(record.get("final_score", record.get("total_score", 0)) or 0)
    row["source_route"] = route
    row["manual_route_reason"] = assign_manual_route_reason(record)
    row["watch_reason"] = watch_reasons
    row["watch_reason_japanese"] = build_watch_reason_japanese(record, score_detail)
    row["quality_flags"] = watch_reasons
    row["noise_reasons"] = detect_noise_signals(record)
    row["noise_categories"] = detect_noise_categories(record)
    row["recommended_next_action"] = _recommended_next_action(record)
    row["recommended_next_action_japanese"] = translate_recommended_next_action(
      row["recommended_next_action"],
    )
    selected.append(row)
    assignee_counts[assignee_key] = assignee_counts.get(assignee_key, 0) + 1
    country_counts[country] = country_counts.get(country, 0) + 1

  return selected


def _watch_priority(score: float, count: int) -> str:
  if score >= 0.7 or count >= 5:
    return "high"
  if score >= 0.5 or count >= 2:
    return "medium"
  return "low"


def build_country_watch_summary(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
  by_country: dict[str, list[dict[str, Any]]] = defaultdict(list)
  for record in candidates:
    by_country[_country(record)].append(record)

  rows: list[dict[str, Any]] = []
  for country, items in sorted(by_country.items(), key=lambda kv: len(kv[1]), reverse=True):
    assignees = Counter(str(item.get("assignee", "不明") or "不明") for item in items)
    clusters = Counter(str(item.get("primary_cluster_id", "other") or "other") for item in items)
    avg_score = sum(float(item.get("strategic_watch_score", 0) or 0) for item in items) / max(len(items), 1)
    note = (
      f"{country}の戦略監視候補{len(items)}件。PDF/手動全文確認が必要な場合があります。"
      if country in MANUAL_ROUTE_COUNTRIES
      else f"{country}の戦略監視候補{len(items)}件。"
    )
    if country == "CN":
      note += " 中国炭素繊維企業（中複神鷹系など）の動向確認に有用です。"
    rows.append(
      {
        "country": country,
        "candidate_count": len(items),
        "top_assignees": "; ".join(name for name, _ in assignees.most_common(5)),
        "top_clusters": "; ".join(name for name, _ in clusters.most_common(5)),
        "watch_priority": _watch_priority(avg_score, len(items)),
        "note_japanese": note,
      },
    )
  return rows


def _normalize_company(assignee: str) -> str:
  lower = assignee.lower()
  for pattern in ZHONGFU_ASSIGNEE_PATTERNS:
    if pattern in lower:
      return "Zhongfu Shenying Group"
  for pattern in GLOBAL_STRATEGIC_ASSIGNEES:
    if pattern in lower:
      return pattern.title()
  return assignee.strip() or "不明"


def build_company_watch_summary(candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
  by_company: dict[str, list[dict[str, Any]]] = defaultdict(list)
  for record in candidates:
    assignee = str(record.get("assignee", "") or "")
    by_company[_normalize_company(assignee)].append(record)

  rows: list[dict[str, Any]] = []
  for company, items in sorted(by_company.items(), key=lambda kv: len(kv[1]), reverse=True):
    countries = sorted({_country(item) for item in items})
    clusters = Counter(str(item.get("primary_cluster_id", "other") or "other") for item in items)
    patents = [str(item.get("publication_number", "")) for item in items[:3]]
    avg_score = sum(float(item.get("strategic_watch_score", 0) or 0) for item in items) / max(len(items), 1)
    note = f"{company}の監視候補{len(items)}件。代表公報: {', '.join(patents)}"
    if "Zhongfu" in company:
      note += " 中国炭素繊維の重点監視対象です。"
    rows.append(
      {
        "normalized_company": company,
        "candidate_count": len(items),
        "countries": "; ".join(countries),
        "top_clusters": "; ".join(name for name, _ in clusters.most_common(5)),
        "representative_patents": "; ".join(patents),
        "watch_priority": _watch_priority(avg_score, len(items)),
        "note_japanese": note,
      },
    )
  return rows
