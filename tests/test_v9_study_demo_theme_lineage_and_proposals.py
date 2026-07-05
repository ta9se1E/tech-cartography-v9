"""Theme lineage and review proposal tests for Study Demo Stage C5A."""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))

from services_v9.study_demo_analysis_context import build_active_context_from_run
from services_v9.study_demo_downstream import build_downstream_bundle, save_run_review, summarize_run_reviews
from services_v9.study_demo_review_proposals import apply_approved_proposals_to_profile_draft, generate_review_proposals
from services_v9.study_demo_review_schema import (
  DECISION_ACCEPT,
  DECISION_HOLD,
  DECISION_REJECT,
  normalize_decision,
  normalize_review_record,
  validate_review_record,
)
from services_v9.study_demo_theme_lineage import (
  build_search_plan_from_watch_profile,
  build_search_run_lineage,
  build_theme_record,
  build_watch_profile_from_theme,
  bump_theme_version,
  compute_theme_signature,
  default_saved_theme_fixture,
  enrich_active_context_with_lineage,
  infer_run_origin,
  lineage_blocks_search_on_mismatch,
  promote_temporary_search_to_theme_draft,
  sizing_fixture_theme,
  summarize_lineage_status,
  theme_dirty,
  validate_theme_lineage,
)

FIXTURE_PATH = ROOT / "tests" / "fixtures" / "study_demo_active_run_connection_samples.json"


def _load_fixture() -> dict:
  return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))


def _sample_theme(**overrides: object) -> dict:
  theme = sizing_fixture_theme()
  theme.update(overrides)
  theme["theme_signature"] = compute_theme_signature(theme)
  return theme


def _fake_storage(artifacts: dict, run_id: str = "study_demo_search_test") -> object:
  prefix = f"search_runs/{run_id}/"

  class _Blob:
    def __init__(self, name: str, payload: bytes | None = None):
      self.name = name
      self._payload = payload

    def exists(self) -> bool:
      return self._payload is not None

    def download_as_bytes(self) -> bytes:
      return self._payload or b"{}"

    def upload_from_string(self, data: str, content_type: str = "") -> None:
      self._payload = data.encode("utf-8")

  class _Bucket:
    def __init__(self, objects: dict[str, bytes]):
      self._objects = objects

    def blob(self, name: str) -> _Blob:
      return _Blob(name, self._objects.get(name))

    def list_blobs(self, *, prefix: str = ""):
      for name, payload in self._objects.items():
        if name.startswith(prefix):
          yield _Blob(name, payload)

  class _Client:
    def bucket(self, _name: str) -> _Bucket:
      return _Bucket(objects)

  objects = {f"{prefix}{key}": json.dumps(value, ensure_ascii=False).encode("utf-8") for key, value in artifacts.items()}
  return _Client()


class TestThemeLineage:
  def test_same_theme_same_signature(self) -> None:
    a = build_theme_record({"name": "A", "description": "desc", "keywords": {"core_en": ["fiber"]}})
    b = build_theme_record({"name": "A", "description": "desc", "keywords": {"core_en": ["fiber"]}})
    assert compute_theme_signature(a) == compute_theme_signature(b)

  def test_content_change_changes_signature(self) -> None:
    a = build_theme_record({"name": "A", "keywords": {"core_en": ["fiber"]}})
    b = build_theme_record({"name": "B", "keywords": {"core_en": ["fiber"]}})
    assert compute_theme_signature(a) != compute_theme_signature(b)

  def test_timestamp_only_does_not_change_signature(self) -> None:
    base = build_theme_record({"name": "A", "keywords": {"core_en": ["fiber"]}})
    sig1 = compute_theme_signature(base)
    mutated = copy.deepcopy(base)
    mutated["updated_at"] = "2099-01-01T00:00:00+00:00"
    assert compute_theme_signature(mutated) == sig1

  def test_theme_version_increment(self) -> None:
    theme = _sample_theme(theme_version=1)
    bumped = bump_theme_version(theme)
    assert bumped["theme_version"] == 2
    assert bumped["theme_id"] == theme["theme_id"]

  def test_watch_profile_keeps_theme_lineage(self) -> None:
    theme = _sample_theme(status="saved")
    profile = build_watch_profile_from_theme(theme)
    assert profile["source_theme_id"] == theme["theme_id"]
    assert profile["source_theme_signature"] == theme["theme_signature"]

  def test_search_plan_keeps_profile_lineage(self) -> None:
    theme = _sample_theme(status="saved")
    profile = build_watch_profile_from_theme(theme)
    plan = build_search_plan_from_watch_profile(profile, theme, provider_limits={"patent": 5, "paper": 5, "web": 5})
    assert plan["source_watch_profile_signature"] == profile["watch_profile_signature"]
    assert plan["source_theme_signature"] == theme["theme_signature"]

  def test_search_run_lineage_watch_profile(self) -> None:
    theme = _sample_theme(status="saved")
    profile = build_watch_profile_from_theme(theme)
    plan = build_search_plan_from_watch_profile(profile, theme)
    run = build_search_run_lineage(
      search_run_id="run1",
      search_plan=plan,
      theme=theme,
      watch_profile=profile,
      run_origin="watch_profile",
    )
    assert run["run_origin"] == "watch_profile"
    assert run["source_search_plan_id"] == plan["search_plan_id"]

  def test_active_context_enrichment(self) -> None:
    fixture = _load_fixture()
    ctx = build_active_context_from_run(
      search_run_id=fixture["search_run_id"],
      artifacts=fixture["artifacts"],
      bucket_name="demo-bucket",
    )
    assert ctx.get("run_origin") == "temporary_search"
    assert ctx.get("lineage_status") == "temporary_unconnected"

  def test_temporary_search_unconnected(self) -> None:
    status = summarize_lineage_status({"run_origin": "temporary_search", "theme": "active theme"})
    assert status["lineage_status"] == "temporary_unconnected"

  def test_watch_profile_connected(self) -> None:
    ctx = {
      "run_origin": "watch_profile",
      "source_theme_id": "t1",
      "source_watch_profile_id": "wp1",
      "source_search_plan_id": "plan1",
    }
    assert summarize_lineage_status(ctx)["lineage_status"] == "connected"

  def test_signature_mismatch_blocks_search(self) -> None:
    ctx = {"lineage_status": "mismatch", "run_origin": "watch_profile"}
    assert lineage_blocks_search_on_mismatch(ctx)

  def test_legacy_context_backward_compatible(self) -> None:
    legacy = {"theme": "old", "active_search_run_id": "run", "context_type": "temporary_search"}
    enriched = enrich_active_context_with_lineage(legacy, search_request={"theme": "old"})
    assert enriched.get("run_origin") == "temporary_search"

  def test_secret_not_in_lineage(self) -> None:
    theme = _sample_theme()
    blob = json.dumps(theme)
    assert "password" not in blob
    assert "api_key" not in blob

  def test_validate_lineage_detects_mismatch(self) -> None:
    theme = _sample_theme(status="saved")
    profile = build_watch_profile_from_theme(theme)
    profile["source_theme_signature"] = "deadbeef"
    errors = validate_theme_lineage({"theme": theme, "watch_profile": profile, "search_plan": {}, "search_run": {}})
    assert any("signature mismatch" in item for item in errors)


class TestThemeFlow:
  def test_dirty_state(self) -> None:
    saved = _sample_theme(status="saved")
    dirty = build_theme_record({**saved, "name": "changed"})
    assert theme_dirty(saved, dirty)

  def test_promote_temporary_search_draft(self) -> None:
    req = _load_fixture()["artifacts"]["search_request.json"]
    draft = promote_temporary_search_to_theme_draft(req, search_run_id="run123")
    assert draft["source"] == "promoted_from_temporary_search"
    assert draft["source_search_run_id"] == "run123"
    assert draft["status"] == "draft"

  def test_promote_does_not_overwrite_saved_theme(self) -> None:
    saved = default_saved_theme_fixture()
    draft = promote_temporary_search_to_theme_draft(
      _load_fixture()["artifacts"]["search_request.json"],
      search_run_id="run123",
    )
    assert draft["theme_id"] != saved["theme_id"]


class TestReviewSchema:
  def test_decision_normalization(self) -> None:
    assert normalize_decision("accepted") == DECISION_ACCEPT
    assert normalize_decision("pending") == DECISION_HOLD
    assert normalize_decision("rejected") == DECISION_REJECT
    assert normalize_decision("採用") == DECISION_ACCEPT

  def test_reason_codes_multiple(self) -> None:
    record = normalize_review_record(
      {"decision": "accept", "reason_codes": ["direct_evidence", "important_company_signal"], "reviewed": True},
      signal_id="s1",
      search_run_id="run1",
    )
    assert len(record["reason_codes"]) == 2

  def test_reason_missing_warning(self) -> None:
    record = normalize_review_record({"decision": "accept", "reviewed": True}, signal_id="s1", search_run_id="run1")
    assert "reason_codes_missing" in validate_review_record(record)


class TestProposalEngine:
  def _signal(self, signal_id: str, **kwargs: object) -> dict:
    base = {
      "signal_id": signal_id,
      "title": "Bio-based aqueous polyurethane sizing agent",
      "summary": "interfacial adhesion drying",
      "organization": "Toray Industries",
      "source_type": "patent",
      "metadata": {"cpc_codes": ["D01F"]},
    }
    base.update(kwargs)
    return base

  def _review(self, signal_id: str, decision: str, reasons: list[str]) -> dict:
    return normalize_review_record(
      {"decision": decision, "reason_codes": reasons, "reviewed": True},
      signal_id=signal_id,
      search_run_id="run1",
    )

  def test_reject_one_no_exclude(self) -> None:
    reviews = [self._review("s1", "reject", ["theme_mismatch"])]
    signals = [self._signal("s1", title="textile fabric noise")]
    payload = generate_review_proposals(reviews=reviews, signals=signals, source_run_id="run1")
    assert not any(item["proposal_type"] == "add_exclude_keyword" for item in payload["proposals"])

  def test_reject_three_exclude_candidate(self) -> None:
    reviews = [
      self._review("s1", "reject", ["commercial_noise"]),
      self._review("s2", "reject", ["commercial_noise"]),
      self._review("s3", "reject", ["commercial_noise"]),
    ]
    signals = [
      self._signal("s1", title="textile fabric commercial"),
      self._signal("s2", title="textile fabric commercial"),
      self._signal("s3", title="textile fabric commercial"),
    ]
    payload = generate_review_proposals(reviews=reviews, signals=signals, source_run_id="run1")
    exclude = [item for item in payload["proposals"] if item["proposal_type"] == "add_exclude_keyword"]
    assert exclude
    assert exclude[0]["recall_risk"] == "high"

  def test_duplicate_not_used_for_exclude(self) -> None:
    reviews = [
      self._review("s1", "reject", ["duplicate"]),
      self._review("s2", "reject", ["duplicate"]),
      self._review("s3", "reject", ["duplicate"]),
    ]
    payload = generate_review_proposals(
      reviews=reviews,
      signals=[self._signal("s1"), self._signal("s2"), self._signal("s3")],
      source_run_id="run1",
    )
    assert not any(item["proposal_type"] == "add_exclude_keyword" for item in payload["proposals"])

  def test_company_boost_two(self) -> None:
    reviews = [
      self._review("s1", "accept", ["important_company_signal"]),
      self._review("s2", "accept", ["important_company_signal"]),
    ]
    signals = [
      self._signal("s1", organization="Toray Industries"),
      self._signal("s2", organization="Toray Industries"),
    ]
    payload = generate_review_proposals(reviews=reviews, signals=signals, source_run_id="run1")
    assert any(item["proposal_type"] == "boost_company" for item in payload["proposals"])

  def test_idempotent_proposal_set(self) -> None:
    reviews = [self._review("s1", "accept", ["direct_evidence"])]
    signals = [self._signal("s1")]
    first = generate_review_proposals(reviews=reviews, signals=signals, source_run_id="run1")
    second = generate_review_proposals(reviews=reviews, signals=signals, source_run_id="run1")
    assert first["proposal_set_id"] == second["proposal_set_id"]


class TestProfileDraft:
  def test_approved_only_profile_draft(self) -> None:
    theme = _sample_theme(status="saved")
    profile = build_watch_profile_from_theme(theme)
    proposal = {
      "proposal_id": "p1",
      "proposal_type": "add_include_keyword",
      "proposed_value": "interfacial",
      "normalized_value": "interfacial",
    }
    draft = apply_approved_proposals_to_profile_draft(
      base_profile=profile,
      approved_proposals=[proposal],
      source_review_run_ids=["run1"],
      theme_id=theme["theme_id"],
    )
    assert draft["status"] == "draft_not_applied"
    assert draft["base_profile_id"] == profile["watch_profile_id"]


class TestDownstreamIntegration:
  def test_bundle_includes_lineage_and_proposals(self) -> None:
    fixture = _load_fixture()
    ctx = build_active_context_from_run(
      search_run_id=fixture["search_run_id"],
      artifacts=fixture["artifacts"],
      bucket_name="demo-bucket",
    )
    client = _fake_storage(fixture["artifacts"], run_id=fixture["search_run_id"])
    bundle = build_downstream_bundle(ctx, storage_client=client, environ={"V9_STUDY_DEMO_MODE": "true", "V9_STUDY_DEMO_BUCKET": "demo"})
    assert bundle.get("lineage_status")
    assert bundle.get("review_proposals")
    assert bundle.get("enriched_context")


class TestUIWiring:
  def test_theme_tab_has_lineage_sections(self) -> None:
    text = (ROOT / "ui_v9" / "tabs.py").read_text(encoding="utf-8")
    assert "render_standard_theme_section" in text
    assert "render_active_analysis_target_section" in text

  def test_lineage_banner_wired(self) -> None:
    text = (ROOT / "ui_v9" / "study_demo_active_banner.py").read_text(encoding="utf-8")
    assert "render_lineage_banner" in text


class TestSafetyRegression:
  def test_infer_run_origin_temporary(self) -> None:
    assert infer_run_origin({"theme": "x", "keywords_en": "a"}) == "temporary_search"

  def test_save_run_review_schema(self, monkeypatch: pytest.MonkeyPatch) -> None:
    class _Blob:
      payload: bytes | None = None

      def exists(self) -> bool:
        return self.payload is not None

      def download_as_bytes(self) -> bytes:
        return self.payload or json.dumps({"search_run_id": "run1", "reviews": []}).encode()

      def upload_from_string(self, data: str, content_type: str = "") -> None:
        self.payload = data.encode()

    class _Bucket:
      def blob(self, _name: str) -> _Blob:
        return _Blob()

    class _Client:
      def bucket(self, _name: str) -> _Bucket:
        return _Bucket()

    monkeypatch.setenv("V9_STUDY_DEMO_MODE", "true")
    monkeypatch.setenv("V9_STUDY_DEMO_BUCKET", "demo-bucket")
    payload = save_run_review(
      search_run_id="run1",
      signal_id="s1",
      decision="accept",
      comment="ok",
      reason_codes=["direct_evidence"],
      storage_client=_Client(),
    )
    saved = payload["reviews"][0]
    assert saved["decision"] == "accept"
    assert saved["reason_codes"] == ["direct_evidence"]
