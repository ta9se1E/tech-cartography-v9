"""Tests for v9 human review input UI helpers and wiring."""

from __future__ import annotations

from copy import deepcopy
from pathlib import Path

from streamlit.testing.v1 import AppTest

from services_v9.review_state import default_review_state
from ui_v9.labels import review_priority_label_ja, review_priority_value_ja
from ui_v9.signal_watch_app import _stable_signal_id
from ui_v9.tabs import _get_review_for_signal

PROJECT_ROOT = Path(__file__).resolve().parents[1]
TABS_SOURCE = (PROJECT_ROOT / "ui_v9" / "tabs.py").read_text(encoding="utf-8")
APP_SOURCE = (PROJECT_ROOT / "ui_v9" / "signal_watch_app.py").read_text(encoding="utf-8")
LABELS_SOURCE = (PROJECT_ROOT / "ui_v9" / "labels.py").read_text(encoding="utf-8")
DIGEST_SOURCE = (PROJECT_ROOT / "services_v9" / "digest_export.py").read_text(encoding="utf-8")


def _signal(signal_id: str | None = "signal_001", **overrides) -> dict:
  signal = {
    "id": signal_id,
    "title": "PAN precursor update",
    "type": "patent",
    "source_url": "https://example.com/signal",
    "source_name": "Demo Source",
    "published_date": "2026-07-04",
    "summary": "前駆体の比較",
    "tags": ["PAN"],
    "companies": ["Demo Corp"],
    "action": "Watch",
  }
  signal.update(overrides)
  return signal


def test_default_review_from_read_now() -> None:
  assert default_review_state(_signal(action="Read Now"))["review_decision"] == "採用"


def test_default_review_from_watch() -> None:
  assert default_review_state(_signal(action="Watch"))["review_decision"] == "保留"


def test_default_review_from_ignore() -> None:
  assert default_review_state(_signal(action="Ignore"))["review_decision"] == "見送り"


def test_priority_one_is_high() -> None:
  assert review_priority_label_ja(1) == "高"


def test_priority_two_is_medium() -> None:
  assert review_priority_label_ja(2) == "中"


def test_priority_three_is_low() -> None:
  assert review_priority_label_ja(3) == "低"


def test_high_maps_to_one() -> None:
  assert review_priority_value_ja("高") == 1


def test_medium_maps_to_two() -> None:
  assert review_priority_value_ja("中") == 2


def test_low_maps_to_three() -> None:
  assert review_priority_value_ja("低") == 3


def test_can_generate_stable_signal_id() -> None:
  assert _stable_signal_id(_signal(signal_id=None), index=0).startswith("generated_")


def test_same_signal_generates_same_stable_id() -> None:
  signal = _signal(signal_id=None)
  assert _stable_signal_id(signal, index=0) == _stable_signal_id(signal, index=0)


def test_different_signals_generate_different_stable_ids() -> None:
  assert _stable_signal_id(_signal(signal_id=None, title="A"), 0) != _stable_signal_id(_signal(signal_id=None, title="B"), 0)


def test_signal_with_id_uses_existing_id() -> None:
  assert _stable_signal_id(_signal(signal_id="signal_123"), index=0) == "signal_123"


def test_signal_without_id_does_not_fail() -> None:
  signal = _signal(signal_id=None)
  signal.pop("id")
  assert _stable_signal_id(signal, index=1).startswith("generated_")


def test_get_review_for_signal_returns_default_when_not_saved() -> None:
  signal = _signal(signal_id="signal_001", action="Watch")
  review = _get_review_for_signal(signal, "signal_001", {})
  assert review["review_decision"] == "保留"
  assert review["reviewed"] is False


def test_get_review_for_signal_returns_saved_review_when_present() -> None:
  signal = _signal(signal_id="signal_001")
  review = _get_review_for_signal(
    signal,
    "signal_001",
    {
      "signal_001": {
        "review_decision": "採用",
        "review_priority": 1,
        "review_comment": "今週確認する",
        "reviewed": True,
      }
    },
  )
  assert review["review_decision"] == "採用"
  assert review["review_comment"] == "今週確認する"


def test_multiple_signals_do_not_mix_reviews() -> None:
  reviews = {
    "signal_001": {"review_decision": "採用", "review_priority": 1, "review_comment": "A", "reviewed": True},
    "signal_002": {"review_decision": "見送り", "review_priority": 3, "review_comment": "B", "reviewed": True},
  }
  review_a = _get_review_for_signal(_signal(signal_id="signal_001"), "signal_001", reviews)
  review_b = _get_review_for_signal(_signal(signal_id="signal_002"), "signal_002", reviews)
  assert review_a["review_comment"] == "A"
  assert review_b["review_comment"] == "B"


def test_stable_signal_id_does_not_mutate_original_signal() -> None:
  signal = _signal(signal_id=None)
  original = deepcopy(signal)
  _stable_signal_id(signal, index=0)
  assert signal == original


def test_ui_code_contains_human_review_label() -> None:
  assert "人間レビュー" in TABS_SOURCE


def test_ui_code_contains_review_decision_label() -> None:
  assert "レビュー判断" in TABS_SOURCE


def test_ui_code_contains_review_comment_label() -> None:
  assert "レビューコメント" in LABELS_SOURCE


def test_ui_code_contains_review_apply_label() -> None:
  assert "レビューを反映" in TABS_SOURCE


def test_ui_code_contains_reviews_by_signal_id() -> None:
  assert "reviews_by_signal_id" in APP_SOURCE or "reviews_by_signal_id" in TABS_SOURCE


def test_digest_export_file_is_unchanged_by_review_ui() -> None:
  assert "review_decision" not in DIGEST_SOURCE
  assert "review_comment" not in DIGEST_SOURCE


def test_ui_code_does_not_auto_save_snapshot_for_reviews() -> None:
  assert "review_apply_" in TABS_SOURCE
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


def test_review_widget_keys_include_signal_id() -> None:
  assert 'f"review_decision_{signal_id}"' in TABS_SOURCE
  assert 'f"review_priority_{signal_id}"' in TABS_SOURCE
  assert 'f"review_note_{signal_id}"' in TABS_SOURCE
  assert 'f"review_apply_{signal_id}"' in TABS_SOURCE


def test_top3_does_not_duplicate_review_widgets() -> None:
  at = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
  at.run()
  review_expanders = [expander for expander in at.expander if expander.label == "人間レビュー"]
  review_buttons = [button for button in at.button if button.label == "レビューを反映"]
  assert review_expanders
  assert review_buttons
  assert len(review_expanders) == len(review_buttons)


def test_streamlit_testing_finds_review_widgets() -> None:
  at = AppTest.from_file(str(PROJECT_ROOT / "app.py"))
  at.run()
  assert any(expander.label == "人間レビュー" for expander in at.expander)
  assert any(select.label == "レビュー判断" for select in at.selectbox)
  assert any(select.label == "優先度" for select in at.selectbox)
  assert any(area.label == "レビューコメント" for area in at.text_area)
  assert any(button.label == "レビューを反映" for button in at.button)
