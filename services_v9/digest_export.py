"""Digest and export helpers for the lightweight v9 signal watch app."""

from __future__ import annotations

import csv
import json
from io import StringIO
from typing import Sequence

from .signal_models import Signal, WatchProfile
from .signal_scoring import (
  format_score_delta,
  select_diverse_top_signals,
  select_top_reads,
  suggest_watch_profile_updates,
  summarize_status_buckets,
)
from .watch_profile_schema import watch_profile_summary
from ui_v9.labels import action_label_ja, status_label_ja, type_label_ja, watch_profile_suggestion_label_ja

LIGHTWEIGHT_NOTE = (
  "このダイジェストは、軽量なR&Dシグナル監視プレビューです。"
  "法的判断、FTO判断、侵害判断、特許性判断、技術的妥当性の証明は行いません。"
)


def build_weekly_digest_markdown(
  signals: Sequence[Signal],
  watch_profile: WatchProfile,
  data_source: str = "デモデータ",
  loaded_count: int | None = None,
) -> str:
  ranked = select_diverse_top_signals(signals, top_n=10)
  top_reads = select_top_reads(ranked, limit=3)
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
    "## 今週まず読むべき3件",
  ]
  for index, signal in enumerate(top_reads, start=1):
    lines.extend(
      [
        f"{index}. **{signal.title}**（{type_label_ja(signal.type)} / スコア {signal.score:.2f} / {status_label_ja(signal.status)}）",
        f"   - なぜ読むべきか: {signal.why_read}",
        f"   - 確認すべき点: {signal.what_to_check}",
        f"   - 次の行動: {signal.next_action}",
        f"   - 出典URL: {signal.source_url}",
        f"   - 判断: {action_label_ja(signal.action)}",
      ]
    )
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
    if signal.next_action not in next_actions:
      next_actions.append(signal.next_action)
  for action in next_actions[:3]:
    lines.append(f"- {action}")
  if not next_actions:
    lines.append("- デモデータが更新されたら、新規シグナルを再確認してください。")

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
  signals: Sequence[Signal],
  watch_profile: WatchProfile,
  data_source: str = "デモデータ",
  loaded_count: int | None = None,
) -> str:
  payload = {
    "app": "Tech Cartography v9",
    "mode": "lightweight_demo",
    "data_source": data_source,
    "loaded_count": loaded_count if loaded_count is not None else len(signals),
    "watch_profile": watch_profile.to_dict(),
    "watch_profile_summary": watch_profile_summary(watch_profile.to_dict()),
    "signals": [signal.to_dict() for signal in signals],
    "notes": LIGHTWEIGHT_NOTE,
    "display_labels_ja": {
      "types": {signal.type: type_label_ja(signal.type) for signal in signals},
      "statuses": {signal.status: status_label_ja(signal.status) for signal in signals},
      "actions": {signal.action: action_label_ja(signal.action) for signal in signals},
    },
  }
  return json.dumps(payload, ensure_ascii=False, indent=2)
