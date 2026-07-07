#!/usr/bin/env python3
"""Simple Mode UI checks for Study Demo hackathon demo."""

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

FIXTURE_PATH = ROOT / "tests" / "fixtures" / "study_demo_p0_watch_profile_samples.json"
DEFAULT_RUN_ID = "study_demo_search_20260705_145711_c06e0a1b"


def _load_fixture() -> dict[str, Any]:
  return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def run_plan(*, mode: str, search_run_id: str) -> dict[str, Any]:
  payload = _load_fixture()
  if str(payload.get("search_run_id", "")) != search_run_id:
    return {"status": "blocked", "message": "fixture run id mismatch", "expected": search_run_id}

  from services_v9.study_demo_simple_ui_analysis import build_simple_ui_check_result

  result = build_simple_ui_check_result(fixture=payload, mode=mode)
  result["search_run_id"] = search_run_id
  return result


def main() -> int:
  parser = argparse.ArgumentParser(description="Study Demo Simple Mode UI checks")
  parser.add_argument("--plan", action="store_true", help="Run plan checks only")
  parser.add_argument("--mode", default="simple", choices=["simple", "advanced"])
  parser.add_argument("--search-run-id", default=DEFAULT_RUN_ID)
  args = parser.parse_args()

  if not args.plan:
    print(json.dumps({"status": "blocked", "message": "only --plan is supported"}, ensure_ascii=False, indent=2))
    return 1

  result = run_plan(mode=args.mode, search_run_id=args.search_run_id)
  print(json.dumps(result, ensure_ascii=False, indent=2))
  return 0 if result.get("status") == "ok" else 1


if __name__ == "__main__":
  raise SystemExit(main())
