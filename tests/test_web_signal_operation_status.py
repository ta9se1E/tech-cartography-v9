"""Operation status includes external API collection fields (Phase 25T)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.services.live_operation_status import build_operation_cycle_status


def test_operation_status_external_api_fields(tmp_path: Path) -> None:
  status = build_operation_cycle_status(tmp_path)
  assert "external_api_collection" in status
  assert "disable_external_api" in status
  assert "enable_manual_web_signal_collection" in status
  assert "tavily_secret_configured" in status
  assert "latest_web_signal_collection_artifact" in status
