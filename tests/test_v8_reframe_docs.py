"""Tests for v8 reframe documentation (Phase27A)."""

from __future__ import annotations

from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_DOCS = (
  "docs/v8_product_reframe.md",
  "docs/v8_three_case_validation_plan.md",
  "docs/v8_user_flow_and_tabs.md",
  "docs/v8_cursor_roadmap.md",
  "README_v8_LOCAL_FIRST.md",
)

CASE_IDS = (
  "case_01_pan_graphitization",
  "case_02_sizing_interface",
  "case_03_pressure_vessel_filament_winding",
)


@pytest.mark.parametrize("rel_path", REQUIRED_DOCS)
def test_v8_doc_exists(rel_path: str) -> None:
  path = PROJECT_ROOT / rel_path
  assert path.exists(), f"missing doc: {rel_path}"
  assert path.stat().st_size > 100


def test_v8_docs_mention_required_capabilities() -> None:
  blob = "\n".join((PROJECT_ROOT / p).read_text(encoding="utf-8") for p in REQUIRED_DOCS)
  lowered = blob.lower()
  for fragment in (
    "メール送信",
    "scheduler",
    "watch profile",
    "scope feedback",
    "run history",
    "定点観測",
    "ローカル",
    "fto",
    "侵害",
    "架空",
    "cloud build",
  ):
    assert fragment in lowered, f"missing doc mention: {fragment}"


def test_v8_docs_mention_local_first() -> None:
  readme = (PROJECT_ROOT / "README_v8_LOCAL_FIRST.md").read_text(encoding="utf-8")
  assert "ローカル" in readme or "local-first" in readme.lower()
  assert "v8-claim-evidence-gap" in readme


def test_v8_docs_forbid_legal_and_fake_evidence() -> None:
  reframe = (PROJECT_ROOT / "docs/v8_product_reframe.md").read_text(encoding="utf-8")
  assert "FTO" in reframe
  assert "架空" in reframe or "fake" in reframe.lower()


@pytest.mark.parametrize("case_id", CASE_IDS)
def test_v8_case_directory_exists(case_id: str) -> None:
  case_dir = PROJECT_ROOT / "cases" / case_id
  assert case_dir.is_dir()
  for name in (
    "case_profile.yaml",
    "source_candidates.csv",
    "expected_outputs.md",
    "validation_checklist.md",
  ):
    assert (case_dir / name).exists(), f"missing {case_id}/{name}"


def test_v8_user_flow_has_ten_tabs() -> None:
  text = (PROJECT_ROOT / "docs/v8_user_flow_and_tabs.md").read_text(encoding="utf-8")
  for tab in (
    "はじめに",
    "入力",
    "Sources一覧",
    "読むべき特許",
    "Claim Map",
    "Evidence Map",
    "Gap / Next Actions",
    "定点観測",
    "Export",
    "管理者設定",
  ):
    assert tab in text
