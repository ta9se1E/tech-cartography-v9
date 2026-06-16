"""OpenAlex paper retrieval."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from tech_cartography.domain.paper_record import PaperRecord
from tech_cartography.evidence.paper_query_builder import prioritize_paper_queries
from tech_cartography.retrieval.openalex_cache import (
  load_openalex_cache,
  openalex_cache_status,
  save_openalex_cache,
)
from tech_cartography.reports.project_export import save_records_csv


@dataclass
class OpenAlexRetrievalConfig:
  execute: bool = False
  max_queries: int = 20
  max_results_per_query: int = 10
  cache_dir: str = "data/runtime/openalex_cache"
  use_cache: bool = True
  polite_email: str | None = None
  request_timeout_sec: int = 30
  sleep_sec: float = 0.2
  output_dir: str = "outputs/openalex_paper_evidence"


def build_openalex_search_url(query: str, max_results: int = 10, polite_email: str | None = None) -> str:
  params: dict[str, str] = {
    "search": query,
    "per-page": str(max_results),
  }
  if polite_email:
    params["mailto"] = polite_email
  return f"https://api.openalex.org/works?{urllib.parse.urlencode(params)}"


def _fetch_openalex_json(url: str, timeout_sec: int) -> dict[str, Any]:
  request = urllib.request.Request(
    url,
    headers={"User-Agent": "PatentScout-AI-v7/0.7 (+https://github.com/local)"},
  )
  with urllib.request.urlopen(request, timeout=timeout_sec) as response:
    return json.loads(response.read().decode("utf-8"))


def search_openalex(query: str, config: OpenAlexRetrievalConfig) -> dict[str, Any]:
  if not config.execute:
    return {
      "status": "plan_only",
      "query": query,
      "url": build_openalex_search_url(query, config.max_results_per_query, config.polite_email),
      "works": [],
    }

  if config.use_cache:
    cached = load_openalex_cache(query, config.cache_dir, config.max_results_per_query)
    if cached is not None:
      return {
        "status": "cache_hit",
        "query": query,
        "works": cached.get("works", []),
        "meta": cached.get("meta", {}),
      }

  url = build_openalex_search_url(query, config.max_results_per_query, config.polite_email)
  try:
    payload = _fetch_openalex_json(url, config.request_timeout_sec)
    works = payload.get("results", [])
    result = {
      "status": "ok",
      "query": query,
      "works": works,
      "meta": payload.get("meta", {}),
    }
    if config.use_cache:
      save_openalex_cache(query, result, config.cache_dir, config.max_results_per_query)
    return result
  except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, ValueError) as exc:
    return {
      "status": "error",
      "query": query,
      "works": [],
      "error": str(exc),
    }


def parse_openalex_work(work: dict[str, Any]) -> PaperRecord:
  return PaperRecord.from_openalex_work(work)


def normalize_openalex_results(raw_result: dict[str, Any], query_row: dict[str, Any]) -> list[dict[str, Any]]:
  papers: list[dict[str, Any]] = []
  for work in raw_result.get("works", []):
    record = parse_openalex_work(work).to_dict()
    record.update(
      {
        "query_id": query_row.get("query_id"),
        "publication_number": query_row.get("publication_number"),
        "element_id": query_row.get("element_id"),
        "element_type": query_row.get("element_type"),
        "query": query_row.get("query") or raw_result.get("query"),
        "query_priority": query_row.get("priority"),
        "query_purpose": query_row.get("purpose"),
        "retrieval_status": raw_result.get("status"),
      },
    )
    papers.append(record)
  return papers


def _dedupe_papers(papers: list[dict[str, Any]]) -> list[dict[str, Any]]:
  deduped: list[dict[str, Any]] = []
  seen: set[str] = set()
  for paper in papers:
    key = (
      str(paper.get("doi") or "").lower()
      or str(paper.get("openalex_id") or "").lower()
      or str(paper.get("paper_id") or "").lower()
      or str(paper.get("title") or "").lower()
    )
    if key in seen:
      continue
    seen.add(key)
    deduped.append(paper)
  return deduped


def search_paper_queries(
  query_rows: list[dict[str, Any]],
  config: OpenAlexRetrievalConfig,
) -> dict[str, Any]:
  warnings: list[str] = []
  errors: list[str] = []
  prioritized = prioritize_paper_queries(query_rows, top_n=config.max_queries)
  plan = [
    {
      "query_id": row.get("query_id"),
      "query": row.get("query"),
      "priority": row.get("priority"),
      "publication_number": row.get("publication_number"),
      "element_id": row.get("element_id"),
      "url": build_openalex_search_url(
        str(row.get("query") or ""),
        config.max_results_per_query,
        config.polite_email,
      ),
      "cache_status": openalex_cache_status(
        str(row.get("query") or ""),
        config.cache_dir,
        config.max_results_per_query,
      )
      if config.use_cache
      else "cache_disabled",
    }
    for row in prioritized
  ]

  if not config.execute:
    return {
      "status": "ok",
      "mode": "plan_only",
      "total_query_candidates": len(query_rows),
      "executed_queries": 0,
      "cache_hits": 0,
      "cache_misses": 0,
      "total_papers_raw": 0,
      "total_papers_dedup": 0,
      "query_plan": plan,
      "papers_raw": [],
      "papers_dedup": [],
      "warnings": warnings,
      "errors": errors,
    }

  papers_raw: list[dict[str, Any]] = []
  cache_hits = 0
  cache_misses = 0
  executed_queries = 0

  for row in prioritized:
    query = str(row.get("query") or "").strip()
    if not query:
      warnings.append(f"Skipped empty query for query_id={row.get('query_id')}")
      continue
    executed_queries += 1
    if config.use_cache and openalex_cache_status(query, config.cache_dir, config.max_results_per_query) == "cache_hit":
      cache_hits += 1
    else:
      cache_misses += 1
    raw_result = search_openalex(query, config)
    if raw_result.get("status") == "error":
      errors.append(f"{query}: {raw_result.get('error')}")
      continue
    if raw_result.get("status") == "cache_hit":
      cache_hits += 0  # already counted
    papers_raw.extend(normalize_openalex_results(raw_result, row))
    if config.sleep_sec > 0:
      time.sleep(config.sleep_sec)

  papers_dedup = _dedupe_papers(papers_raw)
  return {
    "status": "ok",
    "mode": "execute",
    "total_query_candidates": len(query_rows),
    "executed_queries": executed_queries,
    "cache_hits": cache_hits,
    "cache_misses": cache_misses,
    "total_papers_raw": len(papers_raw),
    "total_papers_dedup": len(papers_dedup),
    "query_plan": plan,
    "papers_raw": papers_raw,
    "papers_dedup": papers_dedup,
    "warnings": warnings,
    "errors": errors,
  }


def save_openalex_results(result: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)
  paths: dict[str, str] = {
    "openalex_query_plan_json": str(out / "openalex_query_plan.json"),
    "paper_records_raw_json": str(out / "paper_records_raw.json"),
    "paper_records_csv": save_records_csv(result.get("papers_raw", []), out / "paper_records.csv"),
    "paper_records_dedup_csv": save_records_csv(result.get("papers_dedup", []), out / "paper_records_dedup.csv"),
  }
  with Path(paths["openalex_query_plan_json"]).open("w", encoding="utf-8") as handle:
    json.dump(result.get("query_plan", []), handle, indent=2, ensure_ascii=False)
  with Path(paths["paper_records_raw_json"]).open("w", encoding="utf-8") as handle:
    json.dump(result.get("papers_raw", []), handle, indent=2, ensure_ascii=False)
  paths["output_dir"] = str(out)
  return paths
