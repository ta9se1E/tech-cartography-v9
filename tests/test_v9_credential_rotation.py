"""Tests for secure v9 credential rotation helper."""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import scripts.rotate_v9_credentials_secure as rotation_script

PROJECT_ROOT = Path(__file__).resolve().parents[1]


class _FakeSecretManagerClient:
  def __init__(self, versions: dict[str, list[dict[str, str]]] | None = None) -> None:
    self._versions = versions or {
      "tech-cartography-smtp-password": [
        {"version": "2", "state": "enabled", "create_time": "2026-06-21T13:58:26"},
        {"version": "1", "state": "enabled", "create_time": "2026-06-21T13:46:47"},
      ],
      "tech-cartography-tavily-api-key": [
        {"version": "2", "state": "enabled", "create_time": "2026-06-21T12:50:31"},
        {"version": "1", "state": "enabled", "create_time": "2026-06-21T12:38:18"},
      ],
    }
    self.added: list[tuple[str, str]] = []

  def list_secret_versions(self, request: dict[str, str]):
    secret_name = request["parent"].rsplit("/", 1)[-1]
    for item in self._versions.get(secret_name, []):
      yield SimpleNamespace(
        name=f"{request['parent']}/versions/{item['version']}",
        state=f"State.{item['state'].upper()}",
        create_time=SimpleNamespace(isoformat=lambda: item["create_time"]),
      )

  def add_secret_version(self, request: dict[str, object]):
    parent = str(request["parent"])
    secret_name = parent.rsplit("/", 1)[-1]
    payload = dict(request["payload"])  # type: ignore[arg-type]
    data = bytes(payload["data"])  # type: ignore[index]
    self.added.append((secret_name, data.decode("utf-8")))
    version_number = str(len(self._versions.setdefault(secret_name, [])) + 1)
    self._versions[secret_name].insert(0, {"version": version_number, "state": "enabled", "create_time": "2026-07-05T00:00:00"})
    return SimpleNamespace(name=f"{parent}/versions/{version_number}")


def test_build_rotation_plan_defaults_to_latest_detection() -> None:
  plan = rotation_script.build_rotation_plan(
    dotenv_path=PROJECT_ROOT / ".env.example",
    deploy_script_path=PROJECT_ROOT / "scripts" / "deploy_v9_cloud_run_weekly.sh",
    secret_manager_client=_FakeSecretManagerClient(),
  )
  assert plan["status"] == "plan"
  assert plan["job_secret_reference_mode"] == "latest"
  assert plan["job_secret_pin_plan"]["SMTP_PASSWORD"].endswith("<NEW_NUMERIC_VERSION>")
  assert plan["secret_versions"]["tech-cartography-smtp-password"]["latest_enabled_version"] == "2"


def test_apply_requires_approval_env() -> None:
  with patch.dict(os.environ, {}, clear=True):
    try:
      rotation_script.apply_rotation(targets=["SMTP_PASSWORD"], prompt_fn=lambda _name: "new-secret")
    except RuntimeError as exc:
      assert "V9_CREDENTIAL_ROTATION_APPROVED=true" in str(exc)
    else:
      raise AssertionError("expected apply guard failure")


def test_apply_uses_getpass_and_returns_version_numbers_only(tmp_path: Path) -> None:
  dotenv_path = tmp_path / ".env"
  dotenv_path.write_text("SMTP_PASSWORD=old-value\n", encoding="utf-8")
  os.chmod(dotenv_path, stat.S_IRUSR | stat.S_IWUSR)
  client = _FakeSecretManagerClient()
  with patch.dict(os.environ, {"V9_CREDENTIAL_ROTATION_APPROVED": "true"}, clear=False):
    result = rotation_script.apply_rotation(
      dotenv_path=dotenv_path,
      targets=["SMTP_PASSWORD"],
      secret_manager_client=client,
      prompt_fn=lambda _name: "new-secret-value",
    )
  assert result["status"] == "applied"
  assert result["results"][0]["new_secret_version"] == "3"
  assert "new-secret-value" not in json.dumps(result)
  updated = dotenv_path.read_text(encoding="utf-8")
  assert updated.count("SMTP_PASSWORD=") == 1
  assert "new-secret-value" in updated
  assert oct(dotenv_path.stat().st_mode & 0o777) == oct(stat.S_IRUSR | stat.S_IWUSR)


def test_unused_credentials_do_not_create_secret_versions() -> None:
  client = _FakeSecretManagerClient()
  with patch.dict(os.environ, {"V9_CREDENTIAL_ROTATION_APPROVED": "true"}, clear=False):
    result = rotation_script.apply_rotation(
      dotenv_path=PROJECT_ROOT / ".env.example",
      targets=["OPENAI_API_KEY", "OPENALEX_API_KEY"],
      secret_manager_client=client,
      prompt_fn=lambda _name: "should-not-be-used",
    )
  assert client.added == []
  assert all(item["status"] == "skipped" for item in result["results"])


def test_alias_credentials_are_not_double_rotated_in_default_apply_list() -> None:
  selected = [
    name for name, action in rotation_script.ROTATION_CLASS.items()
    if action in {"ROTATE_CLOUD", "ROTATE_LOCAL"}
  ]
  assert selected.count("LANGCHAIN_API_KEY") == 1
  assert selected.count("LANGSMITH_API_KEY") == 1
  assert "SMTP_PASSWORD" in selected
  assert "OPENAI_API_KEY" not in selected


def test_atomic_dotenv_update_preserves_other_lines_and_permissions(tmp_path: Path) -> None:
  dotenv_path = tmp_path / ".env"
  dotenv_path.write_text("# comment\nKEEP=value\nSMTP_PASSWORD=old\n", encoding="utf-8")
  os.chmod(dotenv_path, stat.S_IRUSR | stat.S_IWUSR)
  rotation_script.atomic_update_dotenv(dotenv_path=dotenv_path, updates={"SMTP_PASSWORD": "new"})
  text = dotenv_path.read_text(encoding="utf-8")
  assert "# comment\n" in text
  assert "KEEP=value\n" in text
  assert text.count("SMTP_PASSWORD=") == 1
  assert "SMTP_PASSWORD=new" in text
  assert oct(dotenv_path.stat().st_mode & 0o777) == oct(stat.S_IRUSR | stat.S_IWUSR)


def test_service_deploy_script_does_not_mount_job_secrets() -> None:
  deploy_text = (PROJECT_ROOT / "scripts" / "deploy_v9_cloud_run_weekly.sh").read_text(encoding="utf-8")
  service_section = deploy_text.split("deploy_service()", 1)[1].split("deploy_job()", 1)[0]
  assert "SMTP_PASSWORD" not in service_section
  assert "TAVILY_API_KEY" not in service_section


def test_helper_defaults_to_plan_mode(capsys) -> None:
  with patch.object(
    rotation_script,
    "build_rotation_plan",
    return_value={"status": "plan", "credentials": []},
  ):
    exit_code = rotation_script.main([])
  captured = capsys.readouterr().out
  assert exit_code == 0
  assert '"status": "plan"' in captured


def test_helper_does_not_define_secret_cli_arguments() -> None:
  text = (PROJECT_ROOT / "scripts" / "rotate_v9_credentials_secure.py").read_text(encoding="utf-8").lower()
  banned_tokens = ("--secret", "--password", "--api-key", "add_argument(\"--smtp", "add_argument('--smtp")
  assert all(token not in text for token in banned_tokens)
  assert "getpass" in text


def test_helper_apply_without_approval_exits_non_zero() -> None:
  helper_path = PROJECT_ROOT / "scripts" / "rotate_v9_credentials_secure.py"
  completed = subprocess.run(
    ["python", str(helper_path), "--apply"],
    cwd=PROJECT_ROOT,
    check=False,
    capture_output=True,
    text=True,
    env={**os.environ, "V9_CREDENTIAL_ROTATION_APPROVED": "false"},
  )
  combined = completed.stdout + completed.stderr
  assert completed.returncode != 0
  assert "V9_CREDENTIAL_ROTATION_APPROVED=true" in combined


def test_plan_output_does_not_include_secret_values(capsys) -> None:
  with patch.object(
    rotation_script,
    "summarize_local_credentials",
    return_value={
      name: rotation_script.LocalCredentialPresence(local_present=True, non_empty=True)
      for name in rotation_script.V9_CREDENTIAL_NAMES
    },
  ), patch.object(
    rotation_script,
    "summarize_secret_versions",
    return_value={"tech-cartography-smtp-password": {"latest_enabled_version": "2", "versions": []}},
  ):
    rotation_script.main(["--plan"])
  captured = capsys.readouterr().out
  assert "SMTP_PASSWORD" in captured
  assert "secret-one" not in captured
  assert "tvly-" not in captured.lower()
