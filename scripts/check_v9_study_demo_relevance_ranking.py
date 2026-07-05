#!/usr/bin/env python3
"""Validate study demo relevance ranking against saved run or local fixture."""

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

from services_v9.study_demo_config import STUDY_DEMO_BUCKET_DEFAULT, get_study_demo_bucket
from services_v9.study_demo_search.relevance_ranking import (
  TIER_A,
  TIER_B,
  TIER_C,
  TIER_D,
  apply_relevance_ranking,
  enrich_integrated_signals,
)
from services_v9.study_demo_search.storage import build_search_result_from_artifacts, load_search_run

FIXTURE_PATH = ROOT / "tests/fixtures/study_demo_relevance_ranking_samples.json"
DEFAULT_RUN_ID = "study_demo_search_20260705_061319_e973e4c2"

EXPECTED_TIER_A_SNIPPETS = [
  "Amphiphilic water-based polyamide acid sizing agent",
  "Bio-based aqueous polyurethane sizing agent",
  "Blocked side chain double bond aqueous polyurethane sizing agent",
  "Effects of Styrene-Acrylic Sizing",
]
EXPECTED_TIER_B_SNIPPET = "Asphalt-based carbon fiber sizing agent"
EXPECTED_TIER_C_SNIPPETS = [
  "Carbon Fibers and Their Composite Materials",
  "Carbon fiber reinforced polymers: matrix modifications",
]


def _load_fixture() -> tuple[list[dict[str, Any]], dict[str, Any]]:
  payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
  return list(payload.get("signals", []) or []), dict(payload.get("query_provenance", {}) or {})


def _load_saved_run(search_run_id: str, *, use_gcs: bool) -> tuple[list[dict[str, Any]], dict[str, Any]]:
  if not use_gcs:
    return _load_fixture()
  bucket = get_study_demo_bucket()
  if "study-demo" not in bucket and bucket != STUDY_DEMO_BUCKET_DEFAULT:
    raise RuntimeError(f"refusing non-demo bucket: {bucket}")
  loaded = load_search_run(search_run_id)
  bundle = build_search_result_from_artifacts(loaded)
  integrated = dict(bundle.get("integrated_signals", {}) or {})
  summary = dict(loaded.get("artifacts", {}).get("search_request.json", {}) or {})
  return list(integrated.get("signals", []) or []), summary


def _ranked_titles(signals: list[dict[str, Any]], tier: str, limit: int = 10) -> list[str]:
  return [
    str(item.get("title", "") or "")
    for item in signals
    if str(item.get("relevance_tier", "")) == tier
  ][:limit]


def _validate_ranking(signals: list[dict[str, Any]], *, source: str) -> dict[str, Any]:
  tier_a_titles = _ranked_titles(signals, TIER_A, 20)
  tier_b_titles = _ranked_titles(signals, TIER_B, 20)
  tier_c_titles = _ranked_titles(signals, TIER_C, 20)
  tier_d_titles = _ranked_titles(signals, TIER_D, 20)

  checks: dict[str, Any] = {"source": source, "ranked_count": len(signals)}
  checks["tier_a_top"] = tier_a_titles[:5]
  checks["tier_b_contains_asphalt"] = any(EXPECTED_TIER_B_SNIPPET in title for title in tier_b_titles)
  checks["tier_c_contains_background"] = any(
    any(snippet in title for snippet in EXPECTED_TIER_C_SNIPPETS) for title in tier_c_titles
  )
  checks["tier_d_present"] = len(tier_d_titles) >= 0
  checks["asphalt_not_tier_a"] = not any(EXPECTED_TIER_B_SNIPPET in title for title in tier_a_titles)

  if source == "fixture":
    checks["fixture_tier_a_count"] = len(tier_a_titles)
    checks["fixture_tier_d_count"] = len(tier_d_titles)
    checks["status"] = "ok" if checks["asphalt_not_tier_a"] and checks["tier_b_contains_asphalt"] else "failed"
  else:
    direct_hits = sum(1 for snippet in EXPECTED_TIER_A_SNIPPETS if any(snippet in title for title in tier_a_titles))
    checks["expected_tier_a_hits"] = direct_hits
    checks["status"] = "ok" if direct_hits >= 3 and checks["asphalt_not_tier_a"] else "failed"

  return checks


def main() -> int:
  parser = argparse.ArgumentParser()
  parser.add_argument("--plan", action="store_true", help="Run local fixture validation only")
  parser.add_argument("--search-run-id", default=DEFAULT_RUN_ID)
  parser.add_argument("--use-gcs", action="store_true", help="Load saved run from demo bucket (read-only)")
  args = parser.parse_args()

  if args.plan:
    signals, provenance = _load_fixture()
    ranked = apply_relevance_ranking(signals, query_provenance=provenance)
    payload = _validate_ranking(ranked, source="fixture")
    payload["mode"] = "plan"
    payload["fixture"] = str(FIXTURE_PATH.name)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("status") == "ok" else 1

  signals, provenance = _load_saved_run(args.search_run_id, use_gcs=args.use_gcs)
  if not signals:
    enriched = enrich_integrated_signals({"signals": []}, query_provenance=provenance)
    signals = list(enriched.get("signals", []) or [])
  else:
    signals = apply_relevance_ranking(signals, query_provenance=provenance)
  payload = _validate_ranking(signals, source="saved_run" if args.use_gcs else "fixture")
  payload["search_run_id"] = args.search_run_id
  payload["mode"] = "execute"
  print(json.dumps(payload, ensure_ascii=False, indent=2))
  return 0 if payload.get("status") == "ok" else 1


if __name__ == "__main__":
  raise SystemExit(main())
