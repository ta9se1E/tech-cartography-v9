"""v8 Structured Research Theme schema (Phase 27Q.1)."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from tech_cartography.runtime.v8_sources_schema import utc_now_iso

RESEARCH_THEME_SAFETY_NOTICES: tuple[str, ...] = (
  "BigQuery 自動実行は管理者限定 — 公開デモでは通常 OFF / 非表示。",
  "JP/CN 特許の claim 本文は BigQuery から安定取得できません — 候補メタデータ抽出のみ。",
  "claim 本文は CSV/Excel アップロードまたは手動入力のみ — システムは生成しません。",
  "FTO、侵害、有効性判断、法的結論は行いません。",
  "score は読む優先度であり、特許価値・権利価値ではありません。",
)

VALID_SEARCH_MODES: tuple[str, ...] = (
  "seed_and_keywords",
  "keyword_only",
  "seed_only",
)

PUB_NORMALIZE_RE = re.compile(r"[^A-Z0-9]")


def normalize_publication_number(value: str) -> str:
  """Normalize JP2022090764A / JP-2022090764-A / jp2022090764a to same form."""
  return PUB_NORMALIZE_RE.sub("", str(value or "").strip().upper())


def normalize_publication_list(values: list[str] | tuple[str, ...]) -> list[str]:
  seen: set[str] = set()
  out: list[str] = []
  for raw in values:
    norm = normalize_publication_number(raw)
    if norm and norm not in seen:
      seen.add(norm)
      out.append(norm)
  return out


def resolve_search_mode(
  search_mode: str,
  seed_publication_numbers: list[str],
) -> str:
  mode = (search_mode or "").strip().lower()
  seeds = normalize_publication_list(seed_publication_numbers)
  if not seeds:
    return "keyword_only"
  if mode in VALID_SEARCH_MODES:
    if mode == "seed_only":
      return "seed_only"
    if mode == "keyword_only":
      return "keyword_only"
    return "seed_and_keywords"
  return "seed_and_keywords"


@dataclass
class ResearchThemeProfile:
  case_id: str
  theme_name: str = ""
  theme_description: str = ""
  core_keywords: list[str] = field(default_factory=list)
  application_keywords: list[str] = field(default_factory=list)
  material_process_keywords: list[str] = field(default_factory=list)
  exclude_keywords: list[str] = field(default_factory=list)
  seed_publication_numbers: list[str] = field(default_factory=list)
  max_results: int = 1000
  countries: list[str] = field(default_factory=list)
  publication_year_from: int | None = None
  publication_year_to: int | None = None
  search_mode: str = "seed_and_keywords"
  notes: str = ""
  created_at: str = field(default_factory=utc_now_iso)
  updated_at: str = field(default_factory=utc_now_iso)

  def __post_init__(self) -> None:
    self.seed_publication_numbers = normalize_publication_list(self.seed_publication_numbers)
    self.search_mode = resolve_search_mode(self.search_mode, self.seed_publication_numbers)
    self.max_results = min(1000, max(1, int(self.max_results or 1000)))

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)

  @classmethod
  def from_dict(cls, data: dict[str, Any]) -> ResearchThemeProfile:
    known = {f.name for f in cls.__dataclass_fields__.values()}  # type: ignore[attr-defined]
    filtered = {k: data[k] for k in known if k in data}
    for list_key in (
      "core_keywords",
      "application_keywords",
      "material_process_keywords",
      "exclude_keywords",
      "seed_publication_numbers",
      "countries",
    ):
      if list_key not in filtered:
        filtered[list_key] = []
    return cls(**filtered)
