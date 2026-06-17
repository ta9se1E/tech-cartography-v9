"""Tests for build_claims_paper_query_plan CLI (Phase 18C/18D)."""

from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

from tech_cartography.manual.manual_fulltext_input_schema import ManualFulltextInput, save_manual_fulltext_input


def test_build_plan_from_manual_input(tmp_path) -> None:
  manual_dir = tmp_path / "manual_inputs"
  out_dir = tmp_path / "out"
  save_manual_fulltext_input(
    ManualFulltextInput(
      publication_number="US-12565719-B2",
      claims_text=(
        "1. A carbon fiber comprising a PAN precursor subjected to oxidation and carbonization, "
        "wherein the carbon fiber has tensile strength of at least 5 GPa and elastic modulus."
      ),
      input_route="manual_google_patents",
    ),
    manual_dir,
  )
  manual_json = manual_dir / "US-12565719-B2.json"
  cmd = [
    sys.executable,
    "scripts/build_claims_paper_query_plan.py",
    "--manual-input",
    str(manual_json),
    "--output-dir",
    str(out_dir),
    "--min-queries",
    "5",
    "--max-queries",
    "10",
    "--quality-report",
  ]
  result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=Path.cwd())
  payload = json.loads(result.stdout)
  assert payload["total_queries"] >= 5
  assert payload["plan_ready_for_openalex"] is True
  assert (out_dir / "paper_query_candidates_from_claims.csv").exists()
  assert (out_dir / "paper_query_quality_report.md").exists()
  assert (out_dir / "paper_query_quality_summary.json").exists()


def test_build_plan_from_run_dir(tmp_path) -> None:
  stage_dir = tmp_path / "stages" / "evidence_validation" / "20260617_120000"
  stage_dir.mkdir(parents=True)
  readiness = {
    "classified_records": [
      {
        "publication_number": "US-12565719-B2",
        "title": "Carbon fiber",
        "retrieval_status": "manual_claims_loaded",
        "claims": "1. PAN precursor oxidation carbonization carbon fiber tensile strength modulus.",
      },
    ],
  }
  (stage_dir / "fulltext_readiness.json").write_text(json.dumps(readiness), encoding="utf-8")
  out_override = tmp_path / "plan_out"
  cmd = [
    sys.executable,
    "scripts/build_claims_paper_query_plan.py",
    "--run-dir",
    str(tmp_path),
    "--publication-number",
    "US-12565719-B2",
    "--output-dir",
    str(out_override),
    "--min-queries",
    "5",
    "--max-queries",
    "10",
  ]
  subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=Path.cwd())
  assert (out_override / "claims_paper_query_plan.md").exists()


def test_fail_if_not_ready_exits_nonzero(tmp_path, monkeypatch) -> None:
  script_path = Path.cwd() / "scripts" / "build_claims_paper_query_plan.py"
  spec = importlib.util.spec_from_file_location("build_claims_paper_query_plan", script_path)
  cli = importlib.util.module_from_spec(spec)
  assert spec.loader is not None
  spec.loader.exec_module(cli)

  dummy = tmp_path / "US-X.json"
  dummy.write_text(
    json.dumps({"publication_number": "US-X", "claims_text": "1. A carbon fiber with PAN."}),
    encoding="utf-8",
  )

  monkeypatch.setattr(
    cli,
    "build_claims_paper_query_plan",
    lambda *args, **kwargs: {
      "total_queries": 1,
      "plan_ready_for_openalex": False,
      "openalex_mode": "plan_only",
      "confidence_levels": ["low"],
      "quality_summary": {"plan_ready_for_openalex": False},
      "queries": [],
    },
  )
  monkeypatch.setattr(cli, "save_claims_paper_query_artifacts", lambda *args, **kwargs: {})
  monkeypatch.setattr(
    sys,
    "argv",
    [
      "build_claims_paper_query_plan.py",
      "--manual-input",
      str(dummy),
      "--output-dir",
      str(tmp_path / "out"),
      "--fail-if-not-ready",
    ],
  )
  assert cli.main() == 2
