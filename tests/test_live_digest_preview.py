"""Tests for live digest preview service (Phase 25F)."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from tech_cartography.runtime.cloud_run_config import DISABLE_EMAIL_SEND_ENV
from tech_cartography.services.live_digest_preview import (
  PREVIEW_ONLY_LABEL,
  SAFETY_NOTICE,
  build_digest_subject,
  can_create_live_digest_preview,
  create_live_digest_preview_from_latest_pack,
  generate_live_digest_preview,
  save_live_digest_preview,
  select_key_signals,
  validate_preview_language,
)
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
      {
        "signal_id": "wsig-bbb",
        "title": "NEDO project page",
        "url": "https://www.nedo.go.jp/project",
        "snippet": "grant funding",
        "score": 0.7,
        "signal_type": "public_project_signal",
        "confidence_label": "medium",
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


def test_generate_preview_from_pack(sample_pack: dict) -> None:
  preview = generate_live_digest_preview(
    sample_pack,
    source_pack_path="/tmp/pack.json",
    recipient_group_name="炭素繊維R&Dチーム",
    user_note="weekly share draft",
  )
  assert preview["subject"].startswith("[Tech Cartography]")
  assert "Carbon Fiber Intelligence" in preview["subject"]
  assert len(preview["key_signals"]) <= 3
  assert preview["key_signals"][0]["title"] == "Toray expansion news"
  assert preview["safety_notice"] == SAFETY_NOTICE
  assert preview["preview_mode"] == PREVIEW_ONLY_LABEL
  assert "key_signals" in preview
  assert "next_actions" in preview
  assert "evidence_gaps" in preview
  assert "PREVIEW ONLY" in preview["plain_text_body"]
  assert validate_preview_language(preview["plain_text_body"]) == []


def test_body_does_not_treat_signals_as_confirmed_facts(sample_pack: dict) -> None:
  preview = generate_live_digest_preview(sample_pack, source_pack_path="pack.json")
  body = preview["plain_text_body"] + preview["markdown_body"]
  assert "candidate" in body.lower() or "候補" in body
  assert "needs_human_review" in body or "確認" in body
  lowered = body.lower()
  assert "infringement confirmed" not in lowered
  assert "fto cleared" not in lowered


def test_can_create_preview_when_email_send_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
  monkeypatch.setenv(DISABLE_EMAIL_SEND_ENV, "true")
  allowed, message = can_create_live_digest_preview()
  assert allowed is True
  assert "preview" in message.lower()


def test_save_preview_excludes_api_key(tmp_path: Path, sample_pack: dict) -> None:
  preview = generate_live_digest_preview(sample_pack, source_pack_path="pack.json")
  saved = save_live_digest_preview(preview, tmp_path)
  json_text = Path(saved["json"]).read_text(encoding="utf-8")
  assert "api_key" not in json_text.lower()
  assert "TAVILY_API_KEY" not in json_text
  assert preview["subject"] in json_text


def test_create_from_latest_pack_success(tmp_path: Path, sample_pack: dict) -> None:
  save_live_web_signal_pack(sample_pack, tmp_path)
  result = create_live_digest_preview_from_latest_pack(
    output_root=tmp_path,
    recipient_group_name="Team A",
    login_required=True,
    is_authenticated=True,
    auth_role="admin",
  )
  assert result["ok"] is True
  assert result["preview"]["subject"]
  assert Path(result["saved_paths"]["json"]).exists()


def test_create_blocked_for_non_admin(tmp_path: Path, sample_pack: dict) -> None:
  save_live_web_signal_pack(sample_pack, tmp_path)
  result = create_live_digest_preview_from_latest_pack(
    output_root=tmp_path,
    login_required=True,
    is_authenticated=True,
    auth_role="member",
  )
  assert result["ok"] is False
  assert result["error"] == "admin_required"
  assert result["message"] == "admin権限が必要です。"


def test_no_email_send_function_called(tmp_path: Path, sample_pack: dict) -> None:
  save_live_web_signal_pack(sample_pack, tmp_path)
  with patch("tech_cartography.delivery.email_sender.send_email_smtp") as send_mock:
    result = create_live_digest_preview_from_latest_pack(
      output_root=tmp_path,
      login_required=True,
      is_authenticated=True,
      auth_role="admin",
    )
  assert result["ok"] is True
  send_mock.assert_not_called()


def test_select_key_signals_limits_to_three(sample_pack: dict) -> None:
  many = list(sample_pack["candidates"])
  for idx in range(5):
    item = dict(many[0])
    item["signal_id"] = f"wsig-{idx}"
    item["score"] = idx * 0.1
    many.append(item)
  selected = select_key_signals(many, limit=3)
  assert len(selected) == 3


def test_build_digest_subject_with_group() -> None:
  subject = build_digest_subject(theme_name="Theme", recipient_group_name="R&D")
  assert "R&D" in subject
