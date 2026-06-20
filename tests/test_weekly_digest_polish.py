"""Tests for weekly digest polish (Phase 24.1 / 24.1.1 / 24.2.1)."""

from __future__ import annotations

from pathlib import Path

from tech_cartography.delivery.digest_diff import DigestDiff, deduplicate_bullets_or_lines
from tech_cartography.delivery.email_outbox import (
  STATUS_DRAFT_SAVED,
  STATUS_SENT,
  build_email_draft_from_weekly_digest,
  save_email_sent,
)
from tech_cartography.delivery.japanese_copy import (
  build_digest_item_title,
  ja_caveats_for_mode,
  ja_email_preamble,
)
from tech_cartography.delivery.weekly_digest import (
  PREVIEW_ONLY_NOTICE,
  build_weekly_digest,
  select_diverse_top_watch_items,
  summarize_link_candidates_for_digest,
  truncate_at_sentence_boundary,
)
from tests.test_digest_diff import _write_snapshot_fixture


def _sample_items() -> list[dict[str, str]]:
  return [
    {
      "watch_theme": "CFRP / carbon fiber national project signal",
      "watch_type": "national_project_signal",
      "watch_priority": "high",
      "related_web_signal_title": "NEDO CFRP高レート生産技術開発",
      "related_web_signal_domain": "nedo.go.jp",
      "related_paper_title": "",
      "link_score": "0.9",
    },
    {
      "watch_theme": "CFRP / carbon fiber national project signal",
      "watch_type": "national_project_signal",
      "watch_priority": "high",
      "related_web_signal_title": "JST PAN系炭素繊維表面処理プロジェクト",
      "related_web_signal_domain": "jst.go.jp",
      "related_paper_title": "",
      "link_score": "0.85",
    },
    {
      "watch_theme": "CFRP / carbon fiber national project signal",
      "watch_type": "money_signal",
      "watch_priority": "medium",
      "related_web_signal_title": "NEDO 低コスト炭素繊維 / 水素タンク用途",
      "related_web_signal_domain": "nedo.go.jp",
      "related_paper_title": "",
      "link_score": "0.7",
    },
    {
      "watch_theme": "CFRP / carbon fiber national project signal",
      "watch_type": "patent_paper_web_signal",
      "watch_priority": "medium",
      "related_web_signal_title": "",
      "related_paper_title": "Carbon fiber surface treatment review",
      "link_score": "0.6",
    },
  ]


def test_select_diverse_top_watch_items_avoids_same_theme_only() -> None:
  selected = select_diverse_top_watch_items(_sample_items(), top_n=3)
  assert len(selected) == 3
  web_titles = [item.get("related_web_signal_title", "") for item in selected]
  assert len({title for title in web_titles if title}) >= 2


def test_select_diverse_top_watch_items_spreads_watch_type() -> None:
  selected = select_diverse_top_watch_items(_sample_items(), top_n=3)
  types = {item.get("watch_type") for item in selected}
  assert len(types) >= 2


def test_truncate_at_sentence_boundary_uses_japanese_period() -> None:
  text = "これは重要な監視候補です。次にNEDOの一次資料を確認してください。さらに詳細な確認が必要です。"
  result = truncate_at_sentence_boundary(text, max_chars=30)
  assert result.endswith("（要確認）")
  assert "確認" not in result[-20:] or "。" in result


def test_truncate_at_sentence_boundary_short_text_unchanged() -> None:
  assert truncate_at_sentence_boundary("短い文", max_chars=220) == "短い文"


def test_build_digest_item_title_uses_web_signal_source() -> None:
  item = _sample_items()[0]
  title = build_digest_item_title(item)
  assert "NEDO" in title
  assert "CFRP" in title or "高レート" in title


def test_build_digest_item_title_distinguishes_similar_themes() -> None:
  titles = [build_digest_item_title(item) for item in _sample_items()[:3]]
  assert len(set(titles)) == 3


def test_preview_only_notice_constant_legacy() -> None:
  assert "Preview only" in PREVIEW_ONLY_NOTICE


def test_sent_mode_does_not_include_draft_wording(tmp_path: Path) -> None:
  _write_snapshot_fixture(tmp_path)
  diff = DigestDiff(unchanged_summary=True)
  digest = build_weekly_digest("US-12565719-B2", tmp_path, diff=diff, mode="sent")
  assert "下書き保存済み" not in digest.markdown_body
  assert "このPhaseではメール送信は行いません" not in digest.markdown_body
  assert "送信済み" in digest.markdown_body
  assert "確認候補" in digest.markdown_body


def test_draft_mode_includes_send_notice(tmp_path: Path) -> None:
  _write_snapshot_fixture(tmp_path)
  digest = build_weekly_digest("US-12565719-B2", tmp_path, diff=DigestDiff(is_initial=True), mode="draft")
  assert "下書き保存済み" in digest.markdown_body
  assert "自動送信は行いません" in digest.markdown_body


def test_preview_mode_includes_preview_notice(tmp_path: Path) -> None:
  _write_snapshot_fixture(tmp_path)
  digest = build_weekly_digest("US-12565719-B2", tmp_path, diff=DigestDiff(is_initial=True), mode="preview")
  assert "プレビューのみ" in digest.markdown_body
  assert "メール送信は行いません" in digest.markdown_body


def test_unchanged_diff_not_duplicated(tmp_path: Path) -> None:
  _write_snapshot_fixture(tmp_path)
  diff = DigestDiff(unchanged_summary=True)
  digest = build_weekly_digest("US-12565719-B2", tmp_path, diff=diff, mode="sent")
  count = digest.markdown_body.count("前回Snapshotから大きな変化は検出されませんでした")
  assert count == 1


def test_deduplicate_bullets_or_lines() -> None:
  lines = [
    "- 前回Snapshotから大きな変化は検出されませんでした。",
    "- 前回Snapshotから大きな変化は検出されませんでした。",
    "- 別の行",
  ]
  result = deduplicate_bullets_or_lines(lines)
  assert len(result) == 2
  assert result[0] == "- 前回Snapshotから大きな変化は検出されませんでした。"


def test_summarize_link_candidates_groups_by_title() -> None:
  links = [
    {"web_signal_title": "[PDF] 革新的新構造材料等研究開発 - NEDO", "web_signal_domain": "nedo.go.jp"},
    {"web_signal_title": "[PDF] 革新的新構造材料等研究開発 - NEDO", "web_signal_domain": "nedo.go.jp"},
    {"web_signal_title": "[PDF] 革新的新構造材料等研究開発 - NEDO", "web_signal_domain": "nedo.go.jp"},
    {"web_signal_title": "プロジェクト用語集 - NEDO", "web_signal_domain": "nedo.go.jp"},
  ]
  summaries = summarize_link_candidates_for_digest(links, max_items=5)
  assert len(summaries) == 2
  assert any("関連リンク候補 3件" in line for line in summaries)
  assert any("関連リンク候補 1件" in line for line in summaries)
  assert all("革新的新構造材料" not in line or "3件" in line for line in summaries)


def test_sent_email_draft_preamble() -> None:
  preamble = ja_email_preamble("sent")
  assert "生成・送信された" in preamble
  assert "下書き" not in preamble


def test_sent_caveats_keep_fto_notice() -> None:
  caveats = ja_caveats_for_mode("sent")
  assert any("FTO" in c for c in caveats)
  assert any("確認候補" in c for c in caveats)
  assert not any("このPhaseではメール送信は行いません" in c for c in caveats)
  assert any("CLIで明示的に送信" in c for c in caveats)


def test_sent_email_draft_body(tmp_path: Path) -> None:
  _write_snapshot_fixture(tmp_path)
  digest = build_weekly_digest("US-12565719-B2", tmp_path, diff=DigestDiff(is_initial=True), mode="sent")
  draft = build_email_draft_from_weekly_digest(
    digest,
    publication_number="US-12565719-B2",
    to="reviewer@example.com",
    status=STATUS_SENT,
    mode="sent",
  )
  assert "下書き保存済み" not in draft.markdown_body
  assert "このPhaseではメール送信は行いません" not in draft.markdown_body
  assert "送信済み" in draft.markdown_body
  assert "生成・送信された" in draft.markdown_body


def test_save_email_sent_writes_files(tmp_path: Path) -> None:
  _write_snapshot_fixture(tmp_path)
  digest = build_weekly_digest("US-12565719-B2", tmp_path, diff=DigestDiff(is_initial=True), mode="sent")
  draft = build_email_draft_from_weekly_digest(
    digest,
    publication_number="US-12565719-B2",
    to="reviewer@example.com",
    status=STATUS_SENT,
    mode="sent",
  )
  paths = save_email_sent(draft, tmp_path)
  assert paths["email_sent_md"].exists()
  assert paths["email_sent_html"].exists()
  assert paths["email_sent_json"].exists()
  assert "送信済みメール" in paths["email_sent_md"].read_text(encoding="utf-8")


def test_draft_email_draft_has_draft_notice(tmp_path: Path) -> None:
  _write_snapshot_fixture(tmp_path)
  digest = build_weekly_digest("US-12565719-B2", tmp_path, diff=DigestDiff(is_initial=True), mode="draft")
  draft = build_email_draft_from_weekly_digest(
    digest,
    publication_number="US-12565719-B2",
    to="reviewer@example.com",
    status=STATUS_DRAFT_SAVED,
    mode="draft",
  )
  assert "送信前の下書き" in draft.markdown_body
  assert "下書き保存済み" in draft.markdown_body
