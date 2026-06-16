"""Configuration loading helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from tech_cartography.domain.search_profile import SearchProfile

PACKAGE_ROOT = Path(__file__).resolve().parent
PROJECT_ROOT = PACKAGE_ROOT.parent.parent
CONFIG_DIR = PROJECT_ROOT / "configs"


def load_yaml_config(filename: str) -> dict[str, Any]:
  path = CONFIG_DIR / filename
  if not path.exists():
    raise FileNotFoundError(f"Config not found: {path}")
  with path.open(encoding="utf-8") as handle:
    data = yaml.safe_load(handle) or {}
  if not isinstance(data, dict):
    raise ValueError(f"Config must be a mapping: {path}")
  return data


def load_search_strategy_defaults() -> dict[str, Any]:
  return load_yaml_config("search_strategy_defaults.yaml")


def load_carbon_fiber_demo_profile() -> SearchProfile:
  return SearchProfile.from_dict(load_yaml_config("carbon_fiber_demo_profile.yaml"))
