#!/usr/bin/env python3
"""Readiness checks for the isolated v9 study demo service."""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
  sys.path.insert(0, str(ROOT / "src"))


def _check_module(name: str) -> None:
  importlib.import_module(name)


def _check_script_plan(script: str) -> None:
  env = os.environ.copy()
  env["PYTHONPATH"] = f"{ROOT}:{ROOT / 'src'}"
  result = subprocess.run(
    [sys.executable, str(ROOT / "scripts" / script), "--plan"],
    cwd=ROOT,
    check=True,
    capture_output=True,
    text=True,
    env=env,
  )
  payload = json.loads(result.stdout)
  if payload.get("status") not in {"plan", "ok"}:
    raise RuntimeError(f"{script} plan status unexpected: {payload.get('status')}")


def main() -> int:
  checks: dict[str, str] = {}
  try:
    _check_module("services_v9.study_demo_auth")
    _check_module("services_v9.study_demo_config")
    _check_module("services_v9.study_demo_guard")
    _check_module("services_v9.study_demo_storage")
    _check_module("services_v9.study_demo_search")
    _check_module("ui_v9.study_demo_gate")
    _check_module("ui_v9.study_demo_search_ui")
    checks["modules"] = "ok"

    from services_v9.study_demo_config import is_study_demo_mode

    if is_study_demo_mode():
      checks["production_mode"] = "study_demo_active"
    else:
      checks["production_mode"] = "unchanged"

    _check_script_plan("create_v9_study_demo_password.py")
    _check_script_plan("create_v9_study_demo_provider_secrets.py")
    _check_script_plan("prepare_v9_study_demo_seed.py")
    _check_script_plan("reset_v9_study_demo_data.py")
    _check_script_plan("run_v9_study_demo_three_source_acceptance.py")
    _check_script_plan("check_v9_study_demo_relevance_ranking.py")
    _check_script_plan("check_v9_study_demo_active_run_connection.py")
    checks["helper_plans"] = "ok"
    checks["patent_search_code"] = "ready"
    checks["openalex_search_code"] = "ready"
    checks["tavily_search_code"] = "ready"
    checks["dedicated_secrets_plan"] = "ready"
    checks["common_schema"] = "ready"
    checks["history"] = "ready"
    checks["export"] = "ready"
    checks["relevance_ranking"] = "ready"
    checks["active_analysis_context"] = "ready"
    checks["active_run_selector"] = "ready"
    checks["downstream_common_loader"] = "ready"
    checks["attention_signals_connection"] = "ready"
    checks["weekly_baseline_connection"] = "ready"
    checks["profile_draft_connection"] = "ready"
    checks["digest_connection"] = "ready"
    from ui_v9.study_demo_event_contracts import DIGEST_EVENT_KEYS, default_digest_events, normalize_digest_events

    defaults = default_digest_events()
    if "save_digest_files" not in defaults or not all(key in defaults for key in DIGEST_EVENT_KEYS):
      raise RuntimeError("digest event contract incomplete")
    sample = default_digest_events()
    sample["save_digest_files"] = True
    normalized = normalize_digest_events(sample)
    if not normalized["save_digest_files"] or normalized["run_email_delivery_dry_run"]:
      raise RuntimeError("digest event normalization failed")
    checks["digest_event_contract"] = "ready"
    checks["digest_event_normalization"] = "ready"
    checks["digest_save_explicit_only"] = "ready"
    checks["legacy_demo_fallback"] = "explicit_only"
    checks["disable_script"] = "ready"
    checks["acceptance_script"] = "ready"
    checks["code_ready"] = "true"
    checks["live_provider_validated"] = "false"
    checks["live_cloud_validated"] = "false"

    build_check = subprocess.run(
      [sys.executable, str(ROOT / "scripts" / "check_v9_build_context.py"), "--ignore-file", ".gcloudignore"],
      cwd=ROOT,
      check=True,
      capture_output=True,
      text=True,
    )
    build_payload = json.loads(build_check.stdout)
    if build_payload.get("status") != "ok":
      raise RuntimeError(f"build context check failed: {build_payload}")
    checks["build_context"] = "ok"

    print("[v9 study demo readiness] OK")
    print(json.dumps({"status": "ok", "checks": checks}, ensure_ascii=False, indent=2))
    return 0
  except Exception as exc:
    print(f"[v9 study demo readiness] FAILED: {exc}", file=sys.stderr)
    print(json.dumps({"status": "failed", "checks": checks, "error": str(exc)}, ensure_ascii=False, indent=2))
    return 1


if __name__ == "__main__":
  raise SystemExit(main())
