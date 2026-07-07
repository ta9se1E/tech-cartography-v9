"""Tests for human-facing baseline, digest, review and proposal safety."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from services_v9.human_datetime import format_datetime_jst, parse_datetime
from services_v9.human_digest_builder import (
  build_human_digest,
  human_digest_to_markdown,
  short_theme_label,
  validate_digest_payload,
)
from services_v9.run_baseline_state import (
  build_baseline_summary,
  build_change_labels,
  is_initial_baseline,
  resolve_run_baseline_state,
)
from services_v9.search_improvement_eligibility import (
  build_insufficient_review_message,
  evaluate_proposal_eligibility,
  normalize_human_keyword,
  reject_internal_token,
)
from services_v9.simple_review_state import (
  can_save_review,
  normalize_simple_decision,
  summarize_simple_reviews,
)
from services_v9.simple_tier_display import tier_display_label_ja
from services_v9.study_demo_review_proposals import generate_review_proposals

FIXTURE_PATH = Path(__file__).resolve().parent / "fixtures" / "study_demo_research_value_samples.json"
ROOT = Path(__file__).resolve().parents[1]


def _load_fixture() -> dict:
  return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _baseline_state() -> dict:
  fx = _load_fixture()
  return resolve_run_baseline_state(
    fx["active_context"],
    previous_run=None,
    snapshots=[],
    weekly_state={"comparison_status": "not_comparable"},
    integrated_count=len(fx["signals"]),
    priority_count=3,
  )


class TestBaseline:
  def test_no_previous_run_is_initial(self) -> None:
    assert _baseline_state()["state"] == "initial_baseline"

  def test_zero_diff_only_not_baseline(self) -> None:
    fx = _load_fixture()
    previous = {"source_run_id": "older_run", "source_theme_id": fx["active_context"]["source_theme_id"]}
    diff = {"counts": {"new": 0, "score_up": 0, "score_down": 0}}
    state = resolve_run_baseline_state(
      fx["active_context"],
      previous_run=previous,
      snapshots=[previous],
      weekly_state={"comparison_status": "comparable", "diff": diff},
      integrated_count=15,
    )
    assert state["state"] == "comparable"

  def test_initial_hides_diff_counts(self) -> None:
    summary = build_baseline_summary(_baseline_state())
    assert summary["show_diff_counts"] is False

  def test_initial_change_label(self) -> None:
    assert build_change_labels(baseline_state=_baseline_state()) == "初回候補"

  def test_weekly_summary_initial(self) -> None:
    summary = build_baseline_summary(_baseline_state())
    assert "初回ベースライン" in summary["headline"]


class TestDigest:
  def test_human_digest_structure(self) -> None:
    fx = _load_fixture()
    digest = build_human_digest(
      theme=fx["theme"],
      signals=fx["signals"],
      baseline_state=_baseline_state(),
      reviews=[],
      integrated_count=15,
    )
    assert digest["heading"] == "今週のR&Dシグナル"
    assert len(digest["top3"]) == 3

  def test_reuses_research_value(self) -> None:
    fx = _load_fixture()
    digest = build_human_digest(theme=fx["theme"], signals=fx["signals"], baseline_state=_baseline_state(), reviews=[])
    assert all(item.get("research_value") for item in digest["top3"])

  def test_role_alignment(self) -> None:
    from services_v9.research_value_pipeline import build_research_value_top3

    fx = _load_fixture()
    ui = build_research_value_top3(fx["signals"], fx["theme"], limit=3)
    digest = build_human_digest(theme=fx["theme"], signals=fx["signals"], baseline_state=_baseline_state(), reviews=[])
    ui_roles = [item["output"]["role"]["label_ja"] for item in ui["items"]]
    digest_roles = [dict(item["role"]).get("label_ja") for item in digest["top3"]]
    assert ui_roles == digest_roles

  def test_questions_max_three(self) -> None:
    fx = _load_fixture()
    digest = build_human_digest(theme=fx["theme"], signals=fx["signals"], baseline_state=_baseline_state(), reviews=[])
    assert all(len(item.get("verification_questions", [])) <= 3 for item in digest["top3"])

  def test_no_python_dict_in_markdown(self) -> None:
    fx = _load_fixture()
    digest = build_human_digest(theme=fx["theme"], signals=fx["signals"], baseline_state=_baseline_state(), reviews=[])
    markdown = human_digest_to_markdown(digest)
    assert "{'A':" not in markdown
    assert "study_demo_search_" not in markdown

  def test_no_internal_token_in_markdown(self) -> None:
    fx = _load_fixture()
    digest = build_human_digest(theme=fx["theme"], signals=fx["signals"], baseline_state=_baseline_state(), reviews=[])
    markdown = human_digest_to_markdown(digest)
    assert "sizing:title" not in markdown

  def test_digest_validation_ok(self) -> None:
    fx = _load_fixture()
    digest = build_human_digest(theme=fx["theme"], signals=fx["signals"], baseline_state=_baseline_state(), reviews=[])
    assert validate_digest_payload(digest)["status"] == "ok"


class TestReview:
  def test_initial_unreviewed(self) -> None:
    assert normalize_simple_decision("") == "unreviewed"

  def test_unreviewed_not_hold(self) -> None:
    assert normalize_simple_decision("unreviewed") != "hold"

  def test_cannot_save_unreviewed(self) -> None:
    assert can_save_review("unreviewed") is False

  def test_summary_counts_unreviewed(self) -> None:
    summary = summarize_simple_reviews([], ["a", "b", "c"])
    assert summary == {"unreviewed": 3, "accept": 0, "hold": 0, "reject": 0}


class TestProposal:
  def test_insufficient_reviews(self) -> None:
    result = evaluate_proposal_eligibility([])
    assert result["eligible"] is False

  def test_internal_token_rejected(self) -> None:
    assert reject_internal_token("sizing:title") is True
    assert normalize_human_keyword("ionic liquid") == "ionic liquid"

  def test_no_proposals_when_review_lt_3(self) -> None:
    fx = _load_fixture()
    payload = generate_review_proposals(
      reviews=[],
      signals=fx["signals"],
      source_run_id=fx["search_run_id"],
      theme_name=fx["theme"]["name"],
    )
    assert payload["summary"]["proposal_count"] == 0
    assert payload["summary"]["observation_only"] is True

  def test_provider_priority_hidden(self) -> None:
    fx = _load_fixture()
    reviews = [
      {"signal_id": "a", "decision": "reject", "reviewed": True, "reason_codes": ["theme_mismatch"]},
      {"signal_id": "b", "decision": "reject", "reviewed": True, "reason_codes": ["theme_mismatch"]},
      {"signal_id": "c", "decision": "reject", "reviewed": True, "reason_codes": ["theme_mismatch"]},
    ]
    payload = generate_review_proposals(
      reviews=reviews,
      signals=fx["signals"],
      source_run_id=fx["search_run_id"],
      theme_name=fx["theme"]["name"],
    )
    assert all(item.get("proposal_type") not in {"boost_source_type", "lower_source_type"} for item in payload["proposals"])


class TestTierLabels:
  def test_tier_labels(self) -> None:
    assert tier_display_label_ja("A") == "優先確認"
    assert tier_display_label_ja("B") == "継続監視"
    assert tier_display_label_ja("C") == "背景資料"
    assert tier_display_label_ja("D") == "低優先"


class TestDatetime:
  def test_jst_format(self) -> None:
    assert format_datetime_jst("2026-07-05T15:30:43.958562+00:00") == "2026/07/06 00:30 JST"

  def test_parse_fail(self) -> None:
    assert format_datetime_jst("invalid") == "日時未記録"


class TestHeader:
  def test_short_theme_label(self) -> None:
    long_name = "PAN系炭素繊維用サイジング剤の組成・付与・乾燥条件"
    assert short_theme_label(long_name) == "PAN系炭素繊維用サイジング剤の組成・付与・乾…"


class TestUiSources:
  def test_simple_sources_history_message(self) -> None:
    source = (ROOT / "ui_v9/study_demo_simple_sources_ui.py").read_text(encoding="utf-8")
    assert "今回のRunが初回ベースラインです" in source

  def test_simple_signals_heading(self) -> None:
    source = (ROOT / "ui_v9/study_demo_simple_signals_ui.py").read_text(encoding="utf-8")
    assert "今回まず確認する3件" in source
    assert "参考・低優先" in source

  def test_review_unreviewed_option(self) -> None:
    source = (ROOT / "ui_v9/study_demo_research_value_ui.py").read_text(encoding="utf-8")
    assert "未判断" in source
    assert "can_save_review" in source


class TestSafetyCheck:
  def test_plan_ok(self) -> None:
    from scripts.check_v9_study_demo_human_facing_safety import run_plan

    result = run_plan(search_run_id="study_demo_search_20260705_145711_c06e0a1b")
    assert result["status"] == "ok"
    assert result["proposal_eligible"] is False


class TestRegression:
  @patch("ui_v9.study_demo_simple_signals_ui.st")
  @patch("ui_v9.study_demo_simple_signals_ui.build_research_value_bundle")
  def test_simple_signals_render(self, mock_bundle: MagicMock, mock_st: MagicMock) -> None:
    from ui_v9.study_demo_simple_signals_ui import render_simple_signals_tab

    mock_bundle.return_value = {"items": []}
    mock_st.columns.side_effect = [[MagicMock(), MagicMock()]]
    render_simple_signals_tab(
      signals=[],
      display_signals=[],
      source_info={"active_context": {"active_search_run_id": "run"}, "study_demo_downstream": {"weekly_state": {"state": "initial_baseline"}}},
    )

  def test_c5b5a_roles_preserved(self) -> None:
    from services_v9.research_value_pipeline import build_research_value_top3

    fx = _load_fixture()
    bundle = build_research_value_top3(fx["signals"], fx["theme"], limit=3)
    labels = [item["output"]["role"]["label_ja"] for item in bundle["items"]]
    assert labels == ["処方・工程候補", "物性エビデンス", "新規処方仮説"]
