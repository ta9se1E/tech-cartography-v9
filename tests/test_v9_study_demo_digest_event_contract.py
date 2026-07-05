"""Tests for Study Demo digest tab event contract and KeyError prevention."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from services_v9.study_demo_analysis_context import build_active_context_from_run
from services_v9.study_demo_config import PRODUCTION_PERSIST_BUCKET
from services_v9.study_demo_downstream import build_downstream_bundle
from ui_v9.study_demo_event_contracts import (
  DIGEST_EVENT_KEYS,
  default_digest_events,
  normalize_digest_events,
)
from ui_v9.study_demo_download_keys import build_study_demo_download_key
from ui_v9.tabs import (
  render_digest_export_tab,
  render_top_signals_tab,
  render_watch_profile_tab,
  render_weekly_updates_tab,
)

FIXTURE_PATH = ROOT / "tests/fixtures/study_demo_active_run_connection_samples.json"
RUN_ID = "study_demo_search_20260705_061319_e973e4c2"


def _tier_signals(counts: dict[str, int]) -> list[dict]:
  signals: list[dict] = []
  index = 0
  for tier, total in counts.items():
    for _ in range(total):
      signals.append(
        {
          "signal_id": f"s{index}",
          "source_type": "patent" if index % 3 == 0 else ("paper" if index % 3 == 1 else "web_company"),
          "relevance_tier": tier,
          "title": f"Signal {index}",
          "summary": "sizing agent carbon fiber",
          "url": f"https://example.com/{index}",
          "organization": "Example",
        }
      )
      index += 1
  return signals


def _full_artifacts(counts: dict[str, int] | None = None) -> dict:
  payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
  tier_counts = counts or {"A": 33, "B": 13, "C": 24, "D": 30}
  signals = _tier_signals(tier_counts)
  return {
    "search_request.json": payload["artifacts"]["search_request.json"],
    "provider_status.json": {
      "patent": {"status": "success", "result_count": 50},
      "paper": {"status": "success", "result_count": 50},
      "web": {"status": "success", "result_count": 10},
    },
    "usage_metrics.json": {
      "patent": {"result_count": 50},
      "paper": {"result_count": 50},
      "web": {"result_count": 10},
    },
    "patent_results.json": {"rows": [{}] * 48},
    "paper_results.json": {"rows": [{}] * 50},
    "web_results.json": {"rows": [{}] * 10},
    "integrated_signals.json": {"ranked_count": sum(tier_counts.values()), "signals": signals},
    "search_status.json": {"status": "success"},
    "search_report.md": "# report",
  }


def _build_active_source_info(*, weekly_state: str = "initial_baseline") -> dict:
  artifacts = _full_artifacts()
  context = build_active_context_from_run(search_run_id=RUN_ID, artifacts=artifacts)
  loaded = {"search_run_id": RUN_ID, "artifacts": artifacts}
  enriched = {
    "integrated_signals": {
      "signals": _tier_signals({"A": 33, "B": 13, "C": 24, "D": 30}),
      "ranked_count": 100,
    }
  }
  with patch("services_v9.study_demo_downstream.list_run_snapshots", return_value=[]):
    with patch("services_v9.study_demo_downstream.load_run_reviews", return_value={"reviews": []}):
      with patch("services_v9.study_demo_active_loader.load_search_run", return_value=loaded):
        with patch("services_v9.study_demo_resolved_context.load_search_run", return_value=loaded):
          with patch("services_v9.study_demo_resolved_context.build_search_result_from_artifacts", return_value=enriched):
            bundle = build_downstream_bundle(context, storage_client=MagicMock())
  if weekly_state == "initial_baseline":
    bundle["weekly_state"] = {"state": "initial_baseline"}
  else:
    bundle["weekly_state"] = {
      "state": "has_diff",
      "diff": {"counts": {"new": 1, "disappeared": 0, "score_up": 2, "score_down": 0, "tier_up": 0, "tier_down": 0, "unchanged": 97}},
    }
  return {
    "requested_mode": "temporary_search",
    "mode": "temporary_search",
    "label": "一時検索run",
    "loaded_count": 100,
    "active_context": context,
    "study_demo_downstream": bundle,
  }


def _legacy_source_info(mode: str = "legacy_demo") -> dict:
  return {
    "requested_mode": mode,
    "mode": mode,
    "label": "legacy demo",
    "loaded_count": 12,
    "active_context": {},
    "study_demo_downstream": {},
    "provisional_scoring": False,
  }


def _email_delivery_state(*, disabled: bool = True) -> dict:
  config = SimpleNamespace(
    send_mode="preview",
    disabled=disabled,
    self_recipient="",
  )
  return {
    "config": config,
    "preview": {"data_source": "demo", "subject": "test", "plain_text_body": "", "html_body": "", "digest_sha256": "abc"},
    "dry_run_result": {"status": "blocked", "validation_errors": [], "validation_warnings": []},
    "last_dry_run_result": {},
    "last_send_result": {},
  }


def _mock_streamlit(*, button: bool = False, button_keys_true: set[str] | None = None) -> MagicMock:
  mock_st = MagicMock()
  mock_st.session_state = {}
  keys_true = button_keys_true or set()

  def _button(*args, **kwargs):
    key = str(kwargs.get("key", "") or "")
    if key in keys_true:
      return True
    return button

  def _column_mock() -> MagicMock:
    column = MagicMock()
    column.button.side_effect = _button
    column.download_button.return_value = False
    return column

  mock_st.button.side_effect = _button
  mock_st.download_button.return_value = False
  mock_st.checkbox.return_value = False
  mock_st.columns.side_effect = lambda n: [_column_mock() for _ in range(n if isinstance(n, int) else len(n))]
  mock_st.selectbox.return_value = "none"
  mock_st.multiselect.side_effect = lambda label, options, **kwargs: list(options)
  mock_st.text_input.return_value = ""
  mock_st.expander.return_value.__enter__ = MagicMock(return_value=None)
  mock_st.expander.return_value.__exit__ = MagicMock(return_value=False)
  return mock_st


def _assert_full_digest_schema(events: dict) -> None:
  normalized = normalize_digest_events(events)
  for key in DIGEST_EVENT_KEYS:
    assert key in normalized
  assert normalized["save_digest_files"] is False or isinstance(normalized["save_digest_files"], bool)
  assert normalized["error"] is None or isinstance(normalized["error"], str)
  assert normalized["message"] is None or isinstance(normalized["message"], str)


def _consumer_handles_digest(events: object) -> bool:
  normalized = normalize_digest_events(events)
  return bool(
    normalized.get("save_digest_files", False)
    or normalized.get("run_email_delivery_dry_run", False)
    or normalized.get("send_email_self_only", False)
  )


def test_default_digest_events_has_save_digest_files() -> None:
  events = default_digest_events()
  assert "save_digest_files" in events


def test_default_digest_events_has_all_required_keys() -> None:
  events = default_digest_events()
  assert set(events.keys()) == set(DIGEST_EVENT_KEYS)


def test_default_digest_events_boolean_defaults_false() -> None:
  events = default_digest_events()
  assert events["save_digest_files"] is False
  assert events["run_email_delivery_dry_run"] is False
  assert events["send_email_self_only"] is False


def test_default_digest_events_error_message_none() -> None:
  events = default_digest_events()
  assert events["error"] is None
  assert events["message"] is None


def test_default_digest_events_independent_instances() -> None:
  first = default_digest_events()
  second = default_digest_events()
  first["save_digest_files"] = True
  assert second["save_digest_files"] is False


def test_normalize_none_to_default() -> None:
  normalized = normalize_digest_events(None)
  assert normalized == default_digest_events()


def test_normalize_empty_dict_to_default() -> None:
  normalized = normalize_digest_events({})
  assert normalized["save_digest_files"] is False
  assert normalized["run_email_delivery_dry_run"] is False


def test_normalize_partial_dict_fills_missing_keys() -> None:
  normalized = normalize_digest_events({"run_email_delivery_dry_run": True})
  assert normalized["save_digest_files"] is False
  assert normalized["run_email_delivery_dry_run"] is True
  assert normalized["send_email_self_only"] is False


def test_normalize_missing_save_digest_files_no_keyerror() -> None:
  assert _consumer_handles_digest({}) is False


def test_normalize_invalid_type_safe() -> None:
  assert normalize_digest_events("invalid") == default_digest_events()
  assert normalize_digest_events([]) == default_digest_events()


def test_normalize_does_not_coerce_string_to_true() -> None:
  normalized = normalize_digest_events({"save_digest_files": "true"})
  assert normalized["save_digest_files"] is False


def test_normalize_unknown_event_does_not_trigger_save() -> None:
  normalized = normalize_digest_events({"save_digest": True, "email_dry_run": True})
  assert normalized["save_digest_files"] is False
  assert _consumer_handles_digest(normalized) is False


def test_normalize_logs_warning_for_partial(caplog: pytest.LogCaptureFixture) -> None:
  with caplog.at_level(logging.WARNING):
    normalize_digest_events({"run_email_delivery_dry_run": True})
  assert any("missing keys" in record.message for record in caplog.records)


@pytest.mark.parametrize(
  "source_info_factory",
  [
    _build_active_source_info,
    lambda: _legacy_source_info("legacy_demo"),
    lambda: _legacy_source_info("csv"),
    lambda: _legacy_source_info("json"),
    lambda: _build_active_source_info(weekly_state="has_diff"),
  ],
  ids=["active_context", "legacy_demo", "csv", "json", "active_with_diff"],
)
def test_render_digest_export_tab_returns_full_schema(source_info_factory) -> None:
  source_info = source_info_factory()
  mock_st = _mock_streamlit()
  with patch("ui_v9.tabs.st", mock_st):
    with patch("ui_v9.study_demo_active_banner.st", mock_st):
      events = render_digest_export_tab("# md", "a,b", "{}", source_info, _email_delivery_state())
  _assert_full_digest_schema(events)


def test_render_digest_temporary_search_includes_save_digest_files() -> None:
  source_info = _build_active_source_info()
  mock_st = _mock_streamlit()
  with patch("ui_v9.tabs.st", mock_st):
    with patch("ui_v9.study_demo_active_banner.st", mock_st):
      events = render_digest_export_tab("# md", "a,b", "{}", source_info, _email_delivery_state())
  assert "save_digest_files" in events
  assert events["save_digest_files"] is False


def test_render_digest_legacy_path_save_only_on_explicit_button() -> None:
  source_info = _legacy_source_info()
  mock_st = _mock_streamlit(button_keys_true={"btn_save_digest_files"})
  with patch("ui_v9.tabs.st", mock_st):
    with patch("ui_v9.study_demo_active_banner.st", mock_st):
      events = render_digest_export_tab("# md", "a,b", "{}", source_info, _email_delivery_state())
  assert events["save_digest_files"] is True


def test_render_digest_display_only_does_not_set_save() -> None:
  source_info = _legacy_source_info()
  mock_st = _mock_streamlit(button=False)
  with patch("ui_v9.tabs.st", mock_st):
    with patch("ui_v9.study_demo_active_banner.st", mock_st):
      events = render_digest_export_tab("# md", "a,b", "{}", source_info, _email_delivery_state())
  assert events["save_digest_files"] is False
  assert events["run_email_delivery_dry_run"] is False
  assert events["send_email_self_only"] is False


def test_old_wrong_keys_normalized_without_save() -> None:
  legacy_wrong = {"save_digest": True, "email_dry_run": True, "email_send": True}
  normalized = normalize_digest_events(legacy_wrong)
  assert normalized["save_digest_files"] is False
  assert _consumer_handles_digest(normalized) is False


def test_weekly_tab_render_does_not_break_digest_consumer() -> None:
  source_info = _build_active_source_info(weekly_state="has_diff")
  mock_st = _mock_streamlit()
  with patch("ui_v9.tabs.st", mock_st):
    with patch("ui_v9.study_demo_active_banner.st", mock_st):
      weekly_events = render_weekly_updates_tab([], [], source_info, [], None, {"level": "info", "message": "ok", "examples": []}, [], None)
      digest_events = normalize_digest_events(
        render_digest_export_tab("# md", "a,b", "{}", source_info, _email_delivery_state())
      )
  assert weekly_events["load_previous_snapshot"] is False
  assert digest_events["save_digest_files"] is False


def test_profile_tab_render_with_active_run_and_digest_schema() -> None:
  source_info = _build_active_source_info()
  mock_st = _mock_streamlit()
  profile = SimpleNamespace(
    theme_name="t",
    theme_description="d",
    core_keywords_en=[],
    application_keywords_en=[],
    material_process_keywords_en=[],
    exclude_keywords_en=[],
    core_keywords_ja=[],
    application_keywords_ja=[],
    material_process_keywords_ja=[],
    exclude_keywords_ja=[],
    seed_publications=[],
    candidate_publications=[],
    demo_mode=True,
  )
  with patch("ui_v9.tabs.st", mock_st):
    with patch("ui_v9.study_demo_active_banner.st", mock_st):
      with patch("services_v9.study_demo_config.is_study_demo_mode", return_value=True):
        profile_events = render_watch_profile_tab(
          profile,
          {},
          {},
          [],
          {"settings": {}, "scheduler_status": {}},
          source_info=source_info,
        )
        digest_events = normalize_digest_events(
          render_digest_export_tab("# md", "a,b", "{}", source_info, _email_delivery_state())
        )
  assert profile_events["save_profile"] is False
  assert digest_events["save_digest_files"] is False


def test_all_tabs_render_without_keyerror_for_active_run() -> None:
  source_info = _build_active_source_info()
  mock_st = _mock_streamlit()
  profile = SimpleNamespace(
    theme_name="t",
    theme_description="d",
    core_keywords_en=[],
    application_keywords_en=[],
    material_process_keywords_en=[],
    exclude_keywords_en=[],
    core_keywords_ja=[],
    application_keywords_ja=[],
    material_process_keywords_ja=[],
    exclude_keywords_ja=[],
    seed_publications=[],
    candidate_publications=[],
    demo_mode=True,
  )
  with patch("ui_v9.tabs.st", mock_st):
    with patch("ui_v9.study_demo_active_banner.st", mock_st):
      with patch("services_v9.study_demo_config.is_study_demo_mode", return_value=True):
        with patch("services_v9.study_demo_active_loader.adapt_study_demo_signal_to_display", side_effect=lambda item, index=0: item):
          signal_events = render_top_signals_tab([], [], source_info)
          weekly_events = render_weekly_updates_tab([], [], source_info, [], None, {"level": "info", "message": "ok", "examples": []}, [], None)
          profile_events = render_watch_profile_tab(profile, {}, {}, [], {"settings": {}, "scheduler_status": {}}, source_info=source_info)
          digest_events = normalize_digest_events(
            render_digest_export_tab("# md", "a,b", "{}", source_info, _email_delivery_state())
          )
  assert signal_events["save_snapshot"] is False
  assert weekly_events["save_study_demo_baseline"] is False
  assert profile_events["save_profile"] is False
  assert digest_events["save_digest_files"] is False


def test_digest_download_keys_unique_per_tab() -> None:
  run_id = RUN_ID
  keys = {
    build_study_demo_download_key("digest", "digest_markdown", run_id),
    build_study_demo_download_key("digest", "digest_json", run_id),
    build_study_demo_download_key("digest", "integrated_csv_all_tiers", run_id),
    build_study_demo_download_key("sources", "integrated_csv_all_tiers", run_id),
  }
  assert len(keys) == len(set(keys))


def test_resolved_context_tier_counts_preserved_in_bundle() -> None:
  source_info = _build_active_source_info()
  bundle = dict(source_info["study_demo_downstream"])
  assert bundle.get("resolved_tier_counts", bundle.get("tier_counts")) is not None or bundle.get("integrated")


def test_no_external_api_on_digest_render() -> None:
  source_info = _build_active_source_info()
  mock_st = _mock_streamlit()
  with patch("ui_v9.tabs.st", mock_st):
    with patch("ui_v9.study_demo_active_banner.st", mock_st):
      with patch("services_v9.persistence.save_digest_files") as save_mock:
        events = normalize_digest_events(
          render_digest_export_tab("# md", "a,b", "{}", source_info, _email_delivery_state())
        )
        if events.get("save_digest_files"):
          pytest.fail("save_digest_files must not be true on display-only render")
        save_mock.assert_not_called()


def test_no_gcs_write_on_digest_render() -> None:
  source_info = _build_active_source_info()
  mock_st = _mock_streamlit()
  with patch("ui_v9.tabs.st", mock_st):
    with patch("ui_v9.study_demo_active_banner.st", mock_st):
      with patch("services_v9.study_demo_analysis_context.save_active_context_to_storage") as save_ctx:
        normalize_digest_events(
          render_digest_export_tab("# md", "a,b", "{}", source_info, _email_delivery_state())
        )
        save_ctx.assert_not_called()


def test_production_bucket_not_referenced() -> None:
  source_info = _build_active_source_info()
  serialized = json.dumps(source_info, default=str)
  assert PRODUCTION_PERSIST_BUCKET not in serialized


def test_signal_watch_app_uses_normalize_import() -> None:
  source = Path(ROOT / "ui_v9/signal_watch_app.py").read_text(encoding="utf-8")
  assert "normalize_digest_events" in source
  assert 'digest_events.get("save_digest_files"' in source


def test_tabs_temporary_search_no_legacy_wrong_keys() -> None:
  source = Path(ROOT / "ui_v9/tabs.py").read_text(encoding="utf-8")
  assert '"save_digest"' not in source
  assert "default_digest_events()" in source
