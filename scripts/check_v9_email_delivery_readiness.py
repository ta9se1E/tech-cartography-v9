"""Readiness check for v9 digest email preview and self-only delivery."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

from streamlit.testing.v1 import AppTest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))

from services_v9.email_delivery import (  # noqa: E402
  EmailDeliveryConfig,
  build_digest_email_preview,
  build_digest_email_subject,
  run_email_delivery_dry_run,
  save_email_delivery_log,
  send_digest_email_self_only,
  validate_self_only_delivery,
)


class _MockSMTP:
  def __init__(self, host: str, port: int, timeout: int):
    self.host = host
    self.port = port
    self.timeout = timeout
    self.starttls_calls = 0
    self.login_calls = 0
    self.send_calls = 0

  def __enter__(self) -> "_MockSMTP":
    return self

  def __exit__(self, exc_type, exc, tb) -> None:
    return None

  def ehlo(self) -> None:
    return None

  def starttls(self, context=None) -> None:
    self.starttls_calls += 1

  def login(self, username: str, password: str) -> None:
    self.login_calls += 1

  def send_message(self, message) -> None:
    self.send_calls += 1


def _config() -> EmailDeliveryConfig:
  return EmailDeliveryConfig(
    send_mode="self_only",
    disabled=False,
    sender="sender@example.com",
    self_recipient="me@example.com",
    recipient_allowlist=("me@example.com",),
    smtp_host="smtp.example.com",
    smtp_port=587,
    smtp_username="smtp-user",
    smtp_password="smtp-password",
    use_starttls=True,
    timeout_seconds=30,
  )


def _preview(*, source_mode: str = "retrieval_saved", partial: bool = False) -> dict:
  provider_status = "partial_success" if partial else "success"
  return build_digest_email_preview(
    digest_markdown=(
      "# Tech Cartography v9 週次ダイジェスト\n\n"
      "1. **候補A**\n"
      "   - 人間レビュー: 採用\n"
      "   - 出典URL: https://example.com/a\n"
    ),
    theme_name="PAN系炭素繊維前駆体の欠陥制御",
    data_source="取得済みデータ" if source_mode == "retrieval_saved" else "デモデータ",
    signals=[
      {
        "id": "sig-1",
        "title": "候補A",
        "source_url": "https://example.com/a",
        "record_stage": "staged",
        "retrieval_mode": "real" if source_mode == "retrieval_saved" else "local",
        "data_origin": "openalex_paper" if source_mode == "retrieval_saved" else "base_signal",
        "source_trace": [
          {
            "source_type": "paper",
            "provider_status": provider_status,
            "data_origin": "openalex_paper" if source_mode == "retrieval_saved" else "base_signal",
          }
        ],
      }
    ],
    data_source_mode=source_mode,
  )


def main() -> None:
  preview = _preview()
  subject = build_digest_email_subject("テーマ名\nInjected")
  assert "\n" not in subject
  assert "Tech Cartography" in subject
  assert "&lt;" not in preview["html_body"] or "https://example.com/a" in preview["html_body"]

  validation_rows = validate_self_only_delivery(
    _config(),
    "me@example.com",
    list(preview.get("signals", []) or []),
    str(preview.get("data_source", "") or ""),
    data_source_mode=str(preview.get("data_source_mode", "") or ""),
  )
  assert not [row for row in validation_rows if row["status"] == "error"]

  demo_rows = validate_self_only_delivery(
    _config(),
    "me@example.com",
    list(_preview(source_mode="demo").get("signals", []) or []),
    "デモデータ",
    data_source_mode="demo",
  )
  assert any("Preview" in row["message"] or "禁止" in row["message"] for row in demo_rows)

  partial_rows = validate_self_only_delivery(
    _config(),
    "me@example.com",
    list(_preview(partial=True).get("signals", []) or []),
    "取得済みデータ",
    data_source_mode="retrieval_saved",
  )
  assert any(row["status"] == "warning" for row in partial_rows)

  dry_run = run_email_delivery_dry_run(preview, _config())
  assert dry_run["status"] == "ready"
  assert dry_run["send_attempted"] is False

  send_result = send_digest_email_self_only(preview, _config(), smtp_factory=_MockSMTP)
  assert send_result["send_succeeded"] is True

  with tempfile.TemporaryDirectory() as tmp_dir:
    log_path = save_email_delivery_log(send_result, tmp_dir)
    payload = json.loads(log_path.read_text(encoding="utf-8"))
    assert payload["send_succeeded"] is True
    assert "smtp-password" not in log_path.read_text(encoding="utf-8")

  env = os.environ.copy()
  env.pop("PYTHONPATH", None)
  imports = subprocess.run(
    [sys.executable, "-c", "import app; import services_v9.email_delivery; print('startup ok')"],
    cwd=str(PROJECT_ROOT),
    env=env,
    capture_output=True,
    text=True,
    check=True,
  )
  assert "startup ok" in imports.stdout

  at = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
  at.run()
  assert len(at.get("tab")) == 6
  labels = [button.label for button in at.button]
  assert "メール送信dry-run" in labels
  assert "自分宛てにメール送信" in labels

  print("[v9 email delivery readiness] OK: digest email preview and self-only delivery are ready.")


if __name__ == "__main__":
  main()
