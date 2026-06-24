"""Safety guards for Web Signal digest integration (Phase 25U)."""

from __future__ import annotations

from pathlib import Path

REVIEW_PATH = Path(__file__).resolve().parents[1] / "src/tech_cartography/services/live_web_signal_review.py"
READER_PATH = Path(__file__).resolve().parents[1] / "src/tech_cartography/services/live_web_signal_artifact_reader.py"
DIGEST_PATH = Path(__file__).resolve().parents[1] / "src/tech_cartography/services/live_digest_preview.py"

FORBIDDEN = ("smtplib", "send_email", "cloudscheduler", "urllib.request", "_default_post_tavily")


def test_review_and_reader_no_external_api() -> None:
  for path in (REVIEW_PATH, READER_PATH):
    text = path.read_text(encoding="utf-8").lower()
    for token in FORBIDDEN:
      assert token not in text


def test_digest_integrates_without_auto_collect() -> None:
  text = DIGEST_PATH.read_text(encoding="utf-8")
  assert "integrate_review_into_preview" in text
  assert "collect_live_web_signals" not in text
  assert "evaluate_digest_preview_access" in text


def test_review_has_candidate_only_notice() -> None:
  text = REVIEW_PATH.read_text(encoding="utf-8")
  assert "candidate_only_notice" in text
  assert "CANDIDATE_ONLY_NOTICE" in text
