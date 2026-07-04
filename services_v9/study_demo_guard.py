"""Fail-closed guards for external execution in study demo mode."""

from __future__ import annotations

from typing import Mapping

from .study_demo_config import is_study_demo_external_execution_disabled, is_study_demo_mode

BLOCKED_MESSAGE = "勉強会用環境では外部検索を停止しています"


class StudyDemoExternalExecutionBlocked(RuntimeError):
  """Raised when study demo mode forbids an external operation."""

  def __init__(self, operation: str) -> None:
    self.operation = str(operation or "unknown")
    super().__init__(f"{BLOCKED_MESSAGE}: {self.operation}")


def assert_external_execution_allowed(operation: str, *, environ: Mapping[str, str] | None = None) -> None:
  if not is_study_demo_mode(environ):
    return
  if is_study_demo_external_execution_disabled(environ):
    raise StudyDemoExternalExecutionBlocked(operation)


__all__ = [
  "BLOCKED_MESSAGE",
  "StudyDemoExternalExecutionBlocked",
  "assert_external_execution_allowed",
]
