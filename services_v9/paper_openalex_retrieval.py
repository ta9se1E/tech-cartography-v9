"""OpenAlex paper retrieval helpers for v9."""

from __future__ import annotations

import csv
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime
from io import StringIO
from pathlib import Path
from typing import Any, Callable

from .persistence import ensure_v9_run_dirs
from .study_demo_guard import assert_external_execution_allowed
from .watch_profile_schema import migrate_watch_profile, normalize_terms

OpenUrl = Callable[[urllib.request.Request, int], Any]
SleepFn = Callable[[float], None]

OPENALEX_WORKS_API = "https://api.openalex.org/works"
SEMANTIC_SCHOLAR_FALLBACK_INTERFACE = {
  "provider": "semantic_scholar",
  "implemented": False,
  "mode": "future_fallback_only",
}


def _redact_sensitive_url(url: str) -> str:
  text = str(url or "")
  if not text:
    return text
  parsed = urllib.parse.urlsplit(text)
  pairs = urllib.parse.parse_qsl(parsed.query, keep_blank_values=True)
  redacted = [(key, "REDACTED") if str(key).lower() in {"api_key", "key"} else (key, value) for key, value in pairs]
  query = urllib.parse.urlencode(redacted)
  return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, parsed.path, query, parsed.fragment))


def build_openalex_paper_preview(
  search_plan: dict[str, Any],
  watch_profile: dict[str, Any],
  *,
  selected_query_id: str | None = None,
  time_range: str = "12m",
  max_results: int | None = None,
  per_page: int = 25,
  retry_limit: int = 2,
  polite_email: str | None = None,
) -> dict[str, Any]:
  migrated_profile = migrate_watch_profile(watch_profile or {})
  paper_plan = dict(search_plan.get("plans", {}).get("paper", {}) or {})
  queries = list(paper_plan.get("queries", []) or [])
  if not queries:
    return {
      "request": {},
      "url_preview": "",
      "query_options": [],
      "selected_query_id": "",
      "validation_rows": [{"status": "error", "message": "論文検索計画にqueryがありません。"}],
    }

  query_options = [str(query.get("query_id", "") or "") for query in queries if str(query.get("query_id", "") or "").strip()]
  resolved_query_id = selected_query_id if selected_query_id in query_options else query_options[0]
  selected_query = next(
    query for query in queries
    if str(query.get("query_id", "") or "") == resolved_query_id
  )

  max_results_value = _normalize_positive_int(max_results, int(paper_plan.get("limit", 0) or 100))
  per_page_value = min(_normalize_positive_int(per_page, 25), 200)
  date_from, date_to = _publication_window_from_time_range(time_range)
  query_terms = normalize_terms(list(selected_query.get("terms", []) or []))
  query_text = _compose_openalex_search_text(str(migrated_profile.get("theme_name", "") or ""), query_terms)
  request = {
    "provider": "openalex",
    "fallback_interface": dict(SEMANTIC_SCHOLAR_FALLBACK_INTERFACE),
    "query_id": resolved_query_id,
    "strategy": str(selected_query.get("strategy", "") or "").strip(),
    "language": str(selected_query.get("language", "") or "").strip(),
    "query_terms": query_terms,
    "query_text": query_text,
    "theme_name": str(migrated_profile.get("theme_name", "") or "").strip(),
    "publication_date_from": date_from,
    "publication_date_to": date_to,
    "max_results": max_results_value,
    "per_page": per_page_value,
    "retry_limit": max(int(retry_limit), 0),
    "polite_email": str(polite_email or "").strip() or None,
    "time_range": str(time_range or "12m"),
    "execute_enabled": True,
    "record_stage": "staged",
    "retrieval_mode": "real",
  }
  url_preview = build_openalex_search_url(request, cursor="*")
  validation_rows = validate_openalex_request(request)
  return {
    "request": request,
    "url_preview": url_preview,
    "query_options": query_options,
    "selected_query_id": resolved_query_id,
    "validation_rows": validation_rows,
  }


def build_openalex_search_url(request: dict[str, Any], *, cursor: str = "*") -> str:
  params: dict[str, str] = {
    "search": str(request.get("query_text", "") or ""),
    "per-page": str(int(request.get("per_page", 25) or 25)),
    "cursor": str(cursor or "*"),
  }
  if request.get("polite_email"):
    params["mailto"] = str(request.get("polite_email", "") or "")
  if str(request.get("api_key", "") or "").strip():
    params["api_key"] = str(request.get("api_key", "") or "").strip()
  filters = []
  date_from = str(request.get("publication_date_from", "") or "").strip()
  date_to = str(request.get("publication_date_to", "") or "").strip()
  if date_from:
    filters.append(f"from_publication_date:{_yyyymmdd_to_iso(date_from)}")
  if date_to:
    filters.append(f"to_publication_date:{_yyyymmdd_to_iso(date_to)}")
  if filters:
    params["filter"] = ",".join(filters)
  return f"{OPENALEX_WORKS_API}?{urllib.parse.urlencode(params)}"


def validate_openalex_request(request: dict[str, Any]) -> list[dict[str, str]]:
  rows: list[dict[str, str]] = []
  if not str(request.get("query_id", "") or "").strip():
    rows.append({"status": "error", "message": "query_id が未設定です。"})
  if not str(request.get("query_text", "") or "").strip():
    rows.append({"status": "error", "message": "OpenAlex query_text が空です。"})
  if int(request.get("max_results", 0) or 0) <= 0:
    rows.append({"status": "error", "message": "max_results は 1 以上である必要があります。"})
  if int(request.get("per_page", 0) or 0) <= 0:
    rows.append({"status": "error", "message": "per_page は 1 以上である必要があります。"})
  if int(request.get("retry_limit", 0) or 0) < 0:
    rows.append({"status": "error", "message": "retry_limit は 0 以上である必要があります。"})
  if not rows:
    rows.append({"status": "ok", "message": "validation passed"})
  return rows


def execute_openalex_paper_retrieval(
  preview: dict[str, Any],
  *,
  opener: OpenUrl | None = None,
  sleeper: SleepFn | None = None,
  timeout_sec: int = 30,
  rate_limit_sleep_sec: float = 0.2,
) -> dict[str, Any]:
  assert_external_execution_allowed("openalex_execute")
  request = dict(preview.get("request", {}) or {})
  validation_rows = list(preview.get("validation_rows", []) or [])
  retrieval_run_id = _build_retrieval_run_id(str(request.get("query_id", "") or "paper"))
  if any(str(row.get("status", "")) == "error" for row in validation_rows):
    return _paper_error_result(
      retrieval_run_id,
      request,
      validation_rows,
      provider_status="validation_error",
      error_message="openalex request validation error",
      rows=[],
      log_rows=[],
    )

  open_url = opener or _default_open_url
  sleep_fn = sleeper or time.sleep
  max_results = int(request.get("max_results", 0) or 0)
  retry_limit = int(request.get("retry_limit", 0) or 0)
  rows: list[dict[str, Any]] = []
  errors: list[str] = []
  log_rows: list[dict[str, Any]] = []
  cursor = "*"
  page_index = 0
  while cursor and len(rows) < max_results:
    page_index += 1
    attempt = 0
    page_succeeded = False
    while attempt <= retry_limit:
      attempt += 1
      url = build_openalex_search_url(request, cursor=cursor)
      try:
        payload = _fetch_openalex_payload(url, timeout_sec, open_url)
        works = list(payload.get("results", []) or [])
        normalized = [
          _normalize_openalex_work(
            work,
            query_id=str(request.get("query_id", "") or ""),
            retrieval_run_id=retrieval_run_id,
            record_stage=str(request.get("record_stage", "staged") or "staged"),
            retrieval_mode=str(request.get("retrieval_mode", "real") or "real"),
          )
          for work in works
        ]
        rows.extend(normalized)
        next_cursor = str(((payload.get("meta") or {}).get("next_cursor") or "")).strip()
        log_rows.append({
          "page_index": page_index,
          "cursor": cursor,
          "url": _redact_sensitive_url(url),
          "attempt": attempt,
          "status": "ok",
          "results_count": len(normalized),
          "next_cursor": next_cursor,
        })
        cursor = next_cursor if next_cursor and len(rows) < max_results else ""
        page_succeeded = True
        if rate_limit_sleep_sec > 0 and cursor:
          sleep_fn(rate_limit_sleep_sec)
        break
      except urllib.error.HTTPError as exc:
        retry_after = _retry_after_seconds(exc)
        log_rows.append({
          "page_index": page_index,
          "cursor": cursor,
          "url": _redact_sensitive_url(url),
          "attempt": attempt,
          "status": f"http_{exc.code}",
          "error": str(exc),
          "retry_after": retry_after,
        })
        if exc.code == 429 and attempt <= retry_limit:
          sleep_fn(retry_after if retry_after is not None else max(rate_limit_sleep_sec, 1.0))
          continue
        errors.append(str(exc))
        break
      except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
        log_rows.append({
          "page_index": page_index,
          "cursor": cursor,
          "url": _redact_sensitive_url(url),
          "attempt": attempt,
          "status": "error",
          "error": str(exc),
        })
        if attempt <= retry_limit:
          sleep_fn(max(rate_limit_sleep_sec, 0.5))
          continue
        errors.append(str(exc))
        break
    if not page_succeeded:
      break

  deduped_rows = _deduplicate_paper_rows(rows)[:max_results]
  provider_status = "success"
  if errors and deduped_rows:
    provider_status = "partial_success"
  elif errors:
    provider_status = "error"
  return {
    "provider": "openalex",
    "fallback_interface": dict(SEMANTIC_SCHOLAR_FALLBACK_INTERFACE),
    "query_id": str(request.get("query_id", "") or ""),
    "retrieval_run_id": retrieval_run_id,
    "provider_status": provider_status,
    "retrieval_mode": str(request.get("retrieval_mode", "real") or "real"),
    "record_stage": str(request.get("record_stage", "staged") or "staged"),
    "rows_retrieved": len(deduped_rows),
    "rows": deduped_rows,
    "error": errors[0] if errors else None,
    "provider_log": log_rows,
    "rate_limit_sleep_sec": float(rate_limit_sleep_sec),
    "retry_limit": retry_limit,
    "pages_fetched": sum(1 for row in log_rows if row.get("status") == "ok"),
    "validation_rows": validation_rows,
  }


def save_openalex_paper_retrieval_artifacts(
  preview: dict[str, Any],
  retrieval_result: dict[str, Any],
  *,
  base_dir: Path | None = None,
) -> dict[str, Path]:
  dirs = ensure_v9_run_dirs(base_dir)
  runs_dir = dirs["root"] / "paper_retrieval_runs"
  runs_dir.mkdir(parents=True, exist_ok=True)
  run_id = str(retrieval_result.get("retrieval_run_id", "") or "").strip() or datetime.now().astimezone().strftime("%Y-%m-%d_%H%M%S")
  target_dir = runs_dir / run_id
  target_dir.mkdir(parents=True, exist_ok=True)

  plan_path = target_dir / "paper_query_plan.json"
  staged_json_path = target_dir / "paper_candidates_staged.json"
  staged_csv_path = target_dir / "paper_candidates_staged.csv"
  provider_log_path = target_dir / "paper_provider_log.json"
  validation_path = target_dir / "paper_query_validation.csv"

  plan_path.write_text(json.dumps({
    "request": preview.get("request", {}),
    "url_preview": preview.get("url_preview", ""),
  }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  staged_json_path.write_text(json.dumps({
    "retrieval_run_id": retrieval_result.get("retrieval_run_id", ""),
    "provider_status": retrieval_result.get("provider_status", ""),
    "rows": retrieval_result.get("rows", []),
  }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  staged_csv_path.write_text(build_openalex_paper_candidates_csv(list(retrieval_result.get("rows", []) or [])), encoding="utf-8")
  provider_log_path.write_text(json.dumps({
    "provider": retrieval_result.get("provider", "openalex"),
    "query_id": retrieval_result.get("query_id", ""),
    "retrieval_run_id": retrieval_result.get("retrieval_run_id", ""),
    "provider_status": retrieval_result.get("provider_status", ""),
    "pages_fetched": retrieval_result.get("pages_fetched", 0),
    "retry_limit": retrieval_result.get("retry_limit", 0),
    "provider_log": retrieval_result.get("provider_log", []),
    "error": retrieval_result.get("error"),
  }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  validation_path.write_text(build_openalex_validation_csv(list(preview.get("validation_rows", []) or [])), encoding="utf-8")
  return {
    "run_dir": target_dir,
    "plan_json": plan_path,
    "staged_json": staged_json_path,
    "staged_csv": staged_csv_path,
    "provider_log_json": provider_log_path,
    "validation_csv": validation_path,
  }


def build_openalex_paper_candidates_csv(rows: list[dict[str, Any]]) -> str:
  fieldnames = [
    "work_id",
    "doi",
    "title",
    "abstract",
    "authors",
    "institutions",
    "publication_date",
    "source_journal",
    "cited_by_count",
    "topics",
    "open_access",
    "original_language",
    "source_url",
    "query_id",
    "retrieval_run_id",
    "provider_status",
    "record_stage",
    "retrieval_mode",
  ]
  buffer = StringIO()
  writer = csv.DictWriter(buffer, fieldnames=fieldnames)
  writer.writeheader()
  for row in rows:
    payload = dict(row)
    payload["authors"] = " | ".join(str(item) for item in list(row.get("authors", []) or []))
    payload["institutions"] = " | ".join(str(item) for item in list(row.get("institutions", []) or []))
    payload["topics"] = " | ".join(str(item) for item in list(row.get("topics", []) or []))
    writer.writerow({key: payload.get(key, "") for key in fieldnames})
  return buffer.getvalue()


def build_openalex_validation_csv(rows: list[dict[str, str]]) -> str:
  buffer = StringIO()
  writer = csv.DictWriter(buffer, fieldnames=["status", "message"])
  writer.writeheader()
  for row in rows:
    writer.writerow({
      "status": str(row.get("status", "") or ""),
      "message": str(row.get("message", "") or ""),
    })
  return buffer.getvalue()


def _compose_openalex_search_text(theme_name: str, terms: list[str]) -> str:
  items = []
  if str(theme_name or "").strip():
    items.append(str(theme_name).strip())
  items.extend(str(term or "").strip() for term in terms if str(term or "").strip())
  return " ".join(normalize_terms(items))


def _publication_window_from_time_range(time_range: str) -> tuple[str, str]:
  normalized = str(time_range or "12m").strip().lower()
  if normalized in {"all", "none", "unbounded"}:
    return "", ""
  today = date.today()
  months = {
    "1m": 1,
    "3m": 3,
    "6m": 6,
    "12m": 12,
    "24m": 24,
  }.get(normalized, 12)
  start_year = today.year
  start_month = today.month - months + 1
  while start_month <= 0:
    start_month += 12
    start_year -= 1
  return f"{start_year:04d}{start_month:02d}01", today.strftime("%Y%m%d")


def _normalize_positive_int(value: Any, default: int) -> int:
  try:
    normalized = int(value)
  except (TypeError, ValueError):
    normalized = int(default)
  return max(normalized, 1)


def _yyyymmdd_to_iso(value: str) -> str:
  text = str(value or "").strip()
  if len(text) != 8 or not text.isdigit():
    return text
  return f"{text[:4]}-{text[4:6]}-{text[6:8]}"


def _default_open_url(request: urllib.request.Request, timeout_sec: int):
  return urllib.request.urlopen(request, timeout=timeout_sec)


def _fetch_openalex_payload(url: str, timeout_sec: int, opener: OpenUrl) -> dict[str, Any]:
  request = urllib.request.Request(
    url,
    headers={"User-Agent": "PatentScout-AI-v9/0.9 (+local staged paper retrieval)"},
  )
  with opener(request, timeout_sec) as response:
    return json.loads(response.read().decode("utf-8"))


def _normalize_openalex_work(
  work: dict[str, Any],
  *,
  query_id: str,
  retrieval_run_id: str,
  record_stage: str,
  retrieval_mode: str,
) -> dict[str, Any]:
  doi = _extract_doi(work)
  openalex_id = _extract_openalex_id(work)
  landing_page_url = _extract_landing_page(work)
  pdf_url = _extract_pdf_url(work)
  title = str(work.get("display_name") or work.get("title") or "").strip()
  abstract = str(work.get("abstract") or _reconstruct_abstract_from_inverted_index(work.get("abstract_inverted_index")) or "").strip()
  authors = _extract_authors(work)
  source_name = _extract_source_name(work)
  display_url = _build_display_url_from_parts(landing_page_url, doi, pdf_url, openalex_id)
  publication_year = work.get("publication_year")
  institutions = _extract_institutions(work)
  topics = _extract_topics(work)
  publication_date = str(work.get("publication_date") or "") or (
    f"{int(publication_year):04d}-01-01" if publication_year else ""
  )
  return {
    "work_id": str(openalex_id or work.get("id") or doi or title or "unknown").strip(),
    "doi": str(doi or "").strip(),
    "title": title,
    "abstract": abstract,
    "authors": authors,
    "institutions": institutions,
    "publication_date": publication_date,
    "source_journal": source_name,
    "cited_by_count": int(work.get("cited_by_count") or 0),
    "topics": topics,
    "open_access": bool((work.get("open_access") or {}).get("is_oa")),
    "original_language": str(work.get("language") or "").strip(),
    "source_url": str(display_url or "").strip(),
    "query_id": query_id,
    "retrieval_run_id": retrieval_run_id,
    "provider_status": "success",
    "record_stage": record_stage,
    "retrieval_mode": retrieval_mode,
    "provider": "openalex",
  }


def _extract_institutions(work: dict[str, Any]) -> list[str]:
  names: list[str] = []
  seen: set[str] = set()
  for authorship in list(work.get("authorships", []) or []):
    for institution in list(authorship.get("institutions", []) or []):
      name = str(institution.get("display_name") or "").strip()
      if not name:
        continue
      key = name.lower()
      if key in seen:
        continue
      seen.add(key)
      names.append(name)
  return names


def _reconstruct_abstract_from_inverted_index(inverted_index: dict[str, list[int]] | None) -> str | None:
  if not inverted_index:
    return None
  positions: list[tuple[int, str]] = []
  for word, indices in inverted_index.items():
    for index in indices:
      positions.append((index, word))
  if not positions:
    return None
  positions.sort(key=lambda item: item[0])
  return " ".join(word for _, word in positions)


def _extract_doi(work: dict[str, Any]) -> str | None:
  doi = work.get("doi")
  if doi:
    return str(doi).replace("https://doi.org/", "")
  ids = work.get("ids") or {}
  raw = ids.get("doi")
  if raw:
    return str(raw).replace("https://doi.org/", "")
  return None


def _extract_openalex_id(work: dict[str, Any]) -> str | None:
  openalex_id = work.get("id")
  if openalex_id:
    return str(openalex_id)
  ids = work.get("ids") or {}
  return str(ids.get("openalex") or "") or None


def _extract_landing_page(work: dict[str, Any]) -> str | None:
  primary = work.get("primary_location") or {}
  landing = primary.get("landing_page_url")
  if landing:
    return str(landing)
  for location in work.get("locations") or []:
    if location.get("landing_page_url"):
      return str(location["landing_page_url"])
  return None


def _extract_pdf_url(work: dict[str, Any]) -> str | None:
  primary = work.get("primary_location") or {}
  pdf = primary.get("pdf_url")
  if pdf:
    return str(pdf)
  open_access = work.get("open_access") or {}
  if open_access.get("oa_url"):
    return str(open_access["oa_url"])
  for location in work.get("locations") or []:
    if location.get("pdf_url"):
      return str(location["pdf_url"])
  return None


def _build_display_url_from_parts(
  landing_page_url: str | None,
  doi: str | None,
  pdf_url: str | None,
  openalex_id: str | None,
) -> str | None:
  if landing_page_url:
    return landing_page_url
  if doi:
    clean = doi.replace("https://doi.org/", "")
    return f"https://doi.org/{clean}"
  if pdf_url:
    return pdf_url
  if openalex_id:
    if openalex_id.startswith("http"):
      return openalex_id
    return f"https://openalex.org/{openalex_id.split('/')[-1]}"
  return None


def _extract_authors(work: dict[str, Any]) -> list[str]:
  authors = [
    str((author.get("author") or {}).get("display_name") or author.get("display_name") or "")
    for author in (work.get("authorships") or [])
  ]
  return [name for name in authors if name]


def _extract_source_name(work: dict[str, Any]) -> str:
  primary = work.get("primary_location") or {}
  source = primary.get("source") or {}
  return str(source.get("display_name") or "").strip()


def _extract_topics(work: dict[str, Any]) -> list[str]:
  topics: list[str] = []
  seen: set[str] = set()
  for item in list(work.get("topics", []) or []):
    name = str(item.get("display_name") or item.get("name") or "").strip()
    if not name:
      continue
    key = name.lower()
    if key in seen:
      continue
    seen.add(key)
    topics.append(name)
  if topics:
    return topics
  for item in list(work.get("concepts", []) or []):
    name = str(item.get("display_name") or item.get("name") or "").strip()
    if not name:
      continue
    key = name.lower()
    if key in seen:
      continue
    seen.add(key)
    topics.append(name)
  return topics


def _retry_after_seconds(exc: urllib.error.HTTPError) -> float | None:
  try:
    raw = exc.headers.get("Retry-After") if exc.headers else None
  except Exception:  # noqa: BLE001
    raw = None
  if raw is None:
    return None
  try:
    return float(str(raw).strip())
  except ValueError:
    return None


def _build_retrieval_run_id(query_id: str) -> str:
  timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
  return f"paper_retrieval_{query_id}_{timestamp}"


def _deduplicate_paper_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
  deduped: list[dict[str, Any]] = []
  seen: set[str] = set()
  for row in rows:
    key = (
      str(row.get("doi", "") or "").lower()
      or str(row.get("work_id", "") or "").lower()
      or str(row.get("title", "") or "").lower()
    )
    if not key or key in seen:
      continue
    seen.add(key)
    deduped.append(row)
  return deduped


def _paper_error_result(
  retrieval_run_id: str,
  request: dict[str, Any],
  validation_rows: list[dict[str, str]],
  *,
  provider_status: str,
  error_message: str,
  rows: list[dict[str, Any]],
  log_rows: list[dict[str, Any]],
) -> dict[str, Any]:
  return {
    "provider": "openalex",
    "fallback_interface": dict(SEMANTIC_SCHOLAR_FALLBACK_INTERFACE),
    "query_id": str(request.get("query_id", "") or ""),
    "retrieval_run_id": retrieval_run_id,
    "provider_status": provider_status,
    "retrieval_mode": str(request.get("retrieval_mode", "real") or "real"),
    "record_stage": str(request.get("record_stage", "staged") or "staged"),
    "rows_retrieved": len(rows),
    "rows": rows,
    "error": error_message,
    "provider_log": log_rows,
    "rate_limit_sleep_sec": 0.0,
    "retry_limit": int(request.get("retry_limit", 0) or 0),
    "pages_fetched": sum(1 for row in log_rows if row.get("status") == "ok"),
    "validation_rows": validation_rows,
  }


__all__ = [
  "OPENALEX_WORKS_API",
  "SEMANTIC_SCHOLAR_FALLBACK_INTERFACE",
  "build_openalex_paper_candidates_csv",
  "build_openalex_paper_preview",
  "build_openalex_search_url",
  "build_openalex_validation_csv",
  "execute_openalex_paper_retrieval",
  "save_openalex_paper_retrieval_artifacts",
  "validate_openalex_request",
]
