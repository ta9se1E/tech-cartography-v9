"""Access mode resolution for the isolated v9 study demo service."""

from __future__ import annotations

import os
from typing import Mapping

from .study_demo_config import is_study_demo_mode

ACCESS_MODE_ENV = "V9_ACCESS_MODE"
ACCESS_MODE_PASSWORD = "password"
ACCESS_MODE_PUBLIC_DEMO = "public_demo"
ALLOWED_ACCESS_MODES = frozenset({ACCESS_MODE_PASSWORD, ACCESS_MODE_PUBLIC_DEMO})

PUBLIC_DEMO_BADGE = "Public Demo — read-only"
PUBLIC_DEMO_SEEDED_NOTICE = (
  "Seeded demo data only. This environment displays a fixed validated study dataset "
  "and does not fetch or update live external sources."
)
PUBLIC_DEMO_LEGAL_CAVEAT = (
  "This public demo is for review only. It does not provide legal advice, freedom-to-operate, "
  "infringement, or validity determinations."
)

DEMO_THEME_ID = "theme_6d2dfb753f7e"
DEMO_THEME_NAME = "PAN系炭素繊維用サイジング剤の組成・付与・乾燥条件"
DEMO_ACTIVE_RUN_ID = "study_demo_search_20260705_145711_c06e0a1b"
DEMO_ACTIVE_CONTEXT_GENERATION = 2
DEMO_SOURCE_COUNTS = {"patent": 5, "paper": 5, "web": 5, "integrated": 15}
DEMO_TIER_COUNTS = {"A": 3, "B": 2, "C": 3, "D": 7}


def resolve_access_mode(environ: Mapping[str, str] | None = None) -> str:
  env = environ if environ is not None else os.environ
  if not is_study_demo_mode(env):
    return ACCESS_MODE_PASSWORD
  value = str(env.get(ACCESS_MODE_ENV, "") or "").strip().lower()
  if value in ALLOWED_ACCESS_MODES:
    return value
  return ACCESS_MODE_PASSWORD


def is_public_demo(environ: Mapping[str, str] | None = None) -> bool:
  return resolve_access_mode(environ) == ACCESS_MODE_PUBLIC_DEMO


def is_password_mode(environ: Mapping[str, str] | None = None) -> bool:
  return resolve_access_mode(environ) == ACCESS_MODE_PASSWORD


__all__ = [
  "ACCESS_MODE_ENV",
  "ACCESS_MODE_PASSWORD",
  "ACCESS_MODE_PUBLIC_DEMO",
  "ALLOWED_ACCESS_MODES",
  "DEMO_ACTIVE_CONTEXT_GENERATION",
  "DEMO_ACTIVE_RUN_ID",
  "DEMO_SOURCE_COUNTS",
  "DEMO_THEME_ID",
  "DEMO_THEME_NAME",
  "DEMO_TIER_COUNTS",
  "PUBLIC_DEMO_BADGE",
  "PUBLIC_DEMO_LEGAL_CAVEAT",
  "PUBLIC_DEMO_SEEDED_NOTICE",
  "is_password_mode",
  "is_public_demo",
  "resolve_access_mode",
]
