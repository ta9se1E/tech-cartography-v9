"""Export helpers for the v9 global web search plan."""

from __future__ import annotations

import csv
import json
from io import StringIO
from pathlib import Path
from typing import Any

from .global_web_plan import (
  build_global_web_country_coverage,
  build_global_web_plan_validation_rows,
  summarize_global_web_search_plan_ja,
)


def export_global_web_search_plan(
  plan: dict[str, Any],
  output_dir: Path | str,
) -> dict[str, Path]:
  target_dir = Path(output_dir)
  target_dir.mkdir(parents=True, exist_ok=True)
  paths = {
    "csv": target_dir / "global_web_search_plan.csv",
    "json": target_dir / "global_web_search_plan.json",
    "markdown": target_dir / "global_web_search_plan.md",
    "country_coverage_csv": target_dir / "global_web_country_coverage.csv",
    "validation_csv": target_dir / "global_web_search_plan_validation.csv",
  }
  paths["csv"].write_text(build_global_web_search_plan_csv(plan), encoding="utf-8")
  paths["json"].write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  paths["markdown"].write_text(build_global_web_search_plan_markdown(plan), encoding="utf-8")
  paths["country_coverage_csv"].write_text(build_global_web_country_coverage_csv(plan), encoding="utf-8")
  paths["validation_csv"].write_text(build_global_web_validation_csv(plan), encoding="utf-8")
  return paths


def build_global_web_search_plan_csv(plan: dict[str, Any]) -> str:
  rows = list(plan.get("queries", []) or [])
  output = StringIO()
  writer = csv.DictWriter(
    output,
    fieldnames=[
      "query_id",
      "country_region_code",
      "web_intent",
      "result_bucket",
      "priority",
      "enabled",
      "query_local",
      "query_english_fallback",
      "local_query_generation_mode",
      "fallback_execution_mode",
      "provider_primary",
      "provider_fallback",
      "verification_provider",
      "search_depth",
      "max_results",
      "generated_from",
      "exclude_terms",
      "dedupe_key",
      "duplicate_of",
    ],
  )
  writer.writeheader()
  for row in rows:
    writer.writerow(
      {
        **{key: row.get(key, "") for key in writer.fieldnames or []},
        "generated_from": " | ".join(str(item) for item in row.get("generated_from", []) or []),
        "exclude_terms": " | ".join(str(item) for item in row.get("exclude_terms", []) or []),
      }
    )
  return output.getvalue()


def build_global_web_country_coverage_csv(plan: dict[str, Any]) -> str:
  rows = build_global_web_country_coverage(plan)
  output = StringIO()
  writer = csv.DictWriter(
    output,
    fieldnames=[
      "country_region_code",
      "country_region_name_ja",
      "priority",
      "primary_language",
      "locale",
      "query_count",
      "enabled_query_count",
      "web_query_count",
      "company_query_count",
      "preferred_domains",
      "excluded_domains",
      "official_source_priority",
    ],
  )
  writer.writeheader()
  for row in rows:
    writer.writerow(
      {
        **{key: row.get(key, "") for key in writer.fieldnames or []},
        "preferred_domains": " | ".join(str(item) for item in row.get("preferred_domains", []) or []),
        "excluded_domains": " | ".join(str(item) for item in row.get("excluded_domains", []) or []),
      }
    )
  return output.getvalue()


def build_global_web_validation_csv(plan: dict[str, Any]) -> str:
  rows = build_global_web_plan_validation_rows(plan)
  output = StringIO()
  writer = csv.DictWriter(output, fieldnames=["status", "message"])
  writer.writeheader()
  for row in rows:
    writer.writerow({"status": row.get("status", ""), "message": row.get("message", "")})
  return output.getvalue()


def build_global_web_search_plan_markdown(plan: dict[str, Any]) -> str:
  lines = [
    "# Global Web Search Plan",
    "",
    summarize_global_web_search_plan_ja(plan),
    "",
    "## Countries",
    "",
  ]
  for row in build_global_web_country_coverage(plan):
    lines.append(
      f"- {row['country_region_code']} {row['country_region_name_ja']}: "
      f"{row['query_count']} queries / enabled {row['enabled_query_count']}"
    )
  lines.extend(["", "## Enabled Queries"])
  for query in plan.get("queries", []) or []:
    if not query.get("enabled"):
      continue
    lines.append(
      f"- {query.get('query_id')}: [{query.get('country_region_code')}] "
      f"{query.get('web_intent')} / {query.get('result_bucket')} / {query.get('query_local')}"
    )
  return "\n".join(lines).rstrip() + "\n"


__all__ = [
  "build_global_web_country_coverage_csv",
  "build_global_web_search_plan_csv",
  "build_global_web_search_plan_markdown",
  "build_global_web_validation_csv",
  "export_global_web_search_plan",
]
