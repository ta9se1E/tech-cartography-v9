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

  mutation_started = (
    str(bool(state_payload and state_payload.get("mutation_started"))).lower()
    if state_parse_status == "ok"
    else "false"
  )
  public_access_verified = "false"
  iam_policy_mutations = "unknown"
  if result_parse_status == "ok" and result_payload is not None:
    public_access_verified = str(result_payload.get("public_access_verified") is True).lower()
    iam_policy_mutations = str(result_payload.get("iam_policy_mutations", "unknown"))

  _append_github_output("mutation_started", mutation_started)
  _append_github_output("public_access_verified", public_access_verified)
  _append_github_output("iam_policy_mutations", iam_policy_mutations)
  _append_github_output("state_parse_status", state_parse_status)
  _append_github_output("result_parse_status", result_parse_status)

  print(f"mutation_started={mutation_started}")
  print(f"public_access_verified={public_access_verified}")
  print(f"iam_policy_mutations={iam_policy_mutations}")
  print(f"state_parse_status={state_parse_status}")
  print(f"result_parse_status={result_parse_status}")
  return 0


if __name__ == "__main__":
  sys.exit(main())
