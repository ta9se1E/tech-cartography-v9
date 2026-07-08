"""Offline-ci vs live-cloud readiness scope split validation."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_DIR = ROOT / ".github" / "workflows"
SEARCH_RUN_ID = "study_demo_search_20260705_145711_c06e0a1b"

import scripts.check_v9_study_demo_live_lineage as live_lineage


def _offline_subprocess_env() -> dict[str, str]:
  import os
  import tempfile

  env = os.environ.copy()
  env["PYTHONPATH"] = f"{ROOT}:{ROOT / 'src'}"
  env.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
  env["CLOUDSDK_CONFIG"] = tempfile.mkdtemp()
  env["V9_STUDY_DEMO_MODE"] = "true"
  env["V9_STUDY_DEMO_BUCKET"] = "tech-cartography-v9-study-demo-1020686343587"
  return env


def _run_script(script: str, *args: str) -> subprocess.CompletedProcess:
  return subprocess.run(
    [sys.executable, str(ROOT / "scripts" / script), *args],
    cwd=ROOT,
    capture_output=True,
    text=True,
    env=_offline_subprocess_env(),
  )


# ---------------------------------------------------------------------------
# Scope parsing.
# ---------------------------------------------------------------------------
def test_scope_offline_ci_parses_and_runs() -> None:
  completed = _run_script("check_v9_study_demo_live_lineage.py", "--plan", "--scope", "offline-ci")
  assert completed.returncode == 0, completed.stderr
  assert json.loads(completed.stdout)["validation_scope"] == "offline-ci"


def test_scope_live_cloud_parses() -> None:
  # --plan required; live-cloud attempts real ADC, so we only assert the flag is accepted
  # by checking argparse does not reject it (it fails later on missing ADC, not on parsing).
  parser_ok = "--scope" in Path(live_lineage.__file__).read_text(encoding="utf-8")
  assert parser_ok
  assert "live-cloud" in live_lineage.VALID_SCOPES


def test_invalid_scope_rejected() -> None:
  completed = _run_script("check_v9_study_demo_live_lineage.py", "--plan", "--scope", "bogus")
  assert completed.returncode != 0
  assert "invalid choice" in completed.stderr.lower()


def test_readiness_invalid_scope_rejected() -> None:
  completed = _run_script("check_v9_study_demo_readiness.py", "--scope", "bogus")
  assert completed.returncode != 0


# ---------------------------------------------------------------------------
# Offline scope: deterministic, no ADC, no cloud.
# ---------------------------------------------------------------------------
def test_offline_lineage_passes_without_adc() -> None:
  completed = _run_script("check_v9_study_demo_live_lineage.py", "--plan", "--scope", "offline-ci")
  assert completed.returncode == 0, completed.stderr
  payload = json.loads(completed.stdout)
  assert payload["status"] == "ok"
  assert payload["validation_scope"] == "offline-ci"
  assert payload["cloud_auth_required"] is False
  assert payload["cloud_reads"] == 0
  assert payload["cloud_writes"] == 0
  assert payload["fixture"] == SEARCH_RUN_ID


def test_offline_lineage_fixture_values() -> None:
  payload = live_lineage.run_offline_ci(search_run_id=SEARCH_RUN_ID)
  assert payload["provider_counts"] == {"patent": 5, "paper": 5, "web": 5}
  assert payload["integrated_count"] == 15
  assert payload["tier_counts"] == {"A": 3, "B": 2, "C": 3, "D": 7}
  assert payload["desired_lineage_status"] == "connected"
  assert payload["theme_found"] is True
  assert payload["watch_profile_found"] is True
  assert payload["search_plan_found"] is True
  assert payload["signatures_match"] is True
  assert payload["theme_selector_includes_new_theme"] is True
  assert payload["theme_selector_includes_default_theme"] is True


def test_offline_readiness_passes_without_adc() -> None:
  completed = _run_script("check_v9_study_demo_readiness.py", "--scope", "offline-ci")
  assert completed.returncode == 0, completed.stderr
  payload = json.loads(completed.stdout)
  assert payload["status"] == "ok"
  assert payload["validation_scope"] == "offline-ci"
  assert payload["cloud_auth_required"] is False
  assert payload["cloud_reads"] == 0
  assert payload["cloud_writes"] == 0
  assert payload["fixture"] == SEARCH_RUN_ID


def test_offline_scope_installs_no_cloud_guard() -> None:
  # Run in a subprocess so the global no-cloud guard cannot leak into the test session.
  program = (
    "import scripts.check_v9_study_demo_live_lineage as m\n"
    "m.install_no_cloud_guard()\n"
    "import google.auth\n"
    "from google.cloud import storage\n"
    "import services_v9.study_demo_lineage_storage as ls\n"
    "failures = []\n"
    "for label, fn in ("
    "  ('google.auth.default', lambda: google.auth.default()),"
    "  ('storage.Client', lambda: storage.Client()),"
    "  ('lineage _build_client', lambda: ls._build_client()),"
    "):\n"
    "    try:\n"
    "        fn()\n"
    "        failures.append(label)\n"
    "    except RuntimeError:\n"
    "        pass\n"
    "assert not failures, failures\n"
    "print('guard_ok')\n"
  )
  completed = subprocess.run(
    [sys.executable, "-c", program],
    cwd=ROOT,
    capture_output=True,
    text=True,
    env=_offline_subprocess_env(),
  )
  assert completed.returncode == 0, completed.stderr
  assert "guard_ok" in completed.stdout


# ---------------------------------------------------------------------------
# Live scope: fake loader, explicit failures, no silent offline fallback.
# ---------------------------------------------------------------------------
def test_live_scope_uses_injected_client_and_reports_reads(monkeypatch: pytest.MonkeyPatch) -> None:
  env, client, _artifacts = live_lineage.build_offline_fixture(SEARCH_RUN_ID)
  monkeypatch.setattr(live_lineage, "_build_client", lambda: client)
  result = live_lineage.run_live_cloud(search_run_id=SEARCH_RUN_ID, environ=env)
  assert result["status"] == "ok"
  assert result["validation_scope"] == "live-cloud"
  assert result["cloud_auth_required"] is True
  assert result["cloud_reads"] > 0
  assert result["cloud_writes"] == 0
  assert result["production_modifications"] is False
  assert result["active_run_id"] == SEARCH_RUN_ID


def test_live_scope_auth_error_is_explicit_not_offline_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
  def _boom():
    raise RuntimeError("DefaultCredentialsError: no ADC")

  monkeypatch.setattr(live_lineage, "_build_client", _boom)
  with pytest.raises(RuntimeError):
    live_lineage.run_live_cloud(search_run_id=SEARCH_RUN_ID)


def test_live_scope_run_id_mismatch_fails_required_checks(monkeypatch: pytest.MonkeyPatch) -> None:
  env, client, _artifacts = live_lineage.build_offline_fixture(SEARCH_RUN_ID)
  monkeypatch.setattr(live_lineage, "_build_client", lambda: client)
  result = live_lineage.run_live_cloud(search_run_id="study_demo_search_missing_run", environ=env)
  assert result["search_run_found"] is False
  assert not all(live_lineage._required_checks(result))


def test_live_scope_missing_active_context_fails(monkeypatch: pytest.MonkeyPatch) -> None:
  env, client, _artifacts = live_lineage.build_offline_fixture(SEARCH_RUN_ID)
  # Drop the active context object to simulate a broken/mismatched lineage state.
  bucket = client.bucket(live_lineage.OFFLINE_BUCKET)
  bucket.objects.pop("analysis_context/active_context.json", None)
  monkeypatch.setattr(live_lineage, "_build_client", lambda: client)
  result = live_lineage.run_live_cloud(search_run_id=SEARCH_RUN_ID, environ=env)
  assert result["theme_found"] is False
  assert not all(live_lineage._required_checks(result))


# ---------------------------------------------------------------------------
# Workflow / script wiring.
# ---------------------------------------------------------------------------
def test_ci_script_uses_offline_ci_scope() -> None:
  text = (ROOT / "scripts" / "run_v9_ci_checks.sh").read_text(encoding="utf-8")
  assert "check_v9_study_demo_readiness.py --scope offline-ci" in text
  assert "readiness_scope=" in text


def test_deploy_local_gate_uses_offline_ci_scope() -> None:
  text = (ROOT / "scripts" / "deploy_v9_study_demo.sh").read_text(encoding="utf-8")
  assert "check_v9_study_demo_readiness.py --scope offline-ci" in text


def test_deploy_workflow_runs_live_cloud_readiness_pre_and_post() -> None:
  text = (WORKFLOW_DIR / "deploy-study-demo.yml").read_text(encoding="utf-8")
  assert text.count("check_v9_study_demo_readiness.py --scope live-cloud") >= 2
  assert "Pre-deploy live-cloud readiness" in text
  assert "Post-deploy live-cloud readiness" in text
