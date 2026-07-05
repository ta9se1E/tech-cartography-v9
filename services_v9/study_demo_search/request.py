"""Search request parsing and validation for study demo."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any, Mapping

from .constants import FORBIDDEN_INPUT_PATTERNS, MAX_FIELD_LENGTH

_YEAR_PATTERN = re.compile(r"^\d{4}$")


@dataclass(frozen=True)
class StudyDemoSearchRequest:
  theme: str = ""
  keywords_ja: str = ""
  keywords_en: str = ""
  exact_phrase: str = ""
  exclude_keywords: str = ""
  seed_patent: str = ""
  year_start: str = ""
  year_end: str = ""
  enable_patent: bool = True
  enable_paper: bool = True
  enable_web: bool = True
  patent_display_limit: int = 50
  paper_display_limit: int = 50
  web_max_results: int = 10
  web_topic: str = "general"
  web_search_depth: str = "basic"
  web_time_range: str = "none"
  web_include_domains: str = ""
  web_exclude_domains: str = ""
  web_exact_match: bool = False
  web_include_raw_content: bool = False
  paper_open_access_only: bool = False
  paper_sort: str = "relevance"


def _normalize_text(value: Any, *, max_length: int = MAX_FIELD_LENGTH) -> str:
  text = str(value or "").strip()
  if len(text) > max_length:
    raise ValueError(f"field exceeds {max_length} characters")
  lowered = text.lower()
  for token in FORBIDDEN_INPUT_PATTERNS:
    if token in lowered:
      raise ValueError("forbidden input pattern detected")
  return text


def parse_search_request(payload: Mapping[str, Any]) -> StudyDemoSearchRequest:
  return StudyDemoSearchRequest(
    theme=_normalize_text(payload.get("theme", "")),
    keywords_ja=_normalize_text(payload.get("keywords_ja", "")),
    keywords_en=_normalize_text(payload.get("keywords_en", "")),
    exact_phrase=_normalize_text(payload.get("exact_phrase", "")),
    exclude_keywords=_normalize_text(payload.get("exclude_keywords", "")),
    seed_patent=_normalize_text(payload.get("seed_patent", "")),
    year_start=_normalize_text(payload.get("year_start", "")),
    year_end=_normalize_text(payload.get("year_end", "")),
    enable_patent=bool(payload.get("enable_patent", True)),
    enable_paper=bool(payload.get("enable_paper", True)),
    enable_web=bool(payload.get("enable_web", True)),
    patent_display_limit=int(payload.get("patent_display_limit", 50) or 50),
    paper_display_limit=int(payload.get("paper_display_limit", 50) or 50),
    web_max_results=min(int(payload.get("web_max_results", 10) or 10), 20),
    web_topic=str(payload.get("web_topic", "general") or "general"),
    web_search_depth=str(payload.get("web_search_depth", "basic") or "basic"),
    web_time_range=str(payload.get("web_time_range", "none") or "none"),
    web_include_domains=_normalize_text(payload.get("web_include_domains", "")),
    web_exclude_domains=_normalize_text(payload.get("web_exclude_domains", "")),
    web_exact_match=bool(payload.get("web_exact_match", False)),
    web_include_raw_content=bool(payload.get("web_include_raw_content", False)),
    paper_open_access_only=bool(payload.get("paper_open_access_only", False)),
    paper_sort=str(payload.get("paper_sort", "relevance") or "relevance"),
  )


def validate_search_request(request: StudyDemoSearchRequest) -> list[str]:
  errors: list[str] = []
  searchable = [
    request.theme,
    request.keywords_ja,
    request.keywords_en,
    request.exact_phrase,
    request.exclude_keywords,
    request.seed_patent,
  ]
  if not any(str(item or "").strip() for item in searchable):
    errors.append("at least one search condition is required")
  if not (request.enable_patent or request.enable_paper or request.enable_web):
    errors.append("at least one provider must be enabled")
  for label, year in (("year_start", request.year_start), ("year_end", request.year_end)):
    if year and not _YEAR_PATTERN.match(year):
      errors.append(f"{label} must be YYYY")
  if request.year_start and request.year_end and int(request.year_start) > int(request.year_end):
    errors.append("year_start must be <= year_end")
  if request.patent_display_limit not in {5, 20, 50, 100}:
    errors.append("patent_display_limit must be 5, 20, 50, or 100")
  if request.paper_display_limit not in {5, 20, 50, 100, 200}:
    errors.append("paper_display_limit must be 5, 20, 50, 100, or 200")
  if request.web_max_results not in {5, 10, 20}:
    errors.append("web_max_results must be 5, 10, or 20")
  if request.web_search_depth not in {"basic", "advanced"}:
    errors.append("web_search_depth must be basic or advanced")
  return errors


def request_fingerprint(request: StudyDemoSearchRequest) -> str:
  import hashlib
  import json

  payload = {
    "theme": request.theme,
    "keywords_ja": request.keywords_ja,
    "keywords_en": request.keywords_en,
    "exact_phrase": request.exact_phrase,
    "exclude_keywords": request.exclude_keywords,
    "seed_patent": request.seed_patent,
    "year_start": request.year_start,
    "year_end": request.year_end,
    "enable_patent": request.enable_patent,
    "enable_paper": request.enable_paper,
    "enable_web": request.enable_web,
    "patent_display_limit": request.patent_display_limit,
    "paper_display_limit": request.paper_display_limit,
    "web_max_results": request.web_max_results,
    "web_topic": request.web_topic,
    "web_search_depth": request.web_search_depth,
    "web_time_range": request.web_time_range,
    "web_include_domains": request.web_include_domains,
    "web_exclude_domains": request.web_exclude_domains,
    "web_exact_match": request.web_exact_match,
    "web_include_raw_content": request.web_include_raw_content,
    "paper_open_access_only": request.paper_open_access_only,
    "paper_sort": request.paper_sort,
  }
  digest = hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
  return digest[:16]
