"""Tests for import_manual_fulltext CLI (Phase 18B)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_import_from_claims_file(tmp_path) -> None:
  claims_file = tmp_path / "claims.txt"
  claims_file.write_text("1. A carbon fiber comprising ...\n2. The carbon fiber according to claim 1.", encoding="utf-8")
  output_dir = tmp_path / "manual_inputs"
  cmd = [
    sys.executable,
    "scripts/import_manual_fulltext.py",
    "--publication-number",
    "US-12565719-B2",
    "--source-url",
    "https://patents.google.com/patent/US12565719B2",
    "--claims-file",
    str(claims_file),
    "--input-route",
    "manual_google_patents",
    "--entered-by",
    "tester",
    "--output-dir",
    str(output_dir),
  ]
  result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=Path.cwd())
  payload = json.loads(result.stdout)
  assert payload["validation_status"] == "valid_claims_only"
  saved = output_dir / "US-12565719-B2.json"
  assert saved.exists()


def test_validate_only_does_not_write_file(tmp_path) -> None:
  output_dir = tmp_path / "manual_inputs"
  cmd = [
    sys.executable,
    "scripts/import_manual_fulltext.py",
    "--publication-number",
    "US-12565719-B2",
    "--claims-text",
    "1. A fiber.",
    "--validate-only",
    "--output-dir",
    str(output_dir),
  ]
  result = subprocess.run(cmd, capture_output=True, text=True, check=True, cwd=Path.cwd())
  payload = json.loads(result.stdout)
  assert payload["validation_status"] == "valid_claims_only"
  assert not list(output_dir.glob("*.json"))
