"""Tests for candidate smoke and explicit traffic promotion rollout."""

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
BASH_BIN = os.environ.get("BASH", "/bin/bash")
VALID_DIGEST_A = "sha256:4c9f8fae6563408b00f34d1a4b4b262d641db06fda6ee6a7e2cc09df9b85bc8f"
VALID_DIGEST_B = "sha256:56bdaa06db7f365246db658f9b769b260e52c844566f493aa02019fc04a9ce9e"
IMAGE_REPO = (
  "us-central1-docker.pkg.dev/devops-ai-agent-hackathon-2026/"
  "cloud-run-source-deploy/tech-cartography-v9-study-demo"
)
_READINESS_FUNCS = [
  "log_image_digest_diagnostics",
  "fail_image_digest_verification",
  "cleanup_candidate_tag",
  "verify_candidate_readiness",
]


def _deploy_script_text() -> str:
  return DEPLOY_SCRIPT.read_text(encoding="utf-8")


def _workflow_text() -> str:
  return DEPLOY_WORKFLOW.read_text(encoding="utf-8")


def _workflow_steps() -> list[dict]:
  workflow = yaml.safe_load(_workflow_text())
  return workflow["jobs"]["deploy"]["steps"]


def _step(name: str) -> dict:
  for step in _workflow_steps():
    if step.get("name") == name:
      return step
  raise AssertionError(f"step not found: {name}")


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


def _apply_body() -> str:
  text = _deploy_script_text()
  return text.split("apply_deploy() {", 1)[1].split('\ncase "${MODE}"', 1)[0]


FAKE_GCLOUD = """#!/usr/bin/env python3
import os
import sys

args = sys.argv[1:]
fmt = ""
for a in args:
    if a.startswith("--format="):
        fmt = a.split("=", 1)[1]

def emit_file(var):
    path = os.environ.get(var, "")
    if path and os.path.exists(path):
        sys.stdout.write(open(path, encoding="utf-8").read())
    sys.exit(0)

if args[:3] == ["run", "services", "describe"]:
    if fmt == "json":
        emit_file("FAKE_SERVICE_JSON")
    if "latestCreatedRevisionName" in fmt:
        print(os.environ.get("FAKE_LATEST_CREATED", ""))
        sys.exit(0)
    if "latestReadyRevisionName" in fmt:
        print(os.environ.get("FAKE_LATEST_READY", ""))
        sys.exit(0)
    if "status.url" in fmt:
        print(os.environ.get("FAKE_SERVICE_URL", ""))
        sys.exit(0)
    sys.exit(0)

if args[:3] == ["run", "revisions", "describe"]:
    emit_file("FAKE_REVISION_JSON")

if args[:3] == ["run", "services", "update-traffic"]:
    log = os.environ.get("FAKE_TRAFFIC_LOG")
    if log:
        with open(log, "a", encoding="utf-8") as handle:
            handle.write(" ".join(args) + "\\n")
    sys.exit(int(os.environ.get("FAKE_UPDATE_TRAFFIC_RC", "0")))

sys.exit(0)
"""

FAKE_CURL = """#!/usr/bin/env python3
import os
import sys

args = sys.argv[1:]
url = args[-1] if args else ""
outfile = None
for i, a in enumerate(args):
    if a == "-o" and i + 1 < len(args):
        outfile = args[i + 1]
log = os.environ.get("FAKE_CURL_URL_LOG")
if log:
    with open(log, "a", encoding="utf-8") as handle:
        handle.write(url + "\\n")
if outfile:
    with open(outfile, "w", encoding="utf-8") as handle:
        handle.write(os.environ.get("FAKE_CURL_BODY", ""))
if any("%{http_code}" in a for a in args):
    sys.stdout.write(os.environ.get("FAKE_CURL_CODE", "200"))
sys.exit(0)
"""


def _install_fakes(tmp_path: Path) -> Path:
  fake_bin = tmp_path / "bin"
  fake_bin.mkdir(exist_ok=True)
  gcloud = fake_bin / "gcloud"
  gcloud.write_text(FAKE_GCLOUD, encoding="utf-8")
  gcloud.chmod(gcloud.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
  curl = fake_bin / "curl"
  curl.write_text(FAKE_CURL, encoding="utf-8")
  curl.chmod(curl.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
  return fake_bin


def _run_functions(
  tmp_path: Path,
  funcs: list[str],
  body: str,
  extra_env: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
  fake_bin = _install_fakes(tmp_path)
  preamble = f"""#!/usr/bin/env bash
set -euo pipefail
PROJECT_ID=devops-ai-agent-hackathon-2026
REGION=us-central1
SERVICE={STUDY_SERVICE}
PY=({sys.executable})
CANDIDATE_READY_MAX_ATTEMPTS="${{V9_CANDIDATE_READY_MAX_ATTEMPTS:-3}}"
CANDIDATE_READY_INTERVAL="${{V9_CANDIDATE_READY_INTERVAL:-0}}"
TRAFFIC_CONVERGE_MAX_ATTEMPTS="${{V9_TRAFFIC_CONVERGE_MAX_ATTEMPTS:-3}}"
TRAFFIC_CONVERGE_INTERVAL="${{V9_TRAFFIC_CONVERGE_INTERVAL:-0}}"
CANDIDATE_TAG=""
CANDIDATE_URL=""
CANDIDATE_SMOKE_HTTP=""
CANDIDATE_CLEANUP="skipped"
NEW_REVISION=""
BUILD_ID="fake-build-1"
IMAGE_REPOSITORY="{IMAGE_REPO}"
IMAGE_TAG="09167a4"
IMAGE_DIGEST="{VALID_DIGEST_A}"
CANDIDATE_TAG="c-test"
log() {{ printf '%s\\n' "$*"; }}
"""
  script = preamble + _extract_bash_functions(*funcs) + "\n" + body
  env = os.environ.copy()
  env["PATH"] = f"{fake_bin}:{env.get('PATH', '')}"
  if extra_env:
    env.update(extra_env)
  return subprocess.run(
    [BASH_BIN, "-c", script],
    cwd=ROOT,
    capture_output=True,
    text=True,
    env=env,
  )


def _write_json(path: Path, payload: dict) -> Path:
  path.write_text(json.dumps(payload), encoding="utf-8")
  return path


# ---------------------------------------------------------------------------
# Static deploy-script contract
# ---------------------------------------------------------------------------


def test_deploy_uses_digest_pinned_image_reference() -> None:
  body = _deploy_script_text().split("deploy_study_demo_service() {", 1)[1].split("\n}\n", 1)[0]
  assert '--image "${IMAGE_BY_DIGEST}"' in body
  assert "digest-pinned image reference is required" in body


def test_deploy_creates_revision_with_no_traffic() -> None:
  body = _deploy_script_text().split("deploy_study_demo_service() {", 1)[1].split("\n}\n", 1)[0]
  assert "--no-traffic" in body


def test_deploy_creates_candidate_tag() -> None:
  body = _deploy_script_text().split("deploy_study_demo_service() {", 1)[1].split("\n}\n", 1)[0]
  assert '--tag "${CANDIDATE_TAG}"' in body or "--tag" in body


def test_candidate_url_from_service_describe_not_guessed() -> None:
  text = _deploy_script_text()
  body = text.split("get_candidate_url() {", 1)[1].split("\n}\n", 1)[0]
  assert "gcloud run services describe" in body
  assert 'entry.get("tag") == tag' in body
  assert "candidate tag URL not found" in body


def test_promotion_uses_explicit_revision_not_latest() -> None:
  text = _deploy_script_text()
  body = text.split("promote_traffic() {", 1)[1].split("\n}\n", 1)[0]
  assert '--to-revisions="${revision}=100"' in body
  assert "--to-latest" not in text


def test_cleanup_uses_remove_tags_not_set_tags() -> None:
  text = _deploy_script_text()
  body = text.split("cleanup_candidate_tag() {", 1)[1].split("\n}\n", 1)[0]
  assert '--remove-tags="${tag}"' in body
  assert "--set-tags" not in text


def test_no_iam_mutation_or_run_admin() -> None:
  text = _deploy_script_text()
  for token in (
    "--allow-unauthenticated",
    "--no-allow-unauthenticated",
    "add-iam-policy-binding",
    "remove-iam-policy-binding",
    "set-iam-policy",
    "roles/run.admin",
    "setIamPolicy",
  ):
    assert token not in text


def test_apply_orders_candidate_rollout_steps() -> None:
  body = _apply_body()
  order = [
    "deploy_study_demo_service",
    "determine_new_revision",
    "get_candidate_url",
    "verify_candidate_readiness",
    "smoke_test_candidate",
    "promote_traffic",
    "wait_for_traffic_convergence",
    "verify_revision_active",
    "verify_public_password_gate",
    "cleanup_candidate_tag",
  ]
  positions = [body.index(name) for name in order]
  assert positions == sorted(positions), positions


def test_state_records_traffic_promotion_started_before_promote() -> None:
  body = _apply_body()
  assert "STATE_TRAFFIC_PROMOTION_STARTED=true" in body
  assert body.index("STATE_TRAFFIC_PROMOTION_STARTED=true") < body.index("promote_traffic")
  assert body.index("STATE_TARGET_REVISION=") < body.index("promote_traffic")


# ---------------------------------------------------------------------------
# Static workflow contract
# ---------------------------------------------------------------------------


def test_verify_step_requires_new_revision_traffic_100() -> None:
  verify = _step("Verify deployed revision")
  run_text = verify["run"]
  assert "traffic_promoted" in run_text
  assert "spec.traffic is not 100% on new revision" in run_text
  assert "status.traffic is not 100% on new revision" in run_text
  assert "latestReadyRevisionName is not the new revision" in run_text
  assert "steps.deploy_state.outputs.new_revision" in run_text


def test_verify_step_rejects_false_success_any_percent() -> None:
  verify = _step("Verify deployed revision")
  # The old false-success predicate must be gone.
  assert "any(item.get(\"percent\") == 100 for item in traffic)" not in verify["run"]


def test_smoke_reconfirms_new_traffic_before_and_after() -> None:
  smoke = _step("Unauthenticated smoke test")
  run_text = smoke["run"]
  assert 'assert_new_traffic "pre-smoke"' in run_text
  assert 'assert_new_traffic "post-smoke"' in run_text
  assert "status.traffic is not 100% on new revision" in run_text


def test_rollback_restores_previous_revision_100() -> None:
  rollback = _step("Rollback to previous revision")
  assert rollback["if"] == (
    "failure() && steps.deploy_state.outputs.mutation_started == 'true' "
    "&& steps.pre.outputs.previous_revision != ''"
  )
  assert '--to-revisions="${PREVIOUS}=100"' in rollback["run"]


def test_reader_warning_only_does_not_trigger_rollback() -> None:
  reader = _step("Read deploy mutation state")
  assert reader["if"] == "always()"
  assert "exit 0" in reader["run"]


def test_workflow_dispatch_only_and_validated_tag_checkout() -> None:
  workflow = yaml.safe_load(_workflow_text())
  triggers = workflow.get("on") or workflow[True]
  assert list(triggers.keys()) == ["workflow_dispatch"]
  assert "ref: ${{ needs.preflight.outputs.release_tag }}" in _workflow_text()


def test_production_guard_maintained() -> None:
  text = _workflow_text()
  assert PRODUCTION_SERVICE in text
  assert "production service deploy is forbidden" in text
  assert "production revision changed" in text


# ---------------------------------------------------------------------------
# Functional: candidate readiness
# ---------------------------------------------------------------------------


def _revision_json(
  *,
  name: str = STUDY_SERVICE + "-00025-kct",
  ready: str = "True",
  container_ready: str = "True",
  active: str = "False",
  ready_reason: str = "Retired",
  image_digest: str = VALID_DIGEST_A,
  spec_image: str | None = None,
  status_digest: str | None = None,
) -> dict:
  digest_ref = image_digest if image_digest.startswith("sha256:") else f"sha256:{image_digest}"
  full_status_digest = status_digest or f"{IMAGE_REPO}@{digest_ref}"
  container_image = spec_image or f"{IMAGE_REPO}:{VALID_DIGEST_A.split(':')[-1][:7]}"
  return {
    "metadata": {"name": name},
    "spec": {"containers": [{"image": container_image}]},
    "status": {
      "imageDigest": full_status_digest,
      "conditions": [
        {"type": "Ready", "status": ready, "reason": ready_reason},
        {"type": "ContainerReady", "status": container_ready},
        {"type": "Active", "status": active, "reason": ready_reason},
      ],
    },
  }


def test_candidate_readiness_ready_true_passes(tmp_path: Path) -> None:
  rev = _write_json(tmp_path / "rev.json", _revision_json())
  result = _run_functions(
    tmp_path,
    _READINESS_FUNCS,
    f'verify_candidate_readiness "{STUDY_SERVICE}-00025-kct" "{VALID_DIGEST_A}"',
    extra_env={"FAKE_REVISION_JSON": str(rev)},
  )
  assert result.returncode == 0, result.stderr + result.stdout


def test_candidate_readiness_retired_zero_traffic_not_failure(tmp_path: Path) -> None:
  # Active=False + reason=Retired must NOT be treated as startup failure.
  rev = _write_json(
    tmp_path / "rev.json",
    _revision_json(active="False", ready="True", container_ready="True", ready_reason="Retired"),
  )
  result = _run_functions(
    tmp_path,
    _READINESS_FUNCS,
    f'verify_candidate_readiness "{STUDY_SERVICE}-00025-kct" "{VALID_DIGEST_A}"',
    extra_env={"FAKE_REVISION_JSON": str(rev)},
  )
  assert result.returncode == 0, result.stderr + result.stdout


def test_candidate_readiness_container_not_ready_fails(tmp_path: Path) -> None:
  rev = _write_json(tmp_path / "rev.json", _revision_json(container_ready="False"))
  result = _run_functions(
    tmp_path,
    _READINESS_FUNCS,
    f'verify_candidate_readiness "{STUDY_SERVICE}-00025-kct" "{VALID_DIGEST_A}"',
    extra_env={
      "FAKE_REVISION_JSON": str(rev),
      "V9_CANDIDATE_READY_MAX_ATTEMPTS": "1",
      "V9_CANDIDATE_READY_INTERVAL": "0",
    },
  )
  assert result.returncode != 0
  assert "container failed to start" in (result.stdout + result.stderr)


def test_candidate_readiness_spec_tag_with_status_digest_passes(tmp_path: Path) -> None:
  rev = _write_json(
    tmp_path / "rev.json",
    _revision_json(
      spec_image=f"{IMAGE_REPO}:09167a4",
      status_digest=f"{IMAGE_REPO}@{VALID_DIGEST_A}",
    ),
  )
  result = _run_functions(
    tmp_path,
    _READINESS_FUNCS,
    f'verify_candidate_readiness "{STUDY_SERVICE}-00025-kct" "{VALID_DIGEST_A}"',
    extra_env={"FAKE_REVISION_JSON": str(rev)},
  )
  assert result.returncode == 0, result.stderr + result.stdout
  assert "digest_match=true" in result.stdout


def test_candidate_readiness_digest_mismatch_fails(tmp_path: Path) -> None:
  rev = _write_json(
    tmp_path / "rev.json",
    _revision_json(image_digest=VALID_DIGEST_B),
  )
  result = _run_functions(
    tmp_path,
    _READINESS_FUNCS,
    f'verify_candidate_readiness "{STUDY_SERVICE}-00025-kct" "{VALID_DIGEST_A}"',
    extra_env={
      "FAKE_REVISION_JSON": str(rev),
      "V9_CANDIDATE_READY_MAX_ATTEMPTS": "1",
      "V9_CANDIDATE_READY_INTERVAL": "0",
    },
  )
  assert result.returncode != 0
  assert "image digest mismatch" in (result.stdout + result.stderr)
  assert "normalized_expected_digest" in (result.stdout + result.stderr)


# ---------------------------------------------------------------------------
# Functional: candidate smoke
# ---------------------------------------------------------------------------


def test_candidate_smoke_http_200_uses_candidate_url(tmp_path: Path) -> None:
  url_log = tmp_path / "curl_urls.txt"
  result = _run_functions(
    tmp_path,
    ["smoke_test_candidate"],
    'smoke_test_candidate "https://candidate---abc.a.run.app" "rev-00025"',
    extra_env={
      "FAKE_CURL_CODE": "200",
      "FAKE_CURL_BODY": "<html><div class='stApp'>streamlit</div></html>",
      "FAKE_CURL_URL_LOG": str(url_log),
    },
  )
  assert result.returncode == 0, result.stderr + result.stdout
  logged = url_log.read_text(encoding="utf-8")
  assert "candidate---abc" in logged
  assert ".run.app" in logged


def test_candidate_smoke_does_not_use_service_url(tmp_path: Path) -> None:
  url_log = tmp_path / "curl_urls.txt"
  service_url = "https://tech-cartography-v9-study-demo-xyz.a.run.app"
  candidate_url = "https://candidate---abc.a.run.app"
  result = _run_functions(
    tmp_path,
    ["smoke_test_candidate"],
    f'smoke_test_candidate "{candidate_url}" "rev-00025"',
    extra_env={
      "FAKE_CURL_CODE": "200",
      "FAKE_CURL_BODY": "<div class='stApp'>streamlit</div>",
      "FAKE_CURL_URL_LOG": str(url_log),
    },
  )
  assert result.returncode == 0
  logged = url_log.read_text(encoding="utf-8")
  assert service_url not in logged
  assert candidate_url in logged


def test_candidate_smoke_private_data_exposed_fails(tmp_path: Path) -> None:
  result = _run_functions(
    tmp_path,
    ["smoke_test_candidate"],
    'smoke_test_candidate "https://candidate---abc.a.run.app" "rev-00025"',
    extra_env={
      "FAKE_CURL_CODE": "200",
      "FAKE_CURL_BODY": "<div class='stApp'>streamlit study_demo_search_20260705_145711_c06e0a1b</div>",
      "FAKE_CURL_URL_LOG": str(tmp_path / "u.txt"),
    },
  )
  assert result.returncode != 0
  assert "exposed private study data" in (result.stdout + result.stderr)


def test_candidate_smoke_http_500_fails(tmp_path: Path) -> None:
  result = _run_functions(
    tmp_path,
    ["smoke_test_candidate"],
    'smoke_test_candidate "https://candidate---abc.a.run.app" "rev-00025"',
    extra_env={
      "FAKE_CURL_CODE": "500",
      "FAKE_CURL_BODY": "error",
      "FAKE_CURL_URL_LOG": str(tmp_path / "u.txt"),
    },
  )
  assert result.returncode != 0
  assert "candidate smoke test HTTP 500" in (result.stdout + result.stderr)


# ---------------------------------------------------------------------------
# Functional: promotion + convergence
# ---------------------------------------------------------------------------


def test_promote_traffic_targets_specific_revision(tmp_path: Path) -> None:
  traffic_log = tmp_path / "traffic.txt"
  result = _run_functions(
    tmp_path,
    ["promote_traffic"],
    'promote_traffic "rev-00025-kct"',
    extra_env={"FAKE_TRAFFIC_LOG": str(traffic_log)},
  )
  assert result.returncode == 0, result.stderr
  logged = traffic_log.read_text(encoding="utf-8")
  assert "update-traffic" in logged
  assert "--to-revisions=rev-00025-kct=100" in logged
  assert "--to-latest" not in logged


def _service_json(target: str, *, converged: bool) -> dict:
  if converged:
    traffic = [{"revisionName": target, "percent": 100}]
    latest_ready = target
  else:
    traffic = [{"revisionName": "old-00022-mmv", "percent": 100}]
    latest_ready = "old-00022-mmv"
  return {
    "spec": {"traffic": traffic},
    "status": {"traffic": traffic, "latestReadyRevisionName": latest_ready},
  }


def test_convergence_success_when_new_revision_100(tmp_path: Path) -> None:
  svc = _write_json(tmp_path / "svc.json", _service_json("rev-00025-kct", converged=True))
  result = _run_functions(
    tmp_path,
    ["wait_for_traffic_convergence"],
    'wait_for_traffic_convergence "rev-00025-kct"',
    extra_env={"FAKE_SERVICE_JSON": str(svc)},
  )
  assert result.returncode == 0, result.stderr + result.stdout


def test_convergence_timeout_when_traffic_stuck(tmp_path: Path) -> None:
  svc = _write_json(tmp_path / "svc.json", _service_json("rev-00025-kct", converged=False))
  result = _run_functions(
    tmp_path,
    ["wait_for_traffic_convergence"],
    'wait_for_traffic_convergence "rev-00025-kct"',
    extra_env={
      "FAKE_SERVICE_JSON": str(svc),
      "V9_TRAFFIC_CONVERGE_MAX_ATTEMPTS": "1",
      "V9_TRAFFIC_CONVERGE_INTERVAL": "0",
    },
  )
  assert result.returncode != 0
  assert "did not converge" in (result.stdout + result.stderr)


def test_verify_revision_active_true_passes(tmp_path: Path) -> None:
  rev = _write_json(tmp_path / "rev.json", _revision_json(ready="True", active="True"))
  result = _run_functions(
    tmp_path,
    ["verify_revision_active"],
    f'verify_revision_active "{STUDY_SERVICE}-00025-kct"',
    extra_env={"FAKE_REVISION_JSON": str(rev)},
  )
  assert result.returncode == 0, result.stderr + result.stdout


def test_verify_revision_active_false_fails(tmp_path: Path) -> None:
  rev = _write_json(tmp_path / "rev.json", _revision_json(ready="True", active="False"))
  result = _run_functions(
    tmp_path,
    ["verify_revision_active"],
    f'verify_revision_active "{STUDY_SERVICE}-00025-kct"',
    extra_env={"FAKE_REVISION_JSON": str(rev)},
  )
  assert result.returncode != 0
  assert "not Active=True" in (result.stdout + result.stderr)


# ---------------------------------------------------------------------------
# Functional: cleanup best-effort
# ---------------------------------------------------------------------------


def test_cleanup_candidate_tag_success(tmp_path: Path) -> None:
  traffic_log = tmp_path / "traffic.txt"
  result = _run_functions(
    tmp_path,
    ["cleanup_candidate_tag"],
    'cleanup_candidate_tag "candidate-123"; echo "cleanup=${CANDIDATE_CLEANUP}"',
    extra_env={"FAKE_TRAFFIC_LOG": str(traffic_log), "FAKE_UPDATE_TRAFFIC_RC": "0"},
  )
  assert result.returncode == 0
  assert "cleanup=removed" in result.stdout
  assert "--remove-tags=candidate-123" in traffic_log.read_text(encoding="utf-8")


def test_cleanup_failure_is_best_effort_no_rollback(tmp_path: Path) -> None:
  result = _run_functions(
    tmp_path,
    ["cleanup_candidate_tag"],
    'cleanup_candidate_tag "candidate-123"; echo "cleanup=${CANDIDATE_CLEANUP}"',
    extra_env={"FAKE_TRAFFIC_LOG": str(tmp_path / "t.txt"), "FAKE_UPDATE_TRAFFIC_RC": "1"},
  )
  assert result.returncode == 0
  assert "cleanup=cleanup_failed" in result.stdout


# ---------------------------------------------------------------------------
# Functional: candidate URL resolution
# ---------------------------------------------------------------------------


def test_get_candidate_url_resolves_from_describe(tmp_path: Path) -> None:
  svc = _write_json(
    tmp_path / "svc.json",
    {
      "status": {
        "traffic": [
          {"revisionName": "rev-00025", "tag": "candidate-999", "url": "https://candidate-999---x.a.run.app"},
          {"revisionName": "rev-00022", "percent": 100},
        ]
      }
    },
  )
  result = _run_functions(
    tmp_path,
    ["get_candidate_url"],
    'get_candidate_url "candidate-999"; echo "url=${CANDIDATE_URL}"',
    extra_env={"FAKE_SERVICE_JSON": str(svc)},
  )
  assert result.returncode == 0, result.stderr + result.stdout
  assert "url=https://candidate-999---x.a.run.app" in result.stdout


def test_get_candidate_url_missing_tag_fails(tmp_path: Path) -> None:
  svc = _write_json(
    tmp_path / "svc.json",
    {"status": {"traffic": [{"revisionName": "rev-00022", "percent": 100}]}},
  )
  result = _run_functions(
    tmp_path,
    ["get_candidate_url"],
    'get_candidate_url "candidate-999"',
    extra_env={"FAKE_SERVICE_JSON": str(svc)},
  )
  assert result.returncode != 0
  assert "candidate tag URL not found" in (result.stdout + result.stderr)


# ---------------------------------------------------------------------------
# State/result atomic contract
# ---------------------------------------------------------------------------


def test_persist_state_includes_promotion_fields(tmp_path: Path) -> None:
  state_file = tmp_path / "state.json"
  body = (
    'STATE_MUTATION_STARTED=true\n'
    'STATE_CLOUD_BUILD_STARTED=true\n'
    'STATE_CLOUD_RUN_UPDATE_STARTED=true\n'
    'STATE_TRAFFIC_PROMOTION_STARTED=true\n'
    'STATE_TARGET_REVISION=rev-00025\n'
    'STATE_PREVIOUS_REVISION=rev-00022\n'
    f'DEPLOY_STATE_FILE="{state_file}"\n'
    'persist_deploy_state'
  )
  result = _run_functions(tmp_path, ["persist_deploy_state"], body)
  assert result.returncode == 0, result.stderr
  payload = json.loads(state_file.read_text(encoding="utf-8"))
  assert payload["mutation_started"] is True
  assert payload["traffic_promotion_started"] is True
  assert payload["target_revision"] == "rev-00025"
  assert payload["previous_revision"] == "rev-00022"
  assert not any(p.name.endswith(".tmp") for p in tmp_path.iterdir())


def test_result_includes_traffic_promotion_fields(tmp_path: Path) -> None:
  result_file = tmp_path / "result.json"
  body = (
    'SERVICE="tech-cartography-v9-study-demo"\n'
    f'DEPLOY_RESULT_FILE="{result_file}"\n'
    'RESULT_PREVIOUS_REVISION=rev-00022\n'
    'RESULT_CANDIDATE_TAG=candidate-999\n'
    'RESULT_CANDIDATE_URL=https://candidate-999---x.a.run.app\n'
    'RESULT_CANDIDATE_SMOKE_STATUS=ok\n'
    'RESULT_CANDIDATE_SMOKE_HTTP=200\n'
    'RESULT_TRAFFIC_PROMOTION_STARTED=true\n'
    'RESULT_TRAFFIC_PROMOTED=true\n'
    'RESULT_TRAFFIC_TARGET_REVISION=rev-00025\n'
    'RESULT_TRAFFIC_PERCENT=100\n'
    'RESULT_FINAL_SMOKE_STATUS=ok\n'
    'RESULT_IMAGE_DIGEST=sha256:abc\n'
    'RESULT_CANDIDATE_CLEANUP=removed\n'
    'write_deploy_result "ok" true true true build-1 true rev-00025'
  )
  extra_env = {"TMPDIR": str(tmp_path)}
  result = _run_functions(tmp_path, ["log", "write_deploy_result"], body, extra_env=extra_env)
  assert result.returncode == 0, result.stderr
  payload = json.loads(result_file.read_text(encoding="utf-8"))
  assert payload["traffic_promoted"] is True
  assert payload["traffic_target_revision"] == "rev-00025"
  assert payload["candidate_smoke_status"] == "ok"
  assert payload["final_smoke_status"] == "ok"
  assert payload["new_revision"] == "rev-00025"
  assert payload["previous_revision"] == "rev-00022"
  assert payload["iam_policy_mutations"] == 0
  assert payload["production_modifications"] is False
  # No credential material in the result contract.
  text = result_file.read_text(encoding="utf-8")
  for token in ("password_secret", "openalex_secret", "tavily_secret", "BEGIN PRIVATE KEY"):
    assert token not in text
