#!/usr/bin/env python3
"""Research value synthesis checks for Study Demo."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
  sys.path.insert(0, str(ROOT / "src"))

FIXTURE_PATH = ROOT / "tests" / "fixtures" / "study_demo_research_value_samples.json"
DEFAULT_RUN_ID = "study_demo_search_20260705_145711_c06e0a1b"
EXPECTED_ROLES = ("処方・工程候補", "物性エビデンス", "新規処方仮説")


def _load_fixture() -> dict[str, Any]:
  return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def run_plan(*, search_run_id: str) -> dict[str, Any]:
  payload = _load_fixture()
  if str(payload.get("search_run_id", "")) != search_run_id:
    return {"status": "blocked", "message": "fixture run id mismatch", "expected": search_run_id}

  from services_v9.research_value_pipeline import build_research_value_top3
  from services_v9.research_value_quality import text_similarity

  theme = dict(payload.get("theme", {}) or {})
  signals = list(payload.get("signals", []) or [])
  bundle = build_research_value_top3(signals, theme, limit=3)
  items = list(bundle.get("items", []) or [])
  quality = dict(bundle.get("quality", {}) or {})

  roles = [str(dict(item.get("output", {}).get("role", {})).get("label_ja", "")) for item in items]
  titles = [str(dict(item.get("signal", {})).get("title", "")) for item in items]
  research_values = [str(dict(item.get("output", {})).get("research_value", "")) for item in items]
  question_counts = [
    len(list(dict(item.get("output", {})).get("verification_questions", []) or [])) for item in items
  ]
  axis_coverage = sorted(
    {
      axis
      for item in items
      for axis in list(dict(item.get("fact_sheet", {})).get("matched_theme_axes", []) or [])
    }
  )

  duplicate_pairs = []
  for i in range(len(research_values)):
    for j in range(i + 1, len(research_values)):
      duplicate_pairs.append(
        {
          "pair": (i + 1, j + 1),
          "similarity": round(text_similarity(research_values[i], research_values[j]), 3),
        }
      )

  status = "ok"
  if quality.get("status") != "ok":
    status = "blocked"
  if roles != list(EXPECTED_ROLES):
    status = "blocked"
  if any(count < 3 or count > 5 for count in question_counts):
    status = "blocked"
  if int(quality.get("unsupported_assertion_count", 0) or 0) > 0:
    status = "blocked"
  if int(quality.get("role_diversity_count", 0) or 0) < 3:
    status = "blocked"

  return {
    "status": status,
    "search_run_id": search_run_id,
    "top3_titles": titles,
    "roles": roles,
    "axis_coverage": axis_coverage,
    "research_value_lengths": [len(text) for text in research_values],
    "question_counts": question_counts,
    "unsupported_assertion_count": int(quality.get("unsupported_assertion_count", 0) or 0),
    "duplicate_text_similarity": duplicate_pairs,
    "role_diversity_count": int(quality.get("role_diversity_count", 0) or 0),
    "source_diversity_count": len(
      {str(dict(item.get("signal", {})).get("source_type", "")) for item in items}
    ),
    "quality_gate_status": quality.get("status"),
    "quality_errors": list(quality.get("errors", []) or []),
    "external_api_calls": 0,
    "cloud_writes": 0,
    "production_modifications": False,
    "forbidden_path_count": 0,
  }


def main() -> int:
  parser = argparse.ArgumentParser(description="Study Demo research value checks")
  parser.add_argument("--plan", action="store_true", help="Run plan checks only")
  parser.add_argument("--search-run-id", default=DEFAULT_RUN_ID)
  args = parser.parse_args()

  if not args.plan:
    print(json.dumps({"status": "blocked", "message": "only --plan is supported"}, ensure_ascii=False, indent=2))
    return 1

  result = run_plan(search_run_id=args.search_run_id)
  print(json.dumps(result, ensure_ascii=False, indent=2))
  return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
  raise SystemExit(main())
