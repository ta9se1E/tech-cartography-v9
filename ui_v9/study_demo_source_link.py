"""Render external source links for Study Demo UI tabs."""

from __future__ import annotations

import hashlib
import re
from typing import Any, Mapping

import streamlit as st

from services_v9.study_demo_source_url import SourceUrlResolution, resolve_signal_source_url


def _normalize_part(value: str) -> str:
  cleaned = re.sub(r"[^a-zA-Z0-9_]+", "_", str(value or "").strip().lower())
  cleaned = re.sub(r"_+", "_", cleaned).strip("_")
  return cleaned or "na"


def build_study_demo_source_link_key(
  tab_name: str,
  signal_id: str,
  search_run_id: str = "",
) -> str:
  parts = [
    "study_demo_source_link",
    _normalize_part(tab_name),
    hashlib.sha256(str(signal_id or "na").encode("utf-8")).hexdigest()[:12],
  ]
  if search_run_id:
    parts.append(hashlib.sha256(search_run_id.encode("utf-8")).hexdigest()[:12])
  key = "_".join(parts)
  return key[:200]


def _signal_mapping(signal: Mapping[str, Any] | Any) -> dict[str, Any]:
  if isinstance(signal, Mapping):
    return dict(signal)
  if hasattr(signal, "to_dict"):
    return dict(signal.to_dict())
  return {
    "id": getattr(signal, "id", ""),
    "signal_id": getattr(signal, "id", ""),
    "title": getattr(signal, "title", ""),
    "source_type": getattr(signal, "type", ""),
    "type": getattr(signal, "type", ""),
    "source_url": getattr(signal, "source_url", ""),
    "url": getattr(signal, "source_url", ""),
  }


def _missing_context(resolution: SourceUrlResolution, signal: Mapping[str, Any]) -> str:
  meta = dict(signal.get("metadata", {}) or {}) if isinstance(signal.get("metadata"), Mapping) else {}
  parts: list[str] = []
  publication = str(
    signal.get("publication_number")
    or signal.get("source_id")
    or signal.get("external_id")
    or meta.get("publication_number")
    or ""
  ).strip()
  doi = str(signal.get("doi") or meta.get("doi") or "").strip()
  openalex = str(signal.get("openalex_id") or meta.get("openalex_id") or "").strip()
  if publication:
    parts.append(f"publication: {publication}")
  if doi:
    parts.append(f"DOI: {doi}")
  if openalex:
    parts.append(f"OpenAlex: {openalex}")
  if signal.get("title"):
    parts.append(str(signal.get("title")))
  if signal.get("organization"):
    parts.append(str(signal.get("organization")))
  if parts:
    return "引用元URL未取得 (" + " / ".join(parts[:3]) + ")"
  return "引用元URL未取得"


def render_external_source_link(
  signal: Mapping[str, Any] | Any,
  *,
  key_namespace: str,
  label: str = "引用元を開く",
  search_run_id: str = "",
) -> SourceUrlResolution:
  payload = _signal_mapping(signal)
  resolution = resolve_signal_source_url(payload)
  signal_id = str(payload.get("signal_id") or payload.get("id") or payload.get("title") or "signal")
  if resolution.is_valid:
    st.link_button(
      label,
      resolution.resolved_url,
      key=build_study_demo_source_link_key(key_namespace, signal_id, search_run_id),
    )
  else:
    st.caption(_missing_context(resolution, payload))
  return resolution
