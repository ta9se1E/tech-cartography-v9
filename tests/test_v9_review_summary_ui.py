"""Tests for v9 review summary UI helpers and wiring."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from streamlit.testing.v1 import AppTest

from services_v9.review_state import apply_reviews_to_signals, summarize_reviews
from ui_v9.signal_watch_app import _stable_signal_id
from ui_v9.tabs import _review_progress, _select_adopted_signals, _select_unreviewed_signals

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TABS_SOURCE = (PROJECT_ROOT / "ui_v9" / "tabs.py").read_text(encoding="utf-8")
APP_SOURCE = (PROJECT_ROOT / "ui_v9" / "signal_watch_app.py").read_text(encoding="utf-8")
DIGEST_SOURCE = (PROJECT_ROOT / "services_v9" / "digest_export.py").read_text(encoding="utf-8")


def _signal(signal_id: str | None = "signal_001", **overrides) -> dict:
  signal = {
    "id": signal_id,
    "title": f"title-{signal_id or 'generated'}",
    "type": "patent",
    "source_url": f"https://example.com/{signal_id or 'generated'}",
    "source_name": "Demo Source",
    "published_date": "2026-07-04",
    "summary": "前駆体の比較",
    "tags": ["PAN"],
    "companies": ["Demo Corp"],
    "action": "Watch",
    "score": 0.6,
  }
  signal.update(overrides)
  return signal


def _review(signal_id: str, decision: str, priority: int, reviewed: bool, comment: str = "") -> tuple[str, dict]:
  return (
    signal_id,
    {
      "review_decision": decision,
      "review_priority": priority,
      "review_comment": comment,
      "reviewed": reviewed,
    },
  )


def test_can_apply_reviews_to_signals() -> None:
  signals = [_signal("signal_001")]
  reviewed = apply_reviews_to_signals(signals, dict([_review("signal_001", "採用", 1, True)]))
  assert reviewed[0]["review"]["review_decision"] == "採用"


def test_can_apply_reviews_to_signals_with_existing_ids() -> None:
  signals = [_signal("signal_001"), _signal("signal_002")]
  reviewed = apply_reviews_to_signals(signals, dict([_review("signal_002", "見送り", 3, True)]))
  assert reviewed[1]["review"]["review_decision"] == "見送り"


def test_can_use_stable_id_for_signals_without_id() -> None:
  signal = _signal(None)
  signal.pop("id")
  stable_id = _stable_signal_id(signal, index=0)
  reviewed = apply_reviews_to_signals([{**signal, "id": stable_id}], dict([_review(stable_id, "採用", 1, True)]))
  assert reviewed[0]["review"]["review_decision"] == "採用"


def test_does_not_mutate_original_signals() -> None:
  signals = [_signal("signal_001")]
  original = deepcopy(signals)
  apply_reviews_to_signals(signals, dict([_review("signal_001", "採用", 1, True)]))
  assert signals == original


def test_can_count_adopted_reviews() -> None:
  summary = summarize_reviews(apply_reviews_to_signals([_signal("signal_001", action="Read Now")], dict([_review("signal_001", "採用", 1, True)])))
  assert summary["採用"] == 1


def test_can_count_hold_reviews() -> None:
  summary = summarize_reviews(apply_reviews_to_signals([_signal("signal_001", action="Watch")], dict([_review("signal_001", "保留", 2, True)])))
  assert summary["保留"] == 1


def test_can_count_rejected_reviews() -> None:
  summary = summarize_reviews(apply_reviews_to_signals([_signal("signal_001", action="Ignore")], dict([_review("signal_001", "見送り", 3, True)])))
  assert summary["見送り"] == 1


def test_can_count_unreviewed_reviews() -> None:
  summary = summarize_reviews(apply_reviews_to_signals([_signal("signal_001", action="Watch")], {}))
  assert summary["未レビュー"] == 1


def test_can_count_total_reviews() -> None:
  summary = summarize_reviews(apply_reviews_to_signals([_signal("signal_001"), _signal("signal_002")], {}))
  assert summary["合計"] == 2


def test_can_compute_review_progress() -> None:
  progress = _review_progress({"合計": 10, "未レビュー": 3})
  assert progress["reviewed_count"] == 7
  assert progress["percent"] == 70


def test_progress_is_zero_when_all_unreviewed() -> None:
  progress = _review_progress({"合計": 5, "未レビュー": 5})
  assert progress["percent"] == 0


def test_progress_is_hundred_when_all_reviewed() -> None:
  progress = _review_progress({"合計": 5, "未レビュー": 0})
  assert progress["percent"] == 100


def test_progress_handles_zero_signals() -> None:
  progress = _review_progress({"合計": 0, "未レビュー": 0})
  assert progress["ratio"] == 0.0
  assert progress["percent"] == 0


def test_can_select_adopted_signals() -> None:
  reviewed = apply_reviews_to_signals(
    [_signal("signal_001"), _signal("signal_002")],
    dict([
      _review("signal_001", "採用", 1, True),
      _review("signal_002", "保留", 2, True),
    ]),
  )
  adopted = _select_adopted_signals(reviewed)
  assert len(adopted) == 1
  assert adopted[0]["id"] == "signal_001"


def test_can_select_unreviewed_signals() -> None:
  reviewed = apply_reviews_to_signals([_signal("signal_001"), _signal("signal_002")], {})
  unreviewed = _select_unreviewed_signals(reviewed)
  assert len(unreviewed) == 2


def test_adopted_signals_are_sorted_by_priority() -> None:
  reviewed = apply_reviews_to_signals(
    [_signal("signal_001", score=0.7), _signal("signal_002", score=0.9)],
    dict([
      _review("signal_001", "採用", 2, True),
      _review("signal_002", "採用", 1, True),
    ]),
  )
  adopted = _select_adopted_signals(reviewed)
  assert adopted[0]["id"] == "signal_002"


def test_adopted_signals_are_sorted_by_score_with_same_priority() -> None:
  reviewed = apply_reviews_to_signals(
    [_signal("signal_001", score=0.7), _signal("signal_002", score=0.9)],
    dict([
      _review("signal_001", "採用", 1, True),
      _review("signal_002", "採用", 1, True),
    ]),
  )
  adopted = _select_adopted_signals(reviewed)
  assert adopted[0]["id"] == "signal_002"


def test_select_lists_limit_to_ten() -> None:
  signals = [_signal(f"signal_{index:03d}") for index in range(12)]
  reviews = dict([_review(signal["id"], "採用", 1, True) for signal in signals])
  reviewed = apply_reviews_to_signals(signals, reviews)
  adopted = _select_adopted_signals(reviewed, limit=10)
  assert len(adopted) == 10


def test_demo_like_data_works() -> None:
  reviewed = apply_reviews_to_signals([_signal("demo_001", action="Read Now")], dict([_review("demo_001", "採用", 1, True)]))
  assert summarize_reviews(reviewed)["採用"] == 1


def test_csv_upload_like_data_works() -> None:
  reviewed = apply_reviews_to_signals([_signal("upload_001", source_name="Upload Source", action="Watch")], dict([_review("upload_001", "保留", 2, True)]))
  assert summarize_reviews(reviewed)["保留"] == 1


def test_json_upload_like_data_works() -> None:
  reviewed = apply_reviews_to_signals([_signal("json_001", source_name="JSON Source", action="Ignore")], dict([_review("json_001", "見送り", 3, True)]))
  assert summarize_reviews(reviewed)["見送り"] == 1


def test_other_data_source_reviews_do_not_mix() -> None:
  demo_reviewed = apply_reviews_to_signals([_signal("demo_001")], dict([_review("demo_001", "採用", 1, True)]))
  csv_reviewed = apply_reviews_to_signals([_signal("csv_001")], dict([_review("demo_001", "採用", 1, True)]))
  assert summarize_reviews(demo_reviewed)["採用"] == 1
  assert summarize_reviews(csv_reviewed)["未レビュー"] == 1


def test_ui_code_contains_review_summary_label() -> None:
  assert "レビュー状況" in TABS_SOURCE


def test_ui_code_contains_review_progress_label() -> None:
  assert "レビュー進捗" in TABS_SOURCE


def test_ui_code_contains_adopted_signals_label() -> None:
  assert "採用したシグナル" in TABS_SOURCE


def test_ui_code_contains_unreviewed_signals_label() -> None:
  assert "未レビューのシグナル" in TABS_SOURCE


def test_digest_export_file_is_unchanged_by_review_summary_ui() -> None:
  assert "レビュー状況" not in DIGEST_SOURCE


def test_ui_code_does_not_auto_save_snapshot_for_review_summary() -> None:
  assert "save_snapshot(" not in TABS_SOURCE


def test_ui_code_does_not_call_external_apis() -> None:
  combined_source = TABS_SOURCE + "\n" + APP_SOURCE
  banned_tokens = [
    "import requests",
    "import httpx",
    "from openai",
    "google.generativeai",
    "WebSearch(",
    "CallMcpTool(",
  ]
  assert all(token not in combined_source for token in banned_tokens)


def test_streamlit_testing_finds_review_summary_in_weekly_updates() -> None:
  at = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
  at.run()
  texts = []
  for collection_name in ["markdown", "caption", "info", "warning", "text"]:
    for item in getattr(at, collection_name, []):
      value = getattr(item, "value", None) or getattr(item, "body", None) or getattr(item, "label", None)
      if value:
        texts.append(str(value))
  assert any("レビュー状況" in text for text in texts)
  assert any("レビュー進捗" in text for text in texts)
  assert any("採用したシグナル" in text for text in texts)
  assert any("未レビューのシグナル" in text for text in texts)
