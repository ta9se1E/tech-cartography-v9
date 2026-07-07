"""Tests for final browser acceptance fixes (Stage C5B-5D)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

from services_v9.ranking_match_evidence import (
  build_field_aware_match_evidence,
  build_human_ranking_summary,
  build_ranking_basis_payload,
  count_false_field_matches,
  simple_internal_token_count,
  validate_match_field,
)
from services_v9.research_value_fact_sheet import build_signal_fact_sheet
from services_v9.research_value_pipeline import build_research_value_top3
from services_v9.research_value_theme_axes import build_theme_axes
from services_v9.run_baseline_state import resolve_snapshot_state
from services_v9.search_improvement_eligibility import evaluate_proposal_eligibility, reject_internal_token
from services_v9.study_demo_review_proposals import generate_review_proposals
from ui_v9.study_demo_simple_tabs_ui import _baseline_save_controls_visible

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "study_demo_research_value_samples.json"
ROOT = Path(__file__).resolve().parents[1]


def _load_fixture() -> dict:
  return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _third_signal() -> dict:
  fx = _load_fixture()
  bundle = build_research_value_top3(fx["signals"], fx["theme"], limit=3)
  return dict(bundle["items"][2]["signal"])


class TestRankingEvidence:
  def test_third_title_has_no_carbon_fiber(self) -> None:
    signal = _third_signal()
    assert "carbon fiber" not in signal["title"].lower()

  def test_carbon_fiber_is_abstract_evidence(self) -> None:
    evidence = build_field_aware_match_evidence(_third_signal())
    assert "carbon fiber" in [item["term"] for item in evidence if item["field"] == "abstract"]
    assert "carbon fiber" not in [item["term"] for item in evidence if item["field"] == "title"]

  def test_aqueous_and_polyurethane_title_evidence(self) -> None:
    evidence = build_field_aware_match_evidence(_third_signal())
    title_terms = {item["term"] for item in evidence if item["field"] == "title"}
    assert "aqueous" in title_terms
    assert "polyurethane" in title_terms

  def test_false_title_match_zero(self) -> None:
    evidence = build_field_aware_match_evidence(_third_signal())
    counts = count_false_field_matches(evidence, _third_signal())
    assert counts["false_title_match_count"] == 0

  def test_false_abstract_match_zero(self) -> None:
    evidence = build_field_aware_match_evidence(_third_signal())
    counts = count_false_field_matches(evidence, _third_signal())
    assert counts["false_abstract_match_count"] == 0

  def test_human_summary_field_aware(self) -> None:
    signal = _third_signal()
    evidence = build_field_aware_match_evidence(signal)
    summary = build_human_ranking_summary(evidence, matched_theme_axes=["composition", "material"], tier="A")
    assert "タイトルでは" in summary
    assert "タイトルにcarbon fiber" not in summary
    assert "概要では" in summary

  def test_simple_ranking_basis_has_no_raw_tokens(self) -> None:
    signal = _third_signal()
    fact_sheet = build_signal_fact_sheet(signal, build_theme_axes(_load_fixture()["theme"]))
    basis = build_ranking_basis_payload(signal, fact_sheet)
    assert simple_internal_token_count(basis) == 0
    assert "sizing:title" not in "\n".join(basis.get("human_labels", []))

  def test_advanced_raw_evidence_preserved(self) -> None:
    signal = _third_signal()
    fact_sheet = build_signal_fact_sheet(signal, build_theme_axes(_load_fixture()["theme"]))
    basis = build_ranking_basis_payload(signal, fact_sheet)
    raw_values = [str(item.get("value", "")) for item in basis.get("raw_evidence", [])]
    assert any("sizing:title" in value for value in raw_values)

  def test_top1_top2_field_validation(self) -> None:
    fx = _load_fixture()
    bundle = build_research_value_top3(fx["signals"], fx["theme"], limit=3)
    for item in bundle["items"][:2]:
      signal = dict(item["signal"])
      evidence = build_field_aware_match_evidence(signal)
      counts = count_false_field_matches(evidence, signal)
      assert counts["false_title_match_count"] == 0
      assert counts["false_abstract_match_count"] == 0

  def test_validate_match_field(self) -> None:
    title = "aqueous polyurethane sizing agent"
    summary = "carbon fiber tow"
    assert validate_match_field("aqueous", "title", title, summary)
    assert validate_match_field("carbon fiber", "abstract", title, summary)
    assert not validate_match_field("carbon fiber", "title", title, summary)


class TestProposalUi:
  def test_review_zero_ineligible(self) -> None:
    result = evaluate_proposal_eligibility([])
    assert result["eligible"] is False

  def test_monitoring_profile_insufficient_message(self) -> None:
    source = (ROOT / "ui_v9/study_demo_simple_tabs_ui.py").read_text(encoding="utf-8")
    assert "検索改善案" in source
    assert "evaluate_proposal_eligibility" in source
    assert "現在の保存済みレビュー" in source

  def test_sizing_title_not_shown_in_simple_profile(self) -> None:
    source = (ROOT / "ui_v9/study_demo_simple_tabs_ui.py").read_text(encoding="utf-8")
    assert "simple_suggestions" not in source
    assert "watch_profile_suggestion_label_ja" not in source

  def test_generic_composite_proposal_not_used(self) -> None:
    proposals = generate_review_proposals(
      reviews=[],
      signals=_load_fixture()["signals"],
      source_run_id=_load_fixture()["search_run_id"],
    )
    values = [str(item.get("proposed_value", "")) for item in proposals.get("proposals", [])]
    assert "generic composite" not in values

  def test_provider_priority_hidden_when_ineligible(self) -> None:
    proposals = generate_review_proposals(
      reviews=[],
      signals=_load_fixture()["signals"],
      source_run_id=_load_fixture()["search_run_id"],
    )
    assert proposals["summary"]["eligible"] is False
    assert proposals["summary"]["proposal_count"] == 0

  def test_action_buttons_disabled_when_eligible_fixture(self) -> None:
    reviews = [
      {"signal_id": "a", "decision": "accept", "reviewed": True, "reason_codes": ["direct_evidence"]},
      {"signal_id": "b", "decision": "reject", "reviewed": True, "reason_codes": ["off_topic"]},
      {"signal_id": "c", "decision": "hold", "reviewed": True, "reason_codes": ["unclear_relevance"]},
    ]
    proposals = generate_review_proposals(
      reviews=reviews,
      signals=_load_fixture()["signals"],
      source_run_id=_load_fixture()["search_run_id"],
    )
    assert proposals["summary"]["eligible"] is True

  def test_raw_token_normalize(self) -> None:
    assert reject_internal_token("sizing:title") is True
    assert reject_internal_token("aqueous polyurethane") is False


class TestBaselineSavedUi:
  def test_saved_snapshot_state(self) -> None:
    fx = _load_fixture()
    state = resolve_snapshot_state(
      snapshots=fx.get("snapshots", []),
      current_run_id=fx["active_context"]["active_search_run_id"],
    )
    assert state == "saved"

  def test_saved_weekly_message(self) -> None:
    from services_v9.run_baseline_state import build_baseline_summary

    source = (ROOT / "ui_v9/study_demo_simple_tabs_ui.py").read_text(encoding="utf-8")
    summary = build_baseline_summary({"state": "initial_baseline", "snapshot_state": "saved"})
    assert "保存状態" in source
    assert "初回ベースラインを保存しました" in summary["headline"]

  def test_checkbox_hidden_when_saved(self) -> None:
    weekly_state = {"state": "initial_baseline", "snapshot_state": "saved"}
    assert _baseline_save_controls_visible(weekly_state) is False

  def test_save_button_hidden_when_saved(self) -> None:
    source = (ROOT / "ui_v9/study_demo_simple_tabs_ui.py").read_text(encoding="utf-8")
    assert "_baseline_save_controls_visible" in source

  def test_unsaved_fixture_shows_button(self) -> None:
    weekly_state = {"state": "initial_baseline", "snapshot_state": "unsaved"}
    assert _baseline_save_controls_visible(weekly_state) is True

  def test_saved_unsaved_state_separated(self) -> None:
    saved = resolve_snapshot_state(
      snapshots=[{"source_run_id": "run-a"}],
      current_run_id="run-a",
    )
    unsaved = resolve_snapshot_state(snapshots=[], current_run_id="run-a")
    assert saved == "saved"
    assert unsaved == "unsaved"

  def test_weekly_tab_saved_state_render(self) -> None:
    from ui_v9.study_demo_simple_tabs_ui import render_simple_weekly_tab

    weekly_state = {"state": "initial_baseline", "snapshot_state": "saved", "current_count": 15, "priority_count": 3}
    source_info = {
      "study_demo_downstream": {"weekly_state": weekly_state},
      "canonical_metrics": {"integrated_count": 15},
    }
    with patch("ui_v9.study_demo_simple_tabs_ui.st") as mock_st:
      mock_st.checkbox = MagicMock()
      mock_st.button = MagicMock(return_value=False)
      render_simple_weekly_tab(source_info=source_info)
      mock_st.checkbox.assert_not_called()
      mock_st.button.assert_not_called()


class TestRegression:
  def test_top3_roles_maintained(self) -> None:
    fx = _load_fixture()
    bundle = build_research_value_top3(fx["signals"], fx["theme"], limit=3)
    roles = [item["output"]["role"]["label_ja"] for item in bundle["items"]]
    assert roles == ["処方・工程候補", "物性エビデンス", "新規処方仮説"]

  def test_research_value_maintained(self) -> None:
    fx = _load_fixture()
    bundle = build_research_value_top3(fx["signals"], fx["theme"], limit=3)
    assert all(item["output"]["research_value"] for item in bundle["items"])

  def test_provider_counts(self) -> None:
    assert _load_fixture()["active_context"]["provider_counts"] == {"patent": 5, "paper": 5, "web": 5}

  def test_tier_counts(self) -> None:
    assert _load_fixture()["active_context"]["tier_counts"] == {"A": 3, "B": 2, "C": 3, "D": 7}

  def test_lineage_connected(self) -> None:
    assert _load_fixture()["active_context"]["lineage_status"] == "connected"
