"""Tests for live web signal artifact reader (Phase 25U)."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.runtime.live_artifact_paths import ensure_live_artifact_dirs
from tech_cartography.services.live_web_signal_artifact_reader import (
  read_latest_web_signal_artifact_summary,
)


def test_empty_when_no_artifact(tmp_path: Path) -> None:
  summary = read_latest_web_signal_artifact_summary(tmp_path)
  assert summary["artifact_exists"] is False
  assert summary["result_count"] == 0


def test_reads_latest_collection_artifact(tmp_path: Path) -> None:
  ensure_live_artifact_dirs(tmp_path)
  out_dir = tmp_path / "outputs" / "live_web_signals"
  payload = {
    "status": "success",
    "theme_name": "Carbon Fiber Intelligence",
    "queries_used": ["PAN precursor"],
    "result_count": 1,
    "web_signals": [
      {
        "title": "Candidate A",
        "url": "https://example.com/a",
        "domain": "example.com",
        "snippet": "text",
        "confidence_label": "candidate",
        "query": "PAN precursor",
      },
    ],
    "safety_flags": {"candidate_information_only": True},
  }
  path = out_dir / "live_web_signal_collection_success_20260624.json"
  path.write_text(json.dumps(payload), encoding="utf-8")
  summary = read_latest_web_signal_artifact_summary(tmp_path)
  assert summary["artifact_exists"] is True
  assert summary["theme_name"] == "Carbon Fiber Intelligence"
  assert summary["result_count"] == 1
  assert "TAVILY_API_KEY" not in json.dumps(summary)


def test_corrupt_json_returns_warning(tmp_path: Path) -> None:
  ensure_live_artifact_dirs(tmp_path)
  out_dir = tmp_path / "outputs" / "live_web_signals"
  path = out_dir / "live_web_signal_collection_success_bad.json"
  path.write_text("{not-json", encoding="utf-8")
  summary = read_latest_web_signal_artifact_summary(tmp_path)
  assert "artifact_corrupt_or_unreadable" in (summary.get("warnings") or [])
