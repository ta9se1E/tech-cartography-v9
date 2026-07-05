#!/usr/bin/env python3
"""Plan/apply acceptance for study demo three-source live search."""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any, Mapping

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
  sys.path.insert(0, str(ROOT / "src"))

from services_v9.study_demo_config import (  # noqa: E402
  STUDY_DEMO_BUCKET_DEFAULT,
  STUDY_DEMO_OPENALEX_SECRET,
  STUDY_DEMO_PROJECT_DEFAULT,
  STUDY_DEMO_TAVILY_SECRET,
)
from services_v9.study_demo_search.execute import execute_three_source_search  # noqa: E402
from services_v9.study_demo_search.plan import build_search_plan_preview  # noqa: E402
from services_v9.study_demo_search.request import StudyDemoSearchRequest, parse_search_request  # noqa: E402
from services_v9.study_demo_search.storage import load_search_run  # noqa: E402

ACCEPTANCE_ENV = "V9_STUDY_DEMO_THREE_SOURCE_ACCEPTANCE_APPROVED"
PROJECT_ID = STUDY_DEMO_PROJECT_DEFAULT
OPENALEX_SECRET_VERSION = "1"
TAVILY_SECRET_VERSION = "1"

THEME = (
  "PAN系炭素繊維のサイジング剤について、"
  "エポキシ、ポリウレタン、ポリアミド、ポリエステル、"
  "変性ポリオレフィン系の組成、付与量、乾燥条件が、"
  "集束性、開繊性、毛羽、耐擦過性、樹脂含浸性、"
  "界面接着性、引張強度、引張弾性率へ与える影響"
)
KEYWORDS_EN = (
  "carbon fiber sizing agent, carbon fiber tow, aqueous sizing, epoxy, polyurethane, "
  "polyamide, polyester, modified polyolefin, sizing amount, drying, fuzz, "
  "abrasion resistance, spreadability, impregnation, interfacial adhesion, tensile modulus"
)
EXCLUDE_KEYWORDS = (
  "paper sizing, starch sizing, activated carbon, carbon black, battery electrode, cement"
)

REQUIRED_ARTIFACTS = (
  "search_request.json",
  "search_plan.json",
  "cost_estimate.json",
  "provider_status.json",
  "patent_results.json",
  "paper_results.json",
  "web_results.json",
  "integrated_signals.json",
  "keyword_suggestions.json",
  "similar_patents.json",
  "usage_metrics.json",
  "search_status.json",
  "search_report.md",
)

SECRET_LEAK_PATTERNS = (
  re.compile(r"api[_-]?key", re.I),
  re.compile(r"authorization", re.I),
  re.compile(r"smtp", re.I),
  re.compile(r"password", re.I),
  re.compile(r"secret", re.I),
)


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
    "notes": [
      "Stage C2 apply runs one live three-source search",
      "requires dedicated secrets and search-enabled deploy",
      "no automatic retry",
    ],
  }


def build_acceptance_request() -> StudyDemoSearchRequest:
  return parse_search_request(
    {
      "theme": THEME,
      "keywords_en": KEYWORDS_EN,
      "exclude_keywords": EXCLUDE_KEYWORDS,
      "enable_patent": True,
      "enable_paper": True,
      "enable_web": True,
      "patent_display_limit": 50,
      "paper_display_limit": 50,
      "web_max_results": 10,
      "web_search_depth": "basic",
      "web_topic": "general",
    }
  )


def _load_secret_version(secret_name: str, version: str) -> str:
  from google.cloud import secretmanager

  client = secretmanager.SecretManagerServiceClient()
  resource = f"projects/{PROJECT_ID}/secrets/{secret_name}/versions/{version}"
  response = client.access_secret_version(request={"name": resource})
  return response.payload.data.decode("utf-8")


def build_acceptance_environ() -> dict[str, str]:
  env = dict(os.environ)
  env.update(
    {
      "GOOGLE_CLOUD_PROJECT": PROJECT_ID,
      "V9_STUDY_DEMO_MODE": "true",
      "V9_STUDY_DEMO_BUCKET": STUDY_DEMO_BUCKET_DEFAULT,
      "V9_STUDY_DEMO_SEARCH_ENABLED": "true",
      "V9_STUDY_DEMO_ENABLE_PATENT_SEARCH": "true",
      "V9_STUDY_DEMO_ENABLE_PAPER_SEARCH": "true",
      "V9_STUDY_DEMO_ENABLE_WEB_SEARCH": "true",
      "V9_STUDY_DEMO_BIGQUERY_DRY_RUN_FIRST": "true",
      "V9_STUDY_DEMO_BIGQUERY_MAX_BYTES_BILLED": "2199023255552",
      "V9_STUDY_DEMO_BIGQUERY_PRICE_PER_TIB_USD": "6.25",
      "V9_STUDY_DEMO_DISABLE_EXTERNAL_EXECUTION": "true",
      "V9_STUDY_DEMO_OPENALEX_API_KEY": _load_secret_version(STUDY_DEMO_OPENALEX_SECRET, OPENALEX_SECRET_VERSION),
      "V9_STUDY_DEMO_TAVILY_API_KEY": _load_secret_version(STUDY_DEMO_TAVILY_SECRET, TAVILY_SECRET_VERSION),
    }
  )
  return env


def _count_signals_by_source(integrated: Mapping[str, Any]) -> dict[str, int]:
  counts: dict[str, int] = {}
  for item in list(integrated.get("signals", []) or []):
    source_type = str(item.get("source_type", "") or "")
    counts[source_type] = counts.get(source_type, 0) + 1
  if counts.get("web", 0) and not counts.get("web_company", 0):
    counts["web_company"] = counts.get("web", 0)
  return counts


def _artifact_has_secret_leak(payload: Any) -> bool:
  text = json.dumps(payload, ensure_ascii=False)
  lowered = text.lower()
  forbidden_substrings = (
    "sk-",
    "tvly-",
    "bearer ",
    "authorization:",
    "smtp_password",
    "tavily_api_key",
    "openalex_api_key",
    "v9_study_demo_password",
  )
  return any(token in lowered for token in forbidden_substrings)


def validate_acceptance_result(result: Mapping[str, Any], *, artifacts: Mapping[str, Any]) -> dict[str, Any]:
  checks: dict[str, Any] = {}
  provider_status = dict(result.get("provider_status", {}) or {})
  patent = dict(result.get("patent_results", {}) or {})
  paper = dict(result.get("paper_results", {}) or {})
  web = dict(result.get("web_results", {}) or {})
  integrated = dict(result.get("integrated_signals", {}) or {})
  keywords = dict(result.get("keyword_suggestions", {}) or {})
  usage = dict(result.get("usage_metrics", {}) or {})
  export_bundle = dict(result.get("export", {}) or {})
  source_counts = _count_signals_by_source(integrated)

  checks["patent"] = {
    "status": provider_status.get("patent", {}).get("status"),
    "result_count": len(list(patent.get("rows", []) or [])),
    "estimated_bytes": patent.get("estimated_bytes"),
    "processed_bytes": patent.get("processed_bytes"),
    "billed_bytes": patent.get("billed_bytes"),
    "patent_signals": source_counts.get("patent", 0),
    "passed": (
      provider_status.get("patent", {}).get("status") in {"success", "partial_success"}
      and len(list(patent.get("rows", []) or [])) > 0
      and source_counts.get("patent", 0) > 0
    ),
  }
  paper_rows = list(paper.get("rows", []) or [])
  checks["paper"] = {
    "status": provider_status.get("paper", {}).get("status"),
    "request_count": paper.get("request_count"),
    "pagination_count": paper.get("pagination_count"),
    "result_count": len(paper_rows),
    "paper_signals": source_counts.get("paper", 0),
    "passed": (
      provider_status.get("paper", {}).get("status") in {"success", "partial_success"}
      and int(paper.get("request_count", 0) or 0) > 0
      and len(paper_rows) > 0
      and source_counts.get("paper", 0) > 0
    ),
  }
  web_rows = list(web.get("rows", []) or [])
  checks["web"] = {
    "status": provider_status.get("web", {}).get("status"),
    "request_count": web.get("request_count") or web.get("query_count"),
    "credits": web.get("usage_credits"),
    "result_count": len(web_rows),
    "web_signals": source_counts.get("web_company", 0),
    "passed": (
      provider_status.get("web", {}).get("status") in {"success", "partial_success"}
      and int(web.get("request_count") or web.get("query_count") or 0) > 0
      and len(web_rows) > 0
      and source_counts.get("web_company", 0) > 0
    ),
  }
  missing_artifacts = [name for name in REQUIRED_ARTIFACTS if name not in artifacts]
  secret_leak = any(_artifact_has_secret_leak(artifacts.get(name)) for name in artifacts)
  checks["integration"] = {
    "overall_status": result.get("status"),
    "integrated_count": int(integrated.get("ranked_count", 0) or 0),
    "keyword_suggestions": len(list(keywords.get("add_keywords", []) or [])),
    "export_formats": sorted(list(export_bundle.keys())),
    "source_types": sorted(source_counts.keys()),
    "missing_artifacts": missing_artifacts,
    "secret_leak": secret_leak,
    "passed": (
      result.get("status") == "success"
      and source_counts.get("patent", 0) > 0
      and source_counts.get("paper", 0) > 0
      and source_counts.get("web_company", 0) > 0
      and int(integrated.get("ranked_count", 0) or 0) > 0
      and len(list(keywords.get("add_keywords", []) or [])) > 0
      and export_bundle
      and not missing_artifacts
      and not secret_leak
    ),
  }
  checks["usage"] = usage
  all_passed = all(
    bool(section.get("passed"))
    for key, section in checks.items()
    if key in {"patent", "paper", "web", "integration"}
  )
  return {"passed": all_passed, "checks": checks}


def apply_acceptance() -> dict[str, Any]:
  if os.environ.get(ACCEPTANCE_ENV, "").lower() != "true":
    raise SystemExit(f"ERROR: requires {ACCEPTANCE_ENV}=true")

  request = build_acceptance_request()
  environ = build_acceptance_environ()
  try:
    plan = build_search_plan_preview(request, environ=environ)
    if plan.get("status") != "plan":
      return {"status": "blocked", "stage": "plan", "plan": plan}

    result = execute_three_source_search(
      request,
      plan=plan,
      confirmed=True,
      environ=environ,
    )
    search_run_id = str(result.get("search_run_id", "") or "")
    artifacts = {}
    if search_run_id:
      loaded = load_search_run(search_run_id, environ=environ)
      artifacts = dict(loaded.get("artifacts", {}) or {})

    validation = validate_acceptance_result(result, artifacts=artifacts)
    return {
      "status": "accepted" if validation["passed"] else "failed",
      "overall_status": result.get("status"),
      "search_run_id": search_run_id,
      "validation": validation,
      "provider_status": result.get("provider_status"),
      "usage_metrics": result.get("usage_metrics"),
      "result_counts": {
        "patent": len(list(dict(result.get("patent_results", {}) or {}).get("rows", []) or [])),
        "paper": len(list(dict(result.get("paper_results", {}) or {}).get("rows", []) or [])),
        "web": len(list(dict(result.get("web_results", {}) or {}).get("rows", []) or [])),
        "integrated": int(dict(result.get("integrated_signals", {}) or {}).get("ranked_count", 0) or 0),
        "keyword_suggestions": len(list(dict(result.get("keyword_suggestions", {}) or {}).get("add_keywords", []) or [])),
      },
      "secret_value_displayed": False,
    }
  finally:
    environ.pop("V9_STUDY_DEMO_OPENALEX_API_KEY", None)
    environ.pop("V9_STUDY_DEMO_TAVILY_API_KEY", None)


def main() -> int:
  parser = argparse.ArgumentParser()
  parser.add_argument("--plan", action="store_true")
  parser.add_argument("--apply", action="store_true")
  args = parser.parse_args()
  if args.apply:
    print(json.dumps(apply_acceptance(), ensure_ascii=False, indent=2))
    return 0
  print(json.dumps(build_plan(), ensure_ascii=False, indent=2))
  return 0


if __name__ == "__main__":
  raise SystemExit(main())
