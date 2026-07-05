"""Live watch profile lineage loader and active context normalization tests."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from services_v9.study_demo_analysis_context import (
  ALLOWED_CONTEXT_TYPES,
  build_active_context_from_run,
  detect_context_lineage_inconsistency,
  normalize_active_context_types,
  validate_active_context,
)
from services_v9.study_demo_live_lineage_loader import (
  hydrate_theme_lineage_session_state,
  lineage_refs_from_search_request,
  pick_active_saved_theme,
  resolve_display_search_plan,
)
from services_v9.study_demo_theme_lineage import (
  build_search_plan_from_watch_profile,
  build_search_run_lineage,
  build_watch_profile_from_theme,
  default_saved_theme_fixture,
  enrich_active_context_with_lineage,
  sizing_fixture_theme,
  summarize_lineage_status,
)


def _sample_saved_theme(**overrides: object) -> dict:
  theme = sizing_fixture_theme()
  theme.update({"theme_id": "theme_6d2dfb753f7e", "status": "saved", **overrides})
  from services_v9.study_demo_theme_lineage import compute_theme_signature

  theme["theme_signature"] = compute_theme_signature(theme)
  return theme


def _watch_profile_chain() -> tuple[dict, dict, dict]:
  theme = _sample_saved_theme()
  profile = build_watch_profile_from_theme(theme)
  plan = build_search_plan_from_watch_profile(
    profile,
    theme,
    provider_limits={"patent": 5, "paper": 5, "web": 5},
  )
  plan["validation_status"] = "ready_for_execution"
  return theme, profile, plan


class TestActiveContextTypes:
  def test_watch_profile_context_type_allowed(self) -> None:
    assert "watch_profile" in ALLOWED_CONTEXT_TYPES

  def test_normalize_watch_profile_run(self) -> None:
    ctx = normalize_active_context_types(
      {"run_origin": "watch_profile", "context_type": "temporary_search", "active_data_source": "temporary_search"}
    )
    assert ctx["context_type"] == "watch_profile"
    assert ctx["active_data_source"] == "watch_profile"

  def test_detect_context_run_origin_mismatch(self) -> None:
    errors = detect_context_lineage_inconsistency(
      {"run_origin": "watch_profile", "context_type": "temporary_search"}
    )
    assert "context_type_run_origin_mismatch" in errors

  def test_validate_watch_profile_context(self) -> None:
    ctx = {
      "schema_version": 1,
      "context_type": "watch_profile",
      "active_search_run_id": "run1",
      "source_prefix": "search_runs/run1/",
    }
    assert not validate_active_context(ctx)


class TestEnrichActiveContext:
  def test_watch_profile_request_preserves_existing_refs(self) -> None:
    theme, profile, plan = _watch_profile_chain()
    request = {
      "run_origin": "watch_profile",
      "source_theme_id": theme["theme_id"],
      "source_theme_version": theme["theme_version"],
      "source_theme_signature": theme["theme_signature"],
      "source_watch_profile_id": profile["watch_profile_id"],
      "source_watch_profile_version": profile["watch_profile_version"],
      "source_watch_profile_signature": profile["watch_profile_signature"],
      "source_search_plan_id": plan["search_plan_id"],
      "source_search_plan_version": plan["search_plan_version"],
      "source_search_plan_signature": plan["search_plan_signature"],
    }
    base = {
      "active_search_run_id": "run1",
      "context_type": "watch_profile",
      "run_origin": "watch_profile",
      **lineage_refs_from_search_request(request),
    }
    enriched = enrich_active_context_with_lineage(base, search_request=request)
    assert enriched["source_theme_id"] == theme["theme_id"]
    assert enriched["source_search_plan_id"] == plan["search_plan_id"]
    assert enriched["context_type"] == "watch_profile"
    assert summarize_lineage_status(enriched)["lineage_status"] == "connected"

  def test_request_without_plan_id_uses_source_fields(self) -> None:
    theme, profile, plan = _watch_profile_chain()
    request = {
      "run_origin": "watch_profile",
      "source_theme_id": theme["theme_id"],
      "source_theme_version": theme["theme_version"],
      "source_theme_signature": theme["theme_signature"],
      "source_watch_profile_id": profile["watch_profile_id"],
      "source_watch_profile_version": profile["watch_profile_version"],
      "source_watch_profile_signature": profile["watch_profile_signature"],
      "source_search_plan_id": plan["search_plan_id"],
      "source_search_plan_version": plan["search_plan_version"],
      "source_search_plan_signature": plan["search_plan_signature"],
    }
    lineage = build_search_run_lineage(
      search_run_id="run1",
      search_plan=None,
      theme=None,
      watch_profile=None,
      run_origin="watch_profile",
      search_request=request,
    )
    assert lineage["source_search_plan_id"] == plan["search_plan_id"]

  def test_legacy_temporary_search_backward_compatible(self) -> None:
    legacy = {"theme": "old", "active_search_run_id": "run", "context_type": "temporary_search"}
    enriched = enrich_active_context_with_lineage(legacy, search_request={"theme": "old"})
    assert enriched.get("run_origin") == "temporary_search"


class TestThemeSelector:
  def test_pick_active_saved_theme_by_context(self) -> None:
    theme, _, _ = _watch_profile_chain()
    default = default_saved_theme_fixture()
    picked = pick_active_saved_theme([default, theme], active_context={"source_theme_id": theme["theme_id"]})
    assert picked["theme_id"] == theme["theme_id"]

  def test_signature_mismatch_does_not_auto_select(self) -> None:
    theme, _, _ = _watch_profile_chain()
    default = default_saved_theme_fixture()
    picked = pick_active_saved_theme(
      [default, theme],
      active_context={"source_theme_id": theme["theme_id"], "source_theme_signature": "deadbeef"},
    )
    assert picked["theme_id"] == default["theme_id"]

  def test_hydrate_sets_saved_themes_and_plan(self) -> None:
    theme, profile, plan = _watch_profile_chain()

    class _Blob:
      def __init__(self, name: str, payload: bytes):
        self.name = name
        self._payload = payload

      def download_as_bytes(self) -> bytes:
        return self._payload

    class _Bucket:
      def list_blobs(self, *, prefix: str = ""):
        yield _Blob(f"themes/{theme['theme_id']}/latest.json", json.dumps(theme).encode())
        yield _Blob(f"themes/theme_default_saved/latest.json", json.dumps(default_saved_theme_fixture()).encode())

    class _Client:
      def bucket(self, _name: str) -> _Bucket:
        return _Bucket()

    from services_v9.study_demo_lineage_storage import (
      search_plan_latest_path,
      theme_latest_path,
      watch_profile_latest_path,
    )

    def _load(path: str, **kwargs: object) -> dict:
      mapping = {
        theme_latest_path(theme["theme_id"]): theme,
        watch_profile_latest_path(profile["watch_profile_id"]): profile,
        search_plan_latest_path(plan["search_plan_id"]): plan,
      }
      if path not in mapping:
        raise FileNotFoundError(path)
      return dict(mapping[path])

    import services_v9.study_demo_live_lineage_loader as loader_mod

    original = loader_mod.load_json_object
    loader_mod.load_json_object = _load  # type: ignore[assignment]
    try:
      ctx = {
        "source_theme_id": theme["theme_id"],
        "source_theme_signature": theme["theme_signature"],
        "source_watch_profile_id": profile["watch_profile_id"],
        "source_watch_profile_signature": profile["watch_profile_signature"],
        "source_search_plan_id": plan["search_plan_id"],
        "source_search_plan_signature": plan["search_plan_signature"],
      }
      state = hydrate_theme_lineage_session_state(ctx, storage_client=_Client(), environ={"V9_STUDY_DEMO_MODE": "true"})
    finally:
      loader_mod.load_json_object = original  # type: ignore[assignment]

    theme_ids = {item["theme_id"] for item in state["saved_themes"]}
    assert "theme_6d2dfb753f7e" in theme_ids
    assert "theme_default_saved" in theme_ids
    assert state["search_plan"]["search_plan_id"] == plan["search_plan_id"]
    assert state["live_lineage_hydrated"] is True


class TestSearchPlanDisplay:
  def test_resolve_display_plan_prefers_active_lineage(self) -> None:
    theme, _, plan = _watch_profile_chain()
    state = {
      "selected_saved_theme_id": theme["theme_id"],
      "active_lineage_search_plan": plan,
      "search_plan": plan,
    }
    ctx = {"source_theme_id": theme["theme_id"]}
    assert resolve_display_search_plan(active_context=ctx, theme_state=state)["search_plan_id"] == plan["search_plan_id"]

  def test_selected_other_theme_loads_that_plan(self, monkeypatch: pytest.MonkeyPatch) -> None:
    theme, _, plan = _watch_profile_chain()
    default = default_saved_theme_fixture()

    def _fake_load(theme_id: str, **kwargs: object) -> dict:
      if theme_id == default["theme_id"]:
        profile = build_watch_profile_from_theme(default)
        old_plan = build_search_plan_from_watch_profile(profile, default)
        return {"theme": default, "watch_profile": profile, "search_plan": old_plan}
      return {"theme": theme, "watch_profile": None, "search_plan": None}

    monkeypatch.setattr(
      "services_v9.study_demo_live_lineage_loader.load_lineage_for_theme_id",
      _fake_load,
    )
    state = {"selected_saved_theme_id": default["theme_id"], "active_lineage_search_plan": plan}
    ctx = {"source_theme_id": theme["theme_id"]}
    display = resolve_display_search_plan(active_context=ctx, theme_state=state)
    assert display["source_theme_id"] == default["theme_id"]


class TestBuildActiveContextFromRun:
  def test_watch_profile_run_sets_context_type(self) -> None:
    theme, profile, plan = _watch_profile_chain()
    artifacts = {
      "search_request.json": {
        "theme": theme["name"],
        "run_origin": "watch_profile",
        "source_theme_id": theme["theme_id"],
        "source_watch_profile_id": profile["watch_profile_id"],
        "source_search_plan_id": plan["search_plan_id"],
      },
      "integrated_signals.json": {"signals": [], "tier_counts": {"A": 3, "B": 2, "C": 3, "D": 7}},
    }
    ctx = build_active_context_from_run(search_run_id="run1", artifacts=artifacts, bucket_name="demo-bucket")
    assert ctx["context_type"] == "watch_profile"
    assert ctx["run_origin"] == "watch_profile"
