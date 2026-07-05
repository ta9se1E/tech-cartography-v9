"""Common signal normalization for study demo search."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping


def _base_signal(
  *,
  source_type: str,
  source_id: str,
  title: str,
  summary: str,
  url: str,
  search_run_id: str,
  query_provenance: Mapping[str, Any],
  organization: str = "",
  country: str = "",
  language: str = "",
  family_id: str = "",
  metadata: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
  return {
    "signal_id": f"{source_type}:{source_id or title[:40]}",
    "source_type": source_type,
    "source_id": source_id,
    "title": title,
    "summary": summary,
    "url": url,
    "published_at": "",
    "organization": organization,
    "country": country,
    "language": language,
    "technology_terms": [],
    "material_terms": [],
    "process_terms": [],
    "property_terms": [],
    "relevance_score": 0.5,
    "source_score": 0.5,
    "source_quality": "medium",
    "query_provenance": dict(query_provenance),
    "retrieved_at": datetime.now(timezone.utc).isoformat(),
    "search_run_id": search_run_id,
    "family_id": family_id,
    "metadata": dict(metadata or {}),
  }


def normalize_patent_row(row: Mapping[str, Any], *, search_run_id: str, query_provenance: Mapping[str, Any]) -> dict[str, Any]:
  pub = str(row.get("publication_number", "") or row.get("external_id", "") or "")
  return _base_signal(
    source_type="patent",
    source_id=pub,
    title=str(row.get("title", "") or ""),
    summary=str(row.get("abstract", "") or ""),
    url=str(row.get("source_url", "") or ""),
    search_run_id=search_run_id,
    query_provenance=query_provenance,
    organization=str(row.get("assignee", "") or ""),
    country=str(row.get("country", "") or ""),
    language=str(row.get("query_language", "") or ""),
    family_id=str(row.get("family_id", "") or ""),
    metadata={"cpc_codes": row.get("cpc_codes", []), "ipc_codes": row.get("ipc_codes", [])},
  )


def normalize_paper_row(row: Mapping[str, Any], *, search_run_id: str, query_provenance: Mapping[str, Any]) -> dict[str, Any]:
  work_id = str(row.get("work_id", "") or row.get("external_id", "") or "")
  return _base_signal(
    source_type="paper",
    source_id=work_id,
    title=str(row.get("title", "") or ""),
    summary=str(row.get("abstract", "") or row.get("reconstructed_abstract", "") or ""),
    url=str(row.get("source_url", "") or row.get("doi", "") or ""),
    search_run_id=search_run_id,
    query_provenance=query_provenance,
    organization=str(row.get("institutions", "") or ""),
    language=str(row.get("language", "") or ""),
    metadata={
      "doi": row.get("doi"),
      "cited_by_count": row.get("cited_by_count"),
      "topics": row.get("topics", []),
      "keywords": row.get("keywords", []),
    },
  )


def normalize_web_row(row: Mapping[str, Any], *, search_run_id: str, query_provenance: Mapping[str, Any]) -> dict[str, Any]:
  url = str(row.get("canonical_url", "") or row.get("source_url", "") or row.get("url", "") or "")
  return _base_signal(
    source_type="web_company",
    source_id=url,
    title=str(row.get("original_title", "") or row.get("title", "") or ""),
    summary=str(row.get("original_snippet", "") or row.get("snippet", "") or ""),
    url=url,
    search_run_id=search_run_id,
    query_provenance=query_provenance,
    organization=str(row.get("domain", "") or ""),
    metadata={
      "score": row.get("score"),
      "published_date": row.get("published_date"),
      "topic": row.get("topic"),
      "search_depth": row.get("search_depth"),
    },
  )
