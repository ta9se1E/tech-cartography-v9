"""Read deploy state/result files for GitHub Actions without failing the workflow."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any


def _load_json_file(path: Path) -> tuple[dict[str, Any] | None, str]:
  if not path:
    return None, "missing"
  if not path.exists() or path.stat().st_size == 0:
    return None, "missing"
  try:
    payload = json.loads(path.read_text(encoding="utf-8"))
  except json.JSONDecodeError:
    return None, "invalid"
  if not isinstance(payload, dict):
    return None, "invalid"
  return payload, "ok"


def _append_github_output(name: str, value: str) -> None:
  output_path = os.environ.get("GITHUB_OUTPUT")
  if not output_path:
    return
  with open(output_path, "a", encoding="utf-8") as handle:
    handle.write(f"{name}={value}\n")


def main() -> int:
  state_path = Path(os.environ.get("V9_DEPLOY_STATE_FILE", ""))
  result_path = Path(os.environ.get("V9_DEPLOY_RESULT_FILE", ""))

  state_payload, state_parse_status = _load_json_file(state_path)
  result_payload, result_parse_status = _load_json_file(result_path)

  if state_parse_status != "ok":
    print(f"::warning::deploy state file {state_parse_status}")
  if result_parse_status != "ok":
    print(f"::warning::deploy result file {result_parse_status}")

  mutation_started = "false"
  traffic_promotion_started = "false"
  target_revision = ""
  previous_revision = ""
  if state_parse_status == "ok" and state_payload is not None:
    mutation_started = str(state_payload.get("mutation_started") is True).lower()
    traffic_promotion_started = str(state_payload.get("traffic_promotion_started") is True).lower()
    target_revision = str(state_payload.get("target_revision", "") or "")
    previous_revision = str(state_payload.get("previous_revision", "") or "")

  public_access_verified = "false"
  iam_policy_mutations = "unknown"
  new_revision = ""
  traffic_promoted = "false"
  traffic_target_revision = ""
  final_smoke_status = "unknown"
  candidate_smoke_status = "unknown"
  if result_parse_status == "ok" and result_payload is not None:
    public_access_verified = str(result_payload.get("public_access_verified") is True).lower()
    iam_policy_mutations = str(result_payload.get("iam_policy_mutations", "unknown"))
    new_revision = str(result_payload.get("new_revision", "") or "")
    traffic_promoted = str(result_payload.get("traffic_promoted") is True).lower()
    traffic_target_revision = str(result_payload.get("traffic_target_revision", "") or "")
    final_smoke_status = str(result_payload.get("final_smoke_status", "unknown") or "unknown")
    candidate_smoke_status = str(result_payload.get("candidate_smoke_status", "unknown") or "unknown")
    if not previous_revision:
      previous_revision = str(result_payload.get("previous_revision", "") or "")

  outputs = {
    "mutation_started": mutation_started,
    "public_access_verified": public_access_verified,
    "iam_policy_mutations": iam_policy_mutations,
    "state_parse_status": state_parse_status,
    "result_parse_status": result_parse_status,
    "traffic_promotion_started": traffic_promotion_started,
    "traffic_promoted": traffic_promoted,
    "new_revision": new_revision,
    "traffic_target_revision": traffic_target_revision or target_revision,
    "previous_revision": previous_revision,
    "final_smoke_status": final_smoke_status,
    "candidate_smoke_status": candidate_smoke_status,
  }
  for name, value in outputs.items():
    _append_github_output(name, value)
    print(f"{name}={value}")
  return 0


if __name__ == "__main__":
  sys.exit(main())
