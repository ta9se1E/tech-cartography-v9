"""Tests for filter_openalex_paper_candidates CLI."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from tech_cartography.reports.project_export import save_records_csv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_ROOT / "scripts" / "filter_openalex_paper_candidates.py"


def _sample_papers() -> list[dict]:
  return [
    {
      "paper_id": "W1",
      "title": "PAN precursor oxidation carbonization for carbon fiber",
      "abstract": "polyacrylonitrile stabilization heat treatment",
    },
    {
      "paper_id": "W2",
      "title": "Natural Fiber Reinforced Composites review",
      "abstract": "hemp fiber general composite",
    },
    {
      "paper_id": "W3",
      "title": "Tensile strength and elastic modulus of carbon fiber",
      "abstract": "mechanical properties",
    },
  ]


def test_script_creates_relevance_csv(tmp_path: Path) -> None:
  paper_csv = tmp_path / "openalex_paper_records.csv"
  save_records_csv(_sample_papers(), paper_csv)
  out = tmp_path / "filtered"
  proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "--paper-records",
      str(paper_csv),
      "--output-dir",
      str(out),
      "--top-n",
      "5",
    ],
    cwd=str(PROJECT_ROOT),
    capture_output=True,
    text=True,
    check=False,
  )
  assert proc.returncode == 0, proc.stderr
  assert (out / "paper_candidate_relevance.csv").exists()
  assert (out / "selected_evidence_papers.csv").exists()
  assert (out / "paper_candidate_relevance_report.md").exists()


def test_script_works_without_claim_elements(tmp_path: Path) -> None:
  paper_csv = tmp_path / "papers.csv"
  save_records_csv(_sample_papers(), paper_csv)
  out = tmp_path / "out"
  proc = subprocess.run(
    [sys.executable, str(SCRIPT), "--paper-records", str(paper_csv), "--output-dir", str(out)],
    cwd=str(PROJECT_ROOT),
    capture_output=True,
    text=True,
    check=False,
  )
  assert proc.returncode == 0, proc.stderr
  assert (out / "selected_evidence_papers.csv").exists()
