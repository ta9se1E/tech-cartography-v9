"""Tests for build_patent_paper_web_signal_links CLI (Phase 23.4 / 23.4.1)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tech_cartography.web_signals.linker import dry_run_link_build

from tests.test_web_signal_linker import _write_fixture

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_ROOT / "scripts" / "build_patent_paper_web_signal_links.py"


def test_dry_run_does_not_write_output(tmp_path: Path) -> None:
  _write_fixture(tmp_path)
  out_dir = tmp_path / "outputs/web_signal_links/US-12565719-B2"
  result = dry_run_link_build(
    publication_number="US-12565719-B2",
    project_root=tmp_path,
    web_signal_review_dir="outputs/web_signals/tavily_pan_carbon_fiber/review_pack",
  )
  assert result["input_counts"]["web_signals"] >= 1
  assert not out_dir.exists()


def test_missing_files_empty_pack(tmp_path: Path) -> None:
  result = dry_run_link_build(
    publication_number="US-12565719-B2",
    project_root=tmp_path,
  )
  assert result["input_counts"]["web_signals"] == 0
  assert result["artifact_checks"]["web_signal_review"] is False


def test_cli_dry_run_subprocess() -> None:
  proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "--publication-number",
      "US-12565719-B2",
      "--dry-run",
    ],
    cwd=PROJECT_ROOT,
    capture_output=True,
    text=True,
    check=False,
  )
  assert proc.returncode == 0
  payload = json.loads(proc.stdout)
  assert payload["publication_number"] == "US-12565719-B2"


def test_build_link_pack_via_linker_api(tmp_path: Path) -> None:
  _write_fixture(tmp_path)
  from tech_cartography.web_signals.linker import build_web_signal_link_pack, save_web_signal_link_pack

  pack = build_web_signal_link_pack(
    publication_number="US-12565719-B2",
    project_root=tmp_path,
    min_link_score=30,
    top_n=20,
  )
  out = tmp_path / "outputs/web_signal_links/US-12565719-B2"
  save_web_signal_link_pack(pack, out)
  assert (out / "web_signal_link_candidates.csv").exists()
  assert (out / "top_priority_web_signal_links.csv").exists()
  assert (out / "weak_web_signal_links.csv").exists()


def test_cli_calibrated_scoring_subprocess(tmp_path: Path) -> None:
  _write_fixture(tmp_path)
  out_dir = tmp_path / "outputs/web_signal_links/US-12565719-B2"
  proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "--publication-number",
      "US-12565719-B2",
      "--web-signal-review-dir",
      str(tmp_path / "outputs/web_signals/tavily_pan_carbon_fiber/review_pack"),
      "--evidence-map-dir",
      str(tmp_path / "outputs/evidence_map_synthesis/US-12565719-B2"),
      "--openalex-dir",
      str(tmp_path / "outputs/openalex_limited_execution"),
      "--output-dir",
      str(out_dir),
      "--calibrated-scoring",
    ],
    cwd=PROJECT_ROOT,
    capture_output=True,
    text=True,
    check=False,
  )
  assert proc.returncode == 0, proc.stderr
  payload = json.loads(proc.stdout)
  assert payload["calibrated_scoring"] is True
  assert (out_dir / "top_priority_web_signal_links.csv").exists()


def test_cli_dry_run_no_output_files(tmp_path: Path) -> None:
  _write_fixture(tmp_path)
  out_dir = tmp_path / "outputs/web_signal_links/US-12565719-B2"
  proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "--publication-number",
      "US-12565719-B2",
      "--dry-run",
    ],
    cwd=PROJECT_ROOT,
    capture_output=True,
    text=True,
    check=False,
  )
  assert proc.returncode == 0
  assert not out_dir.exists()


def test_cli_missing_inputs_no_crash() -> None:
  proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "--publication-number",
      "US-MISSING-PATENT",
      "--dry-run",
    ],
    cwd=PROJECT_ROOT,
    capture_output=True,
    text=True,
    check=False,
  )
  assert proc.returncode == 0
