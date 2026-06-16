"""Top5 fulltext candidate selection with quality-aware rules."""

from __future__ import annotations

from typing import Any

from tech_cartography.curation.dedup import _as_list
from tech_cartography.curation.noise_filter import (
  _is_unknown_assignee,
  detect_noise_categories,
  detect_noise_signals,
  is_likely_noise,
)
from tech_cartography.curation.patent_ranker import (
  BUNDLE_PREPREG_TERMS,
  CORE_MANUFACTURING_TERMS,
  FULLTEXT_PRIORITY_CLUSTERS,
  IMPORTANT_ASSIGNEES,
  PROPERTY_TERMS,
  SURFACE_INTERFACE_TERMS,
  _count_term_hits,
  _record_text,
)
from tech_cartography.ui.japanese_labels import (
  explain_fulltext_priority_top5,
  explain_source_route,
  translate_cluster_id,
  translate_source_route,
)

FULLTEXT_LIST_PURPOSE = "US fulltext retrieval priority"
FULLTEXT_CAVEAT_JAPANESE = (
  "このTop5は全文取得しやすい米国公報を優先したリストです。"
  "中国・EP・JP等の重要特許は Strategic Watch Candidates で別途確認してください。"
)

US_COUNTRIES = {"US"}
MANUAL_ROUTE_COUNTRIES = {"JP", "EP", "WO", "CN", "KR"}

STRONG_NOISE_TERMS = [
  "display apparatus",
  "display device",
  "nanoparticle sensor",
  "nanofibrous membrane",
  "3d printing",
  "moulded articles from carbon or graphite",
  "molded articles from carbon or graphite",
  "battery",
  "graphene",
  "carbon nanotube",
  "activated carbon",
  "semiconductor",
]

PRIORITY_KEY_TERMS = [
  "pan",
  "polyacrylonitrile",
  "precursor",
  "carbonization",
  "carbonisation",
  "surface treatment",
  "sizing",
  "tensile strength",
  "modulus",
  "tow",
  "prepreg",
]


def _country(record: dict[str, Any]) -> str:
  return str(record.get("country", "") or "").upper()


def _has_abstract(record: dict[str, Any]) -> bool:
  abstract = str(record.get("abstract", "") or "").strip()
  return len(abstract) >= 20


def _is_major_assignee(record: dict[str, Any]) -> bool:
  if _is_unknown_assignee(record):
    return False
  assignee = str(record.get("assignee", "") or "").lower()
  return any(company in assignee for company in IMPORTANT_ASSIGNEES)


def _priority_keyword_hits(record: dict[str, Any]) -> int:
  text = _record_text(record)
  return _count_term_hits(text, PRIORITY_KEY_TERMS)


def _core_content_hits(record: dict[str, Any]) -> int:
  text = _record_text(record)
  return _count_term_hits(
    text,
    CORE_MANUFACTURING_TERMS + SURFACE_INTERFACE_TERMS + BUNDLE_PREPREG_TERMS + PROPERTY_TERMS,
  )


def _strong_noise_hits(record: dict[str, Any]) -> int:
  text = _record_text(record)
  return _count_term_hits(text, STRONG_NOISE_TERMS)


def _application_only_thin(record: dict[str, Any]) -> bool:
  primary = str(record.get("primary_cluster_id", ""))
  return primary == "application_pressure_aerospace" and _core_content_hits(record) == 0


def _determine_source_route(record: dict[str, Any]) -> str:
  country = _country(record)
  if country in US_COUNTRIES:
    return "us_bigquery_fulltext_candidate"
  if country in MANUAL_ROUTE_COUNTRIES or country:
    return "manual_fulltext_required"
  return "metadata_only"


def _build_quality_flags(record: dict[str, Any]) -> list[str]:
  flags: list[str] = []
  if is_likely_noise(record):
    flags.append("likely_noise")
  if _is_unknown_assignee(record):
    flags.append("unknown_assignee")
  if _strong_noise_hits(record) > 0:
    flags.append("strong_noise_terms")
  if _application_only_thin(record):
    flags.append("application_only_thin")
  if not _has_abstract(record):
    flags.append("missing_abstract")
  if _country(record) not in US_COUNTRIES:
    flags.append("non_us_manual_route")
  if record.get("primary_cluster_id") in FULLTEXT_PRIORITY_CLUSTERS:
    flags.append("priority_cluster")
  if _is_major_assignee(record):
    flags.append("major_assignee")
  return flags


def _build_why_selected_japanese(record: dict[str, Any], route: str) -> str:
  reasons: list[str] = []
  cluster = str(record.get("primary_cluster_id", ""))
  if cluster in FULLTEXT_PRIORITY_CLUSTERS:
    reasons.append(f"技術分類が{translate_cluster_id(cluster)}に該当")
  if _country(record) == "US":
    reasons.append("米国公報でBigQuery全文取得の候補になりやすい")
  elif _country(record) in MANUAL_ROUTE_COUNTRIES:
    reasons.append("非米国公報のためPDFまたは手動確認が必要")
  if _is_major_assignee(record):
    reasons.append("主要炭素繊維関連企業の出願")
  keyword_hits = _priority_keyword_hits(record)
  if keyword_hits >= 2:
    reasons.append(f"PAN・炭化・表面処理などの重要語が{keyword_hits}件")
  if float(record.get("noise_score", 0) or 0) < 0.35:
    reasons.append("ノイズ度が比較的低い")
  if _has_abstract(record):
    reasons.append("要約あり")
  matched_count = len(_as_list(record.get("matched_terms")))
  if matched_count >= 2:
    reasons.append(f"検索語一致が{matched_count}件")
  if not reasons:
    reasons.append("総合スコアが上位")
  reasons.append(explain_source_route(route))
  return "。".join(reasons) + "。"


def _selection_score(record: dict[str, Any]) -> float:
  score = float(record.get("strategic_score", record.get("total_score", 0)) or 0)
  country = _country(record)

  score += float(record.get("fulltext_route_score", 0) or 0) * 0.20
  if country == "US":
    score += 0.15

  cluster = str(record.get("primary_cluster_id", ""))
  if cluster in FULLTEXT_PRIORITY_CLUSTERS:
    score += 0.20

  score += min(0.20, 0.04 * _priority_keyword_hits(record))
  score += min(0.15, 0.03 * _core_content_hits(record))

  if _is_major_assignee(record):
    score += 0.10
  if _has_abstract(record):
    score += 0.05
  score += min(0.08, 0.02 * len(_as_list(record.get("matched_terms"))))

  noise = float(record.get("noise_score", 0) or 0)
  score -= noise * 0.35
  score -= 0.12 * _strong_noise_hits(record)

  if _is_unknown_assignee(record):
    score -= 0.10
  if _application_only_thin(record):
    score -= 0.20
  if is_likely_noise(record):
    score -= 0.50

  return score


def select_top_fulltext_candidates(
  records: list[dict[str, Any]],
  top_n: int = 5,
) -> list[dict[str, Any]]:
  ranked = sorted(records, key=lambda item: float(item.get("total_score", 0)), reverse=True)
  scored_pool: list[tuple[float, dict[str, Any]]] = []

  for record in ranked:
    if str(record.get("claims_source", "")) not in {"", "not_fetched"}:
      continue
    if is_likely_noise(record) and _strong_noise_hits(record) >= 1:
      continue
    if _application_only_thin(record) and _country(record) != "US":
      continue
    scored_pool.append((_selection_score(record), record))

  scored_pool.sort(key=lambda item: item[0], reverse=True)

  us_pool = [(score, record) for score, record in scored_pool if _country(record) == "US"]
  selection_pool = us_pool if us_pool else scored_pool

  selected: list[dict[str, Any]] = []
  assignee_counts: dict[str, int] = {}

  for selection_score, record in selection_pool:
    if len(selected) >= top_n:
      break

    country = _country(record)
    if country != "US" and selection_score < 0.35:
      continue

    assignee_key = str(record.get("assignee", "unknown") or "unknown").lower()
    if assignee_counts.get(assignee_key, 0) >= 2:
      continue

    route = _determine_source_route(record)
    noise_reasons = detect_noise_signals(record)
    noise_categories = detect_noise_categories(record)
    quality_flags = _build_quality_flags(record)

    row = dict(record)
    row["fulltext_candidate_rank"] = len(selected) + 1
    row["selection_score"] = round(selection_score, 4)
    row["source_route"] = route
    row["fulltext_route"] = (
      "us_fulltext_candidate" if route == "us_bigquery_fulltext_candidate" else "manual_pdf_required"
    )
    row["fulltext_priority_reason"] = (
      f"selection_score={round(selection_score, 4)}; cluster={record.get('primary_cluster_id')}; "
      f"country={country}; noise={record.get('noise_score')}"
    )
    row["manual_route_reason"] = (
      ""
      if route == "us_bigquery_fulltext_candidate"
      else f"{country}公報のためPDF/Google Patents等での手動全文確認を推奨"
    )
    row["quality_flags"] = quality_flags
    row["noise_reasons"] = noise_reasons
    row["noise_categories"] = noise_categories
    row["why_selected_japanese"] = _build_why_selected_japanese(record, route)
    row["fulltext_candidate_reason"] = row["fulltext_priority_reason"]
    row["this_list_purpose"] = FULLTEXT_LIST_PURPOSE
    row["not_global_importance_ranking"] = True
    row["caveat_japanese"] = FULLTEXT_CAVEAT_JAPANESE
    row["fulltext_list_explanation_japanese"] = explain_fulltext_priority_top5()
    row["source_route_japanese"] = translate_source_route(route)
    row["next_step"] = (
      "全文取得候補。次フェーズでclaims/description取得"
      if route == "us_bigquery_fulltext_candidate"
      else "PDFまたは手動で全文確認"
    )
    selected.append(row)
    assignee_counts[assignee_key] = assignee_counts.get(assignee_key, 0) + 1

  return selected


def enrich_top_records_for_display(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
  enriched: list[dict[str, Any]] = []
  for record in records:
    row = dict(record)
    route = _determine_source_route(record)
    row["source_route"] = route
    row["source_route_japanese"] = translate_source_route(route)
    row["primary_cluster_japanese"] = translate_cluster_id(str(record.get("primary_cluster_id", "")))
    row["noise_categories"] = detect_noise_categories(record)
    row["quality_flags"] = _build_quality_flags(record)
    if is_likely_noise(record) or float(record.get("noise_score", 0) or 0) >= 0.45:
      row["attention_flag"] = "注意"
    else:
      row["attention_flag"] = ""
    enriched.append(row)
  return enriched
