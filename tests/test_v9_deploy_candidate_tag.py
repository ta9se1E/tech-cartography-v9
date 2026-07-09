"""Tests for bounded Cloud Run candidate traffic tag length."""

from __future__ import annotations

import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPT = ROOT / "scripts" / "deploy_v9_study_demo.sh"
DEPLOY_WORKFLOW = ROOT / ".github" / "workflows" / "deploy-study-demo.yml"
STUDY_SERVICE = "tech-cartography-v9-study-demo"
PRODUCTION_SERVICE = "tech-cartography-v9-signal-watch"
MAX_COMBINED = 46
BASH_BIN = os.environ.get("BASH", "/bin/bash")


def _deploy_script_text() -> str:
  return DEPLOY_SCRIPT.read_text(encoding="utf-8")


def _extract_bash_functions(*names: str) -> str:
  text = _deploy_script_text()
  chunks: list[str] = []
  for name in names:
    match = re.search(rf"^{re.escape(name)}\(\) \{{", text, flags=re.MULTILINE)
    if not match:
      raise AssertionError(f"function not found: {name}")
    start = match.start()
    depth = 0
    end = start
    for index in range(match.end() - 1, len(text)):
      char = text[index]
      if char == "{":
        depth += 1
      elif char == "}":
        depth -= 1
        if depth == 0:
          end = index + 1
          break
    chunks.append(text[start:end])
  return "\n\n".join(chunks)


def _resolve_tag(
  *,
  service: str = STUDY_SERVICE,
  run_id: str = "29015795337",
) -> subprocess.CompletedProcess[str]:
  preamble = f"""#!/usr/bin/env bash
set -euo pipefail
SERVICE="{service}"
PY=({sys.executable})
log() {{ printf '%s\\n' "$*"; }}
V9_DEPLOY_RUN_ID="{run_id}"
"""
  script = preamble + _extract_bash_functions("resolve_candidate_tag", "assert_candidate_tag_within_limit")
  script += "\nresolve_candidate_tag\nassert_candidate_tag_within_limit\necho \"TAG=${CANDIDATE_TAG}\"\n"
  return subprocess.run(
    [BASH_BIN, "-c", script],
    cwd=ROOT,
    capture_output=True,
    text=True,
    env={**os.environ, "TMPDIR": "/tmp"},
  )


def _tag_from_output(stdout: str) -> str:
  for line in stdout.splitlines():
    if line.startswith("TAG="):
      return line.split("=", 1)[1]
  raise AssertionError(f"tag not found in output: {stdout!r}")


def test_study_demo_service_tag_length_at_most_16() -> None:
  completed = _resolve_tag(run_id="29015795337")
  assert completed.returncode == 0, completed.stderr + completed.stdout
  tag = _tag_from_output(completed.stdout)
  assert len(tag) <= MAX_COMBINED - len(STUDY_SERVICE)


def test_run_29015795337_produces_c_prefix_tag() -> None:
  completed = _resolve_tag(run_id="29015795337")
  assert completed.returncode == 0
  tag = _tag_from_output(completed.stdout)
  assert tag == "c-29015795337"
  assert len(tag) == 13


def test_combined_length_within_46() -> None:
  completed = _resolve_tag(run_id="29015795337")
  tag = _tag_from_output(completed.stdout)
  assert len(STUDY_SERVICE) + len(tag) <= MAX_COMBINED
  assert len(STUDY_SERVICE) + len(tag) == 43


def test_old_candidate_prefix_is_not_emitted() -> None:
  completed = _resolve_tag(run_id="29015795337")
  tag = _tag_from_output(completed.stdout)
  assert not tag.startswith("candidate-")


def test_very_long_run_id_stays_within_limit() -> None:
  long_id = "29015795337" * 5
  completed = _resolve_tag(run_id=long_id)
  assert completed.returncode == 0, completed.stderr
  tag = _tag_from_output(completed.stdout)
  assert len(tag) <= MAX_COMBINED - len(STUDY_SERVICE)
  assert len(STUDY_SERVICE) + len(tag) <= MAX_COMBINED


def test_longer_service_name_reduces_max_tag_dynamically() -> None:
  service = "a" * 40
  completed = _resolve_tag(service=service, run_id="12345")
  assert completed.returncode == 0
  tag = _tag_from_output(completed.stdout)
  assert len(service) + len(tag) <= MAX_COMBINED
  assert len(tag) <= MAX_COMBINED - len(service)


def test_service_name_46_or_more_fails_before_build() -> None:
  service = "a" * 46
  completed = _resolve_tag(service=service, run_id="12345")
  assert completed.returncode != 0
  assert "too long" in (completed.stdout + completed.stderr).lower()


def test_tag_starts_with_letter() -> None:
  completed = _resolve_tag(run_id="29015795337")
  tag = _tag_from_output(completed.stdout)
  assert tag[0].isalpha()


def test_tag_does_not_end_with_hyphen() -> None:
  completed = _resolve_tag(run_id="29015795337---")
  tag = _tag_from_output(completed.stdout)
  assert not tag.endswith("-")


def test_empty_after_sanitize_uses_fallback() -> None:
  completed = _resolve_tag(run_id="!!!")
  assert completed.returncode == 0, completed.stderr
  tag = _tag_from_output(completed.stdout)
  assert tag
  assert tag[0].isalpha()


def test_same_run_is_deterministic() -> None:
  first = _tag_from_output(_resolve_tag(run_id="29015795337").stdout)
  second = _tag_from_output(_resolve_tag(run_id="29015795337").stdout)
  assert first == second


def test_different_runs_produce_different_tags() -> None:
  a = _tag_from_output(_resolve_tag(run_id="29015795337").stdout)
  b = _tag_from_output(_resolve_tag(run_id="29015795338").stdout)
  assert a != b


def test_invalid_tag_fails_before_cloud_build_in_apply_order() -> None:
  body = _deploy_script_text().split("apply_deploy() {", 1)[1].split('\ncase "${MODE}"', 1)[0]
  assert body.index("resolve_candidate_tag") < body.index("build_study_demo_image")
  assert body.index("assert_candidate_tag_within_limit") < body.index("build_study_demo_image")


def test_invalid_tag_keeps_mutation_started_false() -> None:
  body = _deploy_script_text().split("apply_deploy() {", 1)[1].split('\ncase "${MODE}"', 1)[0]
  assert body.index("assert_candidate_tag_within_limit") < body.index("mutation_started=true")


def test_workflow_rollback_not_triggered_without_mutation() -> None:
  text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
  assert "steps.deploy_state.outputs.mutation_started == 'true'" in text
  assert re.search(
    r"Report deploy not started[\s\S]*?steps\.deploy_state\.outputs\.mutation_started != 'true'",
    text,
  )


def test_script_keeps_candidate_url_from_describe() -> None:
  text = _deploy_script_text()
  body = text.split("get_candidate_url() {", 1)[1].split("\n}\n", 1)[0]
  assert 'entry.get("tag") == tag' in body


def test_script_keeps_explicit_promotion() -> None:
  text = _deploy_script_text()
  assert '--to-revisions="${revision}=100"' in text
  assert "--to-latest" not in text


def test_no_iam_mutation_or_run_admin() -> None:
  text = _deploy_script_text()
  for token in (
    "--allow-unauthenticated",
    "--no-allow-unauthenticated",
    "add-iam-policy-binding",
    "remove-iam-policy-binding",
    "roles/run.admin",
    "setIamPolicy",
  ):
    assert token not in text


def test_production_guard_and_validated_checkout() -> None:
  text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
  workflow = yaml.safe_load(text)
  triggers = workflow.get("on") or workflow[True]
  assert list(triggers.keys()) == ["workflow_dispatch"]
  assert PRODUCTION_SERVICE in text
  assert "production service deploy is forbidden" in text
  assert "ref: ${{ needs.preflight.outputs.release_tag }}" in text


def test_state_and_result_use_atomic_write() -> None:
  text = _deploy_script_text()
  assert "tmp.replace(pathlib.Path(os.environ[\"STATE_FILE\"]))" in text
  assert "tmp.replace(path)" in text


def test_assert_logs_length_dimensions() -> None:
  completed = _resolve_tag(run_id="29015795337")
  output = completed.stdout + completed.stderr
  assert "service_name_length=30" in output
  assert "candidate_tag_length=13" in output
  assert "combined_length=43" in output
  assert "max_combined_length=46" in output


def test_raw_tag_uses_c_prefix_not_candidate() -> None:
  text = _deploy_script_text()
  body = text.split("resolve_candidate_tag() {", 1)[1].split("\n}\n", 1)[0]
  assert 'RAW_TAG="c-${run_id}"' in body
  assert 'RAW_TAG="candidate-${run_id}"' not in body
