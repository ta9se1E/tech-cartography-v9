"""Tests for secure v9 credential rotation helper."""

from __future__ import annotations

import json
import os
import stat
import subprocess
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

import pytest

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
      state = item["state"]
      if state == "enabled":
        state_value = "State.ENABLED"
      elif state == "disabled":
        state_value = "State.DISABLED"
      elif state == "destroyed":
        state_value = "State.DESTROYED"
      else:
        state_value = f"State.{state.upper()}"
      yield SimpleNamespace(
        name=f"{request['parent']}/versions/{item['version']}",
        state=state_value,
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


def test_build_rotation_plan_detects_numeric_secret_pin_mode() -> None:
  plan = rotation_script.build_rotation_plan(
    dotenv_path=PROJECT_ROOT / ".env.example",
    deploy_script_path=PROJECT_ROOT / "scripts" / "deploy_v9_cloud_run_weekly.sh",
    secret_manager_client=_FakeSecretManagerClient(),
  )
  assert plan["status"] == "plan"
  assert plan["job_secret_reference_mode"] == "numeric_version"
  assert plan["latest_secret_reference_lines"] == []
  assert plan["job_secret_pin_plan"]["SMTP_PASSWORD"].endswith("<NEW_NUMERIC_VERSION>")
  assert plan["secret_versions"]["tech-cartography-smtp-password"]["latest_enabled_version"] == "2"


def test_resolve_selected_targets_deduplicates_and_rejects_unknown() -> None:
  assert rotation_script.resolve_selected_targets(
    only="SMTP_PASSWORD,TAVILY_API_KEY,SMTP_PASSWORD",
    credentials=[],
  ) == ["SMTP_PASSWORD", "TAVILY_API_KEY"]
  with pytest.raises(ValueError, match="unknown credential"):
    rotation_script.resolve_selected_targets(only="NOT_A_REAL_KEY", credentials=[])


def test_apply_requires_explicit_targets() -> None:
  with patch.dict(os.environ, {"V9_CREDENTIAL_ROTATION_APPROVED": "true"}, clear=False):
    with pytest.raises(ValueError, match="--apply requires --only or --credential"):
      rotation_script.apply_rotation(
        dotenv_path=PROJECT_ROOT / ".env.example",
        targets=[],
        secret_manager_client=_FakeSecretManagerClient(),
        prompt_fn=lambda _name: "value",
      )


def test_apply_requires_approval_env() -> None:
  with patch.dict(os.environ, {}, clear=True):
    with pytest.raises(RuntimeError, match="V9_CREDENTIAL_ROTATION_APPROVED=true"):
      rotation_script.apply_rotation(
        targets=["SMTP_PASSWORD"],
        prompt_fn=lambda _name: "new-secret",
        secret_manager_client=_FakeSecretManagerClient(),
      )


def test_apply_only_smtp_and_tavily_does_not_touch_langchain(tmp_path: Path) -> None:
  dotenv_path = tmp_path / ".env"
  dotenv_path.write_text(
    "SMTP_PASSWORD=old-smtp\nTAVILY_API_KEY=old-tavily\nLANGCHAIN_API_KEY=keep-me\n",
    encoding="utf-8",
  )
  os.chmod(dotenv_path, stat.S_IRUSR | stat.S_IWUSR)
  state_path = tmp_path / "rotation_state.json"
  client = _FakeSecretManagerClient()
  prompts: list[str] = []

  def _prompt(name: str) -> str:
    prompts.append(name)
    return f"new-{name.lower()}"

  with patch.dict(os.environ, {"V9_CREDENTIAL_ROTATION_APPROVED": "true"}, clear=False):
    result = rotation_script.apply_rotation(
      dotenv_path=dotenv_path,
      targets=["SMTP_PASSWORD", "TAVILY_API_KEY"],
      state_path=state_path,
      secret_manager_client=client,
      prompt_fn=_prompt,
    )
  assert prompts == ["SMTP_PASSWORD", "TAVILY_API_KEY"]
  assert "LANGCHAIN_API_KEY" not in prompts
  assert result["status"] == "applied"
  text = dotenv_path.read_text(encoding="utf-8")
  assert "LANGCHAIN_API_KEY=keep-me" in text
  assert "new-smtp_password" in text
  assert client.added[0][0] == "tech-cartography-smtp-password"
  assert client.added[1][0] == "tech-cartography-tavily-api-key"


def test_apply_uses_getpass_and_returns_version_numbers_only(tmp_path: Path) -> None:
  dotenv_path = tmp_path / ".env"
  dotenv_path.write_text("SMTP_PASSWORD=old-value\n", encoding="utf-8")
  os.chmod(dotenv_path, stat.S_IRUSR | stat.S_IWUSR)
  state_path = tmp_path / "rotation_state.json"
  client = _FakeSecretManagerClient()
  with patch.dict(os.environ, {"V9_CREDENTIAL_ROTATION_APPROVED": "true"}, clear=False):
    result = rotation_script.apply_rotation(
      dotenv_path=dotenv_path,
      targets=["SMTP_PASSWORD"],
      state_path=state_path,
      secret_manager_client=client,
      prompt_fn=lambda _name: "new-secret-value",
    )
  assert result["status"] == "applied"
  assert result["results"][0]["new_secret_version"] == "3"
  assert "new-secret-value" not in json.dumps(result)
  updated = dotenv_path.read_text(encoding="utf-8")
  assert updated.count("SMTP_PASSWORD=") == 1
  assert "new-secret-value" in updated


def test_partial_failure_reports_applied_versions_without_secrets(tmp_path: Path) -> None:
  dotenv_path = tmp_path / ".env"
  dotenv_path.write_text("SMTP_PASSWORD=old\nTAVILY_API_KEY=old\n", encoding="utf-8")
  state_path = tmp_path / "rotation_state.json"
  client = _FakeSecretManagerClient()

  def _prompt(name: str) -> str:
    if name == "TAVILY_API_KEY":
      raise RuntimeError(f"{name} input was empty; rotation aborted.")
    return "new-smtp"

  with patch.dict(os.environ, {"V9_CREDENTIAL_ROTATION_APPROVED": "true"}, clear=False):
    result = rotation_script.apply_rotation(
      dotenv_path=dotenv_path,
      targets=["SMTP_PASSWORD", "TAVILY_API_KEY"],
      state_path=state_path,
      secret_manager_client=client,
      prompt_fn=_prompt,
    )
  assert result["status"] == "partial"
  assert result["applied_credentials"] == ["SMTP_PASSWORD"]
  assert result["failed_credentials"] == ["TAVILY_API_KEY"]
  assert result["results"][0]["new_secret_version"] == "3"
  assert "new-smtp" not in json.dumps(result)
  assert dotenv_path.read_text(encoding="utf-8").count("SMTP_PASSWORD=") == 1


def test_reuse_existing_version_when_dotenv_is_older(tmp_path: Path, monkeypatch) -> None:
  dotenv_path = tmp_path / ".env"
  dotenv_path.write_text("SMTP_PASSWORD=old\n", encoding="utf-8")
  os.utime(dotenv_path, (1000.0, 1000.0))
  state_path = tmp_path / "rotation_state.json"
  client = _FakeSecretManagerClient({
    "tech-cartography-smtp-password": [
      {"version": "3", "state": "enabled", "create_time": "2026-07-04T16:44:41+00:00"},
      {"version": "2", "state": "enabled", "create_time": "2026-06-21T13:58:26"},
    ],
  })
  with patch.dict(os.environ, {"V9_CREDENTIAL_ROTATION_APPROVED": "true"}, clear=False):
    result = rotation_script.apply_rotation(
      dotenv_path=dotenv_path,
      targets=["SMTP_PASSWORD"],
      state_path=state_path,
      secret_manager_client=client,
      prompt_fn=lambda _name: "local-only-update",
    )
  assert client.added == []
  assert result["results"][0]["secret_version_reused"] is True
  assert result["results"][0]["new_secret_version"] == "3"


def test_unused_credentials_do_not_create_secret_versions(tmp_path: Path) -> None:
  client = _FakeSecretManagerClient()
  with patch.dict(os.environ, {"V9_CREDENTIAL_ROTATION_APPROVED": "true"}, clear=False):
    result = rotation_script.apply_rotation(
      dotenv_path=tmp_path / ".env",
      targets=["OPENAI_API_KEY", "OPENALEX_API_KEY"],
      state_path=tmp_path / "rotation_state.json",
      secret_manager_client=client,
      prompt_fn=lambda _name: "should-not-be-used",
    )
  assert client.added == []
  assert all(item["status"] == "skipped" for item in result["results"])


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
    return_value={"status": "plan", "credentials": [], "selected_targets": []},
  ):
    exit_code = rotation_script.main([])
  captured = capsys.readouterr().out
  assert exit_code == 0
  assert '"status": "plan"' in captured


def test_plan_mode_with_only_lists_selected_targets(capsys) -> None:
  with patch.object(
    rotation_script,
    "build_rotation_plan",
    return_value={"status": "plan", "credentials": [], "selected_targets": ["SMTP_PASSWORD", "TAVILY_API_KEY"]},
  ) as mocked_plan:
    rotation_script.main(["--only", "SMTP_PASSWORD,TAVILY_API_KEY"])
  mocked_plan.assert_called_once()
  assert mocked_plan.call_args.kwargs["selected_targets"] == ["SMTP_PASSWORD", "TAVILY_API_KEY"]


def test_helper_does_not_define_secret_cli_arguments() -> None:
  text = (PROJECT_ROOT / "scripts" / "rotate_v9_credentials_secure.py").read_text(encoding="utf-8").lower()
  banned_tokens = ("--secret", "--password", "--api-key", "add_argument(\"--smtp", "add_argument('--smtp")
  assert all(token not in text for token in banned_tokens)
  assert "getpass" in text
  assert "--only" in text


def test_helper_apply_without_approval_exits_non_zero() -> None:
  helper_path = PROJECT_ROOT / "scripts" / "rotate_v9_credentials_secure.py"
  completed = subprocess.run(
    ["python", str(helper_path), "--apply", "--only", "SMTP_PASSWORD"],
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
    rotation_script.main(["--plan", "--only", "SMTP_PASSWORD"])
  captured = capsys.readouterr().out
  assert "SMTP_PASSWORD" in captured
  assert "secret-one" not in captured
  assert "tvly-" not in captured.lower()


@pytest.mark.parametrize(
  ("state", "expected"),
  [
    ("ENABLED", "enabled"),
    ("1", "enabled"),
    (1, "enabled"),
    ("SecretVersion.State.ENABLED", "enabled"),
    ("State.ENABLED", "enabled"),
    ("DISABLED", "disabled"),
    ("2", "disabled"),
    ("DESTROYED", "destroyed"),
    ("3", "destroyed"),
  ],
)
def test_normalize_secret_version_state_recognizes_enabled_representations(state, expected) -> None:
  assert rotation_script.normalize_secret_version_state(state) == expected


def test_normalize_secret_version_state_does_not_treat_disabled_or_destroyed_as_enabled() -> None:
  assert rotation_script.normalize_secret_version_state("DISABLED") == "disabled"
  assert rotation_script.normalize_secret_version_state(2) == "disabled"
  assert rotation_script.normalize_secret_version_state("DESTROYED") == "destroyed"
  assert rotation_script.normalize_secret_version_state(3) == "destroyed"


def test_summarize_secret_versions_recognizes_numeric_enum_state_as_enabled() -> None:
  class _NumericEnumClient:
    def list_secret_versions(self, request: dict[str, str]):
      for version in ("4", "3"):
        yield SimpleNamespace(
          name=f"{request['parent']}/versions/{version}",
          state="1",
          create_time=SimpleNamespace(isoformat=lambda v=version: f"2026-07-04T17:00:{version}4+00:00"),
        )

  summary = rotation_script._summarize_secret_versions_with_client(
    project_id="devops-ai-agent-hackathon-2026",
    secret_names=["tech-cartography-smtp-password"],
    client=_NumericEnumClient(),
  )
  payload = summary["tech-cartography-smtp-password"]
  assert payload["enabled_versions"] == ["4", "3"]
  assert payload["latest_enabled_version"] == "4"


def test_summarize_secret_versions_treats_disabled_and_destroyed_as_not_enabled() -> None:
  class _MixedStateClient:
    def list_secret_versions(self, request: dict[str, str]):
      yield SimpleNamespace(
        name=f"{request['parent']}/versions/4",
        state="1",
        create_time=SimpleNamespace(isoformat=lambda: "2026-07-04T17:00:14+00:00"),
      )
      yield SimpleNamespace(
        name=f"{request['parent']}/versions/3",
        state="2",
        create_time=SimpleNamespace(isoformat=lambda: "2026-06-21T13:58:26+00:00"),
      )
      yield SimpleNamespace(
        name=f"{request['parent']}/versions/2",
        state="3",
        create_time=SimpleNamespace(isoformat=lambda: "2026-06-21T13:46:47+00:00"),
      )

  summary = rotation_script._summarize_secret_versions_with_client(
    project_id="devops-ai-agent-hackathon-2026",
    secret_names=["tech-cartography-smtp-password"],
    client=_MixedStateClient(),
  )
  payload = summary["tech-cartography-smtp-password"]
  assert payload["enabled_versions"] == ["4"]
  assert payload["latest_enabled_version"] == "4"
