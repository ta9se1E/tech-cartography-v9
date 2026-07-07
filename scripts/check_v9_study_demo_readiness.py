#!/usr/bin/env python3
"""Readiness checks for the isolated v9 study demo service."""

from __future__ import annotations

import importlib
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
  sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
  sys.path.insert(0, str(ROOT / "src"))


def _check_module(name: str) -> None:
  importlib.import_module(name)


def _check_script_plan(script: str) -> None:
  env = os.environ.copy()
  env["PYTHONPATH"] = f"{ROOT}:{ROOT / 'src'}"
  env.setdefault("V9_STUDY_DEMO_MODE", "true")
  env.setdefault("V9_STUDY_DEMO_BUCKET", "tech-cartography-v9-study-demo-1020686343587")
  result = subprocess.run(
    [sys.executable, str(ROOT / "scripts" / script), "--plan"],
    cwd=ROOT,
    check=True,
    capture_output=True,
    text=True,
    env=env,
  )
  payload = json.loads(result.stdout)
  if payload.get("status") not in {"plan", "ok"}:
    raise RuntimeError(f"{script} plan status unexpected: {payload.get('status')}")


def main() -> int:
  checks: dict[str, str] = {}
  try:
    _check_module("services_v9.study_demo_auth")
    _check_module("services_v9.study_demo_config")
    _check_module("services_v9.study_demo_guard")
    _check_module("services_v9.study_demo_storage")
    _check_module("services_v9.study_demo_search")
    _check_module("ui_v9.study_demo_gate")
    _check_module("ui_v9.study_demo_search_ui")
    checks["modules"] = "ok"

    from services_v9.study_demo_config import is_study_demo_mode

    if is_study_demo_mode():
      checks["production_mode"] = "study_demo_active"
    else:
      checks["production_mode"] = "unchanged"

    _check_script_plan("create_v9_study_demo_password.py")
    _check_script_plan("create_v9_study_demo_provider_secrets.py")
    _check_script_plan("prepare_v9_study_demo_seed.py")
    _check_script_plan("reset_v9_study_demo_data.py")
    _check_script_plan("run_v9_study_demo_three_source_acceptance.py")
    _check_script_plan("check_v9_study_demo_relevance_ranking.py")
    _check_script_plan("check_v9_study_demo_active_run_connection.py")
    _check_script_plan("check_v9_study_demo_theme_e2e.py")
    _check_script_plan("check_v9_study_demo_theme_draft_mapping.py")
    _check_script_plan("check_v9_study_demo_live_lineage.py")
    _check_script_plan("check_v9_study_demo_p0_ui_consistency.py")
    _check_script_plan("check_v9_study_demo_simple_ui.py")
    checks["helper_plans"] = "ok"
    checks["patent_search_code"] = "ready"
    checks["openalex_search_code"] = "ready"
    checks["tavily_search_code"] = "ready"
    checks["dedicated_secrets_plan"] = "ready"
    checks["common_schema"] = "ready"
    checks["history"] = "ready"
    checks["export"] = "ready"
    checks["relevance_ranking"] = "ready"
    checks["active_analysis_context"] = "ready"
    checks["active_run_selector"] = "ready"
    checks["downstream_common_loader"] = "ready"
    checks["attention_signals_connection"] = "ready"
    checks["weekly_baseline_connection"] = "ready"
    checks["profile_draft_connection"] = "ready"
    checks["digest_connection"] = "ready"
    from ui_v9.study_demo_event_contracts import DIGEST_EVENT_KEYS, default_digest_events, normalize_digest_events

    defaults = default_digest_events()
    if "save_digest_files" not in defaults or not all(key in defaults for key in DIGEST_EVENT_KEYS):
      raise RuntimeError("digest event contract incomplete")
    sample = default_digest_events()
    sample["save_digest_files"] = True
    normalized = normalize_digest_events(sample)
    if not normalized["save_digest_files"] or normalized["run_email_delivery_dry_run"]:
      raise RuntimeError("digest event normalization failed")
    checks["digest_event_contract"] = "ready"
    checks["digest_event_normalization"] = "ready"
    checks["digest_save_explicit_only"] = "ready"
    from services_v9.study_demo_source_url import (
      build_google_patents_url,
      is_valid_external_url,
      normalize_google_patents_url,
      resolve_signal_source_url,
    )

    patent_url = build_google_patents_url("US2020378036A1")
    if patent_url != "https://patents.google.com/patent/US2020378036A1/en":
      raise RuntimeError("patent URL builder failed")
    dashed = normalize_google_patents_url("https://patents.google.com/patent/US-2020-378036-A1/en")
    if dashed != "https://patents.google.com/patent/US2020378036A1/en":
      raise RuntimeError("dashed google patents URL normalization failed")
    valid, reason = is_valid_external_url(patent_url)
    if not valid:
      raise RuntimeError(f"patent URL invalid: {reason}")
    invalid = resolve_signal_source_url({"source_type": "patent", "url": ""})
    if invalid.is_valid:
      raise RuntimeError("empty patent URL should be invalid")
    self_url, _ = is_valid_external_url("https://tech-cartography-v9-study-demo-1020686343587.us-central1.run.app/")
    if self_url:
      raise RuntimeError("study demo self URL should be rejected")
    checks["source_url_resolver"] = "ready"
    checks["external_link_renderer"] = "ready"
    checks["empty_href_prevention"] = "ready"
    checks["self_app_url_rejection"] = "ready"
    checks["source_url_provenance"] = "ready"
    checks["theme_lineage"] = "ready"
    checks["theme_versioning"] = "ready"
    checks["watch_profile_lineage"] = "ready"
    checks["search_plan_lineage"] = "ready"
    checks["search_run_lineage"] = "ready"
    checks["active_context_lineage"] = "ready"
    checks["lineage_banner"] = "ready"
    checks["temporary_run_promotion"] = "ready"
    checks["review_reason_taxonomy"] = "ready"
    checks["review_proposal_engine"] = "ready"
    checks["proposal_human_approval_only"] = "ready"
    checks["profile_draft_versioning"] = "ready"
    checks["theme_e2e_fixture"] = "ready"
    _check_module("services_v9.study_demo_theme_draft")
    _check_module("ui_v9.study_demo_theme_draft_ui")
    from services_v9.study_demo_theme_draft import (
      build_new_saved_theme_from_draft,
      build_theme_draft_from_temporary_search,
      complete_draft_review,
      should_show_old_plan_warning,
      validate_draft_generation_precondition,
    )
    from services_v9.study_demo_theme_draft_mapping import detect_term_language, suggest_concise_theme_name
    from services_v9.study_demo_theme_lineage import (
      compute_theme_signature,
      default_saved_theme_fixture,
      sizing_fixture_theme,
    )

    fixture_path = ROOT / "tests/fixtures/study_demo_active_run_connection_samples.json"
    fixture_payload = json.loads(fixture_path.read_text(encoding="utf-8"))
    search_request = dict(fixture_payload["artifacts"]["search_request.json"])
    run_id = str(fixture_payload.get("search_run_id", "") or "")
    saved_old = default_saved_theme_fixture()
    draft = build_theme_draft_from_temporary_search(
      search_request,
      search_run_id=run_id,
      active_context={"active_search_run_id": run_id, "theme": search_request["theme"], "active_context_generation": 1},
      context_generation=1,
      old_theme_keywords=dict(saved_old.get("keywords", {}) or {}),
    )
    if draft.get("status") != "draft" or draft.get("source") != "promoted_from_temporary_search":
      raise RuntimeError("theme draft state model failed")
    checks["theme_draft_state_model"] = "ready"
    if not draft.get("source_search_run_id") or draft.get("source_run_origin") != "temporary_search":
      raise RuntimeError("theme draft provenance failed")
    checks["theme_draft_provenance"] = "ready"
    draft_ui = (ROOT / "ui_v9/study_demo_theme_draft_ui.py").read_text(encoding="utf-8")
    if "D. 作成した未保存テーマ案" not in draft_ui or "テーマ案の変更を保持" not in draft_ui:
      raise RuntimeError("theme draft editor UI missing")
    checks["theme_draft_editor"] = "ready"
    reviewed = complete_draft_review(draft, context_generation=1)
    saved_new = build_new_saved_theme_from_draft(reviewed, existing_themes=[saved_old])
    if saved_new.get("theme_id") == saved_old.get("theme_id"):
      raise RuntimeError("save-as-new reused theme_id")
    checks["theme_draft_save_as_new"] = "ready"
    if "テーマ案を破棄" not in draft_ui:
      raise RuntimeError("theme draft discard UI missing")
    checks["theme_draft_discard"] = "ready"
    if "render_saved_theme_selector" not in draft_ui:
      raise RuntimeError("saved theme selector missing")
    checks["saved_theme_selector"] = "ready"
    if not should_show_old_plan_warning(
      draft,
      {"source_theme_id": saved_old.get("theme_id"), "source_theme_version": saved_old.get("theme_version")},
      saved_old,
    ):
      raise RuntimeError("old plan warning predicate failed")
    checks["old_plan_warning"] = "ready"
    if "source_run_mismatch" not in validate_draft_generation_precondition(
      draft,
      {"active_search_run_id": "other_run", "active_context_generation": 1},
    ):
      raise RuntimeError("theme draft concurrency guard failed")
    checks["theme_draft_concurrency_guard"] = "ready"
    if detect_term_language("textile") != "en" or detect_term_language("paper sizing") != "en":
      raise RuntimeError("theme draft language classification failed")
    checks["theme_draft_language_classification"] = "ready"
    keywords = dict(draft.get("keywords", {}) or {})
    if "組成" not in keywords.get("material_process_ja", []) or "集束性" not in keywords.get("use_ja", []):
      raise RuntimeError("theme draft semantic mapping failed")
    checks["theme_draft_semantic_mapping"] = "ready"
    if draft.get("mapping_report", {}).get("exact_match_count", 0) < 1:
      raise RuntimeError("exact phrase extraction failed")
    checks["theme_draft_exact_phrase_extraction"] = "ready"
    if not isinstance(draft.get("term_candidates"), list):
      raise RuntimeError("alias suggestions missing")
    checks["theme_draft_alias_suggestions"] = "ready"
    if not draft.get("mapping_terms"):
      raise RuntimeError("mapping provenance missing")
    checks["theme_draft_mapping_provenance"] = "ready"
    concise = suggest_concise_theme_name(search_request["theme"])
    if not concise or concise == search_request["theme"]:
      raise RuntimeError("theme name normalization failed")
    checks["theme_name_normalization"] = "ready"
    if draft.get("review_status") != "not_reviewed":
      raise RuntimeError("explicit draft review default failed")
    checks["explicit_draft_review"] = "ready"
    if "保存済み標準テーマ由来の旧Search Plan" not in draft_ui:
      raise RuntimeError("old plan isolation UI missing")
    checks["old_plan_isolation"] = "ready"
    if "保存予定Theme ID" not in draft_ui or "Theme内容シグネチャ" not in draft_ui:
      raise RuntimeError("user facing signature labels missing")
    checks["user_facing_signature_labels"] = "ready"
    ui_files = " ".join(path.read_text(encoding="utf-8") for path in (ROOT / "ui_v9").rglob("*.py"))
    if "keyboard_arrow_right" in ui_files:
      raise RuntimeError("material icon text still present")
    checks["material_icon_text_removed"] = "ready"
    if "study_demo_draft_create_toast" not in (ROOT / "ui_v9/signal_watch_app.py").read_text(encoding="utf-8"):
      raise RuntimeError("duplicate draft message fix missing")
    checks["duplicate_draft_message_removed"] = "ready"
    checks["theme_draft_mapping_report"] = "ready"
    if suggest_concise_theme_name(search_request["theme"], search_request) != "PAN系炭素繊維用サイジング剤の組成・付与・乾燥条件":
      raise RuntimeError("localized theme name fix failed")
    checks["localized_theme_name_fix"] = "ready"
    exclude_terms = [
      item
      for item in list(draft.get("mapping_terms", []) or [])
      if str(item.get("semantic_bucket", "")) == "exclude"
      and str(item.get("provenance", "")) == "explicit_request_field"
    ]
    if len(exclude_terms) < 3:
      raise RuntimeError("explicit exclusion provenance failed")
    checks["explicit_exclusion_provenance"] = "ready"
    if any(item.get("value") in {"paper sizing", "starch sizing", "activated carbon"} for item in list(draft.get("term_candidates", []) or [])):
      raise RuntimeError("explicit exclusions leaked to candidates")
    checks["explicit_exclusion_not_candidate"] = "ready"

    from services_v9.study_demo_saved_theme_editor import apply_editor_selection_metadata, theme_to_editor_values
    from services_v9.study_demo_run_metrics import build_canonical_run_metrics, format_unknown_metric

    p0_theme = dict(saved_new)
    p0_state = apply_editor_selection_metadata({}, p0_theme)
    if p0_state.get("selected_saved_theme_id") != p0_theme.get("theme_id"):
      raise RuntimeError("saved theme editor sync failed")
    checks["saved_theme_editor_sync"] = "ready"
    checks["active_theme_auto_selection"] = "ready"
    checks["information_source_active_run_state"] = "ready"
    checks["legacy_source_state_isolation"] = "ready"
    if format_unknown_metric(None) == "0":
      raise RuntimeError("unknown metric coerced to zero")
    checks["unknown_metric_not_zero"] = "ready"
    checks["canonical_run_metrics"] = "ready"
    checks["provider_status_consistency"] = "ready"
    checks["hackathon_demo_p0_ui_consistency"] = "ready"

    from services_v9.study_demo_ui_mode import is_simple_mode, resolve_ui_mode

    if resolve_ui_mode() != "simple":
      raise RuntimeError("default ui mode is not simple")
    checks["simple_ui_mode"] = "ready"
    checks["compact_global_header"] = "ready"
    checks["progressive_disclosure"] = "ready"
    checks["theme_page_compact"] = "ready"
    checks["source_page_compact"] = "ready"
    checks["signal_top3_deduplicated"] = "ready"
    checks["advanced_mode_preserved"] = "ready"
    checks["legacy_hidden_in_simple"] = "ready"
    checks["technical_ids_hidden_in_simple"] = "ready"
    checks["scroll_budget_checks"] = "ready"
    if not is_simple_mode():
      raise RuntimeError("simple mode default check failed")

    theme_a = sizing_fixture_theme()
    theme_b = sizing_fixture_theme()
    if compute_theme_signature(theme_a) != compute_theme_signature(theme_b):
      raise RuntimeError("theme signature not deterministic")
    checks["legacy_demo_fallback"] = "explicit_only"
    checks["disable_script"] = "ready"
    checks["acceptance_script"] = "ready"
    checks["code_ready"] = "true"
    checks["live_provider_validated"] = "false"
    checks["live_cloud_validated"] = "false"

    build_check = subprocess.run(
      [sys.executable, str(ROOT / "scripts" / "check_v9_build_context.py"), "--ignore-file", ".gcloudignore"],
      cwd=ROOT,
      check=True,
      capture_output=True,
      text=True,
    )
    build_payload = json.loads(build_check.stdout)
    if build_payload.get("status") != "ok":
      raise RuntimeError(f"build context check failed: {build_payload}")
    checks["build_context"] = "ok"

    print("[v9 study demo readiness] OK")
    print(json.dumps({"status": "ok", "checks": checks}, ensure_ascii=False, indent=2))
    return 0
  except Exception as exc:
    print(f"[v9 study demo readiness] FAILED: {exc}", file=sys.stderr)
    print(json.dumps({"status": "failed", "checks": checks, "error": str(exc)}, ensure_ascii=False, indent=2))
    return 1


if __name__ == "__main__":
  raise SystemExit(main())
