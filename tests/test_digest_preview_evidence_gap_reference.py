"""Digest Preview evidence gap reference tests (Phase 25V)."""

from __future__ import annotations

import json
from pathlib import Path

from tech_cartography.runtime.live_artifact_paths import ensure_live_artifact_dirs, get_live_evidence_gaps_dir
from tech_cartography.services.live_digest_preview import attach_strategic_watch_artifact_references, generate_live_digest_preview


def test_attach_references_read_only(tmp_path: Path) -> None:
  ensure_live_artifact_dirs(tmp_path)
  gap_dir = get_live_evidence_gaps_dir(tmp_path)
  gap_path = gap_dir / "live_evidence_gap_test.json"
  gap_path.write_text(
    json.dumps({"evidence_gaps": [{"gap_id": "g1"}], "next_verification_actions": [{"action": "verify"}]}),
    encoding="utf-8",
  )
  pack = {
    "theme_name": "Theme",
    "candidates": [
      {
        "signal_id": "s1",
        "title": "Signal",
        "url": "https://example.com",
        "snippet": "s",
        "signal_type": "company_signal",
        "confidence_label": "medium",
        "review_status": "needs_human_review",
        "score": 0.5,
      },
    ],
  }
  preview = generate_live_digest_preview(pack, source_pack_path="/tmp/pack.json")
  merged = attach_strategic_watch_artifact_references(preview, tmp_path)
  assert merged.get("latest_evidence_gap_artifact_path")
  assert "Strategic Watch References" in merged.get("markdown_body", "")
  assert "collect_live_web_signals" not in Path(
    "src/tech_cartography/services/live_digest_preview.py",
  ).read_text(encoding="utf-8")
