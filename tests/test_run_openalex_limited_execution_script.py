"""Tests for run_openalex_limited_execution CLI script."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

from tech_cartography.evidence.claims_based_paper_query_builder import build_claims_paper_query_candidates
from tech_cartography.evidence.openalex_limited_executor import (
  OpenAlexExecutionConfig,
  execute_openalex_limited,
  save_openalex_limited_artifacts,
)
from tech_cartography.reports.project_export import load_records_csv, save_records_csv


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_ROOT / "scripts" / "run_openalex_limited_execution.py"


def _manual_record() -> dict:
  return {
    "publication_number": "US-12565719-B2",
    "title": "Carbon fiber",
    "retrieval_status": "manual_claims_loaded",
    "claims": (
      "1. A carbon fiber comprising PAN precursor fibers subjected to oxidation "
      "and carbonization, wherein the carbon fiber has tensile strength and elastic modulus."
    ),
  }


@pytest.fixture
def query_candidates_csv(tmp_path: Path) -> Path:
  rows = build_claims_paper_query_candidates(_manual_record(), min_queries=5, max_queries=10)
  path = tmp_path / "paper_query_candidates_from_claims.csv"
  save_records_csv(rows, path)
  return path


@pytest.fixture
def manual_input_json(tmp_path: Path) -> Path:
  path = tmp_path / "US-12565719-B2.json"
  path.write_text(
    json.dumps(
      {
        "publication_number": "US-12565719-B2",
        "claims_text": _manual_record()["claims"],
      },
      ensure_ascii=False,
    ),
    encoding="utf-8",
  )
  return path


def test_plan_only_outputs_selected_queries(
  tmp_path: Path,
  query_candidates_csv: Path,
  manual_input_json: Path,
) -> None:
  out = tmp_path / "out"
  proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "--manual-input",
      str(manual_input_json),
      "--query-candidates",
      str(query_candidates_csv),
      "--output-dir",
      str(out),
      "--max-queries",
      "3",
    ],
    cwd=str(PROJECT_ROOT),
    capture_output=True,
    text=True,
    check=False,
  )
  assert proc.returncode == 0, proc.stderr
  assert (out / "openalex_selected_queries.csv").exists()
  assert (out / "openalex_execution_summary.json").exists()
  assert (out / "openalex_execution_summary.md").exists()
  summary = json.loads((out / "openalex_execution_summary.json").read_text(encoding="utf-8"))
  assert summary["mode"] == "plan_only"
  assert len(summary.get("selected_queries", [])) <= 3
  md = (out / "openalex_execution_summary.md").read_text(encoding="utf-8")
  assert "$" not in md


def test_execute_mock_produces_paper_records(
  tmp_path: Path,
  query_candidates_csv: Path,
) -> None:
  out = tmp_path / "execute_out"
  candidates = load_records_csv(str(query_candidates_csv))

  def _fake_search(query: str, _cfg) -> dict:
    return {
      "status": "ok",
      "works": [
        {
          "id": "https://openalex.org/W-test",
          "display_name": f"Carbon fiber study {query[:12]}",
          "abstract_inverted_index": {"carbon": [0], "fiber": [1]},
        },
      ],
    }

  cfg = OpenAlexExecutionConfig(
    execute_openalex=True,
    max_queries=2,
    max_results_per_query=5,
    allow_low_confidence_queries=True,
    output_dir=str(out),
  )
  with patch("tech_cartography.evidence.openalex_limited_executor.search_openalex", side_effect=_fake_search):
    result = execute_openalex_limited(candidates, cfg, publication_number="US-12565719-B2")
  paths = save_openalex_limited_artifacts(result, out)
  assert paths["openalex_paper_records_csv"]
  assert (out / "openalex_paper_records.json").exists()
  assert (out / "openalex_source_quality.csv").exists()
  assert (out / "openalex_errors.json").exists()
  assert result["total_paper_records"] >= 1
