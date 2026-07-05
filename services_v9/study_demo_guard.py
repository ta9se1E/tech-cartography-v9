"""Fail-closed guards for external execution in study demo mode."""

from __future__ import annotations

from typing import Mapping

from .study_demo_config import (
  is_study_demo_external_execution_disabled,
  is_study_demo_mode,
  is_study_demo_paper_search_enabled,
  is_study_demo_patent_search_enabled,
  is_study_demo_search_enabled,
  is_study_demo_web_search_enabled,
)

BLOCKED_MESSAGE = "勉強会用環境では外部検索を停止しています"

_SEARCH_OPERATION_FLAGS = {
  "bigquery_dry_run": is_study_demo_patent_search_enabled,
  "bigquery_execute": is_study_demo_patent_search_enabled,
  "openalex_execute": is_study_demo_paper_search_enabled,
  "tavily_execute": is_study_demo_web_search_enabled,
}


class StudyDemoExternalExecutionBlocked(RuntimeError):
  """Raised when study demo mode forbids an external operation."""

  def __init__(self, operation: str) -> None:
    self.operation = str(operation or "unknown")
    super().__init__(f"{BLOCKED_MESSAGE}: {self.operation}")


def assert_external_execution_allowed(operation: str, *, environ: Mapping[str, str] | None = None) -> None:
  if not is_study_demo_mode(environ):
    return
  if is_study_demo_search_enabled(environ):
    checker = _SEARCH_OPERATION_FLAGS.get(str(operation or ""))
    if checker is not None and checker(environ):
      return
  if is_study_demo_external_execution_disabled(environ):
    raise StudyDemoExternalExecutionBlocked(operation)


__all__ = [
  "BLOCKED_MESSAGE",
  "StudyDemoExternalExecutionBlocked",
  "assert_external_execution_allowed",
]
