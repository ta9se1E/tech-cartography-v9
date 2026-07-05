"""Resolve external source URLs for Study Demo signals without network access."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Mapping
from urllib.parse import quote, unquote, urlparse

from services_v9.watch_profile_schema import normalize_publication_number

STUDY_DEMO_HOST_SUFFIXES = (
  "tech-cartography-v9-study-demo-1020686343587.us-central1.run.app",
  "tech-cartography-v9-study-demo-utejl5os5a-uc.a.run.app",
)

DOI_PREFIX_RE = re.compile(r"^(?:https?://(?:dx\.)?doi\.org/|doi:)\s*", re.I)
OPENALEX_ID_RE = re.compile(r"^W\d+$", re.I)
GOOGLE_PATENTS_URL_RE = re.compile(
  r"^https?://(?:www\.)?patents\.google\.com/patent/([^/?#]+)",
  re.I,
)


@dataclass(frozen=True, slots=True)
class SourceUrlResolution:
  resolved_url: str
  url_source: str
  source_type: str
  is_valid: bool
  validation_reason: str
  display_label: str
  original_url: str
  url_resolution_status: str


def _metadata(signal: Mapping[str, Any]) -> dict[str, Any]:
  meta = signal.get("metadata")
  return dict(meta) if isinstance(meta, Mapping) else {}


def _first_text(*values: object) -> str:
  for value in values:
    text = str(value or "").strip()
    if text:
      return text
  return ""


def collect_original_url(signal: Mapping[str, Any]) -> str:
  meta = _metadata(signal)
  return _first_text(
    signal.get("url"),
    signal.get("source_url"),
    signal.get("landing_page_url"),
    signal.get("canonical_url"),
    signal.get("web_url"),
    meta.get("landing_page_url"),
    meta.get("canonical_url"),
    meta.get("google_patents_url"),
    meta.get("publication_url"),
  )


def normalize_doi(value: str) -> str:
  text = str(value or "").strip()
  if not text:
    return ""
  return DOI_PREFIX_RE.sub("", text).strip()


def build_doi_url(doi: str) -> str:
  normalized = normalize_doi(doi)
  if not normalized:
    return ""
  return f"https://doi.org/{quote(normalized, safe='/-._;()')}"


def build_google_patents_url(publication_number: str, *, language: str = "en") -> str:
  normalized = normalize_publication_number(publication_number)
  if not normalized:
    return ""
  lang = (language or "en").strip().lower() or "en"
  return f"https://patents.google.com/patent/{quote(normalized, safe='')}/{lang}"


def extract_publication_number_from_google_patents_url(url: str) -> str:
  match = GOOGLE_PATENTS_URL_RE.match(str(url or "").strip())
  if not match:
    return ""
  return normalize_publication_number(unquote(match.group(1)))


def normalize_google_patents_url(url: str) -> str:
  text = str(url or "").strip()
  if not GOOGLE_PATENTS_URL_RE.match(text):
    return text
  pub = extract_publication_number_from_google_patents_url(text)
  if not pub:
    return text
  language = "en"
  tail = text.rstrip("/").rsplit("/", 1)[-1]
  if tail.lower() in {"en", "ja", "zh", "de", "fr", "ko"}:
    language = tail.lower()
  return build_google_patents_url(pub, language=language)


def build_openalex_url(openalex_id: str) -> str:
  text = str(openalex_id or "").strip()
  if not text:
    return ""
  if text.startswith("http://") or text.startswith("https://"):
    return text
  token = text.rsplit("/", 1)[-1]
  if OPENALEX_ID_RE.match(token):
    return f"https://openalex.org/{token.upper()}"
  return ""


def is_valid_external_url(url: str) -> tuple[bool, str]:
  text = str(url or "").strip()
  if not text:
    return False, "empty"
  if text in {"/", "#"}:
    return False, "relative_placeholder"
  lowered = text.lower()
  if lowered.startswith(("javascript:", "data:", "file:")):
    return False, "unsafe_scheme"
  parsed = urlparse(text)
  scheme = (parsed.scheme or "").lower()
  if scheme not in {"http", "https"}:
    return False, "unsupported_scheme"
  host = (parsed.hostname or "").lower()
  if not host:
    return False, "missing_host"
  if host in {"localhost", "127.0.0.1", "0.0.0.0"}:
    return False, "local_host"
  for suffix in STUDY_DEMO_HOST_SUFFIXES:
    if host == suffix or host.endswith(f".{suffix}"):
      return False, "study_demo_self_url"
  if not parsed.netloc:
    return False, "relative_url"
  if text.startswith("//"):
    return False, "protocol_relative"
  if not text.startswith("http://") and not text.startswith("https://"):
    return False, "not_absolute"
  return True, "ok"


def _resolve_patent_url(signal: Mapping[str, Any], meta: Mapping[str, Any]) -> tuple[str, str]:
  candidates = (
    ("source_url", signal.get("source_url")),
    ("url", signal.get("url")),
    ("google_patents_url", meta.get("google_patents_url")),
    ("publication_url", meta.get("publication_url")),
    ("source_url_meta", meta.get("source_url")),
  )
  for source, value in candidates:
    text = str(value or "").strip()
    if GOOGLE_PATENTS_URL_RE.match(text):
      normalized = normalize_google_patents_url(text)
      if normalized != text:
        source = "google_patents_url_normalized"
      text = normalized
    valid, _ = is_valid_external_url(text)
    if valid:
      return text, source

  publication_number = _first_text(
    signal.get("publication_number"),
    signal.get("source_id"),
    signal.get("external_id"),
    meta.get("publication_number"),
  )
  built = build_google_patents_url(publication_number)
  if built:
    return built, "publication_number"
  return "", "missing"


def _resolve_paper_url(signal: Mapping[str, Any], meta: Mapping[str, Any]) -> tuple[str, str]:
  candidates = (
    ("landing_page_url", signal.get("landing_page_url")),
    ("landing_page_url_meta", meta.get("landing_page_url")),
    ("source_url", signal.get("source_url")),
    ("url", signal.get("url")),
    ("primary_location", _first_text((meta.get("primary_location") or {}).get("landing_page_url") if isinstance(meta.get("primary_location"), Mapping) else "")),
  )
  for source, value in candidates:
    text = str(value or "").strip()
    valid, _ = is_valid_external_url(text)
    if valid:
      return text, source

  doi = _first_text(signal.get("doi"), meta.get("doi"))
  doi_url = build_doi_url(doi)
  if doi_url:
    valid, _ = is_valid_external_url(doi_url)
    if valid:
      return doi_url, "doi"

  for source_name, key in (("openalex_url", "openalex_url"), ("openalex_id", "openalex_id")):
    built = build_openalex_url(str(meta.get(key, signal.get(key, "")) or ""))
    valid, _ = is_valid_external_url(built)
    if valid:
      return built, source_name

  return "", "missing"


def _resolve_web_url(signal: Mapping[str, Any], meta: Mapping[str, Any]) -> tuple[str, str]:
  candidates = (
    ("source_url", signal.get("source_url")),
    ("url", signal.get("url")),
    ("web_url", signal.get("web_url")),
    ("canonical_url", signal.get("canonical_url")),
    ("canonical_url_meta", meta.get("canonical_url")),
    ("web_url_meta", meta.get("web_url")),
  )
  for source, value in candidates:
    text = str(value or "").strip()
    valid, _ = is_valid_external_url(text)
    if valid:
      return text, source
  return "", "missing"


def resolve_signal_source_url(signal: Mapping[str, Any]) -> SourceUrlResolution:
  source_type = str(signal.get("source_type", signal.get("type", "")) or "").strip().lower()
  if source_type == "web":
    source_type = "web_company"
  original_url = collect_original_url(signal)
  meta = _metadata(signal)

  if source_type == "patent":
    resolved, url_source = _resolve_patent_url(signal, meta)
  elif source_type == "paper":
    resolved, url_source = _resolve_paper_url(signal, meta)
  elif source_type in {"web_company", "web", "company"}:
    resolved, url_source = _resolve_web_url(signal, meta)
  else:
    resolved = _first_text(signal.get("source_url"), signal.get("url"))
    url_source = "source_url" if resolved else "missing"

  is_valid, validation_reason = is_valid_external_url(resolved)
  status = "resolved" if is_valid else ("missing" if url_source == "missing" else "invalid")
  label = "引用元を開く" if is_valid else "引用元URL未取得"
  return SourceUrlResolution(
    resolved_url=resolved if is_valid else "",
    url_source=url_source,
    source_type=source_type or "unknown",
    is_valid=is_valid,
    validation_reason=validation_reason,
    display_label=label,
    original_url=original_url,
    url_resolution_status=status,
  )


def enrich_signal_with_url_provenance(signal: Mapping[str, Any]) -> dict[str, Any]:
  item = dict(signal)
  resolution = resolve_signal_source_url(item)
  item.setdefault("url", collect_original_url(item) or item.get("url", ""))
  item.setdefault("source_url", item.get("source_url") or item.get("url") or "")
  item["source_url_original"] = resolution.original_url
  item["source_url_resolved"] = resolution.resolved_url
  item["source_url_status"] = resolution.url_resolution_status
  item["source_url_source"] = resolution.url_source
  item["url_resolution_status"] = resolution.url_resolution_status
  if resolution.is_valid:
    item["resolved_url"] = resolution.resolved_url
  else:
    item["resolved_url"] = ""
  return item


def summarize_url_resolution(signals: list[Mapping[str, Any]]) -> dict[str, int]:
  counts = {
    "patent_resolved": 0,
    "paper_resolved": 0,
    "web_resolved": 0,
    "missing": 0,
    "invalid": 0,
    "self_app_url": 0,
    "relative": 0,
    "empty_href": 0,
  }
  for signal in signals:
    resolution = resolve_signal_source_url(signal)
    source_type = resolution.source_type
    if resolution.is_valid:
      if source_type == "patent":
        counts["patent_resolved"] += 1
      elif source_type == "paper":
        counts["paper_resolved"] += 1
      elif source_type in {"web_company", "web", "company"}:
        counts["web_resolved"] += 1
      continue
    if resolution.validation_reason == "study_demo_self_url":
      counts["self_app_url"] += 1
    elif resolution.validation_reason in {"relative_url", "relative_placeholder", "not_absolute", "protocol_relative"}:
      counts["relative"] += 1
    elif resolution.url_resolution_status == "missing":
      counts["missing"] += 1
      counts["empty_href"] += 1
    else:
      counts["invalid"] += 1
      counts["empty_href"] += 1
  return counts
