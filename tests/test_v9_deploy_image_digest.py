"""Tests for image digest normalization and digest-pinned deploy verification."""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
DEPLOY_SCRIPT = ROOT / "scripts" / "deploy_v9_study_demo.sh"
DEPLOY_WORKFLOW = ROOT / ".github" / "workflows" / "deploy-study-demo.yml"
STUDY_SERVICE = "tech-cartography-v9-study-demo"
PRODUCTION_SERVICE = "tech-cartography-v9-signal-watch"
VALID_DIGEST = "sha256:4c9f8fae6563408b00f34d1a4b4b262d641db06fda6ee6a7e2cc09df9b85bc8f"
OTHER_DIGEST = "sha256:56bdaa06db7f365246db658f9b769b260e52c844566f493aa02019fc04a9ce9e"
FULL_STATUS_DIGEST = (
  "us-central1-docker.pkg.dev/devops-ai-agent-hackathon-2026/"
  "cloud-run-source-deploy/tech-cartography-v9-study-demo@"
  "sha256:4c9f8fae6563408b00f34d1a4b4b262d641db06fda6ee6a7e2cc09df9b85bc8f"
)


def _normalize(value: str) -> str:
  completed = subprocess.run(
    [sys.executable, str(ROOT / "scripts" / "v9_image_digest.py"), "normalize", value],
    cwd=ROOT,
    capture_output=True,
    text=True,
    check=False,
  )
  if completed.returncode != 0:
    raise ValueError(completed.stderr.strip() or completed.stdout.strip())
  return completed.stdout.strip()


def test_build_results_images_digest_extraction() -> None:
  from scripts.v9_image_digest import extract_build_image_digest

  payload = {
    "results": {
      "images": [
        {
          "digest": VALID_DIGEST,
          "name": "us-central1-docker.pkg.dev/x/tech-cartography-v9-study-demo:09167a4",
        }
      ]
    }
  }
  assert extract_build_image_digest(payload) == VALID_DIGEST


def test_build_digest_missing_raises() -> None:
  from scripts.v9_image_digest import extract_build_image_digest

  with pytest.raises(ValueError, match="digest missing"):
    extract_build_image_digest({"results": {"images": []}})


def test_normalize_sha256_prefix() -> None:
  assert _normalize(VALID_DIGEST) == VALID_DIGEST


def test_normalize_full_uri_at_sha256() -> None:
  assert _normalize(FULL_STATUS_DIGEST) == VALID_DIGEST


def test_normalize_64hex_only() -> None:
  assert _normalize(VALID_DIGEST.split(":", 1)[1]) == VALID_DIGEST


def test_normalize_uppercase() -> None:
  upper = "SHA256:" + VALID_DIGEST.split(":", 1)[1].upper()
  assert _normalize(upper) == VALID_DIGEST


def test_normalize_invalid_digest_rejected() -> None:
  with pytest.raises(ValueError):
    _normalize("sha256:abc")


def test_normalize_empty_rejected() -> None:
  with pytest.raises(ValueError):
    _normalize("")


def test_digests_match_expected_equals_actual_full_uri() -> None:
  from scripts.v9_image_digest import digests_match

  assert digests_match(VALID_DIGEST, FULL_STATUS_DIGEST) is True


def test_digests_match_mismatch() -> None:
  from scripts.v9_image_digest import digests_match

  assert digests_match(VALID_DIGEST, OTHER_DIGEST) is False


def test_run_29017521562_observed_values_would_match_after_normalization() -> None:
  build_digest = "sha256:4c9f8fae6563408b00f34d1a4b4b262d641db06fda6ee6a7e2cc09df9b85bc8f"
  revision_status = FULL_STATUS_DIGEST
  assert _normalize(build_digest) == _normalize(revision_status)


def test_deploy_script_uses_image_by_digest() -> None:
  text = DEPLOY_SCRIPT.read_text(encoding="utf-8")
  deploy_body = text.split("deploy_study_demo_service() {", 1)[1].split("\n}\n", 1)[0]
  assert '--image "${IMAGE_BY_DIGEST}"' in deploy_body
  assert "IMAGE_BY_DIGEST=" in text
  assert "extract_build_image_digest" in text


def test_deploy_script_does_not_use_tag_only_identity() -> None:
  deploy_body = DEPLOY_SCRIPT.read_text(encoding="utf-8").split("deploy_study_demo_service() {", 1)[1].split("\n}\n", 1)[0]
  assert '--image "${IMAGE_URI}"' not in deploy_body


def test_verify_uses_status_image_digest_not_spec_tag() -> None:
  text = DEPLOY_SCRIPT.read_text(encoding="utf-8")
  body = text.split("verify_candidate_readiness() {", 1)[1].split("\n}\n", 1)[0]
  assert "normalize_digest" in body
  assert "rev_digest_raw = rev.get(\"status\", {}).get(\"imageDigest\", \"\")" in body
  assert "sys.exit(6)" in body


def test_result_json_includes_digest_fields() -> None:
  text = DEPLOY_SCRIPT.read_text(encoding="utf-8")
  assert '"expected_image_digest"' in text
  assert '"revision_image_digest"' in text
  assert '"image_digest_match"' in text
  assert '"image_reference_mode"' in text


def test_diagnostic_log_fields_present() -> None:
  text = DEPLOY_SCRIPT.read_text(encoding="utf-8")
  body = text.split("log_image_digest_diagnostics() {", 1)[1].split("\n}\n", 1)[0]
  for token in (
    "build_id=",
    "image_repository=",
    "expected_digest=",
    "revision_status_image_digest=",
    "normalized_expected_digest=",
    "normalized_actual_digest=",
    "digest_match=",
  ):
    assert token in body


def test_no_credential_paths_in_digest_diagnostics() -> None:
  text = DEPLOY_SCRIPT.read_text(encoding="utf-8")
  diag = text.split("log_image_digest_diagnostics() {", 1)[1].split("\n}\n", 1)[0]
  for token in ("password_secret", "openalex_secret", "credentials", "BEGIN PRIVATE KEY"):
    assert token not in diag


def test_candidate_tag_length_guard_retained() -> None:
  text = DEPLOY_SCRIPT.read_text(encoding="utf-8")
  assert "assert_candidate_tag_within_limit" in text
  assert 'RAW_TAG="c-${run_id}"' in text


def test_no_iam_mutation_or_run_admin() -> None:
  text = DEPLOY_SCRIPT.read_text(encoding="utf-8")
  for token in ("add-iam-policy-binding", "roles/run.admin", "setIamPolicy"):
    assert token not in text


def test_production_guard_and_validated_checkout() -> None:
  text = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
  workflow = yaml.safe_load(text)
  triggers = workflow.get("on") or workflow[True]
  assert list(triggers.keys()) == ["workflow_dispatch"]
  assert PRODUCTION_SERVICE in text
  assert "ref: ${{ needs.preflight.outputs.release_tag }}" in text


def test_atomic_result_state_write_retained() -> None:
  text = DEPLOY_SCRIPT.read_text(encoding="utf-8")
  assert "tmp.replace(pathlib.Path(os.environ[\"STATE_FILE\"]))" in text
  assert "tmp.replace(path)" in text


def test_apply_orders_tag_gate_before_build() -> None:
  body = DEPLOY_SCRIPT.read_text(encoding="utf-8").split("apply_deploy() {", 1)[1].split('\ncase "${MODE}"', 1)[0]
  assert body.index("assert_candidate_tag_within_limit") < body.index("build_study_demo_image")


def test_digest_mismatch_sets_error_stage() -> None:
  text = DEPLOY_SCRIPT.read_text(encoding="utf-8")
  assert 'RESULT_ERROR_STAGE="image_digest_verification"' in text
  assert "fail_image_digest_verification" in text
