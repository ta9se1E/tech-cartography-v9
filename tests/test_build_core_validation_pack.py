"""Tests for build_core_validation_pack CLI (Phase 24.4)."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from tech_cartography.reports.project_export import save_records_csv
from tech_cartography.web_signals.linker import LINK_CSV_COLUMNS

PROJECT_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = PROJECT_ROOT / "scripts" / "build_core_validation_pack.py"


def _minimal_fixture(root: Path) -> None:
  pub = "US-12565719-B2"
  link_dir = root / "outputs" / "web_signal_links" / pub
  ev_dir = root / "outputs" / "evidence_map_synthesis" / pub
  link_dir.mkdir(parents=True, exist_ok=True)
  ev_dir.mkdir(parents=True, exist_ok=True)
  base = {col: "" for col in LINK_CSV_COLUMNS}
  base.update({"link_id": "1", "publication_number": pub, "link_score": 70, "link_type": "project_context_match"})
  save_records_csv([base, {**base, "link_id": "2", "link_score": 45}], link_dir / "web_signal_link_candidates.csv")
  (ev_dir / "evidence_map_synthesis.md").write_text("# m", encoding="utf-8")
  (ev_dir / "evidence_map_synthesis.json").write_text("{}", encoding="utf-8")
  manual = root / "inputs" / "manual"
  manual.mkdir(parents=True, exist_ok=True)
  (manual / f"{pub}_claims.txt").write_text("c", encoding="utf-8")
  oa = root / "outputs" / "openalex_limited_execution"
  oa.mkdir(parents=True, exist_ok=True)
  save_records_csv([{"publication_number": pub, "title": "p"}], oa / "selected_evidence_papers.csv")
  save_records_csv([{"publication_number": pub}], oa / "claim_paper_candidate_links.csv")


def test_build_core_validation_pack_cli(tmp_path: Path) -> None:
  _minimal_fixture(tmp_path)
  out = tmp_path / "outputs" / "validation" / "core_validation"
  proc = subprocess.run(
    [
      sys.executable,
      str(SCRIPT),
      "--publication-numbers",
      "US-12565719-B2",
      "US-12435451-B2",
      "--output-dir",
      str(out),
      "--project-root",
      str(tmp_path),
    ],
    cwd=PROJECT_ROOT,
    capture_output=True,
    text=True,
    check=False,
  )
  assert proc.returncode == 0
  payload = json.loads(proc.stdout)
  assert payload["complete_count"] >= 1
  assert (out / "freeze_readiness_judgement.md").exists()
  assert (out / "readme_patch_notes.md").exists()
  assert (out / "reproducibility_status_report.csv").exists()
