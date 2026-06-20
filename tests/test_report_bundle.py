"""Tests for report bundle builder (Phase 24.0)."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.delivery.report_bundle import REPORT_CAUTION, build_report_bundle


def _write_minimal_fixture(root: Path, pub: str = "US-12565719-B2") -> None:
  ev_dir = root / "outputs" / "evidence_map_synthesis" / pub
  ev_dir.mkdir(parents=True, exist_ok=True)
  (ev_dir / "evidence_map_synthesis.md").write_text("# Evidence Map\n\nTest synthesis.", encoding="utf-8")
  (ev_dir / "evidence_map_synthesis.json").write_text(
    json.dumps({"title": "Carbon fiber patent", "evidence_gaps": ["claims_only"]}),
    encoding="utf-8",
  )


def test_report_bundle_missing_artifacts(tmp_path: Path) -> None:
  bundle = build_report_bundle("US-TEST", project_root=tmp_path)
  assert bundle.publication_number == "US-TEST"
  assert bundle.markdown
  assert "Tech Cartography Intelligence Report" in bundle.markdown


def test_report_bundle_includes_caveats(tmp_path: Path) -> None:
  _write_minimal_fixture(tmp_path)
  bundle = build_report_bundle("US-12565719-B2", project_root=tmp_path)
  assert REPORT_CAUTION.splitlines()[0] in bundle.markdown
  assert "not a final conclusion" in bundle.markdown.lower()


def test_report_bundle_with_evidence_map(tmp_path: Path) -> None:
  _write_minimal_fixture(tmp_path)
  bundle = build_report_bundle("US-12565719-B2", project_root=tmp_path)
  assert any(s.section_id == "evidence_map" for s in bundle.sections)
  assert "Evidence Map" in bundle.markdown
