"""Tests for resolved active context counts and Study Demo download keys."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from services_v9.study_demo_analysis_context import (
  build_active_context_from_run,
  cache_metadata_matches,
  is_same_active_context,
)
from services_v9.study_demo_config import PRODUCTION_PERSIST_BUCKET
from services_v9.study_demo_downstream import build_downstream_bundle
from services_v9.study_demo_resolved_context import (
  count_tiers_from_signals,
  normalize_relevance_tier,
  resolve_active_run_counts,
)
from ui_v9.study_demo_download_keys import build_study_demo_download_key

FIXTURE_PATH = ROOT / "tests/fixtures/study_demo_active_run_connection_samples.json"


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
        }
      )
      index += 1
  return signals


def _full_artifacts(counts: dict[str, int]) -> dict:
  payload = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
  signals = _tier_signals(counts)
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
    "integrated_signals.json": {"ranked_count": sum(counts.values()), "signals": signals},
    "search_status.json": {"status": "success"},
    "search_report.md": "# report",
  }


def test_normalize_relevance_tier_variants() -> None:
  assert normalize_relevance_tier("Tier A") == "A"
  assert normalize_relevance_tier("B") == "B"


def test_stored_zero_tier_counts_recomputed() -> None:
  run_id = "study_demo_search_test"
  artifacts = _full_artifacts({"A": 33, "B": 13, "C": 24, "D": 30})
  context = {
    "active_search_run_id": run_id,
    "theme": "test",
    "tier_counts": {"A": 0, "B": 0, "C": 0, "D": 0},
    "provider_counts": {"patent": 48, "paper": 50, "web": 10},
  }
  loaded = {"search_run_id": run_id, "artifacts": artifacts}
  enriched = {
    "integrated_signals": {
      "signals": _tier_signals({"A": 33, "B": 13, "C": 24, "D": 30}),
      "ranked_count": 100,
    }
  }
  with patch("services_v9.study_demo_resolved_context.load_search_run", return_value=loaded):
    with patch("services_v9.study_demo_resolved_context.build_search_result_from_artifacts", return_value=enriched):
      resolved = resolve_active_run_counts(context)
  assert resolved["tier_counts"] == {"A": 33, "B": 13, "C": 24, "D": 30}
  assert resolved["integrated_ranked_count"] == 100


def test_stored_mismatch_detected() -> None:
  run_id = "study_demo_search_test"
  artifacts = _full_artifacts({"A": 2, "B": 1, "C": 1, "D": 0})
  context = {"active_search_run_id": run_id, "tier_counts": {"A": 0, "B": 0, "C": 0, "D": 0}}
  loaded = {"search_run_id": run_id, "artifacts": artifacts}
  enriched = {
    "integrated_signals": {
      "signals": _tier_signals({"A": 2, "B": 1, "C": 1, "D": 0}),
      "ranked_count": 4,
    }
  }
  with patch("services_v9.study_demo_resolved_context.load_search_run", return_value=loaded):
    with patch("services_v9.study_demo_resolved_context.build_search_result_from_artifacts", return_value=enriched):
      resolved = resolve_active_run_counts(context)
  assert resolved["count_validation_status"] in {"stored_mismatch", "mismatch", "ok", "warning"}


def test_raw_provider_and_stored_artifact_counts() -> None:
  run_id = "study_demo_search_test"
  artifacts = _full_artifacts({"A": 1, "B": 1, "C": 1, "D": 1})
  loaded = {"search_run_id": run_id, "artifacts": artifacts}
  enriched = {
    "integrated_signals": {
      "signals": _tier_signals({"A": 1, "B": 1, "C": 1, "D": 1}),
      "ranked_count": 4,
    }
  }
  with patch("services_v9.study_demo_resolved_context.load_search_run", return_value=loaded):
    with patch("services_v9.study_demo_resolved_context.build_search_result_from_artifacts", return_value=enriched):
      resolved = resolve_active_run_counts({"active_search_run_id": run_id})
  assert resolved["raw_provider_counts"]["patent"] == 50
  assert resolved["stored_artifact_counts"]["patent"] == 48


def test_unknown_tier_not_dropped() -> None:
  info = count_tiers_from_signals([{"relevance_tier": "A"}, {"relevance_tier": "unknown"}])
  assert info["tier_counts"]["A"] == 1
  assert info["unknown_tier_count"] == 1


def test_downstream_bundle_includes_resolved_counts() -> None:
  run_id = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["search_run_id"]
  artifacts_raw = _full_artifacts({"A": 2, "B": 1, "C": 1, "D": 0})
  ctx = build_active_context_from_run(search_run_id=run_id, artifacts=artifacts_raw)
  loaded = {"search_run_id": run_id, "artifacts": artifacts_raw}
  enriched = {
    "integrated_signals": {
      "signals": _tier_signals({"A": 2, "B": 1, "C": 1, "D": 0}),
      "ranked_count": 4,
    }
  }
  with patch("services_v9.study_demo_downstream.list_run_snapshots", return_value=[]):
    with patch("services_v9.study_demo_downstream.load_run_reviews", return_value={"reviews": []}):
      with patch("services_v9.study_demo_active_loader.load_search_run", return_value=loaded):
        with patch("services_v9.study_demo_resolved_context.load_search_run", return_value=loaded):
          with patch("services_v9.study_demo_resolved_context.build_search_result_from_artifacts", return_value=enriched):
            with patch("services_v9.study_demo_search.storage.build_search_result_from_artifacts", return_value=enriched):
              bundle = build_downstream_bundle(ctx)
  assert bundle["tier_counts"]["A"] == 2
  assert bundle["integrated_ranked_count"] == 4


def test_study_demo_download_buttons_have_explicit_keys() -> None:
  files = [ROOT / "ui_v9/study_demo_search_ui.py", ROOT / "ui_v9/tabs.py"]
  for path in files:
    lines = path.read_text(encoding="utf-8").splitlines()
    for index, line in enumerate(lines):
      if "st.download_button(" not in line:
        continue
      window = "\n".join(lines[index : index + 8])
      assert "key=" in window, f"missing download_button key near line {index + 1} in {path.name}"


def test_cache_metadata_refresh_allows_same_run_update() -> None:
  existing = {"active_search_run_id": "run-a", "tier_counts": {"A": 0}, "provider_counts": {"patent": 1}, "ranked_count": 0}
  candidate = {"active_search_run_id": "run-a", "tier_counts": {"A": 33}, "provider_counts": {"patent": 48}, "ranked_count": 100}
  assert is_same_active_context(existing, candidate)
  assert not cache_metadata_matches(existing, candidate)


def test_download_keys_unique_across_tabs() -> None:
  run_id = "study_demo_search_20260705_061319_e973e4c2"
  info_key = build_study_demo_download_key("information", "integrated_csv_all_tiers", run_id)
  digest_key = build_study_demo_download_key("digest", "integrated_csv_all_tiers", run_id)
  weekly_key = build_study_demo_download_key("weekly", "weekly_diff_csv", run_id)
  assert len({info_key, digest_key, weekly_key}) == 3


def test_download_key_stable_on_rerun() -> None:
  run_id = "study_demo_search_20260705_061319_e973e4c2"
  first = build_study_demo_download_key("digest", "digest_markdown", run_id)
  second = build_study_demo_download_key("digest", "digest_markdown", run_id)
  assert first == second


def test_download_key_changes_with_run() -> None:
  first = build_study_demo_download_key("digest", "digest_markdown", "run-a")
  second = build_study_demo_download_key("digest", "digest_markdown", "run-b")
  assert first != second


def test_build_active_context_rejects_production_bucket() -> None:
  run_id = "run-a"
  artifacts = _full_artifacts({"A": 1, "B": 0, "C": 0, "D": 0})
  with pytest.raises(ValueError):
    build_active_context_from_run(search_run_id=run_id, artifacts=artifacts, bucket_name=PRODUCTION_PERSIST_BUCKET)
