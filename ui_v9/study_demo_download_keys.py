"""Stable Streamlit download_button keys for Study Demo."""

from __future__ import annotations

import hashlib
import re


def _normalize_part(value: str) -> str:
  cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value or "").strip().lower())
  cleaned = re.sub(r"_+", "_", cleaned).strip("_")
  return cleaned or "na"


def build_study_demo_download_key(
  tab_name: str,
  artifact_name: str,
  search_run_id: str = "",
  variant: str | None = None,
) -> str:
  parts = [
    "study_demo_download",
    _normalize_part(tab_name),
    _normalize_part(artifact_name),
  ]
  if search_run_id:
    parts.append(hashlib.sha256(search_run_id.encode("utf-8")).hexdigest()[:12])
  if variant:
    parts.append(_normalize_part(variant))
  key = "_".join(parts)
  if len(key) > 200:
    key = key[:200]
  return key
