"""Paper record domain model."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


def reconstruct_abstract_from_inverted_index(inverted_index: dict[str, list[int]] | None) -> str | None:
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
  return ids.get("openalex")


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


def build_display_url_from_parts(
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


@dataclass
class PaperRecord:
  paper_id: str
  title: str
  abstract: str | None = None
  publication_year: int | None = None
  authors: list[str] = field(default_factory=list)
  source_name: str | None = None
  source_type: str | None = None
  doi: str | None = None
  openalex_id: str | None = None
  landing_page_url: str | None = None
  pdf_url: str | None = None
  display_url: str | None = None
  cited_by_count: int | None = None
  is_open_access: bool | None = None
  concepts: list[str] = field(default_factory=list)
  keywords: list[str] = field(default_factory=list)
  raw_source: dict | None = None

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)

  @classmethod
  def from_openalex_work(cls, work: dict[str, Any]) -> PaperRecord:
    doi = _extract_doi(work)
    openalex_id = _extract_openalex_id(work)
    landing_page_url = _extract_landing_page(work)
    pdf_url = _extract_pdf_url(work)
    abstract = work.get("abstract")
    if not abstract:
      abstract = reconstruct_abstract_from_inverted_index(work.get("abstract_inverted_index"))
    authors = [
      str((author.get("author") or {}).get("display_name") or author.get("display_name") or "")
      for author in (work.get("authorships") or [])
    ]
    authors = [name for name in authors if name]
    primary = work.get("primary_location") or {}
    source = primary.get("source") or {}
    concepts = [
      str((concept.get("display_name") or concept.get("name") or ""))
      for concept in (work.get("concepts") or [])
    ]
    concepts = [name for name in concepts if name]
    keywords = [
      str((keyword.get("display_name") or keyword.get("keyword") or ""))
      for keyword in (work.get("keywords") or [])
    ]
    keywords = [name for name in keywords if name]
    open_access = work.get("open_access") or {}
    paper_id = str(work.get("id") or openalex_id or doi or work.get("title") or "unknown")
    return cls(
      paper_id=paper_id,
      title=str(work.get("display_name") or work.get("title") or ""),
      abstract=abstract,
      publication_year=work.get("publication_year"),
      authors=authors,
      source_name=source.get("display_name"),
      source_type=source.get("type"),
      doi=doi,
      openalex_id=openalex_id,
      landing_page_url=landing_page_url,
      pdf_url=pdf_url,
      display_url=build_display_url_from_parts(landing_page_url, doi, pdf_url, openalex_id),
      cited_by_count=work.get("cited_by_count"),
      is_open_access=open_access.get("is_oa"),
      concepts=concepts,
      keywords=keywords,
      raw_source=work,
    )
