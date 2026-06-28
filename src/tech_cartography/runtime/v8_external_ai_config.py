"""External AI integration feature flags (Phase 27R.5) — default OFF."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass

ENABLE_EXTERNAL_AI_SUMMARY_ENV = "ENABLE_EXTERNAL_AI_SUMMARY"
ENABLE_GEMINI_DEEP_RESEARCH_ENV = "ENABLE_GEMINI_DEEP_RESEARCH"
ENABLE_LIVE_WEB_RESEARCH_ENV = "ENABLE_LIVE_WEB_RESEARCH"

EXTERNAL_AI_SAFETY_NOTICES: tuple[str, ...] = (
  "外部AI出力は draft summary / 候補要約のみ — 証明・法的判断ではありません。",
  "請求項本文、DOI、URL、特許番号は外部AIで生成しません。",
  "citations / source trace が無い出力は採用しません。",
  "human review required — Watch Profile / Digest への自動反映は行いません。",
  "公開デモでは外部AI実行は OFF です。",
)


def _env_bool(name: str, default: bool = False) -> bool:
  raw = os.environ.get(name)
  if raw is None:
    return default
  return str(raw).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class ExternalAiConfig:
  enable_external_ai_summary: bool
  enable_gemini_deep_research: bool
  enable_live_web_research: bool
  execution_allowed: bool
  demo_mode_blocked: bool

  @classmethod
  def from_env(cls) -> ExternalAiConfig:
    summary = _env_bool(ENABLE_EXTERNAL_AI_SUMMARY_ENV, False)
    gemini = _env_bool(ENABLE_GEMINI_DEEP_RESEARCH_ENV, False)
    web = _env_bool(ENABLE_LIVE_WEB_RESEARCH_ENV, False)
    execution_allowed = summary and (gemini or web)
    return cls(
      enable_external_ai_summary=summary,
      enable_gemini_deep_research=gemini,
      enable_live_web_research=web,
      execution_allowed=execution_allowed,
      demo_mode_blocked=not execution_allowed,
    )

  def to_dict(self) -> dict[str, bool]:
    return asdict(self)


def external_ai_execution_allowed() -> bool:
  return ExternalAiConfig.from_env().execution_allowed


def external_ai_status_lines() -> list[str]:
  cfg = ExternalAiConfig.from_env()
  return [
    f"{ENABLE_EXTERNAL_AI_SUMMARY_ENV}={cfg.enable_external_ai_summary}",
    f"{ENABLE_GEMINI_DEEP_RESEARCH_ENV}={cfg.enable_gemini_deep_research}",
    f"{ENABLE_LIVE_WEB_RESEARCH_ENV}={cfg.enable_live_web_research}",
    f"execution_allowed={cfg.execution_allowed}",
  ]
