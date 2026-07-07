"""Human-facing digest builder reusing research value synthesis."""

from __future__ import annotations

import re
from typing import Any, Mapping, Sequence

from services_v9.human_datetime import format_datetime_jst
from services_v9.research_value_pipeline import build_research_value_top3
from services_v9.run_baseline_state import build_baseline_summary, is_initial_baseline
from services_v9.simple_review_state import summarize_simple_reviews
from services_v9.study_demo_source_url import resolve_signal_source_url

INTERNAL_TOKEN_RE = re.compile(r"[a-z_]+:(?:title|abstract|summary)|exact_phrase:|_score|study_demo_search_")
PYTHON_DICT_RE = re.compile(r"\{['\"]A['\"]:\s*\d")
RUN_ID_RE = re.compile(r"study_demo_search_\d{8}_[a-f0-9]{8}")


def short_theme_label(theme_name: str, *, max_len: int = 24) -> str:
  text = str(theme_name or "").strip()
  if len(text) <= max_len:
    return text
  return text[: max_len - 1] + "…"


def _summarize_questions(questions: Sequence[str], *, limit: int = 3) -> list[str]:
  return [str(item) for item in list(questions or [])[:limit]]


def build_digest_review_summary(
  reviews: Sequence[Mapping[str, Any]],
  *,
  top_signal_ids: Sequence[str],
) -> dict[str, Any]:
  counts = summarize_simple_reviews(reviews, top_signal_ids)
  return {
    "unreviewed": counts["unreviewed"],
    "accept": counts["accept"],
    "hold": counts["hold"],
    "reject": counts["reject"],
    "labels": {
      "unreviewed": "未判断",
      "accept": "関連",
      "hold": "保留",
      "reject": "除外",
    },
  }


def build_digest_operation_status() -> dict[str, str]:
  return {
    "demo_note": "Demo: 自動週次・メール送信は停止中",
    "weekly": "停止中",
    "email": "停止中",
  }


def build_human_digest(
  *,
  theme: Mapping[str, Any],
  signals: Sequence[Mapping[str, Any]],
  baseline_state: Mapping[str, Any],
  reviews: Sequence[Mapping[str, Any]] | None = None,
  updated_at: str = "",
  integrated_count: int | None = None,
) -> dict[str, Any]:
  research_bundle = build_research_value_top3(list(signals), theme, limit=3)
  items = list(research_bundle.get("items", []) or [])
  top_signal_ids = [str(dict(item.get("signal", {})).get("signal_id", "")) for item in items]
  review_summary = build_digest_review_summary(list(reviews or []), top_signal_ids=top_signal_ids)
  baseline_summary = build_baseline_summary(baseline_state)
  current_count = int(integrated_count if integrated_count is not None else baseline_state.get("current_count", 0) or 0)
  top3 = []
  for item in items:
    output = dict(item.get("output", {}) or {})
    signal = dict(item.get("signal", {}) or {})
    resolution = resolve_signal_source_url(signal)
    top3.append(
      {
        "rank": item.get("rank"),
        "role": dict(output.get("role", {}) or {}),
        "short_title_ja": output.get("short_title_ja", ""),
        "research_value": output.get("research_value", ""),
        "verification_questions": _summarize_questions(output.get("verification_questions", [])),
        "readout_artifact": output.get("readout_artifact", ""),
        "source_url": resolution.resolved_url if resolution.is_valid else "",
        "original_title": output.get("original_title", signal.get("title", "")),
      }
    )
  return {
    "heading": "今週のR&Dシグナル",
    "theme_name": str(theme.get("name", "") or ""),
    "theme_short_label": short_theme_label(str(theme.get("name", "") or "")),
    "updated_at_jst": format_datetime_jst(updated_at),
    "baseline_state": str(baseline_state.get("state", "") or ""),
    "baseline_summary": baseline_summary,
    "current_count": current_count,
    "priority_count": int(baseline_state.get("priority_count", 3) or 3),
    "has_comparison": bool(baseline_state.get("has_comparison")),
    "top3": top3,
    "review_summary": review_summary,
    "operation_status": build_digest_operation_status(),
    "research_bundle": research_bundle,
  }


def human_digest_to_markdown(payload: Mapping[str, Any]) -> str:
  lines = [
    f"# {payload.get('heading', '今週のR&Dシグナル')}",
    "",
    "## テーマ",
    str(payload.get("theme_name", "")),
    "",
    "## 今回の状態",
  ]
  if is_initial_baseline({"state": payload.get("baseline_state", "")}):
    lines.extend(
      [
        "- 初回ベースライン",
        f"- 実データ {payload.get('current_count', 0)}件",
        f"- 優先確認 {payload.get('priority_count', 3)}件",
        "- 比較対象なし",
      ]
    )
  else:
    lines.extend(
      [
        f"- 実データ {payload.get('current_count', 0)}件",
        f"- 優先確認 {payload.get('priority_count', 3)}件",
        "- 比較対象あり",
      ]
    )
  lines.extend(["", "### 今回まず確認する3件", ""])
  for item in list(payload.get("top3", []) or []):
    role = dict(item.get("role", {}) or {})
    lines.append(f"#### {item.get('rank', '')}. {item.get('short_title_ja', '')}")
    lines.append(f"- 役割: {role.get('label_ja', '')}")
    lines.append(f"- この文献で確認できる可能性: {item.get('research_value', '')}")
    lines.append("- 原典で確認する問い:")
    for question in list(item.get("verification_questions", []) or []):
      lines.append(f"  - {question}")
    lines.append(f"- 読後に残すもの: {item.get('readout_artifact', '')}")
    if item.get("source_url"):
      lines.append(f"- 原典URL: {item.get('source_url')}")
    lines.append("")
  review = dict(payload.get("review_summary", {}) or {})
  lines.extend(
    [
      "## 人間レビュー",
      f"- 未判断 {review.get('unreviewed', 0)}",
      f"- 関連 {review.get('accept', 0)}",
      f"- 保留 {review.get('hold', 0)}",
      f"- 除外 {review.get('reject', 0)}",
      "",
      "## 運用状態",
      str(dict(payload.get("operation_status", {}) or {}).get("demo_note", "")),
      "",
    ]
  )
  return "\n".join(lines).strip() + "\n"


def validate_digest_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
  markdown = human_digest_to_markdown(payload)
  errors: list[str] = []
  if PYTHON_DICT_RE.search(markdown):
    errors.append("python_dict_in_markdown")
  if RUN_ID_RE.search(markdown):
    errors.append("run_id_in_simple_markdown")
  if INTERNAL_TOKEN_RE.search(markdown):
    errors.append("internal_token_in_markdown")
  if "Review summary" in markdown:
    errors.append("raw_review_summary")
  if not str(payload.get("theme_name", "")).strip():
    errors.append("missing_theme")
  if not list(payload.get("top3", []) or []):
    errors.append("missing_top3")
  for item in list(payload.get("top3", []) or []):
    if not str(item.get("research_value", "")).strip():
      errors.append("missing_research_value")
  return {
    "status": "ok" if not errors else "blocked",
    "errors": errors,
    "markdown_length": len(markdown),
  }


def count_human_digest_violations(text: str) -> dict[str, int]:
  return {
    "raw_dict_occurrence_count": len(PYTHON_DICT_RE.findall(text)),
    "internal_token_occurrence_count": len(INTERNAL_TOKEN_RE.findall(text)),
    "simple_run_id_occurrence_count": len(RUN_ID_RE.findall(text)),
  }


__all__ = [
  "build_digest_operation_status",
  "build_digest_review_summary",
  "build_human_digest",
  "count_human_digest_violations",
  "human_digest_to_markdown",
  "short_theme_label",
  "validate_digest_payload",
]
