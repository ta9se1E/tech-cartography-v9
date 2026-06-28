"""Tests for Phase27R.5 external AI design (OFF by default)."""

from __future__ import annotations

from pathlib import Path

import pytest

from tech_cartography.runtime.v8_external_ai_config import (
  ENABLE_EXTERNAL_AI_SUMMARY_ENV,
  ENABLE_GEMINI_DEEP_RESEARCH_ENV,
  ENABLE_LIVE_WEB_RESEARCH_ENV,
  ExternalAiConfig,
  external_ai_execution_allowed,
)
from tech_cartography.services.v8_external_ai_summary import (
  build_external_ai_summary_prompt,
  execute_external_ai_summary,
  validate_external_ai_summary_output,
)


def test_external_ai_config_default_off(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.delenv(ENABLE_EXTERNAL_AI_SUMMARY_ENV, raising=False)
  monkeypatch.delenv(ENABLE_GEMINI_DEEP_RESEARCH_ENV, raising=False)
  monkeypatch.delenv(ENABLE_LIVE_WEB_RESEARCH_ENV, raising=False)
  cfg = ExternalAiConfig.from_env()
  assert cfg.enable_external_ai_summary is False
  assert cfg.enable_gemini_deep_research is False
  assert cfg.enable_live_web_research is False
  assert external_ai_execution_allowed() is False


def test_build_summary_plan_disabled() -> None:
  plan = build_external_ai_summary_prompt(
    target="gap_executive_summary",
    case_id="case_01_pan_graphitization",
    source_artifacts=["gap_next_actions.md"],
  )
  assert plan.execution_status == "disabled"
  assert plan.human_review_required is True
  assert "Weekly Digest draft" in plan.future_connections


def test_validate_rejects_forbidden_patterns() -> None:
  result = validate_external_ai_summary_output("これは侵害リスクがあります。既存 artifact に基づく。")
  assert result.ok is False
  assert result.requires_human_review is True


def test_execute_raises() -> None:
  with pytest.raises(RuntimeError, match="disabled"):
    execute_external_ai_summary()


def test_docs_and_config_exist() -> None:
  assert Path("docs/external_ai_integration_phase27r5.md").exists()
  text = Path("src/tech_cartography/ui/v8_admin_settings_ui.py").read_text(encoding="utf-8")
  assert "外部AI" in text or "External AI" in text
