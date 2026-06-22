"""Helpers for Cloud Run ignore-file tests in clean workspaces (Phase 25P.2)."""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def cloudrun_ignore_text(kind: str) -> str:
  if kind not in {"gcloudignore", "dockerignore"}:
    raise ValueError(f"unsupported ignore kind: {kind}")
  dot_path = PROJECT_ROOT / f".{kind}"
  canonical = PROJECT_ROOT / "config" / f"cloudrun.{kind}"
  if dot_path.exists():
    return dot_path.read_text(encoding="utf-8")
  if canonical.exists():
    return canonical.read_text(encoding="utf-8")
  raise FileNotFoundError(f"missing ignore file: .{kind} and config/cloudrun.{kind}")
