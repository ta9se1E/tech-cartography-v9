"""Tests for Evidence Map demo mode loader and display helpers (Phase 21.1–21.2)."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from tech_cartography.ui.evidence_map_demo import (
  ARTIFACT_RELATIVE_PATHS,
  CLAIM_LINKS_NOTICE,
  EVIDENCE_MAP_READING_GUIDE,
  EXECUTIVE_SUMMARY_TEXT,
  FIXED_EVIDENCE_GAPS,
  FIXED_NEXT_ACTIONS,
  MARKET_SIGNAL_NOTICE,
  SELECTED_PAPERS_NOTICE,
  EvidenceMapDemoArtifacts,
  build_evidence_map_summary_metrics,
  get_fixed_evidence_gaps,
  get_fixed_next_actions,
  load_demo_evidence_map_artifacts,
  prepare_claim_paper_links_display_df,
  prepare_selected_papers_display_df,
  render_demo_story_cards,
  render_executive_summary,
  render_three_minute_demo_guide,
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


def _sample_artifacts(**overrides: object) -> EvidenceMapDemoArtifacts:
  defaults = dict(
    publication_number=DEMO_PUBLICATION_NUMBER,
    status="ready",
    base_dir=Path("."),
    evidence_map_md="# md",
    evidence_map_json={"synthesis_status": "ready"},
    evidence_items_df=pd.DataFrame(),
    selected_papers_df=pd.DataFrame([{"title": "Paper A"}]),
    claim_paper_links_df=pd.DataFrame([{"claim_element": "CE-1"}]),
    paper_relevance_report_md=None,
    openalex_execution_summary_md=None,
    missing_artifacts=[],
    errors=[],
  )
  defaults.update(overrides)
  return EvidenceMapDemoArtifacts(**defaults)


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


def test_summary_metrics_reflect_dataframe_counts() -> None:
  artifacts = _sample_artifacts(
    selected_papers_df=pd.DataFrame([{"title": "A"}, {"title": "B"}]),
    claim_paper_links_df=pd.DataFrame([{"claim_element": "CE-1"}]),
    status="partial",
  )
  metrics = build_evidence_map_summary_metrics(artifacts)
  labels = {m["label"]: m["value"] for m in metrics}
  assert labels["Deep Dive Patent"] == DEMO_PUBLICATION_NUMBER
  assert labels["Selected Evidence Papers"] == "2"
  assert labels["Claim × Paper Links"] == "1"
  assert labels["Evidence Level"] == "claims_only / weak-to-medium"
  assert labels["Status"] == "Evidence Map partial"


def test_prepare_selected_papers_display_missing_columns() -> None:
  df = pd.DataFrame([{"title": "Long " * 40, "doi": "10.1234/example"}])
  display = prepare_selected_papers_display_df(df)
  assert list(display.columns) == [
    "title",
    "doi",
    "source",
    "publication_year",
    "cited_by_count",
    "relevance_bucket",
    "evidence_role",
    "confidence",
  ]
  assert display.iloc[0]["doi"] == "10.1234/example"
  assert display.iloc[0]["source"] == "not available"
  assert display.iloc[0]["confidence"] == "low / weak"
  assert display.iloc[0]["title"].endswith("…")


def test_prepare_selected_papers_display_nan_and_empty() -> None:
  df = pd.DataFrame(
    [
      {
        "title": "Paper",
        "doi": None,
        "cited_by_count": float("nan"),
        "relevance_bucket": "",
      },
    ],
  )
  display = prepare_selected_papers_display_df(df)
  assert display.iloc[0]["doi"] == "not available"
  assert display.iloc[0]["cited_by_count"] == "not available"
  assert display.iloc[0]["relevance_bucket"] == "not available"

  empty = prepare_selected_papers_display_df(pd.DataFrame())
  assert empty.empty
  assert list(empty.columns)


def test_prepare_claim_links_display_fallback_and_defaults() -> None:
  df = pd.DataFrame(
    [
      {
        "claim_element": "CE-1",
        "claim_element_text": "a carbon fiber",
        "title": "Fallback Title",
        "link_type": "fallback",
        "confidence": "",
      },
      {
        "claim_element": "CE-2",
        "paper_title": "Paper B",
        "confidence": "medium",
        "link_type": "supporting",
      },
    ],
  )
  display = prepare_claim_paper_links_display_df(df)
  assert display.iloc[0]["paper_display"] == "Fallback Title"
  assert display.iloc[0]["confidence"] == "low / weak"
  assert "弱い対応" in display.iloc[0]["link_type"]
  assert display.iloc[1]["paper_display"] == "Paper B"
  assert display.iloc[1]["confidence"] == "medium"

  empty = prepare_claim_paper_links_display_df(None)
  assert empty.empty


def test_fixed_evidence_gaps_and_next_actions() -> None:
  gaps = get_fixed_evidence_gaps()
  actions = get_fixed_next_actions()
  assert gaps == list(FIXED_EVIDENCE_GAPS)
  assert actions == list(FIXED_NEXT_ACTIONS)
  assert "BigQuery fulltextでclaims/descriptionが取得できなかった" in gaps
  assert "Weekly Digest Previewに反映する" in actions

  merged_gaps = get_fixed_evidence_gaps({"evidence_gaps": ["追加ギャップ"]})
  assert "追加ギャップ" in merged_gaps
  assert len(merged_gaps) >= len(FIXED_EVIDENCE_GAPS)


def test_demo_copy_contains_required_notices() -> None:
  html = render_demo_story_cards(_sample_artifacts())
  guide = render_three_minute_demo_guide()
  executive = render_executive_summary()
  assert "supporting evidence candidate" in html
  assert "FTO" in html
  assert "Synthetic demo signal" in html
  assert "3分デモの見方" in guide
  assert "supporting evidence candidate" in EXECUTIVE_SUMMARY_TEXT
  assert "FTO、侵害、有効性判断ではありません" in EXECUTIVE_SUMMARY_TEXT
  assert "supporting evidence candidate" in executive
  assert "supporting evidence candidate" in EVIDENCE_MAP_READING_GUIDE
  assert "supporting evidence candidate" in SELECTED_PAPERS_NOTICE
  assert "claims_only" in CLAIM_LINKS_NOTICE
  assert "Synthetic demo signal" in MARKET_SIGNAL_NOTICE


def test_render_demo_story_cards_returns_html() -> None:
  html = render_demo_story_cards(_sample_artifacts())
  assert isinstance(html, str)
  assert DEMO_PUBLICATION_NUMBER in html
  assert "Evidence Map ready" in html


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


def test_demo_script_doc_mentions_synthetic_signal() -> None:
  path = Path("docs/demo_script_phase21.md")
  assert path.exists()
  text = path.read_text(encoding="utf-8")
  assert "Synthetic demo signal" in text
  assert "supporting evidence candidate" in text
