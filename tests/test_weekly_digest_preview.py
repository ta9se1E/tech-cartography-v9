"""Tests for weekly digest preview (Phase 16.2)."""

from __future__ import annotations

from tech_cartography.costs.weekly_digest_preview import (
  build_weekly_digest_preview,
  render_weekly_digest_preview_markdown,
  save_weekly_digest_preview,
)


def test_preview_markdown_builds() -> None:
  acquisition = {
    "user_facing_name_japanese": "標準監視モード",
    "user_facing_description_japanese": "広く監視",
    "included_items": ["特許候補の更新"],
    "excluded_items": ["明細書全文"],
    "manual_watch_count": 2,
  }
  preview = build_weekly_digest_preview(
    {
      "top20_patents": [{"publication_number": "US-1", "title": "Fiber", "assignee": "Toray"}],
      "strategic_watch": [
        {
          "publication_number": "CN-1",
          "country": "CN",
          "assignee": "ZHONGFU",
          "watch_reason_japanese": "中複神鷹系",
        },
      ],
      "us_deep_dive_candidates": [{"publication_number": "US-1", "title": "Fiber"}],
    },
    acquisition,
  )
  md = render_weekly_digest_preview_markdown(preview)
  assert "Weekly Digest Preview" in md
  assert "標準監視モード" in md
  assert "中国 Strategic Watch" in md
  assert "ZHONGFU" in md or "中複" in md


def test_china_strategic_watch_included() -> None:
  preview = build_weekly_digest_preview(
    {"strategic_watch": [{"publication_number": "CN-1", "country": "CN"}]},
    {"user_facing_name_japanese": "標準監視モード", "included_items": [], "excluded_items": []},
  )
  assert len(preview["china_strategic_watch"]) == 1


def test_no_email_sending_note() -> None:
  preview = build_weekly_digest_preview({}, {"user_facing_name_japanese": "標準監視モード"})
  md = render_weekly_digest_preview_markdown(preview)
  assert "メール送信" in preview["note_japanese"] or "メール" in md
  assert "未実装" in md or "まだ" in md


def test_no_monetary_amounts_in_preview(tmp_path) -> None:
  preview = build_weekly_digest_preview(
    {},
    {
      "user_facing_name_japanese": "標準監視モード",
      "included_items": ["監視"],
      "excluded_items": ["全文"],
    },
  )
  md = render_weekly_digest_preview_markdown(preview)
  lower = md.lower()
  assert "usd" not in lower
  assert "$" not in md
  assert "ドル" not in md
  paths = save_weekly_digest_preview(preview, tmp_path)
  assert paths["weekly_digest_preview_md"]


def test_weekly_digest_includes_claims_paper_query_section() -> None:
  preview = build_weekly_digest_preview(
    {
      "claims_paper_query_plan": {
        "total_queries": 2,
        "openalex_mode": "plan_only",
        "query_examples": ["PAN carbon fiber carbonization tensile strength"],
        "next_actions_japanese": ["descriptionを追加する"],
      },
    },
    {"user_facing_name_japanese": "標準監視モード", "included_items": [], "excluded_items": []},
  )
  md = render_weekly_digest_preview_markdown(preview)
  assert "技術の裏取り候補" in md
  assert "plan_only" in md or "OpenAlex実行準備" in md
  assert "supporting evidence candidate" in md


def test_weekly_digest_includes_paper_evidence_section() -> None:
  preview = build_weekly_digest_preview(
    {
      "openalex_limited_execution": {
        "mode": "execute",
        "selected_queries": [{"query_type": "material_process", "query": "PAN carbon fiber"}],
        "paper_records": [{"title": "Carbon fiber study"}],
        "source_quality_summary": {"background": 1},
      },
      "claim_paper_candidate_links": [
        {
          "element_type": "material",
          "paper_title": "Carbon fiber study",
          "link_type": "material_process_background",
          "confidence": "low",
        },
      ],
    },
    {"user_facing_name_japanese": "標準監視モード", "included_items": [], "excluded_items": []},
  )
  md = render_weekly_digest_preview_markdown(preview)
  assert "論文裏取り候補" in md
  assert "supporting" in md.lower() or "裏取り候補" in md
  assert "$" not in md
