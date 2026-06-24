"""Operation status includes web signal digest fields (Phase 25U)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.services.live_operation_status import build_operation_cycle_status


def test_operation_status_web_signal_digest_fields(tmp_path: Path) -> None:
  status = build_operation_cycle_status(tmp_path)
  assert "latest_web_signal_artifact_exists" in status
  assert "latest_web_signal_artifact_path" in status
  assert "latest_digest_preview_uses_web_signals" in status
  assert "web_signal_digest_next_recommended_action" in status
