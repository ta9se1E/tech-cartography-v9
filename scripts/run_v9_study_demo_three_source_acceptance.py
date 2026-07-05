#!/usr/bin/env python3
"""Plan/apply acceptance for study demo three-source live search."""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

ACCEPTANCE_ENV = "V9_STUDY_DEMO_THREE_SOURCE_ACCEPTANCE_APPROVED"
THEME = "PAN系炭素繊維のサイジング剤"
KEYWORDS_EN = "carbon fiber sizing agent, epoxy, polyurethane, polyamide, polyester, spreadability, impregnation"


def build_plan() -> dict[str, Any]:
  return {
    "status": "plan",
    "theme": THEME,
    "keywords_en_sample": KEYWORDS_EN,
    "checks": {
      "patent": ["success", "result_count>0", "dry_run_metadata", "billed_bytes", "patent_signal>0"],
      "paper": ["success", "openalex_request>0", "result_count>0", "paper_signal>0"],
      "web": ["success", "tavily_request>0", "result_count>0", "credits_recorded", "web_signal>0"],
      "integration": ["3 source_types", "integrated>0", "keyword_suggestions>0", "export_generated", "no_secret_leak"],
    },
    "apply_guard": ACCEPTANCE_ENV,
    "notes": ["Stage C1 plan only", "requires dedicated secrets and search-enabled deploy"],
  }


def main() -> int:
  parser = argparse.ArgumentParser()
  parser.add_argument("--plan", action="store_true", default=True)
  parser.add_argument("--apply", action="store_true")
  args = parser.parse_args()
  if args.apply:
    if __import__("os").environ.get(ACCEPTANCE_ENV, "").lower() != "true":
      print(f"ERROR: requires {ACCEPTANCE_ENV}=true", file=sys.stderr)
      return 1
    print(json.dumps({"status": "blocked_in_stage_c1", "message": "run acceptance in Stage C2/C3"}, indent=2))
    return 0
  print(json.dumps(build_plan(), ensure_ascii=False, indent=2))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
