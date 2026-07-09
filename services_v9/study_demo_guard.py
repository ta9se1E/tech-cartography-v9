"""Fail-closed guards for external execution and writes in study demo mode."""

from __future__ import annotations

from typing import Mapping

from .study_demo_access import is_public_demo
from .study_demo_config import (
  is_study_demo_external_execution_disabled,
  is_study_demo_mode,
  is_study_demo_paper_search_enabled,
  is_study_demo_patent_search_enabled,
  is_study_demo_search_enabled,
  is_study_demo_web_search_enabled,
)

BLOCKED_MESSAGE = "勉強会用環境では外部検索を停止しています"
WRITE_BLOCKED_MESSAGE = "Public Demo mode is read-only. Shared demo data cannot be changed."

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


class StudyDemoWriteBlocked(RuntimeError):
  """Raised when public demo mode forbids a persistent write."""

  def __init__(self, operation: str) -> None:
    self.operation = str(operation or "unknown")
    super().__init__(f"{WRITE_BLOCKED_MESSAGE} ({self.operation})")


def assert_write_allowed(operation: str, *, environ: Mapping[str, str] | None = None) -> None:
  if is_study_demo_mode(environ) and is_public_demo(environ):
    raise StudyDemoWriteBlocked(operation)


def assert_external_execution_allowed(operation: str, *, environ: Mapping[str, str] | None = None) -> None:
  if not is_study_demo_mode(environ):
    return
  if is_public_demo(environ):
    raise StudyDemoExternalExecutionBlocked(operation)
  if is_study_demo_search_enabled(environ):
    checker = _SEARCH_OPERATION_FLAGS.get(str(operation or ""))
    if checker is not None and checker(environ):
      return
  if is_study_demo_external_execution_disabled(environ):
    raise StudyDemoExternalExecutionBlocked(operation)


__all__ = [
  "BLOCKED_MESSAGE",
  "StudyDemoExternalExecutionBlocked",
  "StudyDemoWriteBlocked",
  "WRITE_BLOCKED_MESSAGE",
  "assert_external_execution_allowed",
  "assert_write_allowed",
]
