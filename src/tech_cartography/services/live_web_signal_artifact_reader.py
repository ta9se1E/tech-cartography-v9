"""Read latest live Web Signal collection artifacts safely (Phase 25U)."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from tech_cartography.runtime.live_artifact_paths import get_live_web_signals_dir
from tech_cartography.services.live_web_signal_collector import (
  find_latest_web_signal_collection_path,
  load_web_signal_collection,
)

_SENSITIVE_PATTERN = re.compile(
  r"(smtp_password|tavily_api_key|api[_-]?key\s*[:=]|authorization|oauth|jwt)",
  re.IGNORECASE,
)

_EMPTY_SUMMARY: dict[str, Any] = {
  "artifact_exists": False,
  "artifact_path": None,
  "status": None,
  "theme_name": None,
  "queries_used": [],
  "result_count": 0,
  "web_signals": [],
  "safety_flags": {},
  "warnings": [],
}


def _scrub_value(value: Any) -> Any:
  if isinstance(value, str) and _SENSITIVE_PATTERN.search(value):
    return "[redacted]"
  if isinstance(value, dict):
    return {k: _scrub_value(v) for k, v in value.items()}
  if isinstance(value, list):
    return [_scrub_value(item) for item in value]
  return value


def _safe_signals(raw: list[Any] | None) -> list[dict[str, Any]]:
  signals: list[dict[str, Any]] = []
  for item in raw or []:
    if not isinstance(item, dict):
      continue
    signals.append(
      {
        "title": str(item.get("title") or "").strip(),
        "url": str(item.get("url") or "").strip(),
        "domain": str(item.get("domain") or "").strip(),
        "snippet": str(item.get("snippet") or item.get("summary") or "").strip(),
        "published_date": item.get("published_date"),
        "source": str(item.get("source") or "").strip(),
        "query": str(item.get("query") or "").strip(),
        "confidence_label": str(item.get("confidence_label") or "candidate").strip() or "candidate",
      },
    )
  return signals


def read_latest_web_signal_artifact_summary(
  output_root: Path | str,
) -> dict[str, Any]:
  """Return safe summary of latest collection artifact. Never calls external APIs."""
  path = find_latest_web_signal_collection_path(output_root)
  if path is None:
    return dict(_EMPTY_SUMMARY)

  data = load_web_signal_collection(path)
  if not data:
    return {
      **_EMPTY_SUMMARY,
      "artifact_path": str(path),
      "warnings": ["artifact_corrupt_or_unreadable"],
    }

  scrubbed = _scrub_value(data)
  if not isinstance(scrubbed, dict):
    return {
      **_EMPTY_SUMMARY,
      "artifact_path": str(path),
      "warnings": ["artifact_invalid_shape"],
    }

  return {
    "artifact_exists": True,
    "artifact_path": str(path),
    "status": scrubbed.get("status"),
    "theme_name": scrubbed.get("theme_name"),
    "queries_used": list(scrubbed.get("queries_used") or []),
    "result_count": int(scrubbed.get("result_count") or len(scrubbed.get("web_signals") or [])),
    "web_signals": _safe_signals(scrubbed.get("web_signals")),
    "safety_flags": dict(scrubbed.get("safety_flags") or {}),
    "warnings": [],
    "run_id": scrubbed.get("run_id"),
    "timestamp": scrubbed.get("timestamp"),
  }


def describe_latest_web_signal_artifact(output_root: Path | str) -> dict[str, Any]:
  summary = read_latest_web_signal_artifact_summary(output_root)
  return {
    "latest_web_signal_artifact_exists": bool(summary.get("artifact_exists")),
    "latest_web_signal_artifact_path": summary.get("artifact_path"),
    "latest_web_signal_result_count": int(summary.get("result_count") or 0),
    "latest_web_signal_artifact_status": summary.get("status"),
    "summary": summary,
  }
