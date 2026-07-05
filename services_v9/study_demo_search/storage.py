"""GCS persistence for study demo search runs."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Mapping

from services_v9.study_demo_config import get_study_demo_bucket
from services_v9.study_demo_storage import validate_study_demo_write_target

from .constants import SEARCH_RUN_PREFIX, SEARCH_USAGE_OBJECT


def _object_path(search_run_id: str, name: str) -> str:
  return f"{SEARCH_RUN_PREFIX}{search_run_id}/{name}"


def _dumps(payload: Mapping[str, Any]) -> str:
  return json.dumps(payload, ensure_ascii=False, indent=2) + "\n"


def save_search_run(
  bundle: Mapping[str, Any],
  *,
  environ: Mapping[str, str] | None = None,
  storage_client: Any | None = None,
) -> dict[str, Any]:
  bucket_name = get_study_demo_bucket(environ)
  validate_study_demo_write_target(bucket_name, environ=environ)
  search_run_id = str(bundle.get("search_run_id", "") or "")
  if not search_run_id:
    raise ValueError("search_run_id is required")

  client = storage_client if storage_client is not None else _build_client()
  bucket = client.bucket(bucket_name)
  summary = dict(bundle.get("summary", {}) or {})
  artifacts = {
    "search_request.json": summary,
    "search_plan.json": dict(bundle.get("search_plan", {}) or {}),
    "cost_estimate.json": dict(bundle.get("cost_estimate", {}) or {}),
    "provider_status.json": dict(bundle.get("provider_status", {}) or {}),
    "patent_results.json": _sanitize_provider_payload(bundle.get("patent_results", {})),
    "paper_results.json": _sanitize_provider_payload(bundle.get("paper_results", {})),
    "web_results.json": _sanitize_provider_payload(bundle.get("web_results", {})),
    "integrated_signals.json": dict(bundle.get("integrated_signals", {}) or {}),
    "keyword_suggestions.json": dict(bundle.get("keyword_suggestions", {}) or {}),
    "similar_patents.json": dict(bundle.get("similar_patents", {}) or {}),
    "usage_metrics.json": dict(bundle.get("usage_metrics", {}) or {}),
    "search_status.json": {
      "search_run_id": search_run_id,
      "status": bundle.get("status"),
      "saved_at": datetime.now(timezone.utc).isoformat(),
    },
    "search_report.md": _build_report_markdown(bundle),
  }
  saved = []
  for name, payload in artifacts.items():
    blob = bucket.blob(_object_path(search_run_id, name))
    if name.endswith(".md"):
      blob.upload_from_string(str(payload), content_type="text/markdown; charset=utf-8")
    else:
      blob.upload_from_string(_dumps(payload if isinstance(payload, dict) else {"value": payload}), content_type="application/json")
    saved.append(_object_path(search_run_id, name))

  usage_blob = bucket.blob(SEARCH_USAGE_OBJECT)
  existing = {}
  if usage_blob.exists():
    existing = json.loads(usage_blob.download_as_bytes().decode("utf-8"))
  merged = dict(existing)
  merged.setdefault("search_run_count", 0)
  merged["search_run_count"] = int(merged.get("search_run_count", 0) or 0) + 1
  merged["last_search_time"] = datetime.now(timezone.utc).isoformat()
  usage_blob.upload_from_string(_dumps(merged), content_type="application/json")
  return {"status": "saved", "search_run_id": search_run_id, "objects": saved}


def load_search_run(
  search_run_id: str,
  *,
  environ: Mapping[str, str] | None = None,
  storage_client: Any | None = None,
) -> dict[str, Any]:
  bucket_name = get_study_demo_bucket(environ)
  validate_study_demo_write_target(bucket_name, environ=environ)
  client = storage_client if storage_client is not None else _build_client()
  bucket = client.bucket(bucket_name)
  prefix = f"{SEARCH_RUN_PREFIX}{search_run_id}/"
  result: dict[str, Any] = {"search_run_id": search_run_id, "artifacts": {}}
  for blob in bucket.list_blobs(prefix=prefix):
    name = str(blob.name or "").rsplit("/", 1)[-1]
    if not name.endswith((".json", ".md")):
      continue
    text = blob.download_as_bytes().decode("utf-8")
    if name.endswith(".md"):
      result["artifacts"][name] = text
    else:
      result["artifacts"][name] = json.loads(text)
  return result


def list_search_history(
  *,
  environ: Mapping[str, str] | None = None,
  storage_client: Any | None = None,
  limit: int = 20,
) -> list[dict[str, Any]]:
  bucket_name = get_study_demo_bucket(environ)
  client = storage_client if storage_client is not None else _build_client()
  bucket = client.bucket(bucket_name)
  runs: dict[str, dict[str, Any]] = {}
  for blob in bucket.list_blobs(prefix=SEARCH_RUN_PREFIX):
    parts = str(blob.name or "").split("/")
    if len(parts) < 3:
      continue
    run_id = parts[1]
    if parts[-1] != "search_status.json":
      continue
    payload = json.loads(blob.download_as_bytes().decode("utf-8"))
    runs[run_id] = payload
  items = sorted(runs.values(), key=lambda item: str(item.get("saved_at", "")), reverse=True)
  return items[:limit]


def _sanitize_provider_payload(payload: Any) -> dict[str, Any]:
  if not isinstance(payload, dict):
    return {}
  cleaned = dict(payload)
  for key in list(cleaned.keys()):
    lowered = str(key).lower()
    if any(token in lowered for token in ("api_key", "authorization", "password", "secret", "smtp")):
      cleaned.pop(key, None)
  return cleaned


def _build_report_markdown(bundle: Mapping[str, Any]) -> str:
  lines = [
    "# Study Demo Search Report",
    "",
    f"- search_run_id: `{bundle.get('search_run_id', '')}`",
    f"- status: `{bundle.get('status', '')}`",
    "",
    "## Provider Status",
  ]
  for name, item in dict(bundle.get("provider_status", {}) or {}).items():
    lines.append(f"- {name}: `{dict(item).get('status', '')}`")
  lines.append("")
  lines.append("## Integrated Signals")
  integrated = dict(bundle.get("integrated_signals", {}) or {})
  lines.append(f"- count: `{integrated.get('ranked_count', 0)}`")
  return "\n".join(lines) + "\n"


def _build_client():
  from google.cloud import storage

  return storage.Client()
