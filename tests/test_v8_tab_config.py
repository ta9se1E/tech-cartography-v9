"""Tests for v8 tab configuration (Phase 27B)."""

from __future__ import annotations

from tech_cartography.ui.v8_tab_config import (
  CLAIM_MAP_TECHNICAL_AXES,
  EVIDENCE_SUPPORT_LEVELS,
  V8_TAB_IDS,
  V8_TAB_LABELS,
  v8_tab_labels,
)


def test_v8_tab_order() -> None:
  assert V8_TAB_IDS == (
    "intro",
    "input",
    "sources",
    "patent_shortlist",
    "claim_map",
    "evidence_map",
    "gap_next_actions",
    "fixed_point_observation",
    "export",
    "admin_settings",
  )


def test_v8_tab_labels_japanese() -> None:
  labels = v8_tab_labels()
  assert labels == [
    "はじめに｜Judge Overview",
    "入力・テーマ設定",
    "Sources｜データ出自",
    "読むべき特許｜Top5",
    "Claim Map｜請求項の技術整理",
    "Evidence Map｜裏取り候補",
    "Gap / Next Actions｜未確認事項",
    "定点観測｜Weekly Watch",
    "Export｜共有レポート",
    "管理者設定｜Demo Safety",
  ]
  assert V8_TAB_LABELS["fixed_point_observation"] == "定点観測｜Weekly Watch"


def test_v8_claim_and_evidence_axes_defined() -> None:
  assert "precursor" in CLAIM_MAP_TECHNICAL_AXES
  assert "pressure vessel / filament winding" in CLAIM_MAP_TECHNICAL_AXES
  assert "needs_human_review" in EVIDENCE_SUPPORT_LEVELS
