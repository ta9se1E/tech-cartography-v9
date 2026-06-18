"""Synthetic demo signal policy for Web Signals (Phase 23.0)."""

from __future__ import annotations

from dataclasses import replace

from tech_cartography.web_signals.schema import (
  SYNTHETIC_DEMO_MARKER,
  WebSignal,
  _cap_confidence,
)

SYNTHETIC_DEMO_CAVEAT_SUFFIX = "Synthetic demo signal. This is not real-world evidence."


def _ensure_marker_in_text(text: str) -> str:
  base = str(text or "").strip()
  if SYNTHETIC_DEMO_MARKER in base:
    return base
  if base:
    return f"{base} {SYNTHETIC_DEMO_CAVEAT_SUFFIX}"
  return SYNTHETIC_DEMO_CAVEAT_SUFFIX


def _label_synthetic_title(title: str) -> str:
  text = str(title or "").strip()
  prefix = "[Synthetic demo signal]"
  if text.startswith(prefix):
    return text
  return f"{prefix} {text}".strip()


def ensure_synthetic_policy(signal: WebSignal) -> WebSignal:
  if signal.is_synthetic_demo:
    return replace(
      signal,
      verification_status="synthetic_demo",
      confidence=_cap_confidence(signal.confidence, "low"),
      caveat=_ensure_marker_in_text(signal.caveat),
      source_title=_label_synthetic_title(signal.source_title),
      next_verification_action=signal.next_verification_action
      or "Do not use as real evidence. Replace with verified source in production.",
    )

  caveat = str(signal.caveat or "")
  if SYNTHETIC_DEMO_MARKER in caveat:
    caveat = caveat.replace(SYNTHETIC_DEMO_MARKER, "").strip()
  verification_status = signal.verification_status
  if verification_status == "verified_source" and not str(signal.source_url or "").strip():
    verification_status = "needs_human_review"
  return replace(signal, caveat=caveat or signal.caveat, verification_status=verification_status)
