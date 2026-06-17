"""Limited OpenAlex execution for claims-based paper query candidates."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any

from tech_cartography.evidence.source_quality_agent import evaluate_paper_source_quality
from tech_cartography.reports.project_export import save_records_csv
from tech_cartography.retrieval.openalex_retriever import (
  OpenAlexRetrievalConfig,
  normalize_openalex_results,
  search_openalex,
)

LIMITED_EXECUTION_CAVEAT = (
  "これらの論文は、特許請求項を証明するものではなく、"
  "技術背景・材料プロセス・物性関係を確認するための supporting evidence candidate です。"
  "明細書・実施例が未入力の場合、技術妥当性の評価には限界があります。"
)

REQUIRED_QUERY_TYPES = ("material_process", "property_condition")
PREFERRED_OPTIONAL_TYPES = ("structure_property", "surface_interface", "process_condition", "measurement_method")
MAX_PER_TYPE = 2


@dataclass
class OpenAlexExecutionConfig:
  max_queries: int = 3
  max_results_per_query: int = 5
  cache_first: bool = True
  execute_openalex: bool = False
  timeout_seconds: int = 30
  source_scope: str = "manual_claims_only"
  allow_low_confidence_queries: bool = False
  cache_dir: str = "data/runtime/openalex_cache"
  output_dir: str = "outputs/openalex_limited_execution"


@dataclass
class OpenAlexExecutionResult:
  publication_number: str = ""
  executed_queries_count: int = 0
  skipped_queries_count: int = 0
  total_paper_records: int = 0
  cache_hits: int = 0
  api_errors: list[str] = field(default_factory=list)
  execution_status: str = "plan_only"
  caveat_japanese: str = LIMITED_EXECUTION_CAVEAT
  mode: str = "plan_only"
  selected_queries: list[dict[str, Any]] = field(default_factory=list)
  paper_records: list[dict[str, Any]] = field(default_factory=list)
  source_quality_results: list[dict[str, Any]] = field(default_factory=list)
  errors: list[dict[str, Any]] = field(default_factory=list)

  def to_dict(self) -> dict[str, Any]:
    return asdict(self)


def _confidence_rank(candidate: dict[str, Any]) -> int:
  return 0 if str(candidate.get("confidence") or "").lower() == "medium" else 1


def _type_score(candidate: dict[str, Any]) -> int:
  qtype = str(candidate.get("query_type") or "")
  if qtype in REQUIRED_QUERY_TYPES:
    return 0
  if qtype in PREFERRED_OPTIONAL_TYPES:
    return 1
  if qtype == "application":
    return 2
  return 3


def select_openalex_queries_for_execution(
  candidates: list[dict[str, Any]],
  max_queries: int = 3,
  *,
  allow_low_confidence_queries: bool = False,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
  usable = [c for c in candidates if str(c.get("query") or "").strip()]
  skipped = [c for c in candidates if c not in usable]
  medium = sorted([c for c in usable if c.get("confidence") == "medium"], key=_type_score)
  low = sorted([c for c in usable if c.get("confidence") != "medium"], key=_type_score)

  selected: list[dict[str, Any]] = []
  type_counts: dict[str, int] = {}

  def _try_add(row: dict[str, Any]) -> bool:
    if len(selected) >= max_queries:
      return False
    qtype = str(row.get("query_type") or "unknown")
    if qtype == "broad_background" and type_counts.get("broad_background", 0) >= 1:
      return False
    if type_counts.get(qtype, 0) >= MAX_PER_TYPE:
      return False
    if row in selected:
      return False
    selected.append(row)
    type_counts[qtype] = type_counts.get(qtype, 0) + 1
    return True

  for req_type in REQUIRED_QUERY_TYPES:
    for row in medium:
      if row.get("query_type") == req_type:
        _try_add(row)
        break

  for opt_type in PREFERRED_OPTIONAL_TYPES:
    if len(selected) >= max_queries:
      break
    for row in medium:
      if row.get("query_type") == opt_type:
        _try_add(row)
        break

  for row in medium:
    if len(selected) >= max_queries:
      break
    _try_add(row)

  if allow_low_confidence_queries and len(selected) < max_queries:
    for row in low:
      if len(selected) >= max_queries:
        break
      _try_add(row)

  selected_keys = {str(r.get("query_id") or r.get("query")) for r in selected}
  skipped.extend([c for c in usable if str(c.get("query_id") or c.get("query")) not in selected_keys])
  return selected[:max_queries], skipped


def deduplicate_paper_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
  deduped: list[dict[str, Any]] = []
  seen: set[str] = set()
  for paper in records:
    key = (
      str(paper.get("doi") or "").lower()
      or str(paper.get("openalex_id") or "").lower()
      or str(paper.get("paper_id") or "").lower()
      or str(paper.get("title") or "").lower()
    )
    if not key or key in seen:
      continue
    seen.add(key)
    deduped.append(paper)
  return deduped


def classify_openalex_execution_status(result: dict[str, Any]) -> str:
  mode = str(result.get("mode") or "plan_only")
  if mode == "plan_only":
    return "plan_only"
  errors = result.get("api_errors") or result.get("errors") or []
  papers = int(result.get("total_paper_records", 0) or len(result.get("paper_records") or []))
  executed = int(result.get("executed_queries_count", 0))
  if executed == 0:
    return "no_queries_executed"
  if errors and papers == 0:
    return "partial_error_no_papers"
  if errors:
    return "partial_success_with_errors"
  if papers == 0:
    return "executed_no_results"
  return "success"


def render_openalex_limited_summary(result: dict[str, Any]) -> str:
  lines = [
    "# OpenAlex Limited Execution Summary",
    "",
    f"- mode: {result.get('mode', 'plan_only')}",
    f"- execution status: {result.get('execution_status', classify_openalex_execution_status(result))}",
    f"- publication number: {result.get('publication_number', '')}",
    f"- executed queries: {result.get('executed_queries_count', 0)}",
    f"- skipped queries: {result.get('skipped_queries_count', 0)}",
    f"- paper records: {result.get('total_paper_records', 0)}",
    f"- cache hits: {result.get('cache_hits', 0)}",
    "",
    "## Selected queries",
    "",
  ]
  for row in result.get("selected_queries", [])[:10]:
    lines.append(
      f"- [{row.get('query_type')}] ({row.get('confidence')}) {row.get('query')}",
    )
  if not result.get("selected_queries"):
    lines.append("- (none)")

  errors = result.get("api_errors") or []
  if errors:
    lines.extend(["", "## API errors", ""])
    for err in errors:
      lines.append(f"- {err}")

  lines.extend(["", "## Caveat", "", result.get("caveat_japanese") or LIMITED_EXECUTION_CAVEAT, ""])
  lines.append("※ 金額・課金情報は含みません。")
  return "\n".join(lines)


def execute_openalex_limited(
  candidates: list[dict[str, Any]],
  config: OpenAlexExecutionConfig,
  *,
  publication_number: str = "",
) -> dict[str, Any]:
  selected, skipped = select_openalex_queries_for_execution(
    candidates,
    max_queries=int(config.max_queries),
    allow_low_confidence_queries=bool(config.allow_low_confidence_queries),
  )
  pub = publication_number or str((selected[0] if selected else candidates[0] if candidates else {}).get("publication_number") or "")

  retrieval_cfg = OpenAlexRetrievalConfig(
    execute=bool(config.execute_openalex),
    max_queries=int(config.max_queries),
    max_results_per_query=int(config.max_results_per_query),
    cache_dir=config.cache_dir,
    use_cache=bool(config.cache_first),
    request_timeout_sec=int(config.timeout_seconds),
    output_dir=config.output_dir,
  )

  paper_records: list[dict[str, Any]] = []
  api_errors: list[str] = []
  error_records: list[dict[str, Any]] = []
  cache_hits = 0
  executed_count = 0

  if not config.execute_openalex:
    result = OpenAlexExecutionResult(
      publication_number=pub,
      executed_queries_count=0,
      skipped_queries_count=len(skipped),
      total_paper_records=0,
      cache_hits=0,
      api_errors=[],
      execution_status="plan_only",
      mode="plan_only",
      selected_queries=selected,
      paper_records=[],
      source_quality_results=[],
      errors=[],
    )
    return result.to_dict()

  for row in selected:
    query = str(row.get("query") or "").strip()
    if not query:
      continue
    executed_count += 1
    raw = search_openalex(query, retrieval_cfg)
    status = str(raw.get("status") or "")
    if status == "cache_hit":
      cache_hits += 1
    if status == "error":
      msg = str(raw.get("error") or "unknown error")
      api_errors.append(f"{query}: {msg}")
      error_records.append({"query": query, "error": msg, "query_id": row.get("query_id")})
      continue
    paper_records.extend(normalize_openalex_results(raw, row))

  deduped = deduplicate_paper_records(paper_records)
  source_quality = [evaluate_paper_source_quality(paper).to_dict() for paper in deduped]

  payload = OpenAlexExecutionResult(
    publication_number=pub,
    executed_queries_count=executed_count,
    skipped_queries_count=len(skipped),
    total_paper_records=len(deduped),
    cache_hits=cache_hits,
    api_errors=api_errors,
    execution_status="",
    mode="execute",
    selected_queries=selected,
    paper_records=deduped,
    source_quality_results=source_quality,
    errors=error_records,
  )
  result_dict = payload.to_dict()
  result_dict["execution_status"] = classify_openalex_execution_status(result_dict)
  result_dict["skipped_queries"] = skipped
  return result_dict


def save_openalex_limited_artifacts(result: dict[str, Any], output_dir: str | Path) -> dict[str, str]:
  out = Path(output_dir)
  out.mkdir(parents=True, exist_ok=True)

  summary_path = out / "openalex_execution_summary.json"
  md_path = out / "openalex_execution_summary.md"
  papers_json = out / "openalex_paper_records.json"
  errors_json = out / "openalex_errors.json"

  summary_path.write_text(json.dumps(result, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
  md_path.write_text(render_openalex_limited_summary(result), encoding="utf-8")
  papers_json.write_text(
    json.dumps(result.get("paper_records", []), indent=2, ensure_ascii=False, default=str),
    encoding="utf-8",
  )
  errors_json.write_text(
    json.dumps(result.get("errors", []), indent=2, ensure_ascii=False),
    encoding="utf-8",
  )

  paths = {
    "openalex_execution_summary_json": str(summary_path),
    "openalex_execution_summary_md": str(md_path),
    "openalex_selected_queries_csv": save_records_csv(
      result.get("selected_queries", []),
      out / "openalex_selected_queries.csv",
    ),
    "openalex_paper_records_csv": save_records_csv(
      result.get("paper_records", []),
      out / "openalex_paper_records.csv",
    ),
    "openalex_paper_records_json": str(papers_json),
    "openalex_source_quality_csv": save_records_csv(
      result.get("source_quality_results", []),
      out / "openalex_source_quality.csv",
    ),
    "openalex_errors_json": str(errors_json),
  }
  return paths
