"""Downstream tab helpers for Study Demo active search run connection."""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

from services_v9.study_demo_config import get_study_demo_bucket
from services_v9.study_demo_storage import validate_study_demo_write_target

REVIEWS_PREFIX = "analysis_context/reviews/"
PROFILE_DRAFTS_PREFIX = "analysis_context/profile_drafts/"
SNAPSHOTS_PREFIX = "analysis_snapshots/"
TIER_ORDER = {"A": 0, "B": 1, "C": 2, "D": 3}


def build_what_to_check(signal: Mapping[str, Any]) -> str:
  source_type = str(signal.get("source_type", "") or "")
  summary = str(signal.get("summary", "") or "")
  title = str(signal.get("title", "") or "")
  blob = f"{title} {summary}".lower()
  if source_type == "patent":
    parts = ["独立請求項相当の範囲", "組成"]
    for term in ("sizing amount", "add-on", "drying", "curing", "matrix"):
      if term.replace("-", " ") in blob or term in blob:
        parts.append(term)
    if "example" in blob or "embodiment" in blob or "実施例" in blob:
      parts.append("実施例有無")
    return " / ".join(parts)
  if source_type == "paper":
    parts = ["評価法", "試料条件"]
    for term in ("interfacial", "tensile", "modulus", "doi"):
      if term in blob:
        parts.append(term)
    return " / ".join(parts)
  parts = ["一次情報か二次情報か", "企業名", "日付"]
  if any(token in blob for token in ("production", "investment", "research")):
    parts.append("量産/研究/投資の区別")
  return " / ".join(parts)


def build_next_action(signal: Mapping[str, Any]) -> str:
  tier = str(signal.get("relevance_tier", "") or "")
  source_type = str(signal.get("source_type", "") or "")
  if tier == "A" and source_type == "patent":
    return "請求項と実施例を確認し、サイジング組成・付与量・乾燥条件の記載を抽出する"
  if tier == "A" and source_type == "paper":
    return "評価条件と界面/引張物性データを確認する"
  if tier in {"A", "B"}:
    return "relevance_reasonに沿って本文を精読する"
  return "背景理解として参照し、直接証拠かどうかを確認する"


def select_top_reads_from_active_signals(signals: Sequence[Mapping[str, Any]], *, limit: int = 3) -> list[dict[str, Any]]:
  ranked = sorted(
    list(signals),
    key=lambda row: (
      TIER_ORDER.get(str(row.get("relevance_tier", "D")), 99),
      -float(row.get("relevance_score", 0) or 0),
      str(row.get("title", "")),
    ),
  )
  tier_a = [item for item in ranked if str(item.get("relevance_tier", "")) == "A"]
  pool = tier_a or ranked
  selected: list[dict[str, Any]] = []
  used_sources: set[str] = set()
  source_order = ("patent", "paper", "web_company")
  for source in source_order:
    for item in pool:
      if str(item.get("source_type", "")) != source:
        continue
      if float(item.get("relevance_score", 0) or 0) < 35 and tier_a:
        continue
      selected.append(dict(item))
      used_sources.add(source)
      break
  for item in pool:
    if len(selected) >= limit:
      break
    if any(str(item.get("signal_id", "")) == str(existing.get("signal_id", "")) for existing in selected):
      continue
    selected.append(dict(item))
  return selected[:limit]


def _review_object_path(search_run_id: str) -> str:
  safe = re.sub(r"[^A-Za-z0-9._-]+", "_", str(search_run_id or ""))
  return f"{REVIEWS_PREFIX}{safe}.json"


def load_run_reviews(
  search_run_id: str,
  *,
  storage_client: Any | None = None,
  environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
  bucket_name = get_study_demo_bucket(environ)
  validate_study_demo_write_target(bucket_name, environ=environ)
  client = storage_client if storage_client is not None else _build_client()
  blob = client.bucket(bucket_name).blob(_review_object_path(search_run_id))
  if not blob.exists():
    return {"search_run_id": search_run_id, "reviews": [], "updated_at": None}
  payload = json.loads(blob.download_as_bytes().decode("utf-8"))
  return dict(payload)


def save_run_review(
  *,
  search_run_id: str,
  signal_id: str,
  decision: str,
  comment: str,
  context_generation: int | None = None,
  storage_client: Any | None = None,
  environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
  bucket_name = get_study_demo_bucket(environ)
  validate_study_demo_write_target(bucket_name, environ=environ)
  existing = load_run_reviews(search_run_id, storage_client=storage_client, environ=environ)
  reviews = [item for item in list(existing.get("reviews", []) or []) if str(item.get("signal_id", "")) != signal_id]
  reviews.append(
    {
      "signal_id": signal_id,
      "decision": decision,
      "comment": comment,
      "reviewed_at": datetime.now(timezone.utc).isoformat(),
      "context_generation": context_generation,
      "source_run_id": search_run_id,
    }
  )
  payload = {"search_run_id": search_run_id, "reviews": reviews, "updated_at": datetime.now(timezone.utc).isoformat()}
  client = storage_client if storage_client is not None else _build_client()
  blob = client.bucket(bucket_name).blob(_review_object_path(search_run_id))
  blob.upload_from_string(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", content_type="application/json")
  return payload


def summarize_run_reviews(reviews_payload: Mapping[str, Any], signal_ids: Sequence[str]) -> dict[str, int]:
  by_id = {str(item.get("signal_id", "")): item for item in list(reviews_payload.get("reviews", []) or [])}
  summary = {"accepted": 0, "pending": 0, "rejected": 0, "unreviewed": 0}
  for signal_id in signal_ids:
    item = by_id.get(str(signal_id))
    if not item:
      summary["unreviewed"] += 1
      continue
    decision = str(item.get("decision", "") or "")
    if decision in {"accepted", "採用"}:
      summary["accepted"] += 1
    elif decision in {"rejected", "見送り"}:
      summary["rejected"] += 1
    elif decision in {"pending", "保留"}:
      summary["pending"] += 1
    else:
      summary["unreviewed"] += 1
  return summary


def theme_signature(theme: str) -> str:
  normalized = re.sub(r"\s+", " ", str(theme or "").strip().lower())
  return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:16]


def _snapshot_object_path(profile_signature: str, snapshot_id: str) -> str:
  return f"{SNAPSHOTS_PREFIX}{profile_signature}/{snapshot_id}.json"


def list_run_snapshots(
  profile_signature: str,
  *,
  storage_client: Any | None = None,
  environ: Mapping[str, str] | None = None,
) -> list[dict[str, Any]]:
  bucket_name = get_study_demo_bucket(environ)
  client = storage_client if storage_client is not None else _build_client()
  prefix = f"{SNAPSHOTS_PREFIX}{profile_signature}/"
  items: list[dict[str, Any]] = []
  for blob in client.bucket(bucket_name).list_blobs(prefix=prefix):
    if not str(blob.name or "").endswith(".json"):
      continue
    payload = json.loads(blob.download_as_bytes().decode("utf-8"))
    items.append(payload)
  return sorted(items, key=lambda row: str(row.get("created_at", "")), reverse=True)


def save_baseline_snapshot(
  *,
  context: Mapping[str, Any],
  integrated: Mapping[str, Any],
  profile_signature: str,
  storage_client: Any | None = None,
  environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
  bucket_name = get_study_demo_bucket(environ)
  validate_study_demo_write_target(bucket_name, environ=environ)
  snapshot_id = f"snapshot_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:8]}"
  signals = list(integrated.get("signals", []) or [])
  payload = {
    "snapshot_id": snapshot_id,
    "source_run_id": str(context.get("active_search_run_id", "")),
    "theme_signature": profile_signature,
    "theme": str(context.get("theme", "")),
    "created_at": datetime.now(timezone.utc).isoformat(),
    "signal_keys": [_stable_signal_key(item) for item in signals],
    "signals": [
      {
        "signal_key": _stable_signal_key(item),
        "signal_id": item.get("signal_id"),
        "relevance_score": item.get("relevance_score"),
        "relevance_tier": item.get("relevance_tier"),
        "source_type": item.get("source_type"),
        "title": item.get("title"),
      }
      for item in signals
    ],
    "provider_counts": dict(context.get("provider_counts", {}) or {}),
    "tier_counts": dict(context.get("tier_counts", {}) or {}),
  }
  client = storage_client if storage_client is not None else _build_client()
  blob = client.bucket(bucket_name).blob(_snapshot_object_path(profile_signature, snapshot_id))
  blob.upload_from_string(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", content_type="application/json")
  return payload


def _normalize_url(url: str) -> str:
  parsed = urlparse(str(url or "").strip())
  host = (parsed.netloc or "").lower()
  path = re.sub(r"/+", "/", parsed.path or "/")
  return f"{host}{path.rstrip('/')}"


def _stable_signal_key(signal: Mapping[str, Any]) -> str:
  source_type = str(signal.get("source_type", "") or "")
  metadata = dict(signal.get("metadata", {}) or {})
  if source_type == "patent":
    family = str(signal.get("family_id", "") or "")
    if family:
      return f"patent:family:{family}"
    return f"patent:pub:{signal.get('source_id', '')}"
  if source_type == "paper":
    doi = str(metadata.get("doi", "") or "")
    if doi:
      return f"paper:doi:{doi.lower()}"
    return f"paper:work:{signal.get('source_id', '')}"
  if source_type == "web_company":
    url = _normalize_url(str(signal.get("url", "") or ""))
    if url:
      return f"web:url:{url}"
  return f"signal:{signal.get('signal_id', '')}"


def compare_active_run_snapshots(
  previous: Mapping[str, Any],
  current_signals: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
  prev_map = {str(item.get("signal_key", "")): item for item in list(previous.get("signals", []) or [])}
  curr_items = [
    {
      "signal_key": _stable_signal_key(item),
      "signal_id": item.get("signal_id"),
      "relevance_score": item.get("relevance_score"),
      "relevance_tier": item.get("relevance_tier"),
      "source_type": item.get("source_type"),
      "title": item.get("title"),
    }
    for item in current_signals
  ]
  curr_map = {str(item["signal_key"]): item for item in curr_items}
  changes: list[dict[str, Any]] = []
  for key, item in curr_map.items():
    prev = prev_map.get(key)
    if not prev:
      changes.append({**item, "change": "new"})
      continue
    prev_score = float(prev.get("relevance_score", 0) or 0)
    curr_score = float(item.get("relevance_score", 0) or 0)
    prev_tier = str(prev.get("relevance_tier", ""))
    curr_tier = str(item.get("relevance_tier", ""))
    if curr_score > prev_score:
      changes.append({**item, "change": "score_up", "previous_score": prev_score})
    elif curr_score < prev_score:
      changes.append({**item, "change": "score_down", "previous_score": prev_score})
    elif curr_tier != prev_tier:
      changes.append({**item, "change": "tier_change", "previous_tier": prev_tier})
    else:
      changes.append({**item, "change": "unchanged"})
  disappeared = [prev_map[key] for key in prev_map if key not in curr_map]
  buckets: dict[str, list[dict[str, Any]]] = {
    "new": [],
    "disappeared": [],
    "score_up": [],
    "score_down": [],
    "tier_up": [],
    "tier_down": [],
    "unchanged": [],
  }
  for item in changes:
    change = str(item.get("change", ""))
    if change == "tier_change":
      prev_tier = str(item.get("previous_tier", ""))
      curr_tier = str(item.get("relevance_tier", ""))
      if TIER_ORDER.get(curr_tier, 99) < TIER_ORDER.get(prev_tier, 99):
        buckets["tier_up"].append(item)
      else:
        buckets["tier_down"].append(item)
    elif change in buckets:
      buckets[change].append(item)
  buckets["disappeared"] = [dict(item, change="disappeared") for item in disappeared]
  return {"changes": changes, "buckets": buckets, "counts": {key: len(value) for key, value in buckets.items()}}


def build_weekly_state(
  *,
  context: Mapping[str, Any],
  snapshots: Sequence[Mapping[str, Any]],
  integrated: Mapping[str, Any],
) -> dict[str, Any]:
  if not snapshots:
    return {
      "state": "initial_baseline",
      "message": "次回runから差分比較できます",
      "previous_snapshot": None,
      "diff": None,
    }
  previous = snapshots[0]
  diff = compare_active_run_snapshots(previous, list(integrated.get("signals", []) or []))
  return {"state": "comparable", "message": "", "previous_snapshot": previous, "diff": diff}


def build_profile_draft_from_search_request(
  *,
  context: Mapping[str, Any],
  search_request: Mapping[str, Any],
  integrated: Mapping[str, Any],
) -> dict[str, Any]:
  signals = list(integrated.get("signals", []) or [])
  companies: set[str] = set()
  countries: set[str] = set()
  cpc_ipc: set[str] = set()
  for item in signals:
    org = str(item.get("organization", "") or "").strip()
    if org:
      companies.add(org)
    country = str(item.get("country", "") or "").strip()
    if country:
      countries.add(country)
    metadata = dict(item.get("metadata", {}) or {})
    for code in list(metadata.get("cpc_codes", []) or []) + list(metadata.get("ipc_codes", []) or []):
      text = str(code or "").strip()
      if text:
        cpc_ipc.add(text)
  seed_patents = [part.strip() for part in str(search_request.get("seed_patent", "") or "").split(",") if part.strip()]
  return {
    "theme_name": str(search_request.get("theme", "") or context.get("theme", ""))[:120],
    "theme_description": str(search_request.get("theme", "") or context.get("theme", "")),
    "keywords_ja": str(search_request.get("keywords_ja", "") or ""),
    "keywords_en": str(search_request.get("keywords_en", "") or ""),
    "exact_phrase": str(search_request.get("exact_phrase", "") or ""),
    "exclude_keywords": str(search_request.get("exclude_keywords", "") or ""),
    "year_start": str(search_request.get("year_start", "") or ""),
    "year_end": str(search_request.get("year_end", "") or ""),
    "selected_sources": {
      "patent": bool(search_request.get("enable_patent", True)),
      "paper": bool(search_request.get("enable_paper", True)),
      "web": bool(search_request.get("enable_web", True)),
    },
    "seed_patents": seed_patents,
    "suggested_companies": sorted(companies)[:20],
    "suggested_countries": sorted(countries)[:20],
    "suggested_cpc_ipc": sorted(cpc_ipc)[:30],
    "update_frequency": "manual_only",
    "source_run_id": str(context.get("active_search_run_id", "")),
    "status": "draft_not_applied",
  }


def save_profile_draft(
  draft: Mapping[str, Any],
  *,
  storage_client: Any | None = None,
  environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
  run_id = str(draft.get("source_run_id", "") or "")
  bucket_name = get_study_demo_bucket(environ)
  validate_study_demo_write_target(bucket_name, environ=environ)
  path = f"{PROFILE_DRAFTS_PREFIX}{run_id}.json"
  client = storage_client if storage_client is not None else _build_client()
  blob = client.bucket(bucket_name).blob(path)
  blob.upload_from_string(json.dumps(dict(draft), ensure_ascii=False, indent=2) + "\n", content_type="application/json")
  return {"status": "saved", "path": path}


def load_profile_draft(
  search_run_id: str,
  *,
  storage_client: Any | None = None,
  environ: Mapping[str, str] | None = None,
) -> dict[str, Any] | None:
  bucket_name = get_study_demo_bucket(environ)
  client = storage_client if storage_client is not None else _build_client()
  blob = client.bucket(bucket_name).blob(f"{PROFILE_DRAFTS_PREFIX}{search_run_id}.json")
  if not blob.exists():
    return None
  return dict(json.loads(blob.download_as_bytes().decode("utf-8")))


def build_active_run_digest(
  *,
  context: Mapping[str, Any],
  integrated: Mapping[str, Any],
  search_request: Mapping[str, Any],
  provider_status: Mapping[str, Any],
  usage_metrics: Mapping[str, Any],
  weekly_state: Mapping[str, Any],
  profile_draft: Mapping[str, Any] | None,
  review_summary: Mapping[str, int],
  resolved: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
  signals = list(integrated.get("signals", []) or [])
  tier_a = [item for item in signals if str(item.get("relevance_tier", "")) == "A"][:10]
  tier_b = [item for item in signals if str(item.get("relevance_tier", "")) == "B"][:10]
  resolved_payload = dict(resolved or {})
  provider_counts = dict(resolved_payload.get("integrated_source_counts", {}) or context.get("provider_counts", {}) or {})
  tier_counts = dict(resolved_payload.get("tier_counts", {}) or context.get("tier_counts", {}) or {})
  return {
    "theme": context.get("theme"),
    "search_run_id": context.get("active_search_run_id"),
    "selected_at": context.get("selected_at"),
    "provider_counts": provider_counts,
    "raw_provider_counts": dict(resolved_payload.get("raw_provider_counts", {}) or {}),
    "stored_artifact_counts": dict(resolved_payload.get("stored_artifact_counts", {}) or {}),
    "integrated_ranked_count": int(resolved_payload.get("integrated_ranked_count", context.get("ranked_count", 0)) or 0),
    "tier_counts": tier_counts,
    "weekly_state": weekly_state.get("state"),
    "weekly_message": weekly_state.get("message"),
    "provider_status": provider_status,
    "top_tier_a": tier_a,
    "top_tier_b": tier_b,
    "review_summary": dict(review_summary),
    "profile_draft_status": (profile_draft or {}).get("status"),
    "usage_metrics": usage_metrics,
    "caveats": [
      "外部検索実行済みartifactの再利用",
      "メール未送信",
      "自動週次停止中",
      "本番未適用",
    ],
    "search_request": {
      "theme": search_request.get("theme"),
      "keywords_en": search_request.get("keywords_en"),
      "keywords_ja": search_request.get("keywords_ja"),
    },
  }


def digest_to_markdown(digest: Mapping[str, Any]) -> str:
  lines = [
    "# Study Demo Active Run Digest",
    "",
    f"- テーマ: {digest.get('theme', '')}",
    f"- search_run_id: `{digest.get('search_run_id', '')}`",
    f"- 選択日時: {digest.get('selected_at', '')}",
    f"- Patent: {dict(digest.get('provider_counts', {})).get('patent', 'unknown')}",
    f"- Paper: {dict(digest.get('provider_counts', {})).get('paper', 'unknown')}",
    f"- Web: {dict(digest.get('provider_counts', {})).get('web', 'unknown')}",
    f"- Tier A/B/C/D: {digest.get('tier_counts', {})}",
    f"- 週次状態: {digest.get('weekly_state', '')}",
    "- メール: 未送信",
    "- 自動週次: 停止中",
    "",
    "## Tier A 上位",
  ]
  for index, item in enumerate(list(digest.get("top_tier_a", []) or []), start=1):
    lines.append(f"{index}. [{item.get('source_type')}] {item.get('title')} (score={item.get('relevance_score')})")
    lines.append(f"   - {item.get('relevance_reason', '')}")
  lines.extend(["", "## Review summary", str(digest.get("review_summary", {})), ""])
  return "\n".join(lines) + "\n"


def build_downstream_bundle(
  context: Mapping[str, Any],
  *,
  storage_client: Any | None = None,
  environ: Mapping[str, str] | None = None,
) -> dict[str, Any]:
  from services_v9.study_demo_active_loader import (
    adapt_integrated_signals_for_display,
    load_active_integrated_signals,
    load_active_provider_status,
    load_active_search_request,
    load_active_usage_metrics,
  )
  from services_v9.study_demo_resolved_context import resolve_active_run_counts

  integrated = load_active_integrated_signals(context, storage_client=storage_client, recompute_relevance=True)
  resolved = resolve_active_run_counts(context, storage_client=storage_client)
  search_request = load_active_search_request(context, storage_client=storage_client)
  provider_status = load_active_provider_status(context, storage_client=storage_client)
  usage_metrics = load_active_usage_metrics(context, storage_client=storage_client)
  profile_signature = theme_signature(str(context.get("theme", "")))
  snapshots = list_run_snapshots(profile_signature, storage_client=storage_client, environ=environ)
  weekly_state = build_weekly_state(context=context, snapshots=snapshots, integrated=integrated)
  profile_draft = build_profile_draft_from_search_request(
    context=context,
    search_request=search_request,
    integrated=integrated,
  )
  reviews = load_run_reviews(str(context.get("active_search_run_id", "")), storage_client=storage_client, environ=environ)
  signal_ids = [str(item.get("signal_id", "")) for item in list(integrated.get("signals", []) or [])]
  review_summary = summarize_run_reviews(reviews, signal_ids)
  digest = build_active_run_digest(
    context=context,
    integrated=integrated,
    search_request=search_request,
    provider_status=provider_status,
    usage_metrics=usage_metrics,
    weekly_state=weekly_state,
    profile_draft=profile_draft,
    review_summary=review_summary,
    resolved=resolved,
  )
  return {
    "integrated": integrated,
    "resolved_context": resolved,
    "raw_provider_counts": dict(resolved.get("raw_provider_counts", {}) or {}),
    "stored_artifact_counts": dict(resolved.get("stored_artifact_counts", {}) or {}),
    "integrated_ranked_count": int(resolved.get("integrated_ranked_count", 0) or 0),
    "integrated_source_counts": dict(resolved.get("integrated_source_counts", {}) or {}),
    "tier_counts": dict(resolved.get("tier_counts", {}) or {}),
    "unknown_tier_count": int(resolved.get("unknown_tier_count", 0) or 0),
    "count_validation_status": str(resolved.get("count_validation_status", "") or ""),
    "count_validation_message": str(resolved.get("count_validation_message", "") or ""),
    "search_request": search_request,
    "provider_status": provider_status,
    "usage_metrics": usage_metrics,
    "weekly_state": weekly_state,
    "profile_draft": profile_draft,
    "reviews": reviews,
    "review_summary": review_summary,
    "digest": digest,
    "top_reads_raw": select_top_reads_from_active_signals(list(integrated.get("signals", []) or [])),
    "display_signals": adapt_integrated_signals_for_display(integrated),
    "digest_exports": build_digest_exports(
      digest,
      integrated=integrated,
      reviews=reviews,
      weekly_state=weekly_state,
      profile_draft=profile_draft,
      context=context,
    ),
    "profile_signature": profile_signature,
  }


def build_digest_exports(
  digest: Mapping[str, Any],
  *,
  integrated: Mapping[str, Any],
  reviews: Mapping[str, Any],
  weekly_state: Mapping[str, Any],
  profile_draft: Mapping[str, Any] | None,
  context: Mapping[str, Any],
) -> dict[str, str]:
  from services_v9.study_demo_search.export import build_export_bundle

  signals = list(integrated.get("signals", []) or [])
  export_bundle = build_export_bundle(signals, {}, {}, dict(digest.get("usage_metrics", {}) or {}))
  diff_rows = weekly_state.get("diff", {}) or {}
  diff_csv = ""
  if diff_rows:
    import csv
    from io import StringIO

    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=["change", "signal_key", "title", "relevance_tier", "relevance_score"])
    writer.writeheader()
    for bucket in diff_rows.get("buckets", {}).values():
      for item in bucket:
        writer.writerow(
          {
            "change": item.get("change"),
            "signal_key": item.get("signal_key"),
            "title": item.get("title"),
            "relevance_tier": item.get("relevance_tier"),
            "relevance_score": item.get("relevance_score"),
          }
        )
    diff_csv = buffer.getvalue()
  return {
    "active_context_json": json.dumps(context, ensure_ascii=False, indent=2),
    "digest_markdown": digest_to_markdown(digest),
    "digest_json": json.dumps(digest, ensure_ascii=False, indent=2),
    "review_json": json.dumps(reviews, ensure_ascii=False, indent=2),
    "profile_draft_json": json.dumps(profile_draft or {}, ensure_ascii=False, indent=2),
    "weekly_diff_csv": diff_csv,
    "integrated_csv_all_tiers": export_bundle.get("integrated_csv_all_tiers", ""),
    "full_provenance_json": json.dumps(
      {"context": context, "digest": digest, "weekly_state": weekly_state},
      ensure_ascii=False,
      indent=2,
    ),
  }


def _build_client():
  from google.cloud import storage

  return storage.Client()
