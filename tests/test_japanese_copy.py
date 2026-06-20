"""Tests for Japanese copy policy (Phase 24.1.1)."""

from __future__ import annotations

from tech_cartography.delivery.japanese_copy import (
  PREVIEW_ONLY_NOTICE_EN,
  build_digest_item_title,
  clean_digest_title,
  ja_caveats,
  ja_next_action,
  ja_preview_only_notice,
  ja_status_label,
  render_japanese_important_caveats,
)


def test_ja_status_label_draft_saved() -> None:
  assert ja_status_label("draft_saved") == "下書き保存済み"


def test_ja_caveats_include_japanese_final_conclusion() -> None:
  caveats = ja_caveats()
  assert any("最終結論ではありません" in item for item in caveats)
  assert any("確認候補" in item for item in caveats)


def test_ja_next_action_translates_verify_public_funding() -> None:
  result = ja_next_action(
    "Verify public funding / project page and thematic overlap with patent claims.",
  )
  assert "公的プロジェクト" in result
  assert "Claim Element" in result


def test_clean_digest_title_removes_pdf_prefix_and_trailing_agency() -> None:
  raw = "[PDF] 革新的新構造材料等研究開発 - NEDO"
  assert clean_digest_title(raw) == "革新的新構造材料等研究開発（PDF）"


def test_clean_digest_title_glossary_reference() -> None:
  raw = "[PDF] (添付-2) プロジェクト用語集 - NEDO"
  assert clean_digest_title(raw) == "プロジェクト用語集（参考資料）"


def test_build_digest_item_title_natural_japanese() -> None:
  item = {
    "related_web_signal_title": "[PDF] 革新的新構造材料等研究開発 - NEDO",
    "related_web_signal_domain": "nedo.go.jp",
    "watch_theme": "CFRP signal",
    "watch_type": "national_project_signal",
  }
  title = build_digest_item_title(item)
  assert title.startswith("NEDO:")
  assert "[PDF]" not in title
  assert " - NEDO" not in title
  assert "（PDF）" in title


def test_render_japanese_important_caveats_without_english_by_default() -> None:
  md = render_japanese_important_caveats(include_english_notes=False)
  assert "重要な注意事項" in md
  assert "English Notes" not in md
  assert PREVIEW_ONLY_NOTICE_EN not in md


def test_render_japanese_important_caveats_with_english_notes() -> None:
  md = render_japanese_important_caveats(include_english_notes=True)
  assert "English Notes" in md
  assert "signal candidates" in md


def test_ja_preview_only_notice_japanese() -> None:
  notice = ja_preview_only_notice()
  assert "プレビューのみ" in notice
  assert "Email sending is disabled" not in notice
