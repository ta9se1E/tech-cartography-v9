"""Digest Preview IAP auth guard tests (Phase 25U.1)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tech_cartography.runtime.live_artifact_paths import ensure_live_artifact_dirs
from tech_cartography.runtime.user_context import AUTH_PROVIDER_GOOGLE_IAP, build_user_context_from_iap_identity
from tech_cartography.services.live_digest_preview import (
  DIGEST_PREVIEW_ACCESS_MESSAGES,
  create_live_digest_preview_from_latest_pack,
  evaluate_digest_preview_access,
)
from tech_cartography.services.live_run_history import list_run_history_entries
from tech_cartography.services.live_web_signal_pack import save_live_web_signal_pack


@pytest.fixture
def sample_pack() -> dict:
  return {
    "theme_name": "Carbon Fiber Intelligence",
    "query": "carbon fiber market",
    "fetched_at": "2026-06-18T12:00:00+00:00",
    "provider": "tavily",
    "candidates": [
      {
        "signal_id": "wsig-aaa",
        "title": "Toray expansion news",
        "url": "https://www.toray.com/news",
        "snippet": "company capacity update",
        "score": 0.9,
        "signal_type": "company_signal",
        "confidence_label": "high",
        "review_status": "needs_human_review",
        "safety_label": "Web Signal candidate",
        "fetched_at": "2026-06-18T12:00:00+00:00",
        "query": "carbon fiber market",
        "provider": "tavily",
        "theme_name": "Carbon Fiber Intelligence",
      },
    ],
    "safety_notice": "candidate only",
    "next_actions": ["Verify primary sources."],
  }


def _iap_admin_context() -> dict:
  return build_user_context_from_iap_identity(
    {
      "email": "ta9se1@gmail.com",
      "user_id": "ta9se1@gmail.com",
      "role": "admin",
      "display_name": "Admin",
      "is_admin": True,
    },
  )


def test_evaluate_digest_preview_access_allows_iap_admin_without_basic_session() -> None:
  allowed, error, message, ctx = evaluate_digest_preview_access(
    login_required=True,
    is_authenticated=False,
    auth_role="member",
    user_context=_iap_admin_context(),
  )
  assert allowed is True
  assert error is None
  assert message == "実行可能"
  assert ctx["auth_provider"] == AUTH_PROVIDER_GOOGLE_IAP
  assert ctx["role"] == "admin"


def test_evaluate_digest_preview_access_blocks_anonymous() -> None:
  allowed, error, message, _ = evaluate_digest_preview_access(
    login_required=True,
    is_authenticated=False,
    auth_role="member",
    user_context=None,
  )
  assert allowed is False
  assert error == "login_required"
  assert message == DIGEST_PREVIEW_ACCESS_MESSAGES["login_required"]


def test_evaluate_digest_preview_access_blocks_iap_member() -> None:
  member_ctx = build_user_context_from_iap_identity(
    {"email": "member@example.com", "user_id": "member@example.com", "role": "member"},
  )
  allowed, error, message, _ = evaluate_digest_preview_access(
    login_required=True,
    is_authenticated=True,
    auth_role="member",
    user_context=member_ctx,
  )
  assert allowed is False
  assert error == "admin_required"
  assert message == "admin権限が必要です。"


def test_create_digest_preview_iap_admin_not_blocked(tmp_path: Path, sample_pack: dict) -> None:
  save_live_web_signal_pack(sample_pack, tmp_path)
  result = create_live_digest_preview_from_latest_pack(
    output_root=tmp_path,
    login_required=True,
    is_authenticated=False,
    auth_role="member",
    user_context=_iap_admin_context(),
  )
  assert result["ok"] is True
  assert result.get("message") != DIGEST_PREVIEW_ACCESS_MESSAGES["login_required"]
  assert Path(result["saved_paths"]["json"]).exists()
  assert Path(result["saved_paths"]["markdown"]).exists()


def test_create_digest_preview_records_user_context_in_run_history(tmp_path: Path, sample_pack: dict) -> None:
  save_live_web_signal_pack(sample_pack, tmp_path)
  create_live_digest_preview_from_latest_pack(
    output_root=tmp_path,
    login_required=True,
    is_authenticated=False,
    auth_role="member",
    user_context=_iap_admin_context(),
  )
  history = list_run_history_entries(tmp_path, limit=100, viewer_user_context=_iap_admin_context())
  digest_runs = [row for row in history if row.get("action_type") in {"live_digest_preview", "live_digest_preview_with_web_signals"}]
  assert digest_runs
  latest = digest_runs[0]
  assert latest.get("user_id") == "ta9se1@gmail.com"
  assert latest.get("auth_provider") == "google_iap"
  assert latest.get("role") == "admin"
  assert latest.get("status") == "success"
  assert latest.get("output_artifact_paths", {}).get("json")
  assert latest.get("output_artifact_paths", {}).get("markdown")


def test_create_digest_with_web_signal_artifact_uses_with_signals_action(
  tmp_path: Path,
  sample_pack: dict,
) -> None:
  ensure_live_artifact_dirs(tmp_path)
  save_live_web_signal_pack(sample_pack, tmp_path)
  collection_path = tmp_path / "outputs" / "live_web_signals" / "live_web_signal_collection_success_20260624.json"
  collection_path.parent.mkdir(parents=True, exist_ok=True)
  collection_path.write_text(
    json.dumps(
      {
        "status": "success",
        "theme_name": "Carbon Fiber Intelligence",
        "queries_used": ["PAN precursor"],
        "result_count": 1,
        "web_signals": [
          {
            "title": "Candidate",
            "url": "https://example.com/a",
            "domain": "example.com",
            "confidence_label": "candidate",
          },
        ],
      },
    ),
    encoding="utf-8",
  )
  result = create_live_digest_preview_from_latest_pack(
    output_root=tmp_path,
    login_required=True,
    is_authenticated=False,
    auth_role="member",
    user_context=_iap_admin_context(),
  )
  assert result["ok"] is True
  assert "Web Signal候補" in (result.get("preview") or {}).get("markdown_body", "")
  history = list_run_history_entries(tmp_path, limit=100, viewer_user_context=_iap_admin_context())
  with_signals = [row for row in history if row.get("action_type") == "live_digest_preview_with_web_signals"]
  assert with_signals
  latest = with_signals[0]
  assert str(collection_path) in (latest.get("source_artifact_paths") or [])
  metadata = latest.get("operation_metadata") or {}
  assert metadata.get("uses_web_signals") is True
  assert metadata.get("candidate_information_only") is True
  assert metadata.get("legal_judgement") is False
  assert metadata.get("no_external_api_call") is True


def test_create_digest_preview_no_external_api(tmp_path: Path, sample_pack: dict) -> None:
  save_live_web_signal_pack(sample_pack, tmp_path)
  with patch("tech_cartography.services.live_web_signal_collector.collect_live_web_signals") as collect_mock:
    result = create_live_digest_preview_from_latest_pack(
      output_root=tmp_path,
      login_required=True,
      is_authenticated=True,
      auth_role="admin",
      user_context=_iap_admin_context(),
    )
  assert result["ok"] is True
  collect_mock.assert_not_called()


def test_create_digest_preview_no_email_send(tmp_path: Path, sample_pack: dict) -> None:
  save_live_web_signal_pack(sample_pack, tmp_path)
  with patch("tech_cartography.delivery.email_sender.send_email_smtp") as send_mock:
    result = create_live_digest_preview_from_latest_pack(
      output_root=tmp_path,
      login_required=True,
      is_authenticated=True,
      auth_role="admin",
      user_context=_iap_admin_context(),
    )
  assert result["ok"] is True
  send_mock.assert_not_called()
