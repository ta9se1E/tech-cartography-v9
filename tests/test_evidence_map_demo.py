"""Tests for Evidence Map demo mode loader (Phase 21.1)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from tech_cartography.ui.evidence_map_demo import (
  ARTIFACT_RELATIVE_PATHS,
  EvidenceMapDemoArtifacts,
  load_demo_evidence_map_artifacts,
  render_demo_story_cards,
  safe_read_csv,
  safe_read_json,
  safe_read_text,
)
from tech_cartography.ui.streamlit_session import (
  DEMO_PUBLICATION_NUMBER,
  DEMO_RUN_ID,
  STATE_DEMO_MODE,
  STATE_DEMO_PUBLICATION_NUMBER,
  STATE_PENDING_SELECTED_RUN_ID,
  STATE_SELECTED_RUN_ID,
  activate_evidence_map_demo_state,
)


def _write_demo_tree(root: Path) -> None:
  ev_dir = root / "outputs/evidence_map_synthesis/US-12565719-B2"
  oa_dir = root / "outputs/openalex_limited_execution"
  ev_dir.mkdir(parents=True, exist_ok=True)
  oa_dir.mkdir(parents=True, exist_ok=True)

  (ev_dir / "evidence_map_synthesis.md").write_text("# Evidence Map\n", encoding="utf-8")
  (ev_dir / "evidence_map_synthesis.json").write_text(
    json.dumps(
      {
        "publication_number": "US-12565719-B2",
        "synthesis_status": "ready",
        "claim_element_count": 3,
        "evidence_gaps": ["claims_only由来の限界"],
        "next_actions": ["専門家レビューが必要"],
      },
    ),
    encoding="utf-8",
  )
  (ev_dir / "evidence_map_items.csv").write_text(
    "claim_element,status\nCE-1,linked\n",
    encoding="utf-8",
  )
  (oa_dir / "selected_evidence_papers.csv").write_text(
    "title,doi,relevance_bucket,confidence\nPaper A,10.1/x,property_background,low\n",
    encoding="utf-8",
  )
  (oa_dir / "claim_paper_candidate_links.csv").write_text(
    "claim_element,paper_title,confidence,link_type\nCE-1,Paper A,low,supporting\n",
    encoding="utf-8",
  )
  (oa_dir / "paper_candidate_relevance_report.md").write_text("# Relevance\n", encoding="utf-8")
  (oa_dir / "openalex_execution_summary.md").write_text("# OpenAlex\n", encoding="utf-8")


def test_safe_read_text_missing(tmp_path: Path) -> None:
  text, err = safe_read_text(tmp_path / "missing.md")
  assert text is None
  assert "not found" in err


def test_safe_read_json_broken(tmp_path: Path) -> None:
  bad = tmp_path / "bad.json"
  bad.write_text("{not json", encoding="utf-8")
  data, err = safe_read_json(bad)
  assert data is None
  assert "json parse error" in err


def test_safe_read_csv_missing(tmp_path: Path) -> None:
  df, err = safe_read_csv(tmp_path / "missing.csv")
  assert df.empty
  assert "not found" in err


def test_loader_missing_files_does_not_raise(tmp_path: Path) -> None:
  artifacts = load_demo_evidence_map_artifacts(tmp_path)
  assert isinstance(artifacts, EvidenceMapDemoArtifacts)
  assert artifacts.status in {"missing", "partial", "error"}
  assert len(artifacts.missing_artifacts) == len(ARTIFACT_RELATIVE_PATHS)


def test_loader_reads_demo_tree(tmp_path: Path) -> None:
  _write_demo_tree(tmp_path)
  artifacts = load_demo_evidence_map_artifacts(tmp_path)
  assert artifacts.status == "ready"
  assert artifacts.evidence_map_md is not None
  assert artifacts.evidence_map_json is not None
  assert not artifacts.selected_papers_df.empty
  assert not artifacts.claim_paper_links_df.empty
  assert artifacts.paper_relevance_report_md is not None
  assert artifacts.openalex_execution_summary_md is not None
  assert artifacts.missing_artifacts == []


def test_loader_partial_status(tmp_path: Path) -> None:
  ev_dir = tmp_path / "outputs/evidence_map_synthesis/US-12565719-B2"
  ev_dir.mkdir(parents=True, exist_ok=True)
  (ev_dir / "evidence_map_synthesis.json").write_text('{"synthesis_status":"partial"}', encoding="utf-8")
  artifacts = load_demo_evidence_map_artifacts(tmp_path)
  assert artifacts.status == "partial"
  assert "selected_evidence_papers_csv" in artifacts.missing_artifacts


def test_render_demo_story_cards_returns_html() -> None:
  html = render_demo_story_cards()
  assert isinstance(html, str)
  assert DEMO_PUBLICATION_NUMBER in html
  assert "supporting evidence candidate" in html
  assert "FTO" in html


def test_activate_evidence_map_demo_state_uses_internal_keys_only() -> None:
  updates = activate_evidence_map_demo_state()
  assert updates[STATE_DEMO_MODE] is True
  assert updates[STATE_DEMO_PUBLICATION_NUMBER] == DEMO_PUBLICATION_NUMBER
  assert updates[STATE_SELECTED_RUN_ID] == DEMO_RUN_ID
  assert updates[STATE_PENDING_SELECTED_RUN_ID] == DEMO_RUN_ID
  assert "WIDGET_" not in str(updates)


@pytest.mark.parametrize("status", ["ready", "partial", "missing", "error"])
def test_status_values_are_valid(tmp_path: Path, status: str) -> None:
  if status == "ready":
    _write_demo_tree(tmp_path)
  elif status == "partial":
    ev_dir = tmp_path / "outputs/evidence_map_synthesis/US-12565719-B2"
    ev_dir.mkdir(parents=True, exist_ok=True)
    (ev_dir / "evidence_map_synthesis.md").write_text("# md", encoding="utf-8")
  elif status == "error":
    bad = tmp_path / "outputs/evidence_map_synthesis/US-12565719-B2"
    bad.mkdir(parents=True, exist_ok=True)
    (bad / "evidence_map_synthesis.json").write_text("{broken", encoding="utf-8")
  artifacts = load_demo_evidence_map_artifacts(tmp_path)
  assert artifacts.status in {"ready", "partial", "missing", "error"}


def test_selected_and_links_csv_columns(tmp_path: Path) -> None:
  _write_demo_tree(tmp_path)
  artifacts = load_demo_evidence_map_artifacts(tmp_path)
  assert "title" in artifacts.selected_papers_df.columns
  assert "claim_element" in artifacts.claim_paper_links_df.columns
  assert artifacts.selected_papers_df.iloc[0]["title"] == "Paper A"


def test_project_outputs_if_present() -> None:
  project_root = Path(__file__).resolve().parents[1]
  artifacts = load_demo_evidence_map_artifacts(project_root)
  if artifacts.status == "missing":
    pytest.skip("demo outputs not present in workspace")
  assert artifacts.publication_number == DEMO_PUBLICATION_NUMBER
  assert isinstance(artifacts.selected_papers_df, pd.DataFrame)
