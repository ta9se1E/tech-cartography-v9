"""External API execution guard — env flag first, then required keys (Phase 25C)."""

from __future__ import annotations

from typing import Any

from tech_cartography.runtime.api_secret_config import (
  can_use_external_api,
  get_api_secret_status,
)
from tech_cartography.runtime.cloud_run_config import is_external_api_disabled

SERVICE_REQUIRED_KEYS: dict[str, tuple[str, ...]] = {
  "openalex": (),
  "tavily": ("TAVILY_API_KEY",),
  "bigquery": ("GOOGLE_API_KEY",),
}


def get_external_api_guard_status() -> dict[str, Any]:
  """Combined guard view for UI — no secret values."""
  status = get_api_secret_status()
  status["disabled_by_env"] = is_external_api_disabled()
  return status


def check_service_external_api(service: str) -> tuple[bool, list[str], str | None]:
  """Return (allowed, missing_keys, block_reason). block_reason is None when allowed."""
  keys = list(SERVICE_REQUIRED_KEYS.get(service, ()))
  allowed, missing = can_use_external_api(keys)
  if is_external_api_disabled():
    return False, missing, "disabled_by_env"
  if missing:
    return False, missing, "missing_keys"
  return True, [], None


def external_api_ui_messages(*, services: tuple[str, ...] = ("openalex", "tavily", "bigquery")) -> list[str]:
  """Human-readable guard messages for Streamlit captions."""
  messages: list[str] = []
  if is_external_api_disabled():
    messages.append("外部API無効化中（DISABLE_EXTERNAL_API=true）")

  missing_for_services: list[str] = []
  for service in services:
    _, missing, reason = check_service_external_api(service)
    if reason == "missing_keys":
      for key in missing:
        if key not in missing_for_services:
          missing_for_services.append(key)

  if missing_for_services and not is_external_api_disabled():
    messages.append(f"APIキー未設定: {', '.join(missing_for_services)}")
  elif missing_for_services and is_external_api_disabled():
    pass
  elif not is_external_api_disabled():
    status = get_api_secret_status()
    if status["missing_keys"]:
      messages.append(f"未設定のAPIキー: {', '.join(status['missing_keys'])}")

  return messages


def resolve_allow_external_api(
  *,
  allow_checkbox: bool,
  run_openalex: bool = False,
  run_tavily: bool = False,
  run_bigquery: bool = False,
) -> tuple[bool, list[str]]:
  """Apply guard to UI checkbox — returns effective allow flag and block reasons."""
  if not allow_checkbox:
    return False, []

  reasons: list[str] = []
  if is_external_api_disabled():
    return False, ["disabled_by_env"]

  if run_openalex:
    allowed, missing, reason = check_service_external_api("openalex")
    if not allowed and reason:
      reasons.append(reason)
      if missing:
        reasons.extend(missing)
  if run_tavily:
    allowed, missing, reason = check_service_external_api("tavily")
    if not allowed and reason:
      if reason not in reasons:
        reasons.append(reason)
      for key in missing:
        if key not in reasons:
          reasons.append(key)
  if run_bigquery:
    allowed, missing, reason = check_service_external_api("bigquery")
    if not allowed and reason:
      if reason not in reasons:
        reasons.append(reason)
      for key in missing:
        if key not in reasons:
          reasons.append(key)

  if reasons:
    return False, reasons
  return True, []
