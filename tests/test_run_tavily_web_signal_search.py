"""Tests for Tavily Web Signal search CLI (Phase 23.1)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from tech_cartography.web_signals.tavily_runner import TavilyRunConfig, run_tavily_web_signal_pipeline

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_ROOT / "scripts" / "run_tavily_web_signal_search.py"


def test_dry_run_does_not_call_tavily() -> None:
  with patch("tech_cartography.web_signals.tavily_runner.run_tavily_search") as mock_search:
    result = run_tavily_web_signal_pipeline(
      TavilyRunConfig(
        topic="PAN carbon fiber",
        categories=["national_project"],
        languages=["en"],
        max_queries=2,
        dry_run=True,
      ),
    )
  mock_search.assert_not_called()
  assert result["status"] == "dry_run"
  assert result["query_count"] >= 1


def test_plan_only_does_not_call_tavily(tmp_path: Path) -> None:
  with patch("tech_cartography.web_signals.tavily_runner.run_tavily_search") as mock_search:
    result = run_tavily_web_signal_pipeline(
      TavilyRunConfig(
        topic="PAN carbon fiber",
        categories=["ir_disclosure"],
        languages=["en"],
        max_queries=2,
        output_dir=str(tmp_path / "batch"),
        plan_only=True,
        execute_tavily=False,
      ),
    )
  mock_search.assert_not_called()
  assert result["status"] == "plan_only"
  assert (tmp_path / "batch" / "web_signal_queries.json").exists()
  assert (tmp_path / "batch" / "web_signal_summary.md").exists()
  summary = (tmp_path / "batch" / "web_signal_summary.md").read_text(encoding="utf-8")
  assert "signal candidates" in summary
  assert "FTO" in summary
  assert "Tavily results" in summary


def test_execute_without_api_key_blocks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv("TAVILY_API_KEY", raising=False)
  with patch("tech_cartography.web_signals.tavily_runner.run_tavily_search") as mock_search:
    result = run_tavily_web_signal_pipeline(
      TavilyRunConfig(
        topic="PAN carbon fiber",
        categories=["company"],
        languages=["en"],
        max_queries=1,
        output_dir=str(tmp_path / "blocked"),
        plan_only=False,
        execute_tavily=True,
      ),
    )
  mock_search.assert_not_called()
  assert result["status"] == "blocked_missing_api_key"


def test_cli_dry_run_subprocess() -> None:
  proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "--topic",
      "PAN carbon fiber",
      "--categories",
      "national_project",
      "--max-queries",
      "2",
      "--dry-run",
    ],
    cwd=PROJECT_ROOT,
    capture_output=True,
    text=True,
    check=False,
  )
  assert proc.returncode == 0
  payload = json.loads(proc.stdout)
  assert payload["status"] == "dry_run"


def test_output_files_on_plan_only(tmp_path: Path) -> None:
  out = tmp_path / "plan_batch"
  run_tavily_web_signal_pipeline(
    TavilyRunConfig(
      topic="PAN carbon fiber",
      categories=["money", "ir_disclosure"],
      languages=["ja"],
      max_queries=3,
      output_dir=str(out),
      plan_only=True,
    ),
  )
  expected = [
    "web_signal_queries.json",
    "tavily_search_raw.json",
    "tavily_extract_raw.json",
    "web_signals.json",
    "web_signals.csv",
    "web_signal_summary.md",
  ]
  for name in expected:
    assert (out / name).exists(), name
