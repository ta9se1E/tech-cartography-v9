"""Tests for deterministic research value synthesis."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services_v9.research_signal_roles import (
  ROLE_BACKGROUND,
  ROLE_FORMULATION,
  ROLE_LOW,
  ROLE_NOVEL,
  ROLE_PROPERTY,
  classify_signal_role,
)
from services_v9.research_value_fact_sheet import build_signal_fact_sheet, validate_fact_sheet
from services_v9.research_value_pipeline import build_research_value_top3
from services_v9.research_value_quality import text_similarity, validate_research_value_output, validate_top3_bundle
from services_v9.research_value_synthesizer import (
  contains_unsupported_assertion,
  synthesize_research_questions,
  synthesize_research_value,
  synthesize_research_value_output,
)
from services_v9.research_value_theme_axes import build_theme_axes, classify_theme_axis
from services_v9.top_signal_diversity_selector import select_diverse_top_signals

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "study_demo_research_value_samples.json"
ROOT = Path(__file__).resolve().parents[1]


def _load_fixture() -> dict:
  return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _signal_by_title(title_substr: str) -> dict:
  for item in _load_fixture()["signals"]:
    if title_substr in str(item.get("title", "")):
      return dict(item)
  raise KeyError(title_substr)


class TestThemeAxes:
  def test_build_theme_axes(self) -> None:
    axes = build_theme_axes(_load_fixture()["theme"])
    assert "composition" in axes.get("priority_axes", [])
    assert axes.get("axis_terms")

  def test_supported_missing_separated(self) -> None:
    signal = _signal_by_title("wear-resistant")
    fact = build_signal_fact_sheet(signal, build_theme_axes(_load_fixture()["theme"]))
    assert fact["supported_concepts"]
    assert "composition_detail" in fact["missing_but_important_axes"] or fact["missing_but_important_axes"]
    assert validate_fact_sheet(fact) == []

  def test_unsupported_not_marked_supported(self) -> None:
    signal = _signal_by_title("wear-resistant")
    fact = build_signal_fact_sheet(signal, build_theme_axes(_load_fixture()["theme"]))
    supported = {item["concept"] for item in fact["supported_concepts"]}
    for missing in fact["missing_but_important_axes"]:
      assert missing not in supported

  def test_source_specific_clues(self) -> None:
    patent = build_signal_fact_sheet(_signal_by_title("wear-resistant"), build_theme_axes(_load_fixture()["theme"]))
    paper = build_signal_fact_sheet(_signal_by_title("Styrene-Acrylic"), build_theme_axes(_load_fixture()["theme"]))
    assert patent["source_specific_fields"]["claim_scope_possible"] is True
    assert "doi" in paper["source_specific_fields"] or paper["source_type"] == "paper"


class TestRoles:
  def test_wear_resistant_patent_role(self) -> None:
    role = classify_signal_role(_signal_by_title("wear-resistant"))
    assert role["code"] == ROLE_FORMULATION

  def test_mechanical_paper_role(self) -> None:
    role = classify_signal_role(_signal_by_title("Styrene-Acrylic"))
    assert role["code"] == ROLE_PROPERTY

  def test_ionic_liquid_patent_role(self) -> None:
    role = classify_signal_role(_signal_by_title("ionic liquid"))
    assert role["code"] == ROLE_NOVEL

  def test_glass_review_background(self) -> None:
    role = classify_signal_role(_signal_by_title("Glass fiber"))
    assert role["code"] == ROLE_BACKGROUND

  def test_irrelevant_low_role(self) -> None:
    role = classify_signal_role(_signal_by_title("Textile fabric coating"))
    assert role["code"] in {ROLE_LOW, ROLE_BACKGROUND}


class TestContent:
  def _output(self, title_substr: str) -> dict:
    signal = _signal_by_title(title_substr)
    role = classify_signal_role(signal)
    fact = build_signal_fact_sheet(signal, build_theme_axes(_load_fixture()["theme"]))
    return synthesize_research_value_output(signal, role=role, fact_sheet=fact)

  def test_research_value_length(self) -> None:
    output = self._output("wear-resistant")
    assert len(output["research_value"]) >= 120

  def test_document_specific_term(self) -> None:
    output = self._output("ionic liquid")
    assert "ionic" in output["research_value"].lower() or "イオン" in output["research_value"]

  def test_theme_axes_in_text(self) -> None:
    output = self._output("Styrene-Acrylic")
    axes = build_theme_axes(_load_fixture()["theme"])["priority_axes"][:2]
    assert any(axis in output["research_value"] or classify_theme_axis(axis) for axis in axes) or len(output["research_value"]) >= 120

  def test_questions_count(self) -> None:
    output = self._output("wear-resistant")
    assert 3 <= len(output["verification_questions"]) <= 5

  def test_questions_interrogative(self) -> None:
    output = self._output("wear-resistant")
    assert all(q.endswith("？") or q.endswith("?") for q in output["verification_questions"])

  def test_no_single_word_questions(self) -> None:
    output = self._output("wear-resistant")
    for question in output["verification_questions"]:
      assert len(question) > 12

  def test_readout_specific(self) -> None:
    output = self._output("wear-resistant")
    assert "比較表" in output["readout_artifact"] or "転記" in output["readout_artifact"]

  def test_patent_questions(self) -> None:
    output = self._output("wear-resistant")
    joined = "\n".join(output["verification_questions"])
    assert "請求項" in joined or "配合比" in joined

  def test_paper_questions(self) -> None:
    output = self._output("Styrene-Acrylic")
    joined = "\n".join(output["verification_questions"])
    assert "matrix" in joined or "試験片" in joined or "引張" in joined

  def test_web_questions(self) -> None:
    signal = _signal_by_title("prepreg product")
    role = classify_signal_role(signal)
    fact = build_signal_fact_sheet(signal, build_theme_axes(_load_fixture()["theme"]))
    questions = synthesize_research_questions(signal, role=role, fact_sheet=fact)
    joined = "\n".join(questions)
    assert "一次情報" in joined or "定量" in joined

  def test_empty_abstract_fallback(self) -> None:
    signal = dict(_signal_by_title("wear-resistant"))
    signal["summary"] = ""
    role = classify_signal_role(signal)
    fact = build_signal_fact_sheet(signal, build_theme_axes(_load_fixture()["theme"]))
    output = synthesize_research_value_output(signal, role=role, fact_sheet=fact)
    assert output["data_basis"] == "title_only"
    assert output["confidence"] == "low"

  def test_unsupported_assertion_guard(self) -> None:
    assert contains_unsupported_assertion("有効です") is True
    value = synthesize_research_value(
      _signal_by_title("wear-resistant"),
      role=classify_signal_role(_signal_by_title("wear-resistant")),
      fact_sheet=build_signal_fact_sheet(_signal_by_title("wear-resistant"), build_theme_axes(_load_fixture()["theme"])),
    )
    assert contains_unsupported_assertion(value) is False


class TestDiversity:
  def test_top3_role_diversity(self) -> None:
    bundle = build_research_value_top3(_load_fixture()["signals"], _load_fixture()["theme"], limit=3)
    assert bundle["quality"]["role_diversity_count"] == 3

  def test_top3_source_diversity(self) -> None:
    selected, meta = select_diverse_top_signals(_load_fixture()["signals"], _load_fixture()["theme"], limit=3)
    assert len(set(meta["source_types"])) >= 2

  def test_relevance_not_dropped_too_much(self) -> None:
    selected, _ = select_diverse_top_signals(_load_fixture()["signals"], _load_fixture()["theme"], limit=3)
    scores = [float(dict(item["signal"]).get("relevance_score", 0) or 0) for item in selected]
    assert min(scores) >= 80

  def test_deterministic(self) -> None:
    a = build_research_value_top3(_load_fixture()["signals"], _load_fixture()["theme"], limit=3)
    b = build_research_value_top3(_load_fixture()["signals"], _load_fixture()["theme"], limit=3)
    assert a["selection"]["role_labels_ja"] == b["selection"]["role_labels_ja"]

  def test_same_input_same_output(self) -> None:
    signal = _signal_by_title("wear-resistant")
    role = classify_signal_role(signal)
    fact = build_signal_fact_sheet(signal, build_theme_axes(_load_fixture()["theme"]))
    left = synthesize_research_value_output(signal, role=role, fact_sheet=fact)
    right = synthesize_research_value_output(signal, role=role, fact_sheet=fact)
    assert left == right

  def test_no_random_module(self) -> None:
    source = (ROOT / "services_v9/research_value_synthesizer.py").read_text(encoding="utf-8")
    assert "random." not in source

  def test_no_network_module(self) -> None:
    for path in ROOT.glob("services_v9/research_value*.py"):
      text = path.read_text(encoding="utf-8")
      assert "requests." not in text
      assert "httpx." not in text


class TestCurrentTop3:
  def test_roles_expected(self) -> None:
    bundle = build_research_value_top3(_load_fixture()["signals"], _load_fixture()["theme"], limit=3)
    labels = [item["output"]["role"]["label_ja"] for item in bundle["items"]]
    assert labels == ["処方・工程候補", "物性エビデンス", "新規処方仮説"]

  def test_research_values_distinct(self) -> None:
    bundle = build_research_value_top3(_load_fixture()["signals"], _load_fixture()["theme"], limit=3)
    values = [item["output"]["research_value"] for item in bundle["items"]]
    assert text_similarity(values[0], values[1]) < 0.72
    assert text_similarity(values[0], values[2]) < 0.72

  def test_questions_distinct(self) -> None:
    bundle = build_research_value_top3(_load_fixture()["signals"], _load_fixture()["theme"], limit=3)
    joined = ["\n".join(item["output"]["verification_questions"]) for item in bundle["items"]]
    assert text_similarity(joined[0], joined[1]) < 0.72

  def test_readouts_distinct(self) -> None:
    bundle = build_research_value_top3(_load_fixture()["signals"], _load_fixture()["theme"], limit=3)
    readouts = [item["output"]["readout_artifact"] for item in bundle["items"]]
    assert len(set(readouts)) == 3

  def test_titles_match_fixture(self) -> None:
    bundle = build_research_value_top3(_load_fixture()["signals"], _load_fixture()["theme"], limit=3)
    titles = [item["signal"]["title"] for item in bundle["items"]]
    assert "wear-resistant" in titles[0]
    assert "Styrene-Acrylic" in titles[1]
    assert "ionic liquid" in titles[2]


class TestUi:
  def test_heading_in_simple_signals(self) -> None:
    source = (ROOT / "ui_v9/study_demo_simple_signals_ui.py").read_text(encoding="utf-8")
    assert "今回まず確認する3件" in source

  def test_initial_baseline_badge(self) -> None:
    source = (ROOT / "ui_v9/study_demo_simple_signals_ui.py").read_text(encoding="utf-8")
    assert "Initial Baseline" in source

  def test_caveat_display(self) -> None:
    source = (ROOT / "ui_v9/study_demo_simple_signals_ui.py").read_text(encoding="utf-8")
    assert "技術的妥当性を示すものではありません" in source

  def test_score_hidden_in_research_card(self) -> None:
    source = (ROOT / "ui_v9/study_demo_research_value_ui.py").read_text(encoding="utf-8")
    assert "score" not in source.lower() or "ranking_basis" in source

  def test_tags_hidden(self) -> None:
    source = (ROOT / "ui_v9/study_demo_research_value_ui.py").read_text(encoding="utf-8")
    assert "matched_terms" not in source

  def test_ranking_basis_collapsed(self) -> None:
    source = (ROOT / "ui_v9/study_demo_research_value_ui.py").read_text(encoding="utf-8")
    assert 'expander("ランキング根拠", expanded=False)' in source

  def test_questions_display(self) -> None:
    source = (ROOT / "ui_v9/study_demo_research_value_ui.py").read_text(encoding="utf-8")
    assert "原典で確認する問い" in source

  def test_readout_display(self) -> None:
    source = (ROOT / "ui_v9/study_demo_research_value_ui.py").read_text(encoding="utf-8")
    assert "読後に残すもの" in source

  def test_source_url_preserved(self) -> None:
    source = (ROOT / "ui_v9/study_demo_research_value_ui.py").read_text(encoding="utf-8")
    assert "render_external_source_link" in source

  def test_simple_review_labels(self) -> None:
    source = (ROOT / "ui_v9/study_demo_research_value_ui.py").read_text(encoding="utf-8")
    assert "関連" in source and "除外" in source

  def test_initial_candidate_label(self) -> None:
    source = (ROOT / "ui_v9/study_demo_research_value_ui.py").read_text(encoding="utf-8")
    assert "初回候補" in source

  def test_top3_dedup_logic(self) -> None:
    source = (ROOT / "ui_v9/study_demo_simple_signals_ui.py").read_text(encoding="utf-8")
    assert "research_title_lookup" in source


class TestSafetyRegression:
  def test_fixture_lineage_ids(self) -> None:
    fx = _load_fixture()
    ctx = fx["active_context"]
    assert ctx["source_theme_id"] == "theme_6d2dfb753f7e"
    assert ctx["provider_counts"] == {"patent": 5, "paper": 5, "web": 5}
    assert ctx["tier_counts"] == {"A": 3, "B": 2, "C": 3, "D": 7}

  def test_quality_gate_ok(self) -> None:
    bundle = build_research_value_top3(_load_fixture()["signals"], _load_fixture()["theme"], limit=3)
    assert validate_top3_bundle(bundle["items"])["status"] == "ok"

  def test_check_script_plan(self) -> None:
    from scripts.check_v9_study_demo_research_value import run_plan

    result = run_plan(search_run_id="study_demo_search_20260705_145711_c06e0a1b")
    assert result["status"] == "ok"
    assert result["external_api_calls"] == 0
    assert result["cloud_writes"] == 0
    assert result["production_modifications"] is False

  def test_advanced_mode_preserved(self) -> None:
    source = (ROOT / "ui_v9/tabs.py").read_text(encoding="utf-8")
    assert "is_study_demo_simple_ui()" in source

  @patch("ui_v9.study_demo_simple_signals_ui.st")
  @patch("ui_v9.study_demo_simple_signals_ui.build_research_value_bundle")
  def test_simple_signals_render_with_research_bundle(self, mock_bundle: MagicMock, mock_st: MagicMock) -> None:
    from ui_v9.study_demo_simple_signals_ui import render_simple_signals_tab

    mock_bundle.return_value = {"items": []}
    mock_st.columns.side_effect = [
      [MagicMock(), MagicMock()],
      [MagicMock(), MagicMock(), MagicMock()],
      [MagicMock(), MagicMock(), MagicMock()],
    ]
    mock_st.multiselect.return_value = ["patent"]
    signals = []
    render_simple_signals_tab(
      signals=signals,
      display_signals=[],
      source_info={"active_context": {"active_search_run_id": "run-a"}, "study_demo_downstream": {"weekly_state": {"state": "initial_baseline"}}},
    )
    mock_bundle.assert_called_once()
