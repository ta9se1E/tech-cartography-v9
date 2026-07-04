from __future__ import annotations

import hashlib
import json
import os
import smtplib
import subprocess
import sys
from pathlib import Path

from streamlit.testing.v1 import AppTest

import services_v9.email_delivery as email_delivery_module
from services_v9.email_delivery import (
  EMAIL_PREVIEW_BODY_TEXT_MAX_BYTES,
  EMAIL_SEND_MODE_PREVIEW,
  EMAIL_SEND_MODE_SELF_ONLY,
  EmailDeliveryConfig,
  build_email_preview_artifact,
  build_digest_email_preview,
  build_digest_email_subject,
  has_successful_digest_delivery,
  is_successful_digest_delivery_record,
  load_email_delivery_config,
  run_email_delivery_dry_run,
  save_email_delivery_log,
  send_digest_email_self_only,
  validate_self_only_delivery,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _digest_markdown() -> str:
  return (
    "# Tech Cartography v9 週次ダイジェスト\n\n"
    "## 今週まず読むべき3件\n\n"
    "1. **高性能PAN前駆体**\n"
    "   - 人間レビュー: 採用\n"
    "   - 出典URL: https://example.com/pan\n"
    "   - メモ: <script>alert('x')</script>\n"
  )


def _real_retrieval_signals(*, partial: bool = False) -> list[dict]:
  status = "partial_success" if partial else "success"
  return [
    {
      "id": "sig-1",
      "title": "高性能PAN前駆体",
      "type": "paper",
      "source_url": "https://example.com/pan",
      "action": "Read Now",
      "review": {"reviewed": True, "review_decision": "採用", "review_comment": "確認したい"},
      "record_stage": "staged",
      "retrieval_mode": "real",
      "data_origin": "openalex_paper",
      "source_trace": [
        {
          "source_type": "paper",
          "provider_status": status,
          "data_origin": "openalex_paper",
        }
      ],
    }
  ]


def _preview(
  *,
  source_label: str = "取得済みデータ",
  source_mode: str = "retrieval_saved",
  signals: list[dict] | None = None,
) -> dict:
  return build_digest_email_preview(
    _digest_markdown(),
    theme_name="PAN系炭素繊維前駆体の欠陥制御",
    data_source=source_label,
    signals=signals if signals is not None else _real_retrieval_signals(),
    data_source_mode=source_mode,
  )


def _config(**overrides: object):
  values = {
    "send_mode": EMAIL_SEND_MODE_SELF_ONLY,
    "disabled": False,
    "sender": "sender@example.com",
    "self_recipient": "me@example.com",
    "recipient_allowlist": ("me@example.com",),
    "smtp_host": "smtp.example.com",
    "smtp_port": 587,
    "smtp_username": "smtp-user",
    "smtp_password": "smtp-password",
    "use_starttls": True,
    "timeout_seconds": 30,
  }
  values.update(overrides)
  return EmailDeliveryConfig(**values)


class _MockSMTP:
  instances: list["_MockSMTP"] = []

  def __init__(self, host: str, port: int, timeout: int):
    self.host = host
    self.port = port
    self.timeout = timeout
    self.ehlo_calls = 0
    self.starttls_calls = 0
    self.login_calls: list[tuple[str, str]] = []
    self.send_message_calls = 0
    _MockSMTP.instances.append(self)

  def __enter__(self) -> "_MockSMTP":
    return self

  def __exit__(self, exc_type, exc, tb) -> None:
    return None

  def ehlo(self) -> None:
    self.ehlo_calls += 1

  def starttls(self, context=None) -> None:
    self.starttls_calls += 1

  def login(self, username: str, password: str) -> None:
    self.login_calls.append((username, password))

  def send_message(self, message) -> None:
    self.send_message_calls += 1


class _FailingSMTP(_MockSMTP):
  def send_message(self, message) -> None:
    raise smtplib.SMTPException("boom")


def _write_email_delivery_log(root: Path, run_id: str, payload: dict) -> Path:
  run_dir = root / "email_delivery_runs" / run_id
  run_dir.mkdir(parents=True, exist_ok=True)
  path = run_dir / "email_delivery_log.json"
  path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
  return path


def _log_result(
  *,
  delivery_run_id: str = "email_delivery_test",
  status: str = "sent",
  digest_sha256: str | None = None,
  send_attempted: bool = True,
  send_succeeded: bool = True,
  error_type: str = "",
  safe_error_message: str = "",
) -> dict[str, object]:
  preview = _preview()
  return {
    "delivery_run_id": delivery_run_id,
    "created_at": "2026-07-04T17:00:00+09:00",
    "status": status,
    "send_mode": EMAIL_SEND_MODE_SELF_ONLY,
    "recipient_masked": "m***@example.com",
    "sender_masked": "s***@example.com",
    "subject": str(preview["subject"]),
    "data_source": str(preview["data_source"]),
    "signal_count": int(preview["signal_count"]),
    "digest_sha256": digest_sha256 or str(preview["digest_sha256"]),
    "send_attempted": send_attempted,
    "send_succeeded": send_succeeded,
    "smtp_host": "smtp.example.com",
    "error_type": error_type,
    "safe_error_message": safe_error_message,
  }


def test_build_subject_sanitizes_newlines_and_truncates() -> None:
  subject = build_digest_email_subject("テーマ名\nInjected: nope")
  assert "\n" not in subject
  assert "\r" not in subject
  assert subject.startswith("[Tech Cartography]")


def test_build_preview_keeps_review_aware_digest_and_source_url() -> None:
  preview = _preview()
  assert _digest_markdown().strip() in preview["plain_text_body"]
  assert "https://example.com/pan" in preview["plain_text_body"]
  assert "人間レビュー: 採用" in preview["plain_text_body"]


def test_build_preview_generates_safe_html() -> None:
  preview = _preview()
  assert "&lt;script&gt;alert" in preview["html_body"]
  assert '<a href="https://example.com/pan">https://example.com/pan</a>' in preview["html_body"]
  assert "<script>" not in preview["html_body"]


def test_load_config_has_safe_defaults() -> None:
  config = load_email_delivery_config({})
  assert config.disabled is True
  assert config.send_mode == EMAIL_SEND_MODE_PREVIEW
  assert config.use_starttls is True


def test_load_config_uses_smtp_aliases_when_canonical_names_missing() -> None:
  config = load_email_delivery_config(
    {
      "DISABLE_EMAIL_SEND": "false",
      "EMAIL_SEND_MODE": "self_only",
      "SMTP_HOST": "smtp.example.com",
      "SMTP_PORT": "587",
      "SMTP_USER": "alias-user",
      "SMTP_PASSWORD": "alias-password",
      "SMTP_FROM_EMAIL": "alias@example.com",
    }
  )
  assert config.disabled is False
  assert config.send_mode == EMAIL_SEND_MODE_SELF_ONLY
  assert config.smtp_username == "alias-user"
  assert config.sender == "alias@example.com"
  assert config.self_recipient == "alias@example.com"
  assert config.recipient_allowlist == ("alias@example.com",)


def test_load_config_prefers_canonical_names_over_aliases() -> None:
  config = load_email_delivery_config(
    {
      "SMTP_USERNAME": "canonical-user",
      "SMTP_USER": "alias-user",
      "EMAIL_SENDER": "sender@example.com",
      "SMTP_FROM_EMAIL": "alias@example.com",
      "EMAIL_SELF_RECIPIENT": "self@example.com",
      "EMAIL_RECIPIENT_ALLOWLIST": "self@example.com;other@example.com",
      "SMTP_HOST": "smtp.example.com",
      "SMTP_PORT": "587",
      "SMTP_PASSWORD": "alias-password",
    }
  )
  assert config.smtp_username == "canonical-user"
  assert config.sender == "sender@example.com"
  assert config.self_recipient == "self@example.com"
  assert config.recipient_allowlist == ("other@example.com", "self@example.com")


def test_load_config_ignores_empty_alias_values() -> None:
  config = load_email_delivery_config(
    {
      "SMTP_HOST": "smtp.example.com",
      "SMTP_PORT": "587",
      "SMTP_USER": "   ",
      "SMTP_PASSWORD": "alias-password",
      "SMTP_FROM_EMAIL": " ",
    }
  )
  assert config.smtp_username == ""
  assert config.sender == ""
  assert config.self_recipient == ""
  assert config.recipient_allowlist == ()


def test_load_config_reads_project_dotenv_for_aliases(monkeypatch, tmp_path: Path) -> None:
  (tmp_path / ".env").write_text(
    "\n".join(
      [
        "SMTP_HOST=smtp.example.com",
        "SMTP_PORT=587",
        "SMTP_USER=dotenv-user",
        "SMTP_PASSWORD=dotenv-password",
        "SMTP_FROM_EMAIL=dotenv@example.com",
      ]
    )
    + "\n",
    encoding="utf-8",
  )
  monkeypatch.setattr(email_delivery_module, "PROJECT_ROOT", tmp_path)
  for name in [
    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USER",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",
    "SMTP_FROM_EMAIL",
    "EMAIL_SENDER",
    "EMAIL_SELF_RECIPIENT",
    "EMAIL_RECIPIENT_ALLOWLIST",
  ]:
    monkeypatch.delenv(name, raising=False)
  config = load_email_delivery_config()
  assert config.smtp_host == "smtp.example.com"
  assert config.smtp_port == 587
  assert config.smtp_username == "dotenv-user"
  assert config.sender == "dotenv@example.com"
  assert config.self_recipient == "dotenv@example.com"
  assert config.recipient_allowlist == ("dotenv@example.com",)


def test_alias_based_config_passes_self_only_validation() -> None:
  preview = _preview()
  config = load_email_delivery_config(
    {
      "DISABLE_EMAIL_SEND": "false",
      "EMAIL_SEND_MODE": "self_only",
      "SMTP_HOST": "smtp.example.com",
      "SMTP_PORT": "587",
      "SMTP_USER": "alias-user",
      "SMTP_PASSWORD": "alias-password",
      "SMTP_FROM_EMAIL": "me@example.com",
    }
  )
  rows = validate_self_only_delivery(
    config,
    "me@example.com",
    preview["signals"],
    preview["data_source"],
    data_source_mode=preview["data_source_mode"],
  )
  assert not [row for row in rows if row["status"] == "error"]


def test_validate_blocks_preview_mode_and_disable_flag() -> None:
  preview = _preview()
  rows = validate_self_only_delivery(
    _config(send_mode=EMAIL_SEND_MODE_PREVIEW, disabled=True),
    "me@example.com",
    preview["signals"],
    preview["data_source"],
    data_source_mode=preview["data_source_mode"],
  )
  messages = [row["message"] for row in rows]
  assert any("停止中" in message for message in messages)
  assert any("EMAIL_SEND_MODE=self_only" in message for message in messages)


def test_validate_blocks_allowlist_mismatch_and_self_mismatch_and_multi_recipient() -> None:
  preview = _preview()
  rows = validate_self_only_delivery(
    _config(self_recipient="self@example.com", recipient_allowlist=("self@example.com",)),
    "self@example.com,other@example.com",
    preview["signals"],
    preview["data_source"],
    data_source_mode=preview["data_source_mode"],
  )
  messages = [row["message"] for row in rows]
  assert any("複数宛先" in message for message in messages)
  assert any("allowlist" in message.lower() or "ALLOWLIST" in message for message in messages)


def test_validate_blocks_demo_csv_json_and_synthetic_data() -> None:
  demo_rows = validate_self_only_delivery(
    _config(),
    "me@example.com",
    _real_retrieval_signals(),
    "デモデータ",
    data_source_mode="demo",
  )
  csv_rows = validate_self_only_delivery(
    _config(),
    "me@example.com",
    _real_retrieval_signals(),
    "CSVアップロード",
    data_source_mode="csv",
  )
  json_rows = validate_self_only_delivery(
    _config(),
    "me@example.com",
    _real_retrieval_signals(),
    "JSONアップロード",
    data_source_mode="json",
  )
  synthetic_rows = validate_self_only_delivery(
    _config(),
    "me@example.com",
    [
      {
        **_real_retrieval_signals()[0],
        "is_synthetic_demo": True,
      }
    ],
    "取得済みデータ",
    data_source_mode="retrieval_saved",
  )
  assert any("実送信は禁止" in row["message"] for row in demo_rows)
  assert any("CSVアップロード" in row["message"] for row in csv_rows)
  assert any("JSONアップロード" in row["message"] for row in json_rows)
  assert any("synthetic" in row["message"] for row in synthetic_rows)


def test_validate_allows_real_retrieval_and_warns_on_partial_success() -> None:
  preview = _preview(signals=_real_retrieval_signals(partial=True))
  rows = validate_self_only_delivery(
    _config(),
    "me@example.com",
    preview["signals"],
    preview["data_source"],
    data_source_mode=preview["data_source_mode"],
  )
  assert not [row for row in rows if row["status"] == "error"]
  assert any("partial_success" in row["message"] for row in rows if row["status"] == "warning")


def test_dry_run_does_not_connect_smtp_and_returns_ready() -> None:
  preview = _preview()
  result = run_email_delivery_dry_run(preview, _config())
  assert result["status"] == "ready"
  assert result["send_attempted"] is False
  assert result["recipient"] == "me@example.com"
  assert result["validation_errors"] == []


def test_build_email_preview_artifact_reuses_payload_body_and_masks_recipient() -> None:
  preview = _preview()
  dry_run_result = run_email_delivery_dry_run(preview, _config())
  artifact = build_email_preview_artifact(
    preview,
    dry_run_result,
    source_digest_path="weekly_runs/run_a/weekly_digest.md",
  )
  assert artifact["subject"] == preview["subject"]
  assert artifact["body_text"] == preview["plain_text_body"]
  assert artifact["body_sha256"] == hashlib.sha256(preview["plain_text_body"].encode("utf-8")).hexdigest()
  assert artifact["body_length"] == len(preview["plain_text_body"].encode("utf-8"))
  assert artifact["source_digest_path"] == "weekly_runs/run_a/weekly_digest.md"
  assert artifact["recipient_masked"] == "m***@example.com"
  assert artifact["email_mode"] == EMAIL_SEND_MODE_SELF_ONLY
  assert artifact["send_attempted"] is False
  assert artifact["send_succeeded"] is False
  raw_artifact = json.dumps(artifact, ensure_ascii=False)
  assert "me@example.com" not in raw_artifact
  assert "smtp-password" not in raw_artifact
  assert "credential" not in raw_artifact.lower()


def test_build_email_preview_artifact_blocks_oversized_body_without_truncation() -> None:
  preview = _preview()
  preview["plain_text_body"] = "A" * (EMAIL_PREVIEW_BODY_TEXT_MAX_BYTES + 1)
  dry_run_result = run_email_delivery_dry_run(preview, _config())
  artifact = build_email_preview_artifact(
    preview,
    dry_run_result,
    source_digest_path="weekly_runs/run_b/weekly_digest.md",
  )
  assert artifact["status"] == "blocked"
  assert artifact["body_text"] == preview["plain_text_body"]
  assert artifact["body_length"] == EMAIL_PREVIEW_BODY_TEXT_MAX_BYTES + 1
  assert any("上限" in message for message in artifact["validation_errors"])


def test_send_self_only_uses_starttls_login_and_single_send() -> None:
  _MockSMTP.instances.clear()
  preview = _preview()
  result = send_digest_email_self_only(preview, _config(), smtp_factory=_MockSMTP)
  assert result["status"] == "sent"
  assert result["send_attempted"] is True
  assert result["send_succeeded"] is True
  smtp_client = _MockSMTP.instances[-1]
  assert smtp_client.starttls_calls == 1
  assert smtp_client.login_calls == [("smtp-user", "smtp-password")]
  assert smtp_client.send_message_calls == 1
  assert "smtp_password" not in json.dumps(result)


def test_send_self_only_returns_safe_error_result() -> None:
  preview = _preview()
  result = send_digest_email_self_only(preview, _config(), smtp_factory=_FailingSMTP)
  assert result["send_attempted"] is True
  assert result["send_succeeded"] is False
  assert result["error_type"] == "SMTPException"
  assert "smtp-password" not in json.dumps(result)


def test_send_is_blocked_when_validation_fails() -> None:
  preview = _preview(source_label="デモデータ", source_mode="demo")
  result = send_digest_email_self_only(preview, _config(), smtp_factory=_MockSMTP)
  assert result["send_attempted"] is False
  assert result["send_succeeded"] is False
  assert result["status"] == "blocked"


def test_save_email_delivery_log_redacts_sensitive_content(tmp_path: Path) -> None:
  preview = _preview()
  result = run_email_delivery_dry_run(preview, _config())
  log_path = save_email_delivery_log(result, tmp_path)
  payload = json.loads(log_path.read_text(encoding="utf-8"))
  raw_text = log_path.read_text(encoding="utf-8")
  assert payload["digest_sha256"] == preview["digest_sha256"]
  assert "smtp-password" not in raw_text
  assert _digest_markdown() not in raw_text


def test_is_successful_digest_delivery_record_requires_matching_digest_and_true_true_flags() -> None:
  digest = _preview()["digest_sha256"]
  assert is_successful_digest_delivery_record(
    {"digest_sha256": digest, "send_attempted": True, "send_succeeded": True},
    digest,
  ) is True
  assert is_successful_digest_delivery_record(
    {"digest_sha256": digest, "send_attempted": False, "send_succeeded": True},
    digest,
  ) is False
  assert is_successful_digest_delivery_record(
    {"digest_sha256": digest, "send_attempted": True, "send_succeeded": False},
    digest,
  ) is False
  assert is_successful_digest_delivery_record(
    {"digest_sha256": "different", "send_attempted": True, "send_succeeded": True},
    digest,
  ) is False
  assert is_successful_digest_delivery_record(
    {"digest_sha256": digest, "send_attempted": "true", "send_succeeded": "true"},
    digest,
  ) is False


def test_has_successful_digest_delivery_ignores_preview_dry_run_blocked_and_failed_logs(tmp_path: Path) -> None:
  digest = _preview()["digest_sha256"]
  ignored_payloads = [
    {"status": "preview", "digest_sha256": digest, "send_attempted": False, "send_succeeded": False},
    {"status": "dry_run", "digest_sha256": digest, "send_attempted": False, "send_succeeded": False},
    {"status": "blocked", "digest_sha256": digest, "send_attempted": False, "send_succeeded": False, "safe_error_message": "allowlist rejected"},
    {"status": "blocked", "digest_sha256": digest, "send_attempted": False, "send_succeeded": False, "safe_error_message": "self-only config missing"},
    {"status": "failed", "digest_sha256": digest, "send_attempted": False, "send_succeeded": False},
    {"status": "error", "digest_sha256": digest, "send_attempted": True, "send_succeeded": False, "error_type": "SMTPConnectError"},
    {"status": "error", "digest_sha256": digest, "send_attempted": True, "send_succeeded": False, "error_type": "SMTPAuthenticationError"},
    {"status": "error", "digest_sha256": digest, "send_attempted": True, "send_succeeded": False, "error_type": "SMTPException"},
    {"status": "sent", "digest_sha256": digest, "send_attempted": False, "send_succeeded": True},
    {"status": "sent", "digest_sha256": digest, "send_attempted": True, "send_succeeded": False},
    {"status": "sent", "digest_sha256": "different", "send_attempted": True, "send_succeeded": True},
    {"status": "sent", "digest_sha256": digest},
  ]
  for index, payload in enumerate(ignored_payloads, start=1):
    case_root = tmp_path / f"case_{index}"
    _write_email_delivery_log(case_root, f"log_{index}", payload)
    assert has_successful_digest_delivery(case_root, digest) is False


def test_has_successful_digest_delivery_ignores_broken_json_and_detects_real_success(tmp_path: Path) -> None:
  digest = _preview()["digest_sha256"]
  broken_dir = tmp_path / "email_delivery_runs" / "broken"
  broken_dir.mkdir(parents=True, exist_ok=True)
  (broken_dir / "email_delivery_log.json").write_text("{not-json\n", encoding="utf-8")
  _write_email_delivery_log(
    tmp_path,
    "valid_success",
    {"status": "sent", "digest_sha256": digest, "send_attempted": True, "send_succeeded": True},
  )
  assert has_successful_digest_delivery(tmp_path, digest) is True


def test_save_email_delivery_log_keeps_send_flags_strict_booleans(tmp_path: Path) -> None:
  log_path = save_email_delivery_log(
    {
      "delivery_run_id": "email_delivery_non_bool_flags",
      "status": "sent",
      "digest_sha256": _preview()["digest_sha256"],
      "send_attempted": "false",
      "send_succeeded": "false",
    },
    tmp_path,
  )
  payload = json.loads(log_path.read_text(encoding="utf-8"))
  assert payload["send_attempted"] is False
  assert payload["send_succeeded"] is False
  assert has_successful_digest_delivery(tmp_path, payload["digest_sha256"]) is False


def test_save_email_delivery_log_does_not_mutate_input_dict(tmp_path: Path) -> None:
  original = _log_result(delivery_run_id="email_delivery_input_preserved")
  before = json.loads(json.dumps(original))
  save_email_delivery_log(original, tmp_path)
  assert original == before


def test_success_and_duplicate_blocked_logs_use_distinct_run_ids(tmp_path: Path) -> None:
  digest = _preview()["digest_sha256"]
  success_result = _log_result(delivery_run_id="email_delivery_same", digest_sha256=digest)
  blocked_result = _log_result(
    delivery_run_id="email_delivery_same",
    status="blocked",
    digest_sha256=digest,
    send_attempted=False,
    send_succeeded=False,
    safe_error_message="duplicate digest blocked before SMTP",
  )
  success_path = save_email_delivery_log(success_result, tmp_path)
  blocked_path = save_email_delivery_log(blocked_result, tmp_path)
  success_payload = json.loads(success_path.read_text(encoding="utf-8"))
  blocked_payload = json.loads(blocked_path.read_text(encoding="utf-8"))
  assert success_payload["delivery_run_id"] == "email_delivery_same"
  assert blocked_payload["delivery_run_id"] != success_payload["delivery_run_id"]
  assert blocked_payload["delivery_run_id"].startswith("email_delivery_same_")
  assert blocked_payload["status"] == "blocked"
  assert has_successful_digest_delivery(tmp_path, digest) is True


def test_preview_and_failed_logs_do_not_overwrite_success_log(tmp_path: Path) -> None:
  digest = _preview()["digest_sha256"]
  success_path = save_email_delivery_log(_log_result(delivery_run_id="email_delivery_shared", digest_sha256=digest), tmp_path)
  preview_path = save_email_delivery_log(
    _log_result(
      delivery_run_id="email_delivery_shared",
      status="preview",
      digest_sha256=digest,
      send_attempted=False,
      send_succeeded=False,
    ),
    tmp_path,
  )
  failed_path = save_email_delivery_log(
    _log_result(
      delivery_run_id="email_delivery_shared",
      status="error",
      digest_sha256=digest,
      send_attempted=True,
      send_succeeded=False,
      error_type="SMTPException",
    ),
    tmp_path,
  )
  success_payload = json.loads(success_path.read_text(encoding="utf-8"))
  assert success_payload["status"] == "sent"
  assert success_path != preview_path
  assert success_path != failed_path
  assert has_successful_digest_delivery(tmp_path, digest) is True


def test_save_email_delivery_log_avoids_generated_id_collision_same_second(tmp_path: Path, monkeypatch) -> None:
  monkeypatch.setattr(email_delivery_module, "_build_delivery_run_id", lambda: "email_delivery_fixed")
  first_path = save_email_delivery_log(_log_result(delivery_run_id=""), tmp_path)
  second_path = save_email_delivery_log(_log_result(delivery_run_id=""), tmp_path)
  first_payload = json.loads(first_path.read_text(encoding="utf-8"))
  second_payload = json.loads(second_path.read_text(encoding="utf-8"))
  assert first_payload["delivery_run_id"] == "email_delivery_fixed"
  assert second_payload["delivery_run_id"] != first_payload["delivery_run_id"]
  assert second_payload["delivery_run_id"].startswith("email_delivery_fixed_")


def test_save_email_delivery_log_preserves_existing_broken_log_and_switches_id(tmp_path: Path) -> None:
  broken_dir = tmp_path / "email_delivery_runs" / "email_delivery_broken"
  broken_dir.mkdir(parents=True, exist_ok=True)
  broken_path = broken_dir / "email_delivery_log.json"
  broken_path.write_text("{broken-json\n", encoding="utf-8")
  new_path = save_email_delivery_log(_log_result(delivery_run_id="email_delivery_broken"), tmp_path)
  assert broken_path.read_text(encoding="utf-8") == "{broken-json\n"
  assert new_path != broken_path
  new_payload = json.loads(new_path.read_text(encoding="utf-8"))
  assert new_payload["delivery_run_id"].startswith("email_delivery_broken_")


def test_page_render_keeps_six_tabs_and_email_buttons_without_sending(monkeypatch) -> None:
  def _raise_if_called(*args, **kwargs):
    raise AssertionError("SMTP should not be used during render")

  monkeypatch.setattr("services_v9.email_delivery.smtplib.SMTP", _raise_if_called)
  monkeypatch.setattr("services_v9.email_delivery.smtplib.SMTP_SSL", _raise_if_called)
  at = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
  at.run()
  assert len(at.get("tab")) == 6
  assert any(button.label == "メール送信dry-run" for button in at.button)
  assert any(button.label == "自分宛てにメール送信" for button in at.button)


def test_plain_imports_work_without_pythonpath() -> None:
  env = os.environ.copy()
  env.pop("PYTHONPATH", None)
  completed = subprocess.run(
    [sys.executable, "-c", "import app; import services_v9.email_delivery; print('ok')"],
    cwd=str(PROJECT_ROOT),
    env=env,
    capture_output=True,
    text=True,
    check=True,
  )
  assert "ok" in completed.stdout
