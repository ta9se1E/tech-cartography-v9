"""Publication number normalization and variant generation for BigQuery lookup."""

from __future__ import annotations

import re
from typing import Any

_KIND_SUFFIXES = ("A1", "A2", "B1", "B2")
_METADATA_PUB_KEYS = (
  "application_publication_number",
  "application_number",
  "related_publication_number",
  "grant_publication_number",
  "priority_publication_number",
  "family_publication_number",
)


def normalize_publication_number(publication_number: str) -> str:
  """Compact uppercase form without spaces or hyphens."""
  return re.sub(r"[\s\-]+", "", str(publication_number or "").upper()).strip()


def infer_country_kind_number(publication_number: str) -> dict[str, str]:
  compact = normalize_publication_number(publication_number)
  country = ""
  kind = ""
  number = ""
  if len(compact) >= 2 and compact[:2].isalpha():
    country = compact[:2]
    rest = compact[2:]
    if len(rest) >= 2 and rest[-2:] in _KIND_SUFFIXES:
      kind = rest[-2:]
      number = rest[:-2]
    else:
      number = rest
  return {
    "country": country,
    "kind": kind,
    "number": number,
    "compact": compact,
  }


def _base_us_variants(compact: str) -> list[str]:
  if not compact.startswith("US"):
    return []
  body = compact[2:]
  variants: list[str] = [
    compact,
    f"US-{body}",
  ]
  if len(body) > 2 and body[-2:] in _KIND_SUFFIXES:
    kind = body[-2:]
    digits = body[:-2]
    variants.extend(
      [
        f"US{digits}{kind}",
        f"US-{digits}{kind}",
        f"US{digits}-{kind}",
        f"US-{digits}-{kind}",
        f"US{digits}{kind}",
        f"US-{digits}{kind}",
        f"US {digits} {kind}",
        f"US-{body}",
      ],
    )
    variants.append(f"US-{digits}{kind}")
    variants.append(f"US{digits}")
    variants.append(f"US-{digits}")
  else:
    variants.append(f"US{body}")
    variants.append(f"US-{body}")
  return variants


def build_publication_number_variants(
  publication_number: str,
  *,
  metadata: dict[str, Any] | None = None,
) -> list[str]:
  compact = normalize_publication_number(publication_number)
  variants: list[str] = []
  if not compact.startswith("US"):
    return variants

  variants.extend(_base_us_variants(compact))
  spaced = str(publication_number or "").strip().upper()
  if spaced and spaced not in variants:
    variants.append(spaced)

  if metadata:
    for key in _METADATA_PUB_KEYS:
      value = metadata.get(key)
      if not value:
        continue
      meta_compact = normalize_publication_number(str(value))
      if not meta_compact or meta_compact == compact:
        continue
      if meta_compact.endswith("A1") or "A1" in meta_compact:
        variants.extend(_base_us_variants(meta_compact))

  deduped: list[str] = []
  seen: set[str] = set()
  for item in variants:
    key = item.upper().replace(" ", "")
    if not item or key in seen:
      continue
    seen.add(key)
    deduped.append(item)
  return deduped


def build_google_patents_url_variants(publication_number: str) -> list[str]:
  compact = normalize_publication_number(publication_number)
  urls: list[str] = []
  if not compact:
    return urls
  urls.append(f"https://patents.google.com/patent/{compact}")
  urls.append(f"https://patents.google.com/patent/{compact}/en")
  if compact.startswith("US") and len(compact) > 2:
    body = compact[2:]
    urls.append(f"https://patents.google.com/patent/US{body}")
    if "-" not in publication_number and len(body) > 2 and body[-2:] in _KIND_SUFFIXES:
      kind = body[-2:]
      digits = body[:-2]
      urls.append(f"https://patents.google.com/patent/US{digits}{kind}")
      urls.append(f"https://patents.google.com/patent/US-{digits}-{kind}")
  deduped: list[str] = []
  seen: set[str] = set()
  for url in urls:
    if url not in seen:
      seen.add(url)
      deduped.append(url)
  return deduped
