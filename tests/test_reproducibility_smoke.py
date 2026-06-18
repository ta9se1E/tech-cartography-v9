"""Tests for Phase 22 reproducibility smoke run."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from tech_cartography.retrieval.bigquery_fulltext_availability_probe import FulltextAvailabilityProbeResult
from tech_cartography.validation.reproducibility_smoke import (
  DEFAULT_PUBLICATION_NUMBERS,
  DEMO_PUBLICATION_NUMBER,
  MARKDOWN_CAUTION,
  ReproducibilitySmokeConfig,
  build_import_command_example,
  detect_artifact_flags,
  process_patent_smoke,
  render_manual_claims_checklist,
  render_reproducibility_summary_markdown,
  resolve_patent_status,
  run_reproducibility_smoke,
  save_reproducibility_outputs,
)


def _manual_route_probe(publication_number: str, **kwargs: object) -> FulltextAvailabilityProbeResult:
  return FulltextAvailabilityProbeResult(
    publication_number=publication_number,
    has_publication_row=True,
    has_claims=False,
    has_description=False,
    probe_status="manual_route_recommended",
  )


def _claims_probe(publication_number: str, **kwargs: object) -> FulltextAvailabilityProbeResult:
  return FulltextAvailabilityProbeResult(
    publication_number=publication_number,
    has_publication_row=True,
    has_claims=True,
    has_description=False,
    probe_status="found_claims",
  )


def _error_probe(publication_number: str, **kwargs: object) -> FulltextAvailabilityProbeResult:
  raise RuntimeError("probe failed intentionally")


def test_default_publication_number_list() -> None:
  assert "US-12565719-B2" in DEFAULT_PUBLICATION_NUMBERS
  assert len(DEFAULT_PUBLICATION_NUMBERS) >= 3


def test_missing_manual_claims_blocked_status(tmp_path: Path) -> None:
  config = ReproducibilitySmokeConfig(
    publication_numbers=["US-12435451-B2"],
    output_dir=tmp_path / "out",
    project_root=tmp_path,
    skip_bigquery=False,
    dry_run=False,
  )
  result = process_patent_smoke("US-12435451-B2", config, probe_fn=_manual_route_probe)
  assert result.status == "blocked_missing_manual_claims"
  assert result.retrieval_route == "manual_route_required"


def test_existing_evidence_map_ready_for_demo(tmp_path: Path) -> None:
  pub = DEMO_PUBLICATION_NUMBER
  ev_dir = tmp_path / "outputs/evidence_map_synthesis" / pub
  oa_dir = tmp_path / "outputs/openalex_limited_execution"
  ev_dir.mkdir(parents=True)
  oa_dir.mkdir(parents=True)
  (ev_dir / "evidence_map_synthesis.md").write_text("# md", encoding="utf-8")
  (ev_dir / "evidence_map_synthesis.json").write_text("{}", encoding="utf-8")
  (oa_dir / "selected_evidence_papers.csv").write_text("title\nPaper\n", encoding="utf-8")
  (oa_dir / "claim_paper_candidate_links.csv").write_text("claim_element\nCE-1\n", encoding="utf-8")

  flags = detect_artifact_flags(tmp_path, pub)
  assert flags["evidence_map_exists"] is True

  config = ReproducibilitySmokeConfig(
    publication_numbers=[pub],
    output_dir=tmp_path / "out",
    project_root=tmp_path,
    skip_bigquery=True,
    dry_run=True,
  )
  result = process_patent_smoke(pub, config)
  assert result.status == "complete_existing_demo"


def test_per_patent_error_does_not_stop_summary(tmp_path: Path) -> None:
  config = ReproducibilitySmokeConfig(
    publication_numbers=["US-12565719-B2", "US-12435451-B2"],
    output_dir=tmp_path / "out",
    project_root=tmp_path,
    max_patents=2,
    skip_bigquery=False,
    dry_run=False,
  )

  def _mixed_probe(publication_number: str, **kwargs: object) -> FulltextAvailabilityProbeResult:
    if publication_number == "US-12435451-B2":
      raise RuntimeError("boom")
    return _manual_route_probe(publication_number, **kwargs)

  run = run_reproducibility_smoke(config, probe_fn=_mixed_probe)
  assert len(run.patents) == 2
  statuses = {p.publication_number: p.status for p in run.patents}
  assert statuses["US-12435451-B2"] == "error"
  assert statuses["US-12565719-B2"] == "blocked_missing_manual_claims"


def test_per_patent_error_recorded_in_process(tmp_path: Path) -> None:
  config = ReproducibilitySmokeConfig(
    publication_numbers=["US-12435451-B2"],
    output_dir=tmp_path / "out",
    project_root=tmp_path,
    dry_run=False,
  )
  result = process_patent_smoke("US-12435451-B2", config, probe_fn=_error_probe)
  assert result.status == "error"
  assert "probe failed intentionally" in result.error


def test_manual_claims_checklist_import_command(tmp_path: Path) -> None:
  from tech_cartography.validation.reproducibility_smoke import PatentSmokeResult

  patent = PatentSmokeResult(
    publication_number="US-12435451-B2",
    status="blocked_missing_manual_claims",
    retrieval_route="manual_route_required",
  )
  md = render_manual_claims_checklist([patent], tmp_path)
  cmd = build_import_command_example("US-12435451-B2", tmp_path)
  assert "import_manual_fulltext.py" in md
  assert "US-12435451-B2" in md
  assert "patents.google.com" in md
  assert cmd in md or "import_manual_fulltext.py" in cmd


def test_markdown_contains_required_notices(tmp_path: Path) -> None:
  from tech_cartography.validation.reproducibility_smoke import PatentSmokeResult, ReproducibilitySmokeRunResult

  config = ReproducibilitySmokeConfig(
    publication_numbers=["US-12435451-B2"],
    output_dir=tmp_path / "out",
    project_root=tmp_path,
  )
  run = ReproducibilitySmokeRunResult(
    config=config,
    patents=[
      PatentSmokeResult(publication_number="US-12435451-B2", status="blocked_missing_manual_claims"),
    ],
  )
  md = render_reproducibility_summary_markdown(run)
  assert "supporting evidence candidate" in md
  assert "FTO、侵害、有効性判断ではありません" in md
  assert "架空情報は使いません" in md
  assert MARKDOWN_CAUTION in md


def test_save_outputs_create_files(tmp_path: Path) -> None:
  from tech_cartography.validation.reproducibility_smoke import PatentSmokeResult, ReproducibilitySmokeRunResult

  config = ReproducibilitySmokeConfig(
    publication_numbers=["US-12435451-B2"],
    output_dir=tmp_path / "out",
    project_root=tmp_path,
  )
  run = ReproducibilitySmokeRunResult(
    config=config,
    patents=[
      PatentSmokeResult(
        publication_number="US-12435451-B2",
        status="blocked_missing_manual_claims",
        retrieval_route="manual_route_required",
      ),
    ],
  )
  paths = save_reproducibility_outputs(run)
  assert Path(paths["reproducibility_summary_csv"]).exists()
  assert Path(paths["reproducibility_summary_json"]).exists()
  assert Path(paths["reproducibility_summary_md"]).exists()
  assert Path(paths["next_manual_claims_checklist_md"]).exists()
  summary = json.loads(Path(paths["reproducibility_summary_json"]).read_text(encoding="utf-8"))
  assert summary["summary"][0]["status"] == "blocked_missing_manual_claims"


def test_bigquery_claims_available_status() -> None:
  from tech_cartography.validation.reproducibility_smoke import PatentSmokeResult

  row = PatentSmokeResult(
    publication_number="US-12435451-B2",
    claims_available=True,
    retrieval_route="bigquery_fulltext",
  )
  assert resolve_patent_status(row) == "bigquery_fulltext_available"
