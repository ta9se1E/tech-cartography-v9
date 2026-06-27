"""BigQuery candidate search schema (Phase 27Q.1)."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from tech_cartography.runtime.v8_sources_schema import utc_now_iso

BIGQUERY_SAFETY_NOTICES: tuple[str, ...] = (
  "BigQuery は候補特許メタデータ抽出のみ — JP/CN claim/description 取得は期待しない。",
  "claim 本文は CSV/Excel または手動入力のみ — 自動生成しない。",
  "公開 Cloud Run では ENABLE_BIGQUERY_RUN=false / SHOW_BIGQUERY_ADMIN=false を推奨。",
  "dry_run と maximum_bytes_billed でコスト事故を防ぐ。",
  "FTO、侵害、有効性判断、法的結論は行いません。",
)

VALID_RUN_MODES: tuple[str, ...] = (
  "generate_sql",
  "dry_run",
  "execute",
)


@dataclass
class BigQueryQueryConfig:
  case_id: str
  theme_name: str
  search_mode: str
  limit: int
  countries: list[str]
  publication_year_from: int | None
  publication_year_to: int | None
  seed_publication_numbers: list[str]
  core_keyword_count: int
  material_keyword_count: int
  application_keyword_count: int
  exclude_keyword_count: int
  generated_at: str = field(default_factory=utc_now_iso)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class BigQueryDryRunReport:
  case_id: str
  dry_run_ok: bool
  total_bytes_processed: int
  maximum_bytes_billed: int
  job_id: str = ""
  location: str = "US"
  warnings: list[str] = field(default_factory=list)
  errors: list[str] = field(default_factory=list)
  generated_at: str = field(default_factory=utc_now_iso)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


@dataclass
class BigQueryRunManifest:
  run_id: str
  case_id: str
  mode: str
  output_dir: str
  sql_path: str
  config_path: str
  dry_run_path: str = ""
  results_csv_path: str = ""
  large_candidate_csv_path: str = ""
  row_count: int = 0
  warnings: list[str] = field(default_factory=list)
  generated_at: str = field(default_factory=utc_now_iso)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)
