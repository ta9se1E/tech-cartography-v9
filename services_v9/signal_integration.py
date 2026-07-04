"""Multi-source signal integration helpers for v9."""

from __future__ import annotations

import hashlib
import re
from datetime import date, datetime
from typing import Any, Iterable, Sequence
from urllib.parse import urlparse

from tech_cartography.web_signals.schema import extract_source_domain

from .signal_scoring import classify_action, classify_status
from .watch_profile_schema import normalize_publication_number, normalize_terms

_WORD_PATTERN = re.compile(r"[A-Za-z0-9\u3040-\u30ff\u3400-\u9fff]+")
_DATE_FORMATS = ("%Y-%m-%d", "%Y/%m/%d", "%Y%m%d", "%Y-%m", "%Y/%m", "%Y")
_ACTIONABILITY_HINTS = {
  "patent": 0.65,
  "paper": 0.55,
  "web": 0.62,
  "company": 0.72,
}
_SOURCE_QUALITY_SCORES = {
  "high": 0.95,
  "medium_high": 0.80,
  "medium": 0.65,
  "low": 0.35,
  "unknown": 0.45,
}


def integrate_multi_source_signals(
  *,
  base_signals: list[dict[str, Any]],
  watch_profile: dict[str, Any],
  patent_rows: list[dict[str, Any]] | None = None,
  paper_rows: list[dict[str, Any]] | None = None,
  web_company_rows: list[dict[str, Any]] | None = None,
  max_items: int = 1000,
  ranking_limit: int = 100,
) -> dict[str, Any]:
  integration_run_id = "integration_" + datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
  normalized: list[dict[str, Any]] = []
  normalized.extend(_normalize_base_signals(base_signals, watch_profile, integration_run_id))
  normalized.extend(_normalize_patent_rows(list(patent_rows or []), watch_profile, integration_run_id))
  normalized.extend(_normalize_paper_rows(list(paper_rows or []), watch_profile, integration_run_id))
  normalized.extend(_normalize_web_company_rows(list(web_company_rows or []), watch_profile, integration_run_id))

  capped = normalized[: max(max_items, 0)]
  duplicate_groups = deduplicate_signal_candidates(capped)
  merged = [_merge_duplicate_group(group) for group in duplicate_groups]
  ranked = rank_integrated_signals(merged, top_n=ranking_limit)
  by_source = build_source_top_signals(ranked, top_n=5)
  return {
    "integration_run_id": integration_run_id,
    "raw_count": len(normalized),
    "capped_count": len(capped),
    "deduped_count": len(merged),
    "ranked_count": len(ranked),
    "signals": ranked,
    "top_by_source": by_source,
  }


def deduplicate_signal_candidates(candidates: list[dict[str, Any]]) -> list[list[dict[str, Any]]]:
  groups: list[dict[str, Any]] = []
  for candidate in candidates:
    keys = _duplicate_keys(candidate)
    matching_indexes = [
      index
      for index, group in enumerate(groups)
      if keys & group["keys"]
    ]
    if not matching_indexes:
      groups.append({"keys": set(keys), "items": [candidate]})
      continue
    primary_index = matching_indexes[0]
    groups[primary_index]["items"].append(candidate)
    groups[primary_index]["keys"].update(keys)
    for index in reversed(matching_indexes[1:]):
      groups[primary_index]["items"].extend(groups[index]["items"])
      groups[primary_index]["keys"].update(groups[index]["keys"])
      groups.pop(index)
  return [list(group["items"]) for group in groups]


def rank_integrated_signals(signals: list[dict[str, Any]], top_n: int = 100) -> list[dict[str, Any]]:
  ranked = sorted(
    signals,
    key=lambda signal: (
      -_safe_float(signal.get("final_score")),
      str(signal.get("publication_date", "") or ""),
      str(signal.get("title", "") or ""),
    ),
  )
  selected: list[dict[str, Any]] = []
  org_counts: dict[str, int] = {}
  family_counts: dict[str, int] = {}
  source_counts: dict[str, int] = {}
  group_counts: dict[str, int] = {}

  for signal in ranked:
    if len(selected) >= top_n:
      break
    organization_key = str(signal.get("organization", "") or "").strip().lower()
    family_key = str(signal.get("duplicate_group_family", "") or "").strip().lower()
    source_key = str(signal.get("source_subtype", signal.get("source_type", "")) or "").strip().lower()
    group_key = str(signal.get("duplicate_group", "") or "").strip().lower()
    if organization_key and org_counts.get(organization_key, 0) >= 3:
      continue
    if family_key and family_counts.get(family_key, 0) >= 1:
      continue
    if source_key and source_counts.get(source_key, 0) >= 4:
      continue
    if group_key and group_counts.get(group_key, 0) >= 1:
      continue
    selected.append(dict(signal))
    if organization_key:
      org_counts[organization_key] = org_counts.get(organization_key, 0) + 1
    if family_key:
      family_counts[family_key] = family_counts.get(family_key, 0) + 1
    if source_key:
      source_counts[source_key] = source_counts.get(source_key, 0) + 1
    if group_key:
      group_counts[group_key] = group_counts.get(group_key, 0) + 1

  if len(selected) < min(top_n, len(ranked)):
    seen_ids = {str(signal.get("id", "") or "") for signal in selected}
    for signal in ranked:
      if len(selected) >= top_n:
        break
      if str(signal.get("id", "") or "") in seen_ids:
        continue
      selected.append(dict(signal))
      seen_ids.add(str(signal.get("id", "") or ""))

  for index, signal in enumerate(selected, start=1):
    signal["current_rank"] = index
  return selected


def build_source_top_signals(signals: list[dict[str, Any]], top_n: int = 5) -> dict[str, list[dict[str, Any]]]:
  grouped: dict[str, list[dict[str, Any]]] = {"patent": [], "paper": [], "web": [], "company": []}
  for signal in signals:
    signal_type = str(signal.get("type", "") or "").strip().lower()
    grouped.setdefault(signal_type, []).append(dict(signal))
  return {
    source_type: rows[:max(top_n, 0)]
    for source_type, rows in grouped.items()
  }


def apply_signal_change_tracking(
  current_signals: list[dict[str, Any]],
  previous_signals: list[dict[str, Any]],
) -> list[dict[str, Any]]:
  previous_index = {
    str(signal.get("id", signal.get("signal_id", "")) or "").strip(): dict(signal)
    for signal in previous_signals
    if str(signal.get("id", signal.get("signal_id", "")) or "").strip()
  }
  previous_rank_map = {
    signal_id: int(previous.get("current_rank", index))
    for index, (signal_id, previous) in enumerate(previous_index.items(), start=1)
  }
  updated: list[dict[str, Any]] = []
  for index, signal in enumerate(current_signals, start=1):
    copied = dict(signal)
    signal_id = str(copied.get("id", copied.get("signal_id", "")) or "").strip()
    previous = previous_index.get(signal_id)
    previous_rank = previous_rank_map.get(signal_id)
    previous_score = _safe_optional_float(previous.get("final_score")) if previous else None
    current_score = _safe_float(copied.get("final_score", copied.get("score")))
    copied["current_rank"] = int(copied.get("current_rank", index) or index)
    copied["previous_rank"] = previous_rank
    copied["previous_score"] = previous_score
    copied["status"] = classify_status(current_score, previous_score)
    copied["action"] = classify_action(current_score, copied["status"])
    copied["change_status"] = _classify_change_status(copied, previous)
    updated.append(copied)
  return updated


def _normalize_base_signals(
  base_signals: list[dict[str, Any]],
  watch_profile: dict[str, Any],
  integration_run_id: str,
) -> list[dict[str, Any]]:
  normalized: list[dict[str, Any]] = []
  for signal in base_signals:
    title = str(signal.get("title", "") or "").strip()
    summary = str(signal.get("summary", "") or "").strip()
    source_type = str(signal.get("type", "") or "web").strip().lower()
    base_score = _safe_float(signal.get("score"))
    normalized_signal = dict(signal)
    signal_id = str(signal.get("id", "") or "").strip() or _stable_signal_id(source_type, title, str(signal.get("source_url", "") or ""), str(signal.get("published_date", "") or ""))
    relevance = _clip_score(base_score)
    novelty = _clip_score(0.60 if str(signal.get("status", "") or "") in {"New", "Rising"} else 0.45)
    actionability = _clip_score(0.80 if str(signal.get("action", "") or "") == "Read Now" else 0.60 if str(signal.get("action", "") or "") == "Watch" else 0.30)
    recency = _recency_score(str(signal.get("published_date", "") or ""))
    final_score = _weighted_final_score(relevance, novelty, actionability, recency)
    normalized_signal.update(
      {
        "id": signal_id,
        "signal_id": signal_id,
        "source_type": source_type,
        "run_id": integration_run_id,
        "source_subtype": "base_signal",
        "external_id": signal_id,
        "retrieved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "record_stage": "base",
        "retrieval_mode": "local",
        "organization": _pick_first(signal.get("companies", [])),
        "country_region": "",
        "original_language": str(signal.get("language", "") or ""),
        "original_text_or_snippet": summary,
        "source_quality": "medium",
        "relevance_score": relevance,
        "novelty_score": novelty,
        "actionability_score": actionability,
        "recency_score": recency,
        "final_score": final_score,
        "query_id": "",
        "source_trace": [
          {
            "source_type": source_type,
            "source_subtype": "base_signal",
            "external_id": signal_id,
            "query_id": "",
            "provider_status": "success",
            "data_origin": "base_signal",
            "source_url": str(signal.get("source_url", "") or ""),
          }
        ],
        "duplicate_group": f"dup_{hashlib.sha1(signal_id.encode('utf-8')).hexdigest()[:10]}",
        "duplicate_group_family": "",
        "data_origin": "base_signal",
        "score": final_score,
      }
    )
    normalized_signal.setdefault("why_read", f"{title} は監視テーマとの関連度が高く、既存Signalとして継続監視する価値があります。")
    normalized_signal.setdefault("what_to_check", f"{title} の出典・日付・関連企業を確認してください。")
    normalized_signal.setdefault("next_action", f"{title} を確認して、監視テーマとの関係をメモしてください。")
    normalized.append(normalized_signal)
  return normalized


def _normalize_patent_rows(
  rows: list[dict[str, Any]],
  watch_profile: dict[str, Any],
  integration_run_id: str,
) -> list[dict[str, Any]]:
  normalized: list[dict[str, Any]] = []
  for row in rows:
    publication_number = normalize_publication_number(str(row.get("publication_number", "") or ""))
    title = str(row.get("title", "") or "").strip() or publication_number
    summary = str(row.get("abstract", "") or "").strip()
    organization = str(row.get("assignee", "") or "").strip()
    source_quality = "high" if str(row.get("provider_status", "") or "") == "success" else "medium"
    relevance = _keyword_relevance_score(watch_profile, title, summary, [organization], [str(row.get("cpc_codes", "") or "")])
    novelty = _novelty_score(
      has_identifier=bool(publication_number),
      is_duplicate=bool(row.get("family_duplicate_candidate")),
      base=0.62,
    )
    actionability = _clip_score(_ACTIONABILITY_HINTS["patent"] + (0.08 if organization else 0.0))
    recency = _recency_score(str(row.get("publication_date", "") or ""))
    final_score = _weighted_final_score(relevance, novelty, actionability, recency)
    signal_id = _stable_signal_id("patent", publication_number or title, str(row.get("family_id", "") or ""), str(row.get("query_id", "") or ""))
    normalized.append(
      {
        "id": signal_id,
        "signal_id": signal_id,
        "title": title,
        "type": "patent",
        "source_type": "patent",
        "source_url": str(row.get("source_url", "") or ""),
        "source_name": "BigQuery Patent",
        "published_date": str(row.get("publication_date", "") or ""),
        "summary": summary,
        "score": final_score,
        "previous_score": None,
        "status": "New",
        "action": classify_action(final_score, "New"),
        "why_read": f"{organization or '関連出願'} の特許候補で、監視テーマとの関連度と新規性を確認しやすいためです。",
        "what_to_check": "公開番号、ファミリー重複、CPC、出願人、公開日を確認してください。",
        "next_action": "要約を読み、重要出願なら週次ダイジェスト候補に残してください。",
        "tags": normalize_terms([str(row.get("cpc_codes", "") or ""), publication_number]),
        "companies": normalize_terms([organization]),
        "language": _language_from_country(str(row.get("country", "") or "")),
        "memo": "",
        "run_id": integration_run_id,
        "source_subtype": "bigquery_patent",
        "external_id": publication_number or str(row.get("candidate_id", "") or ""),
        "retrieved_at": _retrieved_at_from_run_id(str(row.get("retrieval_run_id", "") or "")),
        "record_stage": str(row.get("record_stage", "staged") or "staged"),
        "retrieval_mode": str(row.get("retrieval_mode", "real") or "real"),
        "organization": organization,
        "country_region": str(row.get("country", "") or ""),
        "original_language": _language_from_country(str(row.get("country", "") or "")),
        "original_text_or_snippet": summary,
        "source_quality": source_quality,
        "relevance_score": relevance,
        "novelty_score": novelty,
        "actionability_score": actionability,
        "recency_score": recency,
        "final_score": final_score,
        "current_rank": None,
        "previous_rank": None,
        "change_status": "New",
        "query_id": str(row.get("query_id", "") or ""),
        "source_trace": [
          {
            "source_type": "patent",
            "source_subtype": "bigquery_patent",
            "external_id": publication_number or str(row.get("candidate_id", "") or ""),
            "query_id": str(row.get("query_id", "") or ""),
            "provider_status": str(row.get("provider_status", "") or ""),
            "retrieval_run_id": str(row.get("retrieval_run_id", "") or ""),
            "bigquery_job_id": str(row.get("bigquery_job_id", "") or ""),
            "source_url": str(row.get("source_url", "") or ""),
          }
        ],
        "duplicate_group": "",
        "duplicate_group_family": str(row.get("family_id", "") or ""),
        "data_origin": str(row.get("data_source", "bigquery_patent") or "bigquery_patent"),
      }
    )
  return normalized


def _normalize_paper_rows(
  rows: list[dict[str, Any]],
  watch_profile: dict[str, Any],
  integration_run_id: str,
) -> list[dict[str, Any]]:
  normalized: list[dict[str, Any]] = []
  for row in rows:
    title = str(row.get("title", "") or "").strip()
    summary = str(row.get("abstract", "") or "").strip()
    organization = _pick_first(row.get("institutions", []))
    source_quality = _paper_source_quality(row)
    relevance = _keyword_relevance_score(
      watch_profile,
      title,
      summary,
      list(row.get("authors", []) or []) + list(row.get("institutions", []) or []),
      list(row.get("topics", []) or []),
    )
    novelty = _novelty_score(
      has_identifier=bool(str(row.get("doi", "") or "").strip() or str(row.get("work_id", "") or "").strip()),
      is_duplicate=False,
      base=0.68,
    )
    actionability = _clip_score(_ACTIONABILITY_HINTS["paper"] + (0.08 if int(row.get("cited_by_count", 0) or 0) >= 10 else 0.0))
    recency = _recency_score(str(row.get("publication_date", "") or ""))
    final_score = _weighted_final_score(relevance, novelty, actionability, recency)
    external_id = str(row.get("doi", "") or "").strip() or str(row.get("work_id", "") or "").strip()
    signal_id = _stable_signal_id("paper", external_id or title, str(row.get("query_id", "") or ""), str(row.get("source_url", "") or ""))
    normalized.append(
      {
        "id": signal_id,
        "signal_id": signal_id,
        "title": title,
        "type": "paper",
        "source_type": "paper",
        "source_url": str(row.get("source_url", "") or ""),
        "source_name": str(row.get("source_journal", "") or "OpenAlex").strip() or "OpenAlex",
        "published_date": str(row.get("publication_date", "") or ""),
        "summary": summary,
        "score": final_score,
        "previous_score": None,
        "status": "New",
        "action": classify_action(final_score, "New"),
        "why_read": "監視テーマに近い論文候補で、技術的背景や検証観点を補強しやすいためです。",
        "what_to_check": "DOI、著者、所属、掲載誌、引用数、要旨を確認してください。",
        "next_action": "必要なら論文要旨を読み、次回の監視キーワード更新候補をメモしてください。",
        "tags": normalize_terms(list(row.get("topics", []) or [])),
        "companies": normalize_terms([organization]),
        "language": str(row.get("original_language", "") or ""),
        "memo": "",
        "run_id": integration_run_id,
        "source_subtype": "openalex_paper",
        "external_id": external_id,
        "retrieved_at": _retrieved_at_from_run_id(str(row.get("retrieval_run_id", "") or "")),
        "record_stage": str(row.get("record_stage", "staged") or "staged"),
        "retrieval_mode": str(row.get("retrieval_mode", "real") or "real"),
        "organization": organization,
        "country_region": "",
        "original_language": str(row.get("original_language", "") or ""),
        "original_text_or_snippet": summary,
        "source_quality": source_quality,
        "relevance_score": relevance,
        "novelty_score": novelty,
        "actionability_score": actionability,
        "recency_score": recency,
        "final_score": final_score,
        "current_rank": None,
        "previous_rank": None,
        "change_status": "New",
        "query_id": str(row.get("query_id", "") or ""),
        "source_trace": [
          {
            "source_type": "paper",
            "source_subtype": "openalex_paper",
            "external_id": external_id,
            "query_id": str(row.get("query_id", "") or ""),
            "provider_status": str(row.get("provider_status", "") or ""),
            "retrieval_run_id": str(row.get("retrieval_run_id", "") or ""),
            "source_url": str(row.get("source_url", "") or ""),
          }
        ],
        "duplicate_group": "",
        "duplicate_group_family": "",
        "data_origin": "openalex_paper",
      }
    )
  return normalized


def _normalize_web_company_rows(
  rows: list[dict[str, Any]],
  watch_profile: dict[str, Any],
  integration_run_id: str,
) -> list[dict[str, Any]]:
  normalized: list[dict[str, Any]] = []
  for row in rows:
    source_type = "company" if str(row.get("result_bucket", "") or "") == "company" else "web"
    title = str(row.get("original_title", "") or "").strip()
    summary = str(row.get("summary_ja", "") or str(row.get("original_snippet", "") or "")).strip()
    organization = str(row.get("organization", "") or "").strip()
    source_quality = str(row.get("source_quality", "") or "unknown")
    relevance = _keyword_relevance_score(
      watch_profile,
      title,
      str(row.get("original_text_or_snippet", row.get("original_snippet", "")) or ""),
      [organization],
      [str(row.get("event_type", "") or ""), str(row.get("country_region", "") or "")],
    )
    novelty = _novelty_score(
      has_identifier=bool(str(row.get("canonical_url", "") or "").strip() or str(row.get("source_url", "") or "").strip()),
      is_duplicate=False,
      base=0.58 if source_type == "web" else 0.64,
    )
    actionability = _clip_score(_ACTIONABILITY_HINTS[source_type] + (0.08 if str(row.get("content_access", "") or "") == "full" else 0.0))
    recency = _recency_score(str(row.get("publication_date", "") or ""))
    final_score = _weighted_final_score(relevance, novelty, actionability, recency)
    external_id = str(row.get("canonical_url", "") or row.get("source_url", "") or row.get("candidate_id", "")).strip()
    signal_id = _stable_signal_id(source_type, external_id or title, str(row.get("query_id", "") or ""), str(row.get("same_story_group", "") or ""))
    normalized.append(
      {
        "id": signal_id,
        "signal_id": signal_id,
        "title": title,
        "type": source_type,
        "source_type": source_type,
        "source_url": str(row.get("canonical_url", "") or row.get("source_url", "") or ""),
        "source_name": organization or extract_source_domain(str(row.get("source_url", "") or "")) or "Global Web",
        "published_date": str(row.get("publication_date", "") or ""),
        "summary": summary,
        "score": final_score,
        "previous_score": None,
        "status": "New",
        "action": classify_action(final_score, "New"),
        "why_read": f"{organization or '関連組織'} に関する {str(row.get('event_type', '') or 'シグナル')} 候補で、事業・研究の動きを追いやすいためです。",
        "what_to_check": "原典URL、組織名、国・地域、イベント種別、本文アクセス可否を確認してください。",
        "next_action": "一次情報なら保存し、同一ニュース群の重複を避けながら要点を比較してください。",
        "tags": normalize_terms([str(row.get("event_type", "") or ""), str(row.get("country_region", "") or "")]),
        "companies": normalize_terms([organization]),
        "language": str(row.get("original_language", "") or ""),
        "memo": "",
        "run_id": integration_run_id,
        "source_subtype": f"global_{source_type}",
        "external_id": external_id,
        "retrieved_at": _retrieved_at_from_run_id(str(row.get("retrieval_run_id", "") or "")),
        "record_stage": str(row.get("record_stage", "staged") or "staged"),
        "retrieval_mode": str(row.get("retrieval_mode", "real") or "real"),
        "organization": organization,
        "country_region": str(row.get("country_region", "") or ""),
        "original_language": str(row.get("original_language", "") or ""),
        "original_text_or_snippet": str(row.get("original_snippet", "") or ""),
        "source_quality": source_quality,
        "relevance_score": relevance,
        "novelty_score": novelty,
        "actionability_score": actionability,
        "recency_score": recency,
        "final_score": final_score,
        "current_rank": None,
        "previous_rank": None,
        "change_status": "New",
        "query_id": str(row.get("query_id", "") or ""),
        "source_trace": [
          {
            "source_type": source_type,
            "source_subtype": f"global_{source_type}",
            "external_id": external_id,
            "query_id": str(row.get("query_id", "") or ""),
            "provider_status": str(row.get("provider_status", "") or ""),
            "retrieval_run_id": str(row.get("retrieval_run_id", "") or ""),
            "source_url": str(row.get("source_url", "") or ""),
            "same_story_group": str(row.get("same_story_group", "") or ""),
          }
        ],
        "duplicate_group": str(row.get("same_story_group", "") or ""),
        "duplicate_group_family": "",
        "data_origin": f"global_{source_type}",
      }
    )
  return normalized


def _merge_duplicate_group(group: list[dict[str, Any]]) -> dict[str, Any]:
  ordered = sorted(
    group,
    key=lambda signal: (
      -_safe_float(signal.get("final_score")),
      -_safe_float(signal.get("relevance_score")),
      str(signal.get("title", "") or ""),
    ),
  )
  primary = dict(ordered[0])
  trace: list[dict[str, Any]] = []
  organizations: list[str] = []
  tags: list[str] = []
  companies: list[str] = []
  source_types: list[str] = []
  duplicate_group_family = ""
  for item in ordered:
    trace.extend(list(item.get("source_trace", []) or []))
    organizations.extend(normalize_terms([str(item.get("organization", "") or "")]))
    tags.extend(list(item.get("tags", []) or []))
    companies.extend(list(item.get("companies", []) or []))
    source_types.append(str(item.get("type", "") or ""))
    if not duplicate_group_family and str(item.get("duplicate_group_family", "") or "").strip():
      duplicate_group_family = str(item.get("duplicate_group_family", "") or "").strip()
  primary["tags"] = normalize_terms(tags)
  primary["companies"] = normalize_terms(companies or organizations)
  primary["organization"] = _pick_first(companies or organizations)
  primary["source_trace"] = trace
  primary["duplicate_group_family"] = duplicate_group_family
  primary["duplicate_group"] = _build_duplicate_group_id(group)
  primary["data_origin"] = "integrated_multi_source" if len(set(source_types)) > 1 else str(primary.get("data_origin", "") or "")
  primary["query_id"] = str(primary.get("query_id", "") or _pick_first([item.get("query_id", "") for item in ordered]))
  primary["signal_id"] = primary.get("id", "")
  primary["score"] = _safe_float(primary.get("final_score", primary.get("score")))
  return primary


def _build_duplicate_group_id(group: list[dict[str, Any]]) -> str:
  if not group:
    return "dup_empty"
  preferred = str(group[0].get("duplicate_group", "") or "").strip()
  if preferred:
    return preferred if preferred.startswith("dup_") else f"dup_{hashlib.sha1(preferred.encode('utf-8')).hexdigest()[:10]}"
  raw = "|".join(sorted(str(item.get("id", "") or "") for item in group))
  return "dup_" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:10]


def _duplicate_keys(signal: dict[str, Any]) -> set[str]:
  keys: set[str] = set()
  if str(signal.get("type", "") or "") == "patent":
    publication_number = normalize_publication_number(str(signal.get("external_id", "") or ""))
    if publication_number:
      keys.add(f"pub:{publication_number}")
    family = str(signal.get("duplicate_group_family", "") or "").strip()
    if family:
      keys.add(f"family:{family.lower()}")
  doi = str(signal.get("external_id", "") or "").strip().lower()
  if str(signal.get("type", "") or "") == "paper" and doi:
    keys.add(f"doi:{doi}")
  source_url = str(signal.get("source_url", "") or "").strip()
  if source_url:
    keys.add(f"url:{_normalize_url_key(source_url)}")
  original_text = str(signal.get("original_text_or_snippet", "") or "").strip()
  if original_text:
    keys.add(f"hash:{hashlib.sha1(original_text.lower().encode('utf-8')).hexdigest()[:16]}")
  duplicate_group = str(signal.get("duplicate_group", "") or "").strip()
  if duplicate_group:
    keys.add(f"group:{duplicate_group.lower()}")
  title_key = _title_similarity_key(str(signal.get("title", "") or ""))
  if title_key:
    keys.add(f"title:{title_key}")
  return keys


def _keyword_relevance_score(
  watch_profile: dict[str, Any],
  title: str,
  summary: str,
  organizations: Sequence[str],
  extra_terms: Sequence[str],
) -> float:
  profile_keywords = watch_profile.get("keywords", {}) if isinstance(watch_profile, dict) else {}
  core_terms = normalize_terms(
    list(profile_keywords.get("core_en", []) or [])
    + list(profile_keywords.get("core_ja", []) or [])
  )
  material_terms = normalize_terms(
    list(profile_keywords.get("material_process_en", []) or [])
    + list(profile_keywords.get("material_process_ja", []) or [])
  )
  application_terms = normalize_terms(
    list(profile_keywords.get("application_en", []) or [])
    + list(profile_keywords.get("application_ja", []) or [])
  )
  exclude_terms = normalize_terms(
    list(profile_keywords.get("exclude_en", []) or [])
    + list(profile_keywords.get("exclude_ja", []) or [])
  )
  target_companies = normalize_terms(list(watch_profile.get("target_companies", []) or [])) if isinstance(watch_profile, dict) else []
  searchable = "\n".join([title, summary, *organizations, *extra_terms]).lower()
  score = 0.35
  if _count_hits(core_terms, searchable):
    score += 0.25
  if _count_hits(material_terms, searchable):
    score += 0.15
  if _count_hits(application_terms, searchable):
    score += 0.10
  if _count_hits(target_companies, searchable):
    score += 0.10
  if _count_hits(exclude_terms, searchable):
    score -= 0.30
  return _clip_score(score)


def _count_hits(terms: Iterable[str], searchable: str) -> int:
  return sum(1 for term in terms if term and term.lower() in searchable)


def _novelty_score(*, has_identifier: bool, is_duplicate: bool, base: float) -> float:
  score = base + (0.08 if has_identifier else 0.0) - (0.20 if is_duplicate else 0.0)
  return _clip_score(score)


def _paper_source_quality(row: dict[str, Any]) -> str:
  cited_by = int(row.get("cited_by_count", 0) or 0)
  if cited_by >= 20:
    return "high"
  if cited_by >= 5:
    return "medium_high"
  return "medium"


def _recency_score(published_date: str) -> float:
  parsed = _parse_date(published_date)
  if parsed is None:
    return 0.45
  days = max((date.today() - parsed).days, 0)
  months = days / 30.0
  score = 1.0 / (1.0 + months / 6.0)
  return _clip_score(score)


def _parse_date(value: str) -> date | None:
  text = str(value or "").strip()
  if not text:
    return None
  for fmt in _DATE_FORMATS:
    try:
      parsed = datetime.strptime(text, fmt)
      if fmt == "%Y":
        return date(parsed.year, 1, 1)
      if fmt in {"%Y-%m", "%Y/%m"}:
        return date(parsed.year, parsed.month, 1)
      return parsed.date()
    except ValueError:
      continue
  return None


def _weighted_final_score(relevance: float, novelty: float, actionability: float, recency: float) -> float:
  return _clip_score((relevance * 0.40) + (novelty * 0.20) + (actionability * 0.25) + (recency * 0.15))


def _language_from_country(country: str) -> str:
  code = str(country or "").strip().upper()
  if code == "JP":
    return "ja"
  if code:
    return "en"
  return ""


def _title_similarity_key(title: str) -> str:
  tokens = [match.group(0).lower() for match in _WORD_PATTERN.finditer(str(title or ""))]
  return " ".join(tokens[:10])


def _normalize_url_key(url: str) -> str:
  text = str(url or "").strip()
  if not text:
    return ""
  parsed = urlparse(text if "://" in text else f"https://{text}")
  host = (parsed.netloc or parsed.path or "").lower()
  if host.startswith("www."):
    host = host[4:]
  path = parsed.path if parsed.netloc else ""
  if path.endswith("/") and path != "/":
    path = path[:-1]
  return f"{host}{path}"


def _stable_signal_id(*parts: str) -> str:
  raw = "||".join(str(part or "").strip() for part in parts if str(part or "").strip())
  if not raw:
    raw = "empty-signal"
  return "sig_" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


def _clip_score(value: float) -> float:
  return max(0.0, min(1.0, value))


def _pick_first(values: Sequence[Any]) -> str:
  for value in values:
    text = str(value or "").strip()
    if text:
      return text
  return ""


def _retrieved_at_from_run_id(run_id: str) -> str:
  text = str(run_id or "").strip()
  if not text:
    return datetime.now().astimezone().isoformat(timespec="seconds")
  match = re.search(r"(\d{8})_(\d{6})$", text)
  if not match:
    return datetime.now().astimezone().isoformat(timespec="seconds")
  raw = match.group(1) + match.group(2)
  try:
    parsed = datetime.strptime(raw, "%Y%m%d%H%M%S").astimezone()
    return parsed.isoformat(timespec="seconds")
  except ValueError:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def _safe_float(value: Any) -> float:
  try:
    return float(value)
  except (TypeError, ValueError):
    return 0.0


def _safe_optional_float(value: Any) -> float | None:
  if value in {None, ""}:
    return None
  try:
    return float(value)
  except (TypeError, ValueError):
    return None


def _classify_change_status(current: dict[str, Any], previous: dict[str, Any] | None) -> str:
  if previous is None:
    return "New"
  previous_rank = current.get("previous_rank")
  current_rank = current.get("current_rank")
  if previous_rank is not None and current_rank is not None:
    try:
      if int(current_rank) < int(previous_rank):
        return "Rising"
      if int(current_rank) > int(previous_rank):
        return "Dropped"
    except (TypeError, ValueError):
      pass
  current_hash = hashlib.sha1(
    ("\n".join([
      str(current.get("title", "") or ""),
      str(current.get("summary", "") or ""),
      str(current.get("original_text_or_snippet", "") or ""),
      str(current.get("source_url", "") or ""),
    ])).encode("utf-8")
  ).hexdigest()
  previous_hash = hashlib.sha1(
    ("\n".join([
      str(previous.get("title", "") or ""),
      str(previous.get("summary", "") or ""),
      str(previous.get("original_text_or_snippet", "") or ""),
      str(previous.get("source_url", "") or ""),
    ])).encode("utf-8")
  ).hexdigest()
  if current_hash != previous_hash:
    return "Updated"
  return "Stable"


__all__ = [
  "apply_signal_change_tracking",
  "build_source_top_signals",
  "deduplicate_signal_candidates",
  "integrate_multi_source_signals",
  "rank_integrated_signals",
]
