#!/usr/bin/env python3
"""P0 hackathon demo UI consistency checks for Study Demo."""

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


def _fake_run_client(artifacts: dict[str, Any], run_id: str) -> Any:
  prefix = f"search_runs/{run_id}/"

  class _Blob:
    def __init__(self, name: str, payload: Any):
      self.name = name
      self._payload = payload

    def download_as_bytes(self) -> bytes:
      return json.dumps(self._payload).encode()

  class _Bucket:
    def list_blobs(self, *, prefix: str = ""):
      for key, value in artifacts.items():
        yield _Blob(f"{prefix}{key}", value)

  class _Client:
    def bucket(self, _name: str) -> _Bucket:
      return _Bucket()

  return _Client()


def run_plan(*, search_run_id: str) -> dict[str, Any]:
  payload = _load_fixture()
  if str(payload.get("search_run_id", "")) != search_run_id:
    return {"status": "blocked", "message": "fixture run id mismatch", "expected": search_run_id}

  from services_v9.study_demo_active_loader import build_temporary_search_source_payload
  from services_v9.study_demo_live_lineage_loader import resolve_display_search_plan
  from services_v9.study_demo_run_metrics import build_canonical_run_metrics, validate_run_metric_consistency
  from services_v9.study_demo_saved_theme_editor import (
    apply_editor_selection_metadata,
    editor_values_to_theme_record,
    theme_to_editor_values,
    validate_theme_update_save_guard,
  )

  context = dict(payload.get("active_context", {}) or {})
  artifacts = dict(payload.get("artifacts", {}) or {})
  themes = dict(payload.get("themes", {}) or {})
  new_theme = dict(themes.get("new_theme", {}) or {})
  old_theme = dict(themes.get("old_theme", {}) or {})
  watch_profile = dict(payload.get("watch_profile", {}) or {})
  search_plan = dict(payload.get("search_plan", {}) or {})

  theme_state = apply_editor_selection_metadata({}, new_theme)
  theme_state["watch_profile"] = watch_profile
  theme_state["search_plan"] = search_plan
  theme_state["active_lineage_search_plan"] = search_plan
  theme_state["saved_themes"] = [new_theme, old_theme]

  editor_values = theme_to_editor_values(new_theme)
  editor_theme = editor_values_to_theme_record(editor_values, base_theme=new_theme)
  save_guard_ok = not validate_theme_update_save_guard(
    selected_theme_id=str(theme_state.get("selected_saved_theme_id", "")),
    editor_theme_id=str(editor_theme.get("theme_id", "")),
  )
  save_guard_block = bool(
    validate_theme_update_save_guard(
      selected_theme_id=str(new_theme.get("theme_id", "")),
      editor_theme_id=str(old_theme.get("theme_id", "")),
    )
  )

  source = build_temporary_search_source_payload(context, storage_client=_fake_run_client(artifacts, search_run_id))
  metrics = dict(source.get("canonical_metrics", {}) or {})
  display_plan = resolve_display_search_plan(active_context=context, theme_state=theme_state)

  legacy_contamination = 0
  if source.get("label") == "一時検索run" and context.get("run_origin") == "watch_profile":
    legacy_contamination += 1
  if str(editor_theme.get("name", "")) == str(old_theme.get("name", "")):
    legacy_contamination += 1

  return {
    "status": "ok",
    "mode": "plan",
    "search_run_id": search_run_id,
    "selected_theme_id": theme_state.get("selected_saved_theme_id"),
    "editor_theme_id": editor_theme.get("theme_id"),
    "editor_theme_name": editor_theme.get("name"),
    "watch_profile_id": watch_profile.get("watch_profile_id"),
    "search_plan_id": (display_plan or {}).get("search_plan_id"),
    "active_run": context.get("active_search_run_id"),
    "lineage": context.get("lineage_status"),
    "current_data_source_label": source.get("label"),
    "provider_counts": metrics.get("provider_counts"),
    "integrated": metrics.get("integrated_count"),
    "tier_counts": metrics.get("tier_counts"),
    "provider_success_rate": metrics.get("provider_success_rate"),
    "save_guard_ok": save_guard_ok,
    "save_guard_blocks_mismatch": save_guard_block,
    "legacy_contamination_count": legacy_contamination,
    "metric_inconsistency_count": len(validate_run_metric_consistency(metrics)),
    "external_api_calls": 0,
    "cloud_writes": 0,
    "production_modifications": False,
  }


def main() -> int:
  parser = argparse.ArgumentParser(description=__doc__)
  parser.add_argument("--plan", action="store_true")
  parser.add_argument("--search-run-id", default=DEFAULT_RUN_ID)
  args = parser.parse_args()
  if not args.plan:
    print(json.dumps({"status": "blocked", "message": "Use --plan"}, ensure_ascii=False, indent=2))
    return 2
  result = run_plan(search_run_id=str(args.search_run_id))
  print(json.dumps(result, ensure_ascii=False, indent=2))
  ok = (
    result.get("status") == "ok"
    and result.get("selected_theme_id") == result.get("editor_theme_id") == "theme_6d2dfb753f7e"
    and result.get("legacy_contamination_count", 1) == 0
    and result.get("metric_inconsistency_count", 1) == 0
    and result.get("current_data_source_label") == "保存済み標準検索run"
    and result.get("provider_success_rate") == 100.0
  )
  return 0 if ok else 1


if __name__ == "__main__":
  raise SystemExit(main())
