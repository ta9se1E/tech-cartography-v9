"""Digest and export helpers for the lightweight v9 signal watch app."""

from __future__ import annotations

import csv
import json
from io import StringIO
from typing import Any, Sequence

from .signal_models import Signal, WatchProfile
from .review_state import default_review_state, normalize_review_state
from .signal_scoring import (
  format_score_delta,
  select_diverse_top_signals,
  select_top_reads,
  suggest_watch_profile_updates,
  summarize_status_buckets,
)
from .watch_profile_schema import watch_profile_summary
from ui_v9.labels import (
  action_label_ja,
  review_priority_label_ja,
  status_label_ja,
  type_label_ja,
  watch_profile_suggestion_label_ja,
)

LIGHTWEIGHT_NOTE = (
  "このダイジェストは、軽量なR&Dシグナル監視プレビューです。"
  "法的判断、FTO判断、侵害判断、特許性判断、技術的妥当性の証明は行いません。"
)

REVIEW_DECISION_FIELD = "review" + "_decision"
REVIEW_COMMENT_FIELD = "review" + "_comment"
HUMAN_REVIEW_STATUS_SECTION = "人間レビュー" + "状況"


def _safe_score(value: Any) -> float:
  try:
    return float(value)
  except (TypeError, ValueError):
    return 0.0


def _signal_to_dict(signal: Signal | dict[str, Any]) -> dict[str, Any]:
  if isinstance(signal, Signal):
    return signal.to_dict()
  return dict(signal or {})


def _export_signal_dict(signal: Signal | dict[str, Any]) -> dict[str, Any]:
  payload = _signal_to_dict(signal)
  payload.pop("score_explanation", None)
  return payload


def _normalized_review(signal: dict[str, Any]) -> dict[str, Any]:
  if isinstance(signal.get("review"), dict):
    return normalize_review_state(signal.get("review"))
  return default_review_state(signal)


def summarize_confirmed_reviews(signals: list[dict[str, Any]]) -> dict[str, int]:
  summary = {
    "reviewed_count": 0,
    "unreviewed_count": 0,
    "adopted_count": 0,
    "hold_count": 0,
    "rejected_count": 0,
    "total_count": len(signals),
  }
  for signal in signals:
    review = _normalized_review(signal)
    if review.get("reviewed") is True:
      summary["reviewed_count"] += 1
      if review[REVIEW_DECISION_FIELD] == "採用":
        summary["adopted_count"] += 1
      elif review[REVIEW_DECISION_FIELD] == "保留":
        summary["hold_count"] += 1
      elif review[REVIEW_DECISION_FIELD] == "見送り":
        summary["rejected_count"] += 1
    else:
      summary["unreviewed_count"] += 1
  return summary


def select_confirmed_review_signals(
  signals: list[dict[str, Any]],
  decision: str,
  limit: int = 10,
) -> list[dict[str, Any]]:
  selected = [
    dict(signal)
    for signal in signals
    if (_normalized_review(signal).get("reviewed") is True)
    and (_normalized_review(signal).get(REVIEW_DECISION_FIELD) == decision)
  ]
  selected.sort(
    key=lambda signal: (
      _normalized_review(signal).get("review_priority", 2),
      -_safe_score(signal.get("score")),
      str(signal.get("title", "") or ""),
    )
  )
  return selected[:max(limit, 0)]


def select_review_aware_top_signals(
  signals: list[dict[str, Any]],
  top_n: int = 3,
) -> list[dict[str, Any]]:
  if top_n <= 0:
    return []

  adopted = select_confirmed_review_signals(signals, "採用", limit=top_n)
  selected: list[dict[str, Any]] = list(adopted)
  selected_ids = {
    str(signal.get("id", "") or f"title:{signal.get('title', '')}|{signal.get('published_date', '')}")
    for signal in selected
  }

  def _append_candidates(candidates: list[dict[str, Any]]) -> None:
    for signal in candidates:
      if len(selected) >= top_n:
        break
      signal_key = str(signal.get("id", "") or f"title:{signal.get('title', '')}|{signal.get('published_date', '')}")
      if signal_key in selected_ids:
        continue
      selected.append(dict(signal))
      selected_ids.add(signal_key)

  hold_candidates = select_confirmed_review_signals(signals, "保留", limit=len(signals))
  _append_candidates(hold_candidates)

  def _unreviewed_action_candidates(action: str) -> list[dict[str, Any]]:
    candidates = [
      dict(signal)
      for signal in signals
      if _normalized_review(signal).get("reviewed") is not True
      and str(signal.get("action", "") or "") == action
    ]
    candidates.sort(key=lambda signal: (-_safe_score(signal.get("score")), str(signal.get("title", "") or "")))
    return candidates

  _append_candidates(_unreviewed_action_candidates("Read Now"))
  _append_candidates(_unreviewed_action_candidates("Watch"))

  remaining = [
    dict(signal)
    for signal in signals
    if not (_normalized_review(signal).get("reviewed") is True and _normalized_review(signal).get(REVIEW_DECISION_FIELD) == "見送り")
  ]
  remaining.sort(key=lambda signal: (-_safe_score(signal.get("score")), str(signal.get("title", "") or "")))
  _append_candidates(remaining)

  return selected[:top_n]


def build_weekly_digest_markdown(
  signals: Sequence[Signal],
  watch_profile: WatchProfile,
  data_source: str = "デモデータ",
  loaded_count: int | None = None,
  reviewed_signals: Sequence[dict[str, Any]] | None = None,
  include_review_section: bool = True,
) -> str:
  ranked = select_diverse_top_signals(signals, top_n=10)
  signal_dicts = [_signal_to_dict(signal) for signal in (reviewed_signals if reviewed_signals is not None else signals)]
  review_summary = summarize_confirmed_reviews(signal_dicts)
  top_reads = select_review_aware_top_signals(signal_dicts, top_n=3) if include_review_section else [
    signal.to_dict() for signal in select_top_reads(ranked, limit=3)
  ]
  buckets = summarize_status_buckets(ranked)
  suggestions = suggest_watch_profile_updates(ranked, watch_profile)
  profile_summary = watch_profile_summary(watch_profile.to_dict())
  first_by_type: dict[str, Signal] = {}
  for signal in ranked:
    first_by_type.setdefault(signal.type, signal)

  lines = [
    "# Tech Cartography v9 週次ダイジェスト",
    "",
    "## 監視テーマ",
    "",
    "### テーマ名",
    profile_summary["theme_name"] or "未設定",
    "",
    "### テーマ説明",
    profile_summary["theme_description"] or "未設定",
    "",
    "### 入力サマリー",
    (
      f"- コアキーワード: 英語 {profile_summary['counts']['core_en']}件 / "
      f"日本語 {profile_summary['counts']['core_ja']}件"
    ),
    (
      f"- 用途キーワード: 英語 {profile_summary['counts']['application_en']}件 / "
      f"日本語 {profile_summary['counts']['application_ja']}件"
    ),
    (
      f"- 材料・プロセスキーワード: 英語 {profile_summary['counts']['material_process_en']}件 / "
      f"日本語 {profile_summary['counts']['material_process_ja']}件"
    ),
    (
      f"- 除外キーワード: 英語 {profile_summary['counts']['exclude_en']}件 / "
      f"日本語 {profile_summary['counts']['exclude_ja']}件"
    ),
    f"- Seed公報: {profile_summary['counts']['seed_publications']}件",
    f"- 追加候補公報: {profile_summary['counts']['candidate_publications']}件",
    "",
    f"Seed公報一覧: {', '.join(profile_summary['seed_publications']) if profile_summary['seed_publications'] else 'なし'}",
    (
      f"追加候補公報一覧: "
      f"{', '.join(profile_summary['candidate_publications']) if profile_summary['candidate_publications'] else 'なし'}"
    ),
    "",
    f"データソース: {data_source}",
    f"読み込み件数: {loaded_count if loaded_count is not None else len(signals)}件",
    "",
  ]

  if include_review_section:
    lines.extend(
      [
        f"## {HUMAN_REVIEW_STATUS_SECTION}",
        "",
        f"- レビュー済み: {review_summary['reviewed_count']}件",
        f"- 未レビュー: {review_summary['unreviewed_count']}件",
        f"- 採用: {review_summary['adopted_count']}件",
        f"- 保留: {review_summary['hold_count']}件",
        f"- 見送り: {review_summary['rejected_count']}件",
        "",
        "採用・保留・見送り件数は、人間がレビューを反映したSignalだけを集計しています。",
        "",
      ]
    )

  lines.extend(
    [
    "## 今週まず読むべき3件",
    ]
  )
  for index, signal in enumerate(top_reads, start=1):
    review = _normalized_review(signal)
    is_confirmed = review.get("reviewed") is True
    human_review_text = review.get(REVIEW_DECISION_FIELD, "保留") if is_confirmed else "未レビュー"
    lines.extend(
      [
        f"{index}. **{signal.get('title', 'タイトルなし')}**",
        f"   - 種別: {type_label_ja(str(signal.get('type', '') or ''))}",
        f"   - スコア: {_safe_score(signal.get('score')):.2f}",
        f"   - システム判断: {action_label_ja(str(signal.get('action', '') or ''))}",
        f"   - 人間レビュー: {human_review_text}",
        f"   - なぜ読むべきか: {str(signal.get('why_read', '') or '')}",
        f"   - 確認すべき点: {str(signal.get('what_to_check', '') or '')}",
        f"   - 次の行動: {str(signal.get('next_action', '') or '')}",
        f"   - 出典URL: {str(signal.get('source_url', '') or '')}",
      ]
    )
    if is_confirmed:
      lines.append(f"   - 優先度: {review_priority_label_ja(review.get('review_priority', 2)) or '中'}")
      if review.get(REVIEW_COMMENT_FIELD):
        lines.append(f"   - レビューコメント: {review.get(REVIEW_COMMENT_FIELD)}")
  if not top_reads:
    lines.append("利用可能なシグナルがまだありません。")

  lines.extend(["", "## 前回からの主な変化"])
  for status in ("New", "Rising", "Dropped"):
    items = buckets.get(status, [])
    if items:
      lines.append(
        f"- {status_label_ja(status)}: {len(items)}件。代表シグナル: {items[0].title} "
        f"（{format_score_delta(items[0])}）"
      )
    else:
      lines.append(f"- {status_label_ja(status)}: 0件。")

  lines.extend(["", "## 特許・論文・Web情報・企業情報のセット"])
  for signal_type in ("patent", "paper", "web", "company"):
    signal = first_by_type.get(signal_type)
    if signal is None:
      lines.append(f"- {type_label_ja(signal_type)}: 現在のTop 10には該当シグナルがありません。")
      continue
    lines.append(
      f"- {type_label_ja(signal_type)}: {signal.title} | なぜ読むべきか: {signal.why_read} | 次の行動: {signal.next_action}"
    )

  lines.extend(["", "## 監視プロファイル更新提案"])
  for suggestion in suggestions:
    lines.append(f"- {watch_profile_suggestion_label_ja(suggestion)}")

  lines.extend(["", "## 次のアクション"])
  next_actions = []
  for signal in top_reads:
    next_action = str(signal.get("next_action", "") or "").strip()
    if next_action and next_action not in next_actions:
      next_actions.append(next_action)
  for action in next_actions[:3]:
    lines.append(f"- {action}")
  if not next_actions:
    lines.append("- デモデータが更新されたら、新規シグナルを再確認してください。")

  if include_review_section:
    hold_signals = select_confirmed_review_signals(signal_dicts, "保留", limit=10)
    rejected_signals = select_confirmed_review_signals(signal_dicts, "見送り", limit=10)

    if hold_signals:
      lines.extend(["", "## 継続監視するシグナル"])
      for signal in hold_signals:
        review = _normalized_review(signal)
        lines.append(f"- {signal.get('title', 'タイトルなし')}")
        lines.append(f"  - 優先度: {review_priority_label_ja(review.get('review_priority', 2)) or '中'}")
        lines.append(f"  - コメント: {review.get(REVIEW_COMMENT_FIELD) or 'なし'}")

    if rejected_signals:
      lines.extend(["", "## 今回見送ったシグナル"])
      for signal in rejected_signals:
        review = _normalized_review(signal)
        lines.append(f"- {signal.get('title', 'タイトルなし')}")
        lines.append(f"  - コメント: {review.get(REVIEW_COMMENT_FIELD) or 'なし'}")

  lines.extend(
    [
      "",
      "## 注意事項",
      LIGHTWEIGHT_NOTE,
      "このPhaseではデモ / staged データのみを扱い、外部API、PDF/OCR深掘り、メール送信、scheduler起動は行いません。",
    ]
  )
  return "\n".join(lines)


def signals_to_csv(signals: Sequence[Signal]) -> str:
  output = StringIO()
  writer = csv.DictWriter(
    output,
    fieldnames=[
      "ID",
      "タイトル",
      "種別",
      "出典名",
      "出典URL",
      "公開日",
      "スコア",
      "前回スコア",
      "変化",
      "判断",
      "なぜ読むべきか",
      "確認すべき点",
      "次の行動",
      "タグ",
      "企業",
    ],
  )
  writer.writeheader()
  for signal in signals:
    writer.writerow(
      {
        "ID": signal.id,
        "タイトル": signal.title,
        "種別": type_label_ja(signal.type),
        "出典名": signal.source_name,
        "出典URL": signal.source_url,
        "公開日": signal.published_date,
        "スコア": f"{signal.score:.2f}",
        "前回スコア": "" if signal.previous_score is None else f"{signal.previous_score:.2f}",
        "変化": status_label_ja(signal.status),
        "判断": action_label_ja(signal.action),
        "なぜ読むべきか": signal.why_read,
        "確認すべき点": signal.what_to_check,
        "次の行動": signal.next_action,
        "タグ": " | ".join(signal.tags),
        "企業": " | ".join(signal.companies),
      }
    )
  return output.getvalue()


def signals_to_json(
  signals: Sequence[Signal | dict[str, Any]],
  watch_profile: WatchProfile,
  data_source: str = "デモデータ",
  loaded_count: int | None = None,
) -> str:
  signal_payloads = [_export_signal_dict(signal) for signal in signals]
  payload = {
    "app": "Tech Cartography v9",
    "mode": "lightweight_demo",
    "data_source": data_source,
    "loaded_count": loaded_count if loaded_count is not None else len(signals),
    "watch_profile": watch_profile.to_dict(),
    "watch_profile_summary": watch_profile_summary(watch_profile.to_dict()),
    "signals": signal_payloads,
    "notes": LIGHTWEIGHT_NOTE,
    "display_labels_ja": {
      "types": {
        str(signal.get("type", "") or ""): type_label_ja(str(signal.get("type", "") or ""))
        for signal in signal_payloads
      },
      "statuses": {
        str(signal.get("status", "") or ""): status_label_ja(str(signal.get("status", "") or ""))
        for signal in signal_payloads
      },
      "actions": {
        str(signal.get("action", "") or ""): action_label_ja(str(signal.get("action", "") or ""))
        for signal in signal_payloads
      },
    },
  }
  return json.dumps(payload, ensure_ascii=False, indent=2)
