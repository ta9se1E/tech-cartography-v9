"""Toggle v9 cloud weekly delivery enabled flag via formal settings save."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Mapping

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
  sys.path.insert(0, str(PROJECT_ROOT))

from services_v9.cloud_runtime import (  # noqa: E402
  get_persist_bucket_name,
  get_runtime_mode,
  get_weekly_config_object_name,
  is_cloud_runtime,
)
from services_v9.cloud_weekly_settings import (  # noqa: E402
  load_weekly_delivery_settings,
  mask_email_address,
  save_weekly_delivery_settings,
)

DEFAULT_PROJECT_ID = "devops-ai-agent-hackathon-2026"
DEFAULT_BUCKET = "tech-cartography-v9-weekly-persist-1020686343587"
DEFAULT_CONFIG_OBJECT = "v9_config/weekly_delivery_config.json"
DEFAULT_PERSIST_ROOT = "/mnt/v9_persist"
PRESERVED_FIELDS = (
  "recipient_email",
  "weekday",
  "hour",
  "minute",
  "timezone",
  "email_mode",
  "scheduler_applied_revision",
  "last_scheduler_apply_status",
  "last_scheduler_apply_at",
  "last_scheduler_known_state",
)


def build_cloud_environ(
  *,
  project_id: str = DEFAULT_PROJECT_ID,
  bucket: str = DEFAULT_BUCKET,
  config_object: str = DEFAULT_CONFIG_OBJECT,
  persist_root: str = DEFAULT_PERSIST_ROOT,
) -> dict[str, str]:
  env = dict(os.environ)
  env.update({
    "GOOGLE_CLOUD_PROJECT": str(project_id or DEFAULT_PROJECT_ID),
    "V9_RUNTIME_MODE": "cloud",
    "V9_PERSIST_BUCKET": str(bucket or DEFAULT_BUCKET),
    "V9_WEEKLY_CONFIG_OBJECT": str(config_object or DEFAULT_CONFIG_OBJECT),
    "V9_PERSIST_ROOT": str(persist_root or DEFAULT_PERSIST_ROOT),
  })
  return env


def require_apply_guard() -> None:
  if os.environ.get("V9_CLOUD_CHANGE_APPROVED", "").strip().lower() != "true":
    raise RuntimeError("--enable/--disable requires V9_CLOUD_CHANGE_APPROVED=true")


def validate_cloud_target(environ: Mapping[str, str]) -> None:
  if get_runtime_mode(environ) != "cloud":
    raise RuntimeError("V9_RUNTIME_MODE must be cloud for enabled toggle.")
  bucket = get_persist_bucket_name(environ)
  object_name = get_weekly_config_object_name(environ)
  if not bucket:
    raise RuntimeError("V9_PERSIST_BUCKET is required for cloud enabled toggle.")
  if bucket != DEFAULT_BUCKET:
    raise RuntimeError("Refusing to update unexpected bucket target.")
  if object_name != DEFAULT_CONFIG_OBJECT:
    raise RuntimeError("Refusing to update unexpected weekly config object.")


def _snapshot_settings(settings: Mapping[str, Any]) -> dict[str, Any]:
  return {
    "enabled": bool(settings.get("enabled", False)),
    "revision": int(settings.get("revision", 0) or 0),
    "weekday": str(settings.get("weekday", "") or ""),
    "hour": int(settings.get("hour", 0) or 0),
    "minute": int(settings.get("minute", 0) or 0),
    "timezone": str(settings.get("timezone", "") or ""),
    "email_mode": str(settings.get("email_mode", "") or ""),
    "recipient_masked": mask_email_address(str(settings.get("recipient_email", "") or "")),
    "schema_version": str(settings.get("schema_version", "") or ""),
  }


def plan_enabled_toggle(
  *,
  target_enabled: bool,
  environ: Mapping[str, str],
  storage_client: Any | None = None,
) -> dict[str, Any]:
  validate_cloud_target(environ)
  current = load_weekly_delivery_settings(environ=environ, storage_client=storage_client)
  return {
    "status": "plan",
    "action": "enable" if target_enabled else "disable",
    "storage_mode": "cloud",
    "location": f"gs://{get_persist_bucket_name(environ)}/{get_weekly_config_object_name(environ)}",
    "current": _snapshot_settings(current),
    "target_enabled": bool(target_enabled),
    "would_change": bool(current.get("enabled", False)) != bool(target_enabled),
  }


def apply_enabled_toggle(
  *,
  target_enabled: bool,
  updated_by: str,
  environ: Mapping[str, str],
  storage_client: Any | None = None,
) -> dict[str, Any]:
  require_apply_guard()
  validate_cloud_target(environ)
  current = load_weekly_delivery_settings(environ=environ, storage_client=storage_client)
  before = _snapshot_settings(current)
  preserved = {field: current.get(field) for field in PRESERVED_FIELDS}
  save_result = save_weekly_delivery_settings(
    {
      **preserved,
      "enabled": bool(target_enabled),
    },
    updated_by=updated_by,
    environ=environ,
    storage_client=storage_client,
  )
  readback = load_weekly_delivery_settings(environ=environ, storage_client=storage_client)
  after = _snapshot_settings(readback)
  if bool(readback.get("enabled", False)) != bool(target_enabled):
    raise RuntimeError("enabled readback mismatch after save.")
  return {
    "status": "applied",
    "action": "enable" if target_enabled else "disable",
    "storage_mode": str(save_result.get("storage_mode", "") or ""),
    "location": str(save_result.get("location", "") or ""),
    "before": before,
    "after": after,
    "enabled": bool(readback.get("enabled", False)),
    "revision": int(readback.get("revision", 0) or 0),
  }


def build_parser() -> argparse.ArgumentParser:
  parser = argparse.ArgumentParser(description="Plan or apply v9 cloud weekly enabled toggle.")
  mode = parser.add_mutually_exclusive_group()
  mode.add_argument("--plan", action="store_true", help="Plan only (default).")
  mode.add_argument("--enable", action="store_true", help="Set enabled=true in cloud weekly settings.")
  mode.add_argument("--disable", action="store_true", help="Set enabled=false in cloud weekly settings.")
  parser.add_argument("--project-id", default=DEFAULT_PROJECT_ID)
  parser.add_argument("--bucket", default=DEFAULT_BUCKET)
  parser.add_argument("--config-object", default=DEFAULT_CONFIG_OBJECT)
  parser.add_argument("--persist-root", default=DEFAULT_PERSIST_ROOT)
  return parser


def main(argv: list[str] | None = None) -> int:
  args = build_parser().parse_args(argv)
  environ = build_cloud_environ(
    project_id=str(args.project_id),
    bucket=str(args.bucket),
    config_object=str(args.config_object),
    persist_root=str(args.persist_root),
  )
  if args.enable and args.disable:
    print(json.dumps({"status": "failed", "error": "Use either --enable or --disable."}, ensure_ascii=False, indent=2))
    return 1

  try:
    if args.enable:
      payload = apply_enabled_toggle(target_enabled=True, updated_by="set-v9-cloud-weekly-enabled", environ=environ)
    elif args.disable:
      payload = apply_enabled_toggle(target_enabled=False, updated_by="set-v9-cloud-weekly-enabled", environ=environ)
    else:
      current = load_weekly_delivery_settings(environ=environ)
      target_enabled = not bool(current.get("enabled", False))
      payload = plan_enabled_toggle(target_enabled=target_enabled, environ=environ)
  except RuntimeError as exc:
    print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False, indent=2))
    return 1

  serialized = json.dumps(payload, ensure_ascii=False, indent=2)
  banned_tokens = ("smtp_password", "tavily_api_key", "secret", "password", "tvly-")
  lowered = serialized.lower()
  if any(token in lowered for token in banned_tokens):
    print(json.dumps({"status": "failed", "error": "Refusing to print sensitive output."}, ensure_ascii=False, indent=2))
    return 1
  print(serialized)
  return 0 if payload.get("status") in {"plan", "applied"} else 2


if __name__ == "__main__":
  raise SystemExit(main())
