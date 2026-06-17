"""Tests for build_evidence_map_synthesis CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tech_cartography.reports.project_export import save_records_csv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_ROOT / "scripts" / "build_evidence_map_synthesis.py"


def test_script_from_openalex_dir(tmp_path: Path) -> None:
  oa = tmp_path / "openalex"
  oa.mkdir()
  save_records_csv(
    [{"paper_id": "W1", "title": "PAN carbon fiber carbonization", "relevance_bucket": "strong_material_process_background", "relevance_score": 0.9}],
    oa / "selected_evidence_papers.csv",
  )
  save_records_csv(
    [{"paper_id": "W1", "title": "PAN carbon fiber carbonization"}],
    oa / "openalex_paper_records.csv",
  )
  out = tmp_path / "out"
  proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "--publication-number",
      "US-12565719-B2",
      "--openalex-dir",
      str(oa),
      "--output-dir",
      str(out),
    ],
    cwd=str(PROJECT_ROOT),
    capture_output=True,
    text=True,
    check=False,
  )
  assert proc.returncode == 0, proc.stderr
  assert (out / "evidence_map_synthesis.md").exists()
  assert (out / "evidence_map_items.csv").exists()


def test_script_missing_papers_does_not_crash(tmp_path: Path) -> None:
  out = tmp_path / "weak"
  proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "--publication-number",
      "US-9999999-B2",
      "--output-dir",
      str(out),
    ],
    cwd=str(PROJECT_ROOT),
    capture_output=True,
    text=True,
    check=False,
  )
  assert proc.returncode == 0, proc.stderr
  assert (out / "evidence_map_synthesis.json").exists()
