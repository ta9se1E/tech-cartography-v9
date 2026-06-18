"""Orchestrate Tavily Web Signal search runs (Phase 23.1)."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from tech_cartography.web_signals.query_templates import WebSignalQuery, build_web_signal_queries
from tech_cartography.web_signals.schema import WebSignal, WebSignalBatch, new_batch_id, utc_now_iso
from tech_cartography.web_signals.store import SOURCE_POLICY_VERSION, save_tavily_web_signal_run
from tech_cartography.web_signals.tavily_adapter import (
  get_tavily_api_key,
  run_tavily_extract,
  run_tavily_search,
  tavily_extract_results_to_web_signals,
  tavily_search_results_to_web_signals,
)


@dataclass
class TavilyRunConfig:
  topic: str
  categories: list[str]
  languages: list[str] = field(default_factory=lambda: ["ja", "en"])
  max_queries: int = 10
  max_results_per_query: int = 5
  include_domains: list[str] = field(default_factory=list)
  exclude_domains: list[str] = field(default_factory=list)
  output_dir: str | None = None
  dry_run: bool = False
  plan_only: bool = True
  execute_tavily: bool = False
  extract_top_urls: bool = False
  max_extract_urls: int = 3


def _merge_domains(base: list[str], extra: list[str]) -> list[str]:
  merged: list[str] = []
  for item in [*base, *extra]:
    value = str(item).strip()
    if value and value not in merged:
      merged.append(value)
  return merged


def prepare_web_signal_queries(config: TavilyRunConfig) -> list[WebSignalQuery]:
  queries = build_web_signal_queries(config.topic, config.categories, config.languages)
  if config.max_queries > 0:
    queries = queries[: config.max_queries]
  if config.include_domains or config.exclude_domains:
    adjusted: list[WebSignalQuery] = []
    for query in queries:
      adjusted.append(
        WebSignalQuery(
          query_id=query.query_id,
          category=query.category,
          query=query.query,
          language=query.language,
          intended_signal_type=query.intended_signal_type,
          include_domains=_merge_domains(query.include_domains, config.include_domains),
          exclude_domains=_merge_domains(query.exclude_domains, config.exclude_domains),
          notes=query.notes,
        ),
      )
    queries = adjusted
  return queries


def run_tavily_web_signal_pipeline(config: TavilyRunConfig) -> dict[str, Any]:
  queries = prepare_web_signal_queries(config)
  batch_id = new_batch_id()
  output_dir = Path(config.output_dir) if config.output_dir else Path("outputs/web_signals") / batch_id

  result: dict[str, Any] = {
    "status": "planned",
    "batch_id": batch_id,
    "output_dir": str(output_dir),
    "query_count": len(queries),
    "signal_count": 0,
    "execute_tavily": config.execute_tavily,
    "dry_run": config.dry_run,
    "plan_only": config.plan_only,
    "errors": [],
  }

  if config.dry_run:
    result["status"] = "dry_run"
    result["queries"] = [query.to_dict() for query in queries]
    return result

  search_raw: list[dict[str, Any]] = []
  extract_raw: list[dict[str, Any]] = []
  signals: list[WebSignal] = []

  if config.execute_tavily:
    api_key = get_tavily_api_key()
    if not api_key:
      result["status"] = "blocked_missing_api_key"
      result["errors"].append("TAVILY_API_KEY is not set. Set the env var or use --dry-run / --plan-only.")
      if config.output_dir:
        save_tavily_web_signal_run(
          batch=WebSignalBatch(
            batch_id=batch_id,
            topic=config.topic,
            created_at=utc_now_iso(),
            query_set=[query.query for query in queries],
            signals=[],
            source_policy_version=SOURCE_POLICY_VERSION,
            notes="Blocked: missing TAVILY_API_KEY",
          ),
          queries=queries,
          search_raw=search_raw,
          extract_raw=extract_raw,
          output_dir=output_dir,
        )
      return result

    result["status"] = "executed"
    extract_urls: list[str] = []

    for query in queries:
      include_domains = query.include_domains or None
      exclude_domains = query.exclude_domains or None
      try:
        search_response = run_tavily_search(
          query=query.query,
          api_key=api_key,
          max_results=config.max_results_per_query,
          include_domains=include_domains,
          exclude_domains=exclude_domains,
        )
      except Exception as exc:  # noqa: BLE001 — keep pipeline alive
        search_response = {"error": "unexpected_exception", "detail": str(exc)}
        result["errors"].append(f"search failed for {query.query_id}: {exc}")

      search_raw.append(
        {
          "query_id": query.query_id,
          "category": query.category,
          "query": query.query,
          "response": search_response,
        },
      )
      query_signals = tavily_search_results_to_web_signals(
        search_response,
        query=query.query,
        default_signal_type=query.intended_signal_type,
        query_category=query.category,
      )
      signals.extend(query_signals)

      if config.extract_top_urls and not search_response.get("error"):
        for hit in search_response.get("results") or []:
          if not isinstance(hit, dict):
            continue
          url = str(hit.get("url") or "").strip()
          if url and url not in extract_urls:
            extract_urls.append(url)
          if len(extract_urls) >= config.max_extract_urls:
            break

    if config.extract_top_urls and extract_urls:
      try:
        extract_response = run_tavily_extract(extract_urls, api_key)
      except Exception as exc:  # noqa: BLE001
        extract_response = {"error": "unexpected_exception", "detail": str(exc)}
        result["errors"].append(f"extract failed: {exc}")
      extract_raw.append({"urls": extract_urls, "response": extract_response})
      signals.extend(
        tavily_extract_results_to_web_signals(
          extract_response,
          query=config.topic,
          default_signal_type="other",
          query_category="",
        ),
      )

  batch = WebSignalBatch(
    batch_id=batch_id,
    topic=config.topic,
    created_at=utc_now_iso(),
    query_set=[query.query for query in queries],
    signals=signals,
    source_policy_version=SOURCE_POLICY_VERSION,
    notes="Tavily plan-only run" if config.plan_only and not config.execute_tavily else "Tavily web signal run",
  )

  if config.output_dir or config.execute_tavily or config.plan_only:
    save_tavily_web_signal_run(
      batch=batch,
      queries=queries,
      search_raw=search_raw,
      extract_raw=extract_raw,
      output_dir=output_dir,
    )

  result["signal_count"] = len(signals)
  result["queries"] = [query.to_dict() for query in queries]
  if config.plan_only and not config.execute_tavily:
    result["status"] = "plan_only"
  return result
